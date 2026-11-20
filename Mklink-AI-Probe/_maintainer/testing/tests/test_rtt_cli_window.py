import json
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from mklink import rtt_cli, runtime_cli
from mklink.rtt_cache import RttChannelCache
from mklink.runtime import RuntimeErrorResponse


class Capture:
    def __init__(self, legacy=False):
        self.cache = RttChannelCache()
        self.cache.reset('one', [3, 7])
        self.legacy = legacy
        self.history = []
        self.ends = []
        self.running = True

    def rtt_subscribe_bytes(self, ch, *, session):
        cursor = self.cache.read(ch)['available_end']
        def read(timeout):
            nonlocal cursor
            page = self.cache.read(ch, cursor, session)
            cursor = page['cursor']
            return {'data': bytes.fromhex(page['data_hex']), 'cursor': cursor}
        return nullcontext(SimpleNamespace(read=read, missing_batches=0, mux_dropped_bytes=0))

    def call(self, name, args=None):
        if name == 'rtt_read_channel':
            return self.cache.read(**args)
        if name == 'rtt_history':
            return {'points': self.history}
        assert name == 'rtt_status'
        session, offsets = self.cache.positions()
        self.ends.append(dict(offsets))
        return {'running': self.running, 'channels': list(offsets), 'session': session,
                'encoding': 'utf-8', 'channel_status': {'7': {'encoding': 'gbk'}},
                'control_block_addr': 0x20000000,
                **({} if self.legacy else {'channel_cursors': {str(ch): end for ch, end in offsets.items()}})}


def clock(monkeypatch, step):
    now = [0.]
    def sleep(seconds):
        now[0] += seconds
        step()
    monkeypatch.setattr(rtt_cli, 'time', SimpleNamespace(monotonic=lambda: now[0], sleep=sleep))


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('duration', [.017, .12])
def test_window_reads_all_active_channels_after_attach(monkeypatch, duration, legacy):
    capture = Capture(legacy)
    capture.cache.append(3, b'old line\n')
    capture.cache.append(7, b'old data\n')
    def produce():
        capture.cache.append(3, '温度\r\nv=3\nv=4\n'.encode())
        capture.cache.append(7, '电机'.encode('gbk'))
    clock(monkeypatch, produce)
    result = rtt_cli.collect(capture, {'reused': True}, None, '0x20000000', duration)
    first, second = result['channels']
    assert '温度' in first['text'] and '电机' in second['text']
    assert 'old' not in first['text'] + second['text']
    assert all(row['lost_bytes'] == 0 for row in result['channels'])
    assert [p['v'] for p in first['points']][:2] == [3, 4]
    assert result['points'] == first['points'] and not second['points']


def test_infinite_reader_streams_split_characters_and_returns_on_interrupt(monkeypatch, capsys):
    capture = Capture()
    capture.history = [{'value': 4, '_t': 10}]
    chunks = iter([b'\xe6', b'\xb8', b'\xa9\n'])
    def produce():
        data = next(chunks, None)
        if data is None:
            raise KeyboardInterrupt()
        capture.cache.append(3, data)
    clock(monkeypatch, produce)
    result = rtt_cli.collect(capture, {}, [3], None, 0)
    blocks = [json.loads(line)['rtt_chunk'] for line in capsys.readouterr().out.splitlines()[1:]]
    assert ''.join(b['text'] for b in blocks) == '温\n'
    assert result['points'] == capture.history
    assert result['channels'][0]['bytes_read'] == result['channels'][0]['emitted_bytes'] == 4


def test_burst_reports_overwrite_and_drains_all_pages_without_duplicating(monkeypatch, capsys):
    capture = Capture()
    payload = b'abcd' * (RttChannelCache.LIMIT // 2)
    clock(monkeypatch, lambda: capture.cache.append(3, payload))
    result = rtt_cli.collect(capture, {}, [3], None, .001)
    blocks = [json.loads(line)['rtt_chunk'] for line in capsys.readouterr().out.splitlines()[1:]]
    row, = result['channels']
    assert row['lost_bytes'] == row['bytes_read'] == RttChannelCache.LIMIT
    assert bytes.fromhex(''.join(b['data_hex'] for b in blocks) + row['data_hex']) == payload[-row['bytes_read']:]


def test_replaced_capture_is_not_mixed_with_the_first(monkeypatch):
    capture = Capture()
    clock(monkeypatch, lambda: capture.cache.reset('two', [3]))
    with pytest.raises(RuntimeErrorResponse, match='changed'):
        rtt_cli.collect(capture, {'reused': True}, [3], None, .017)


def test_discovery_finishes_before_default_channels_and_window_are_selected(monkeypatch):
    capture = Capture()
    call = capture.call
    def starting(name, args=None):
        reply = call(name, args)
        if name == 'rtt_status' and len(capture.ends) == 1:
            reply.update(progress_state='starting', channels=[0])
        return reply
    capture.call = starting
    clock(monkeypatch, lambda: capture.cache.append(7, b'tick\n'))
    result = rtt_cli.collect(capture, {'reused': True}, None, None, .001)
    assert [c['channel'] for c in result['channels']] == [3, 7]
    assert result['channels'][1]['text'] == 'tick\n'


def test_websocket_gap_replays_only_missing_bytes_from_the_channel_cache():
    capture = Capture()
    window = rtt_cli.ChannelWindow(3, 0, 'one', 'utf-8')
    capture.cache.append(3, b'prefix suffix')
    reader = SimpleNamespace(read=lambda timeout: {'data': b'suffix', 'cursor': 13})
    window.receive(capture, reader, False)
    window.receive(capture, reader, False)
    row = window.finish()
    assert row['text'] == 'prefix suffix' and row['bytes_read'] == 13 and row['lost_bytes'] == 0


@pytest.mark.parametrize('channels,address,error', [([7], '0x20000000', None),
                                                    ([2], None, 'not active'),
                                                    ([7], '0x20000004', 'address differs')])
def test_running_cli_treats_selection_as_a_read_filter(monkeypatch, channels, address, error):
    capture = Capture()
    calls = []
    class Client:
        def __init__(self, **kw): pass
        def connect(self, **kw): pass
        def close(self): calls.append('detach')
        def rtt_subscribe_bytes(self, channel, **args): return capture.rtt_subscribe_bytes(channel, **args)
        def call(self, name, args=None):
            calls.append(name)
            if name == 'rtt_start':
                assert args == {}
                return {'reused': True}
            return capture.call(name, args)
    monkeypatch.setattr(runtime_cli, 'RuntimeClient', Client)
    clock(monkeypatch, lambda: None)
    args = SimpleNamespace(command='rtt', channels=channels, addr=address, duration=.01)
    if error:
        with pytest.raises(SystemExit, match=error):
            runtime_cli.run(args)
    else:
        runtime_cli.run(args)
    assert 'rtt_stop' not in calls and calls[-1] == 'detach'

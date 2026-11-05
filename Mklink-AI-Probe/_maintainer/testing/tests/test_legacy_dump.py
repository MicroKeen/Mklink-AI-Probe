"""Explicit restored DMPM uses the sole bridge and verifies its stop receipt."""
from types import SimpleNamespace

import pytest

from mklink._types import DeviceState, MKLINK_IDENTITY_COMMAND, MKLINK_IDENTITY_TOKEN
from mklink.bridge import MKLinkSerialBridge
from mklink.dump_memory import DumpMemoryStreamSession, DumpSampleAssembler, capture_dump_stream
from test_dump_memory_session import _b1_frame, _old_frame


class LegacyBridge(MKLinkSerialBridge):
    def __init__(self, chunks, *, caps=True):
        super().__init__('TEST_DMPM_NO_HARDWARE')
        self.chunks, self.calls = list(chunks), []
        self._ctx.state = DeviceState.READY
        self._ctx.swd_clock_hz = 30000000
        self._firmware_capabilities = frozenset({'DUMP_MEMORY=1', 'DUMP_STOP=1'} if caps else ())
        self.stop_reply = b'DUMP_STOPPED\r\n>>> '
        self._serial = SimpleNamespace(write=self._write_raw, is_open=True)

    def _try_enter_stream(self, state):
        self.calls.append(('enter', state))
        return super()._try_enter_stream(state)

    def _write_raw(self, data):
        self.calls.append(('write', data))
        if b'-1.0)' in data:
            self.chunks.append(self.stop_reply)
        elif data == (MKLINK_IDENTITY_COMMAND + '\n').encode('ascii'):
            self.chunks.append((MKLINK_IDENTITY_TOKEN + '\r\n>>> ').encode('ascii'))
        return len(data)

    def drain_stream_bytes(self, max_bytes=None):
        self.calls.append(('drain', max_bytes))
        return self.chunks.pop(0) if self.chunks else b''


def test_explicit_4096_capture_checks_b1_and_confirms_stop():
    expected = bytes(range(256))*16
    raw = b''.join(_b1_frame(123, expected[i*2048:(i+1)*2048], block_index=i,
                            block_count=2, total_size=4096) for i in range(2))
    bridge = LegacyBridge([raw])
    result = capture_dump_stream(SimpleNamespace(_bridge=bridge), [{'address':0x20000000, 'size':4096}], protocol='dmpm')
    assert result['protocol'] == 'dmpm' and result['sample_count'] == 1
    assert bytes.fromhex(result['samples'][0]['regions'][0]['data_hex']) == expected
    assert bridge.state is DeviceState.READY
    writes = [data for kind, data in bridge.calls if kind == 'write']
    assert writes == [b'cmd.dump_memory(0x20000000, 4096, 0.0)\n',
                      b'cmd.dump_memory(0x20000000, 4096, -1.0)\n',
                      (MKLINK_IDENTITY_COMMAND+'\n').encode('ascii')]


@pytest.mark.parametrize('period,token', [(0, '0.0'), (1, '1.0'), (60, '60.0'),
                                        (.000001, '0.000001'), (.01, '0.01'), (-1, '-1.0')])
def test_legacy_period_preserves_pika_float_token(period, token):
    from mklink.legacy_dump import command_for
    assert command_for([(0x20000000, 4)], period).endswith(f', {token})')


@pytest.mark.parametrize('busy', [False, True])
def test_no_legacy_start_without_capability_or_when_other_stream_is_active(busy):
    bridge = LegacyBridge([], caps=busy)
    if busy: bridge._mux = SimpleNamespace(sampling=True, _error=None)
    session = DumpMemoryStreamSession(bridge, [(0x20000000, 4096)], .001, protocol='dmpm')
    with pytest.raises(RuntimeError): session.start()
    assert not bridge.calls and not session.started


@pytest.mark.parametrize('reply', [b'Error: DAP busy\r\n>>> ', b'DUMP_STOPPED\r\n'+_old_frame(1, b'abc')+b'>>> '])
def test_rejected_stop_never_retries_or_reports_ready(reply):
    bridge = LegacyBridge([])
    bridge.stop_reply = reply
    session = DumpMemoryStreamSession(bridge, [(0x20000000, 4)], .001, protocol='dmpm')
    session.start()
    with pytest.raises(RuntimeError): session.stop()
    assert bridge.state is DeviceState.ERROR
    assert len([1 for kind, data in bridge.calls if kind == 'write' and b'-1.0)' in data]) == 1


def test_sample_bytes_cannot_forge_a_stop_receipt(monkeypatch):
    monkeypatch.setattr('mklink.dump_control.STOP_TIMEOUT', .02)
    bridge = LegacyBridge([])
    bridge.stop_reply = _old_frame(1, b'\r\nDUMP_STOPPED\r\n>>> '+MKLINK_IDENTITY_TOKEN.encode()) + b'>>> '
    session = DumpMemoryStreamSession(bridge, [(0x20000000, 4)], .001, protocol='dmpm')
    session.start()
    with pytest.raises(RuntimeError, match='unconfirmed'): session.stop()
    assert bridge.state is DeviceState.ERROR

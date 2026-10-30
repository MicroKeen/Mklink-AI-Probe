"""Regression for the reported 4 KiB B1 echo and false READY after DAP busy."""
from contextlib import contextmanager
import queue
import threading

import pytest

from mklink._types import DeviceState, MKLINK_IDENTITY_COMMAND, MKLINK_IDENTITY_TOKEN
from mklink.bridge import MKLinkSerialBridge
from mklink.dump_memory import DumpMemoryParser, DumpMemoryStreamSession, build_dump_mem_command
from mklink.memory_access import parse_read_ram_response
from mklink.superwatch import parse_timestamped_read_ram_response
from test_dump_memory_session import FakeBridge, _b1_frame, _old_frame

COMMAND = build_dump_mem_command([(0x20018BE0, 4096)], .000001)
ECHO = (COMMAND + '\n\r\n>>> ').encode('ascii')
STOP = b'cmd.dump_memory(0x20018BE0, 4096, -1.0)\n'
IDENTITY = (MKLINK_IDENTITY_COMMAND + '\n').encode('ascii')
IDENTITY_REPLY = (MKLINK_IDENTITY_COMMAND + '\r\n' + MKLINK_IDENTITY_TOKEN + '\r\n>>> ').encode('ascii')
BLOCKS = b''.join(_b1_frame(123, bytes(2048), block_index=i, block_count=2, total_size=4096) for i in range(2))


@pytest.mark.parametrize('split', [1, 7, 43, 49, 50, 51, 4096, 65536])
def test_exact_startup_echo_is_accounted_separately_across_usb_chunks(split):
    assert len(ECHO) == 50
    parser = DumpMemoryParser([4096], startup_command=COMMAND)
    frames = []
    wire = ECHO + BLOCKS
    for offset in range(0, len(wire), split):
        frames.extend(parser.feed(wire[offset:offset+split]))
    assert len(frames) == 2
    assert parser.startup_control_bytes == 50
    assert parser.dropped_bytes == parser.dropped_frames == parser.crc_errors == 0
    assert not parser.pending_bytes


@pytest.mark.parametrize('prefix', [b'garbage', b'Error: DAP busy\r\n', ECHO.replace(b'4096', b'4095')])
def test_unknown_startup_text_still_counts_as_damage(prefix):
    parser = DumpMemoryParser([4096], startup_command=COMMAND)
    assert len(parser.feed(prefix + BLOCKS)) == 2
    assert parser.dropped_bytes == len(prefix)
    assert not parser.startup_control_bytes


def test_later_echo_and_corrupt_frame_are_never_ignored():
    parser = DumpMemoryParser([4096], startup_command=COMMAND)
    assert len(parser.feed(BLOCKS)) == 2
    assert len(parser.feed(ECHO + BLOCKS)) == 2
    assert parser.dropped_bytes == 50
    damaged = bytearray(BLOCKS); damaged[40] ^= 1
    parser.feed(damaged)
    assert parser.crc_errors == parser.dropped_frames == 1


def test_stream_statistics_distinguish_control_text_from_sample_damage():
    session = DumpMemoryStreamSession(FakeBridge([ECHO + BLOCKS]), [(0x20018BE0, 4096)], .000001)
    session.start()
    try:
        assert len(session.read_frames()) == 2
        assert session.stats['startup_control_bytes'] == 50
        assert session.stats['parser_dropped_bytes'] == 0
        assert session.stats['complete_samples'] == 1
    finally:
        session.stop()


@contextmanager
def bridge_wire(monkeypatch, reply, *, ack=True, identity=IDENTITY_REPLY, split=65536):
    monkeypatch.setattr('mklink.dump_control.STOP_TIMEOUT', .12)
    monkeypatch.setattr('mklink.dump_control.QUIET_PERIOD', .015)
    incoming = queue.Queue()
    writes = []
    bridge = MKLinkSerialBridge('TEST_DUMP_STOP')
    bridge._firmware_capabilities = frozenset({'DUMP_STOP=1'} if ack else ())
    class SerialPort:
        is_open = True
        @property
        def in_waiting(self): return 0
        def write(self, data):
            writes.append(data)
            response = reply if data == STOP else identity if data == IDENTITY else b'NEXT_OK\r\n>>> '
            for offset in range(0, len(response), split):
                incoming.put(response[offset:offset+split])
        def read(self, _size):
            try: return incoming.get(timeout=.001)
            except queue.Empty: return b''
    bridge._serial = SerialPort()
    bridge._ctx.state = DeviceState.DUMP_STREAM
    bridge._running = True
    reader = threading.Thread(target=bridge._reader_loop)
    reader.start()
    try:
        yield bridge, writes
    finally:
        bridge._running = False
        reader.join(timeout=1)
        assert not reader.is_alive()


@pytest.mark.parametrize('ack', [False, True])
@pytest.mark.parametrize('split', [1, 17, 65536])
def test_stop_drains_frames_and_confirms_clean_ready(monkeypatch, ack, split):
    reply = BLOCKS + STOP + b'\r\n' + (b'DUMP_STOPPED\r\n' if ack else b'') + b'>>> '
    with bridge_wire(monkeypatch, reply, ack=ack, split=split) as (bridge, writes):
        assert bridge._stop_stream_and_sync(STOP)
        assert bridge.state is DeviceState.READY
        assert bridge.send_command('next()', timeout=.2).strip() == 'NEXT_OK'
        assert writes == [STOP, IDENTITY, b'next()\n']


@pytest.mark.parametrize('split', [1, 65536])
@pytest.mark.parametrize('ack', [False, True])
@pytest.mark.parametrize('error', [b'Error: DAP busy; use multiplex or disconnect debugger',
    b'Error: dump stop unconfirmed (timeout or superseded)', b'Error: dump stop acknowledgement blocked'])
def test_rejected_stop_is_not_retried_or_declared_ready(monkeypatch, ack, error, split):
    with bridge_wire(monkeypatch, BLOCKS + STOP + error + b'\r\n>>> ', ack=ack, split=split) as (bridge, writes):
        assert not bridge._stop_stream_and_sync(STOP)
        assert bridge.state is DeviceState.ERROR
        assert error.decode() in bridge.last_stream_stop_error
        assert writes == [STOP]
        with pytest.raises(ConnectionError): bridge.send_command('next()')


@pytest.mark.parametrize('reply,ack', [
    (STOP + b'>>> ', True),  # advertised capability makes ACK mandatory
    (STOP + b'DUMP_STOPPED\r\n', True),  # still needs a prompt
    (STOP + b'DUMP_STOPPED\r\n' + BLOCKS + b'>>> ', True),
    (STOP + b'>>> ' + BLOCKS, False),
])
def test_missing_receipt_or_frames_after_stop_keep_error(monkeypatch, reply, ack):
    with bridge_wire(monkeypatch, reply, ack=ack) as (bridge, writes):
        assert not bridge._stop_stream_and_sync(STOP)
        assert bridge.state is DeviceState.ERROR


def test_identity_does_not_hide_ongoing_frames(monkeypatch):
    with bridge_wire(monkeypatch, STOP + b'>>> ', ack=False, identity=IDENTITY_REPLY + BLOCKS) as (bridge, writes):
        assert not bridge._stop_stream_and_sync(STOP)
        assert 'still produced frames' in bridge.last_stream_stop_error


def test_corrupt_pending_frame_does_not_expose_its_ack_bytes(monkeypatch):
    frame = bytearray(_old_frame(1, b'\r\nDUMP_STOPPED\r\n>>> '))
    frame[-1] ^= 1
    with bridge_wire(monkeypatch, bytes(frame) + STOP + b'DUMP_STOPPED\r\n>>> ') as (bridge, writes):
        assert not bridge._stop_stream_and_sync(STOP)
        assert 'CRC' in bridge.last_stream_stop_error
        assert writes == [STOP]


def test_stop_capability_is_cached_before_streaming(monkeypatch):
    bridge = MKLinkSerialBridge('TEST_DUMP_FEATURE')
    calls = []
    def version(command, **options):
        assert bridge.state is DeviceState.READY
        calls.append(command)
        return 'V4.7.2\r\nDUMP_STOP=1\r\nMUX_TARGET=1\r\n'
    monkeypatch.setattr(bridge, 'send_command', version)
    bridge._ctx.state = DeviceState.READY
    bridge.prepare_dump_stop()
    bridge.prepare_dump_stop()
    assert bridge.supports_multiplex()
    assert 'DUMP_STOP=1' in bridge._firmware_capabilities
    assert calls == ['cmd.get_version()']


def test_partial_frame_and_control_lookalikes_in_ram_do_not_satisfy_stop(monkeypatch):
    frame = _old_frame(1, b'\r\nDUMP_STOPPED\r\n>>> \r\n' + MKLINK_IDENTITY_TOKEN.encode() + b'\r\nError: DAP busy\r\n')
    with bridge_wire(monkeypatch, frame[10:] + STOP + b'>>> ') as (bridge, writes):
        assert not bridge._stop_stream_and_sync(STOP, dump_prefix=frame[:10])
        assert writes == [STOP]
        assert 'DUMP_STOPPED' in bridge.last_stream_stop_error


@pytest.mark.parametrize('prefix', ['', '20000000 aa bb cc dd\r\n'])
@pytest.mark.parametrize('failure', ['Error: DAP busy; use multiplex or disconnect debugger',
    'SBA unavailable: debug disabled, unauthenticated or unsupported', 'RuntimeError: read failed'])
def test_read_errors_are_preserved_even_after_partial_hex_rows(prefix, failure):
    response = 'cmd.read_ram(0x20000000, 4)\r\n' + prefix + failure + '\r\n>>> '
    for parser in (parse_read_ram_response, parse_timestamped_read_ram_response):
        with pytest.raises(RuntimeError, match=failure): parser(response)

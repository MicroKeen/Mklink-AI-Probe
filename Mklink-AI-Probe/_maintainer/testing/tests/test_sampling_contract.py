"""Current sampling admission and finite MUX readback; no physical target I/O."""
import struct
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink._types import DeviceState
from mklink.dump_memory import (
    DumpMemoryBusyError, DumpMemoryStreamSession, DumpMemoryUnsupported,
    read_dump_memory_range_once, read_dump_memory_regions_once,
)
from mklink.mux import MuxError, MuxTargetError
from mklink.mux_watch import MuxWatchSession
from test_mux_block_read import peer, reply
from test_watch_timing_v2 import peer as watch_peer, bridge_for


def memory_bridge(transport):
    return SimpleNamespace(state=DeviceState.READY, _cmd_lock=threading.RLock(),
        supports_multiplex=Mock(return_value=True), enable_multiplex=Mock(return_value=transport),
        _write_raw=Mock(side_effect=AssertionError('legacy I/O')),
        _leave_multiplex=Mock(side_effect=AssertionError('legacy transition')))


@pytest.mark.parametrize('missing', [8, 16, 512, 1024])
@pytest.mark.parametrize('fastest', [False, True])
@pytest.mark.parametrize('size', [1, 2, 4])
def test_every_required_capability_is_checked_before_drain_or_start(missing, fastest, size):
    transport, calls = watch_peer()
    transport.capabilities &= ~missing
    transport.drain = Mock(side_effect=AssertionError('must preserve queued events'))
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x58021010, size)], 0, fastest=fastest)
    before = list(calls)
    with pytest.raises(RuntimeError, match='0x618.*update'):
        session.start()
    assert calls == before and not session.started and not transport.watch_running
    transport.drain.assert_not_called()


@pytest.mark.parametrize('size', [1920, 1921, 4096, 524288])
def test_continuous_capacity_never_falls_back_to_old_bulk(size):
    transport, calls = watch_peer()
    bridge = memory_bridge(transport)
    session = DumpMemoryStreamSession(bridge, [(0x20010000, size)], .001)
    if size > 4096:
        with pytest.raises(ValueError, match='4096 bytes'):
            session.start()
        bridge.supports_multiplex.assert_not_called()
        bridge.enable_multiplex.assert_not_called()
    elif size > 1920:
        with pytest.raises(RuntimeError, match='0x800'):
            session.start()
        assert all(op not in (0x32, 0x34) for op, _ in calls)
    else:
        session.start()
        session.stop()
    bridge._write_raw.assert_not_called()
    bridge._leave_multiplex.assert_not_called()


@pytest.mark.parametrize('stream', [False, True])
def test_unsupported_bridge_reports_upgrade_without_legacy_io(stream):
    bridge = memory_bridge(None)
    bridge.supports_multiplex.return_value = False
    with pytest.raises(DumpMemoryUnsupported, match='update the probe firmware'):
        if stream:
            DumpMemoryStreamSession(bridge, [(0x20000000, 4)], .001).start()
        else:
            read_dump_memory_range_once(bridge, 0x80000000, 4)
    bridge.enable_multiplex.assert_not_called()
    bridge._write_raw.assert_not_called()


@pytest.mark.parametrize('caps,op,quantum', [(63, 0x11, 128), (127, 0x16, 4096)])
@pytest.mark.parametrize('regions', [
    [(0x80000123, 32769)], [(0x20010001, 1), (0x58021012, 2), (0x20020003, 65537)],
    [(0xfff80000, 524288)],
])
def test_finite_capture_preserves_full_exact_ranges_without_sampling(caps, op, quantum, regions):
    transport, calls = peer(caps=caps, fragment=997)
    bridge = memory_bridge(transport)
    result = read_dump_memory_regions_once(bridge, regions)
    assert result == tuple(bytes((address + i) & 255 for i in range(size)) for address, size in regions)
    expected = [(op, struct.pack('<IH', address + off, min(quantum, size-off)))
                for address, size in regions for off in range(0, size, quantum)]
    assert calls[2:] == expected
    assert not transport.watch_running and transport.ready
    bridge._write_raw.assert_not_called()
    bridge._leave_multiplex.assert_not_called()


@pytest.mark.parametrize('kind', ['crc', 'short', 'wrong_id', 'wrong_epoch', 'busy'])
def test_failure_in_second_block_never_returns_partial_or_retries(kind):
    n = [0]
    def failure(op, seq, answer):
        n[0] += 1
        if n[0] == 1:
            return reply(op | 0x80, 17, seq, b'\0' + answer)
        wire = reply(op | 0x80, 18 if kind == 'wrong_epoch' else 17,
            seq + 1 if kind == 'wrong_id' else seq,
            b'\x06' if kind == 'busy' else b'\0' + (answer[:-1] if kind == 'short' else answer))
        return wire[:-1] + bytes([wire[-1] ^ 1]) if kind == 'crc' else wire
    transport, calls = peer(failure=failure)
    bridge = memory_bridge(transport)
    with pytest.raises((MuxError, MuxTargetError)):
        read_dump_memory_range_once(bridge, 0x80000000, 16384)
    assert [op for op, _ in calls] == [1, 4, 0x16, 0x16]
    bridge._write_raw.assert_not_called()


@pytest.mark.parametrize('state', [DeviceState.RTT_STREAM, DeviceState.SYSTEMVIEW_STREAM, DeviceState.ERROR])
def test_busy_bridge_preserves_existing_owner_before_any_io(state):
    bridge = memory_bridge(None)
    bridge.state = state
    with pytest.raises(DumpMemoryBusyError):
        read_dump_memory_range_once(bridge, 0x20000000, 4)
    bridge.supports_multiplex.assert_not_called()
    bridge.enable_multiplex.assert_not_called()


@pytest.mark.parametrize('active', ['watch_running', 'rtt_mask'])
def test_finite_capture_does_not_stop_or_drain_an_active_mux_stream(active):
    transport, calls = peer()
    setattr(transport, active, 1)
    before = list(calls)
    with pytest.raises(DumpMemoryBusyError):
        read_dump_memory_range_once(memory_bridge(transport), 0x20000000, 4)
    assert calls == before and getattr(transport, active) == 1


@pytest.mark.parametrize('reason', ['cancel', 'timeout'])
def test_cancel_and_deadline_between_chunks_never_publish_partial(monkeypatch, reason):
    transport, calls = peer()
    now, cancelled = [time.monotonic()], [False]
    original = transport.read_memory
    def read(address, size, **kwargs):
        data = original(address, size, **kwargs)
        now[0] += 2.0
        cancelled[0] = reason == 'cancel'
        return data
    transport.read_memory = read
    monkeypatch.setattr('mklink.dump_memory.time', SimpleNamespace(monotonic=lambda: now[0]))
    with pytest.raises(InterruptedError if reason == 'cancel' else TimeoutError):
        read_dump_memory_regions_once(memory_bridge(transport), [(0x20010000, 8192)],
                                      timeout=1, cancelled=lambda: cancelled[0])
    assert [op for op, _ in calls] == [1, 4, 0x16]
    assert transport.ready  # Complete reply drained; cancellation does not poison ownership.


def test_concurrent_finite_captures_do_not_interleave_or_replace_owner():
    transport, calls = peer()
    bridge = memory_bridge(transport)
    entered, release = threading.Event(), threading.Event()
    original = transport.read_memory
    results, errors = [], []
    def read(address, size, **kwargs):
        if address == 0x20010000:
            entered.set()
            assert release.wait(2)
        return original(address, size, **kwargs)
    transport.read_memory = read
    def capture(address):
        try: results.append(read_dump_memory_range_once(bridge, address, 8192))
        except Exception as exc: errors.append(exc)
    first = threading.Thread(target=capture, args=(0x20010000,))
    second = threading.Thread(target=capture, args=(0x20020000,))
    first.start()
    try:
        assert entered.wait(2)
        second.start()
    finally:
        release.set()
        first.join(3)
        second.join(3)
    assert not errors and len(results) == 2
    assert [struct.unpack('<IH', body)[0] for op, body in calls if op == 0x16] == [
        0x20010000, 0x20011000, 0x20020000, 0x20021000]


def test_legacy_stop_is_rejected_without_transmitting():
    from mklink.bridge import MKLinkSerialBridge
    bridge = MKLinkSerialBridge('TEST_NO_IO')
    bridge._serial = Mock()
    with pytest.raises(RuntimeError, match='Legacy dump control was removed'):
        bridge._stop_stream_and_sync(b'cmd.dump_memory(0x20000000, 4, -1)\n')
    bridge._serial.write.assert_not_called()


def test_silent_memory_reply_obeys_capture_deadline_and_poisoned_session_cannot_replay():
    transport, calls = peer()
    sent = []
    transport._write = lambda wire: sent.append(wire) or len(wire)
    with pytest.raises(MuxError, match='timed out.*no replay'):
        read_dump_memory_range_once(memory_bridge(transport), 0x80000000, 8192, timeout=.01)
    assert len(sent) == 1 and sent[0][5] == 0x16
    with pytest.raises(MuxError):
        transport.read_memory(0x80000000, 4)
    assert len(sent) == 1


def test_expired_deadline_does_not_transmit_or_poison_idle_session():
    transport, calls = peer()
    before = list(calls)
    with pytest.raises(TimeoutError, match='before command delivery'):
        transport.read_memory(0x20010000, 4, deadline=time.monotonic() - 1)
    assert calls == before and transport.ready
    assert transport.read_memory(0x20010000, 4) == bytes(range(4))

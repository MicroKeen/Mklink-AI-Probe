"""Exercise negotiated sampling semantics through actual MUX reply framing."""
import struct
from types import SimpleNamespace

import pytest

from mklink.dump_memory import DumpMemoryStreamSession, build_dump_mem_command
from mklink.mux import MuxTargetError, MuxTransport, packet
from mklink.mux_watch import MuxWatchSession


def peer(*, timing_v2=True, ack=None, timebase=360_000_000,
         start_status=0, stop_status=0, first_sample=False):
    calls = []

    def write(wire):
        _, _, op, size, epoch, request = struct.unpack_from('<4sBBHII', wire)
        payload = wire[16:16 + size]
        body = payload[len(transport.nonce):] if 0x10 <= op < 0x40 else payload
        calls.append((op, body))
        answer = b''
        status = 0
        if op == 1:
            answer = struct.pack('<IHH', 15 | (512 if timing_v2 else 0), 256, 1)
        elif op == 4:
            answer = payload
        elif op == 0x32:
            period, = struct.unpack_from('<I', body)
            answer = ack if ack is not None else struct.pack('<II', period, timebase) if timing_v2 else b''
            status = start_status
        elif op == 0x31:
            status = stop_status
        reply = packet(op | 0x80, 17, request, bytes([status]) + answer)
        if op == 0x32 and first_sample and not status:
            reply += packet(0x41, 17, 1, struct.pack('<BBI', 0, 0, 1234) + b'abcd')
        transport.feed(reply[:11])
        transport.feed(reply[11:])
        return len(wire)

    transport = MuxTransport(write)
    transport.handshake()
    return transport, calls


def bridge_for(transport, *, multiplex=True):
    return SimpleNamespace(
        supports_multiplex=lambda: multiplex,
        enable_multiplex=lambda: transport,
        _enter_stream=lambda *a: pytest.fail('must not enter legacy stream'),
        _write_raw=lambda *a: pytest.fail('must not fall back or replay'),
    )


@pytest.mark.parametrize('period,expected', [(0, 2000), (1e-6, 1), (.0005, 500), (.001, 1000), (60, 60_000_000)])
@pytest.mark.parametrize('timebase', [24_000_000, 360_000_000])
def test_periodic_ack_preserves_exact_period_and_microsecond_samples(period, expected, timebase):
    transport, calls = peer(timebase=timebase, first_sample=True)
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 4)], period)
    session.start()
    assert session.timing == {'mode': 'periodic', 'requested_period_us': expected,
                              'accepted_period_us': expected, 'timebase_hz': timebase}
    assert struct.unpack_from('<I', next(body for op, body in calls if op == 0x32))[0] == expected
    assert session.read_frames()[0]['timestamp_us'] == 1234
    session.stop()
    assert not session.started and not transport.watch_running


def test_fastest_is_explicit_and_preserves_ack_adjacent_first_sample():
    transport, calls = peer(first_sample=True)
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 4)], 0, fastest=True)
    session.start()
    assert next(body for op, body in calls if op == 0x32) == struct.pack('<IBIB', 0, 1, 0x20000000, 4)
    assert session.timing['mode'] == 'fastest' and session.timing['accepted_period_us'] == 0
    sample, = session.read_frames()
    assert sample['regions'] == [(0, b'abcd')]
    copy = session.timing
    copy['accepted_period_us'] = 10
    assert session.timing['accepted_period_us'] == 0
    session.stop()
    assert [op for op, _ in calls].count(0x32) == 1


def test_old_zero_dump_still_means_single_read():
    assert build_dump_mem_command([(0x20000000, 4)], 0).endswith(', 0)')
    transport, calls = peer(timing_v2=False)
    watch = MuxWatchSession(transport, [(0x20000000, 4)], 0)
    watch.start()
    assert struct.unpack_from('<I', next(body for op, body in calls if op == 0x32))[0] == 2000
    assert watch.timing is None
    watch.stop()


@pytest.mark.parametrize('factory', [MuxWatchSession, DumpMemoryStreamSession])
@pytest.mark.parametrize('period,fastest', [(.001, True), (0, 1), (0, 'yes')])
def test_conflicting_or_untyped_mode_is_rejected_before_io(factory, period, fastest):
    with pytest.raises(ValueError, match='Fastest sampling requires'):
        factory(None, [(0x20000000, 4)], period, fastest=fastest)


@pytest.mark.parametrize('multiplex', [False, True])
def test_unsupported_fastest_never_starts_or_falls_back(multiplex):
    transport, calls = peer(timing_v2=False)
    session = DumpMemoryStreamSession(bridge_for(transport, multiplex=multiplex),
                                      [(0x20000000, 4)], 0, fastest=True, allow_legacy_bulk=True)
    with pytest.raises(RuntimeError, match='Fastest sampling requires'):
        session.start()
    assert not session.started and not transport.watch_running
    assert all(op not in (0x31, 0x32) for op, _ in calls)


def test_fastest_capacity_error_does_not_use_legacy_bulk():
    transport, calls = peer()
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 2048)], 0,
                                      fastest=True, allow_legacy_bulk=True)
    with pytest.raises(ValueError, match='15 regions'):
        session.start()
    assert all(op != 0x32 for op, _ in calls)


@pytest.mark.parametrize('ack', [b'', b'1234567', b'123456789',
                                struct.pack('<II', 0, 360_000_000),
                                struct.pack('<II', 1001, 360_000_000),
                                struct.pack('<II', 1000, 0)])
def test_invalid_v2_ack_stops_only_new_watch_without_replay(ack):
    transport, calls = peer(ack=ack)
    transport.rtt_mask = 2
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 4)], .001)
    with pytest.raises(RuntimeError, match='WATCH_TIMING=2 START acknowledgement'):
        session.start()
    assert not session.started and session.timing is None
    assert not transport.watch_running and transport.rtt_mask == 2 and transport.ready
    assert [op for op, _ in calls if op >= 0x10] == [0x32, 0x31]


def test_rejected_start_does_not_stop_unstarted_watch_or_replay():
    transport, calls = peer(start_status=5)
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 4)], 0, fastest=True)
    with pytest.raises(MuxTargetError):
        session.start()
    assert session.timing is None and not session.started and not transport.watch_running
    assert [op for op, _ in calls if op >= 0x10] == [0x32]


def test_failed_cleanup_keeps_unknown_capture_visible_and_invalidates_transport():
    transport, calls = peer(ack=b'', stop_status=5)
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 4)], .001)
    with pytest.raises(RuntimeError, match='stopping the unconfirmed capture failed'):
        session.start()
    assert session.timing is None and not session.started
    assert transport.watch_running and not transport.ready
    assert [op for op, _ in calls if op >= 0x10] == [0x32, 0x31]

import struct

import pytest

from mklink.mux import MuxTransport, packet


def session(monkeypatch, **options):
    now = [100.0]
    monkeypatch.setattr('mklink.mux.time.monotonic', lambda: now[0])
    writes = []
    mux = MuxTransport(lambda wire: writes.append(wire), command_timeout=60, **options)
    mux.ready = True
    mux.epoch = 7
    return mux, now, writes


def test_default_transport_keeps_single_slot(monkeypatch):
    mux, now, writes = session(monkeypatch)
    mux._send(0x16, b'')
    now[0] += 6
    mux.tick()
    assert len(writes) == 1 and not mux._heartbeats


def test_delayed_target_reply_survives_separately_correlated_pings(monkeypatch):
    mux, now, writes = session(monkeypatch, background_heartbeats=True)
    mux._send(0x16, b'')
    pending = mux._pending
    for _ in range(10):
        now[0] += 1.1
        mux.tick()
    assert len(writes) == 11 and mux._pending == pending
    assert [struct.unpack_from('<I', wire, 12)[0] for wire in writes] == list(range(1, 12))
    assert all(wire[5] == 2 for wire in writes[1:])
    mux.feed(packet(0x96, 7, 1, b'\0data'))
    for request in range(2, 12):
        mux.feed(packet(0x82, 7, request, b'\0'))
    assert not mux._heartbeats and mux._pending is None and mux._reply == b'\0data'
    assert mux._error is None


@pytest.mark.parametrize('opcode,epoch,payload', [(0x82, 8, b'\0'), (0x82, 7, b'\3'), (0x92, 7, b'\0')])
def test_invalid_ping_reply_never_completes_target_request(monkeypatch, opcode, epoch, payload):
    mux, now, writes = session(monkeypatch, background_heartbeats=True)
    mux._send(0x12, b'')
    now[0] += 1.1
    mux.tick()
    mux.feed(packet(opcode, epoch, 2, payload))
    mux.tick()
    assert mux._error is not None and mux._pending[0] == 0x12
    assert len(writes) == 2


def test_duplicate_ping_and_missing_ping_fail_closed(monkeypatch):
    mux, now, writes = session(monkeypatch, background_heartbeats=True)
    now[0] += 1.1
    mux.tick()
    reply = packet(0x82, 7, 1, b'\0')
    mux.feed(reply)
    mux.feed(reply)
    assert mux._error is not None
    mux, now, writes = session(monkeypatch, background_heartbeats=True)
    now[0] += 1.1
    mux.tick()
    now[0] += 61
    mux.tick()
    assert 'heartbeat timed out' in str(mux._error) and len(writes) == 1


def test_close_drains_pings_before_exit_without_emitting_more(monkeypatch):
    mux, now, writes = session(monkeypatch, background_heartbeats=True)
    now[0] += 1.1
    mux.tick()
    def drain(timeout):
        assert mux._closing and len(writes) == 1
        mux.feed(packet(0x82, 7, 1, b'\0'))
    monkeypatch.setattr(mux._condition, 'wait', drain)
    def write(wire):
        writes.append(wire)
        mux.feed(packet(0x83, 7, 2, b'\0'))
    mux._write = write
    mux.close()
    assert [wire[5] for wire in writes] == [2, 3]
    assert not mux.ready and not mux._heartbeats


def test_ping_window_stays_bounded_without_acknowledgements(monkeypatch):
    mux, now, writes = session(monkeypatch, background_heartbeats=True)
    mux.command_timeout = 3600
    for _ in range(65):
        now[0] += 1.1
        mux.tick()
    assert len(writes) == len(mux._heartbeats) == 64
    assert 'window full' in str(mux._error)

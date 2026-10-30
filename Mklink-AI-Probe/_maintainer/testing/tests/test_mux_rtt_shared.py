"""Wire-level shared RTT/SystemView contract, without serial or hardware."""
import struct
import threading
from types import SimpleNamespace

import pytest

from mklink.mux import MuxTransport, MuxTargetError, packet
from mklink.mux_rtt import MuxRTTSession, MuxRTTManager
from mklink.systemview import SystemViewSession
from test_shared_runtime import runtime


def rig(caps=255):
    calls, reject = [], {}
    def write(wire):
        _, _, op, size, _, req = struct.unpack_from('<4sBBHII', wire)
        payload = wire[16:16+size]
        data = payload[8:] if 0x10 <= op < 0x40 else payload
        calls.append((op, data))
        answer = {1: struct.pack('<IHH', caps, 256, 1), 4: payload}.get(op, b'')
        if op == 0x21:
            answer = bytes([len(data)-1])
        t.feed(packet(op | 0x80, 17, req, bytes([reject.get(op, 0)]) + answer))
        return len(wire)
    t = MuxTransport(write)
    t.handshake()
    calls.clear()
    seq = 0
    def emit(ch, data=b'data', status=0, op=0x40):
        nonlocal seq
        seq += 1
        t.feed(packet(op, 17, seq, struct.pack('<BBI', ch, status, seq)+data))
    info = {'down_buffers': [{'channel': ch, 'active': True} for ch in range(8)]}
    bridge = SimpleNamespace(supports_multiplex=lambda: True, enable_multiplex=lambda: t)
    return t, calls, reject, emit, info, bridge


def test_two_channels_preserve_other_capture_and_watch():
    t, calls, _, emit, info, bridge = rig()
    rtt = MuxRTTSession(t, info)
    rtt.start('0x20000000')
    t.watch_running = True
    emit(0, b'before')
    sv = SystemViewSession(bridge, info=info)
    sv.start('0x20000000')
    assert [op for op, _ in calls] == [0x20, 0x23, 0x21]
    assert calls[1] == (0x23, b'\x03\x03')
    emit(0, b'after')
    emit(1, b'\x00\xfftrace')
    emit(0, b'watch', op=0x41)
    assert rtt.read_output_bytes(0) == b'beforeafter'
    assert sv.read_bytes(0, max_bytes=2) == b'\x00\xff'
    assert sv.read_bytes(0) == b'trace'
    sv.stop()
    assert calls[-2:] == [(0x21, b'\x01\x02'), (0x23, b'\x01\x01')]
    assert t.watch_running and t.rtt_mask == 1
    assert t.drain(0x41, 255)[0][6:] == b'watch'
    emit(0, b'survives')
    assert rtt.read_output_bytes(0) == b'survives'
    rtt.stop()
    assert calls[-1] == (0x22, b'') and t.watch_running


@pytest.mark.parametrize('stop_sv_first', [True, False])
def test_same_channel_fanout_recorder_stays_for_remaining_consumer(stop_sv_first):
    t, calls, _, emit, info, bridge = rig()
    sv = SystemViewSession(bridge, info=info)
    sv.start('0x20000000')
    observer = MuxRTTSession(t, info, channel=1)
    observer.start('0x20000000')
    emit(1, b'one-read-two-consumers')
    assert sv.read_bytes(0) == observer.read_output_bytes(0) == b'one-read-two-consumers'
    assert sum(op == 0x20 for op, _ in calls) == 1
    first, second = (sv, observer) if stop_sv_first else (observer, sv)
    first.stop()
    assert not any(op in (0x22, 0x23) for op, _ in calls)
    emit(1, b'alive')
    assert (second.read_bytes(0) if second is sv else second.read_output_bytes(0)) == b'alive'
    second.stop()
    assert calls[-2:] == [(0x21, b'\x01\x02'), (0x22, b'')]


def test_conflicts_old_firmware_and_rejected_mask_leave_existing_consumer():
    t, calls, reject, emit, info, _ = rig()
    one = MuxRTTSession(t, info)
    one.start('0x20000000')
    two = MuxRTTSession(t, info, channel=1)
    with pytest.raises(RuntimeError, match='control-block conflict'):
        two.start('0x20000100')
    assert len(calls) == 1
    reject[0x23] = 6
    with pytest.raises(MuxTargetError):
        two.start('0x20000000')
    assert t.rtt_mask == 1 and len(t._rtt_manager.consumers) == 1
    emit(0, b'old survives')
    assert one.read_output_bytes(0) == b'old survives'
    t.capabilities &= ~128
    with pytest.raises(RuntimeError, match='incremental'):
        two.start('0x20000000')
    assert len(calls) == 2


def test_slow_consumer_drops_do_not_steal_fast_data_or_hide_target_error(monkeypatch):
    t, _, _, emit, info, _ = rig()
    monkeypatch.setattr(MuxRTTManager, 'QUEUE_BYTES', 30)
    fast, slow = [MuxRTTSession(t, info) for _ in range(2)]
    fast.start('0x20000000')
    slow.start('0x20000000')
    for i in range(10):
        emit(0, bytes([i])*10)
        assert fast.read_output_bytes(0) == bytes([i])*10
    assert not fast.dropped_bytes and slow.dropped_bytes[0] == 90
    emit(0, b'', status=7)
    for session in (fast, slow):
        with pytest.raises(RuntimeError, match='DAP changed'):
            session.read_output_bytes(0)
    assert t.ready


def test_waiting_reader_wakes_without_polling_and_stop_is_local():
    t, _, _, emit, info, _ = rig()
    session = MuxRTTSession(t, info)
    session.start('0x20000000')
    result = []
    reader = threading.Thread(target=lambda: result.append(session.read_output_bytes(2)))
    reader.start()
    emit(0, b'awake')
    reader.join(1)
    assert not reader.is_alive() and result == [b'awake']


def test_systemview_missing_capability_never_sends_legacy_commands():
    _, calls, _, _, info, bridge = rig(127)
    with pytest.raises(RuntimeError, match='incremental'):
        SystemViewSession(bridge, info=info).start('0x20000000')
    assert calls == []


def test_first_payload_in_same_read_as_start_ack_is_not_discarded():
    t, _, _, _, info, _ = rig()
    def write(wire):
        _, _, op, _, _, request = struct.unpack_from('<4sBBHII', wire)
        t.feed(packet(op | 0x80, 17, request, b'\0')
               + packet(0x40, 17, 1, struct.pack('<BBI', 0, 0, 1)+bytes(range(128))))
        return len(wire)
    t._write = write
    session = MuxRTTSession(t, info)
    session.start('0x20000000')
    assert session.read_output_bytes(0) == bytes(range(128))
    assert t.stats()['rtt_dropped_bytes'][0] == 0


def test_busy_stop_keeps_device_subscription_reachable_and_other_stream_alive():
    from mklink.device import Device
    from mklink._types import DeviceState
    t, _, reject, emit, info, _ = rig()
    one, two = MuxRTTSession(t, info), MuxRTTSession(t, info, channel=1)
    one.start('0x20000000')
    two.start('0x20000000')
    device = Device()
    device._connected = True
    device._bridge = SimpleNamespace(state=DeviceState.READY, _transport_error=None)
    device._rtt_session = one
    reject[0x23] = 6
    with pytest.raises(MuxTargetError):
        device.rtt_stop()
    assert device._rtt_session is one and one._running
    emit(1, b'alive')
    assert two.read_output_bytes(0) == b'alive'
    reject.clear()
    device.rtt_stop()  # Explicit retry, not an automatic replay.
    assert device._rtt_session is None and t.rtt_mask == 2


def test_shared_http_admission_and_leases_allow_three_captures(runtime):
    from test_shared_runtime import attach, call
    from mklink.remote.api import acquire_dashboard_resources, target_debug_lease
    from mklink.remote.resource_manager import ResourceError
    client, control, _, managers, app = runtime
    t, _, _, _, _, _ = rig()
    state = app.state.mklink_state
    state['device']._bridge = SimpleNamespace(_mux=t, _mux_supported=True, supports_multiplex=lambda: True)
    @app.post('/api/dash/systemview/start')
    async def start_sv():
        acquire_dashboard_resources(state, 'systemview')
        managers['systemview'].running = True
        return {'status': 'started'}
    @app.post('/api/device/read-memory')
    async def read_memory():
        return {'data_hex': '01020304'}
    session = attach(client)
    acquire_dashboard_resources(state, 'rtt')
    acquire_dashboard_resources(state, 'superwatch')
    managers['rtt'].running = managers['superwatch'].running = True
    assert call(client, session, 'systemview_start').status_code == 200
    assert call(client, session, 'read_memory', {'address': '0x20000000', 'size': 4}).status_code == 200
    with target_debug_lease(state, 'read-memory'):
        pass
    with pytest.raises(ResourceError):
        with target_debug_lease(state, 'halt'):
            pytest.fail('legacy debug admitted over active SystemView')
    state['resource_manager'].release('user:dashboard:systemview')
    assert len(state['resource_manager'].get_status()) == 2

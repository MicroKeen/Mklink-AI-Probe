"""Live-control framing and real worker lifecycle, with a simulated wire peer."""
import binascii
from concurrent.futures import Future
import struct
import time
from types import SimpleNamespace

import pytest

from mklink.dump_memory import DumpMemoryParser, DumpMemoryStreamSession, MAGIC
from mklink.remote.dashboards import SuperWatchStreamManager
from mklink.superwatch import SuperWatchRuntime, WatchItem
from test_rtt_superwatch_streaming import _symbol_write_device, _dump_frame


def ack(request_id=1, address=0x20000020, value=1.5, status=0):
    body = MAGIC + struct.pack('<QHBBIIBB8s', 12000, 42, 0, 0x57,
                              request_id, address, 4, status, struct.pack('<f', value))
    return body + struct.pack('<I', binascii.crc32(body))


@pytest.mark.parametrize('split', range(1, 42))
def test_ack_fragmented_among_samples(split):
    parser = DumpMemoryParser([4])
    wire = ack()
    frames = parser.feed(_dump_frame(1000, b'abcd') + wire[:split])
    frames += parser.feed(wire[split:] + _dump_frame(13000, b'efgh'))
    assert [x['format'] for x in frames] == ['OLD', 'WRITE_ACK', 'OLD']
    assert frames[1]['request_id'] == 1
    assert frames[1]['data'] == struct.pack('<f', 1.5)
    assert parser.crc_errors == 0


def test_corrupt_ack_is_not_success():
    wire = bytearray(ack()); wire[30] ^= 1
    parser = DumpMemoryParser([4])
    assert parser.feed(wire) == []
    assert parser.crc_errors == 1


class Peer:
    """Current MUX peer; historical ACK decoding is tested separately above."""
    def __init__(self, live=True):
        from mklink.mux import MuxTransport, packet
        self.live, self.writes, self.timestamp, self.value, self.ack_status = live, [], 1000, 0.0, 0
        self.sequence = 0
        def write(wire):
            self.writes.append(wire)
            _, _, op, n, epoch, seq = struct.unpack_from('<4sBBHII', wire)
            payload = wire[16:16+n]
            answer, status = b'', 0
            if op == 1: answer = struct.pack('<IHH', 0x61f, 256, 1)
            elif op == 4: answer = payload
            elif op in (0x32, 0x33): answer = struct.pack('<II', struct.unpack_from('<I', payload, 8)[0], 360000000)
            elif op == 0x12:
                data = payload[12:]
                if len(data) == 4: self.value = struct.unpack('<f', data)[0]
                status = self.ack_status
            self.transport.feed(packet(op | 0x80, 17, seq, bytes([status]) + answer))
            return len(wire)
        self.transport = MuxTransport(write)
        self.transport.handshake()
        original = self.transport.drain
        def drain(op, channel, **kwargs):
            if op == 0x41 and self.transport.watch_running:
                self.timestamp += 1000
                self.sequence += 1
                self.transport.feed(packet(0x41, 17, self.sequence,
                    struct.pack('<BBIf', 0, 0, self.timestamp, self.value)))
            return original(op, channel, **kwargs)
        self.transport.drain = drain

    def supports_multiplex(self): return True
    def enable_multiplex(self): return self.transport
    def supports_dump_write(self): return self.live


def manager_peer(tmp_path, live=True, write_error=None, hpm=False):
    device, operations = _symbol_write_device(tmp_path, write_error=write_error)
    peer = Peer(live)
    address = 0x20000020
    if hpm:
        from dataclasses import replace
        address = 0x01200020
        peer._ctx = SimpleNamespace(idcode=0x1000563D)
        peer.supports_hpm_dump_write = lambda: live
        device._target_writable_ram_ranges = lambda: [(address, address + 4)]
        device.symbol_catalog = replace(device.symbol_catalog, _ram_ranges=((address, address + 4),), items=tuple(
            replace(desc, address=address) for desc in device.symbol_catalog.items
        ))
    device._bridge = peer
    device.read_memory = lambda address, size: struct.pack('<f', peer.value)
    original_write = device.write_memory
    def write(address, data):
        original_write(address, data)
        peer.value = struct.unpack('<f', data)[0]
    device.write_memory = write
    manager = SuperWatchStreamManager()
    manager._runtime = SuperWatchRuntime(items=[WatchItem('gain', address, 'float', 4)])
    manager.start(device)
    end = time.monotonic() + 1
    while manager._origin_us is None and time.monotonic() < end: time.sleep(.001)
    assert manager._origin_us is not None
    return manager, peer, operations


@pytest.mark.parametrize('paused', [True, False])
def test_write_preserves_worker_epoch_origin_and_paused_state(tmp_path, paused):
    manager, peer, operations = manager_peer(tmp_path)
    try:
        if paused: manager.pause()
        before = (manager._thread, manager._origin_us, manager._metadata_version)
        result = manager.write_symbol('gain', generation=1, value=1.5)
        assert result['acknowledged'] and not result['verified'] and result['value'] == 1.5
        assert result['mode'] == 'cdc-mux'
        assert (manager._thread, manager._origin_us, manager._metadata_version) == before
        assert manager.get_status()['state'] == ('paused' if paused else 'running')
        assert len(manager.get_status()['write_events']) == 1
        assert not operations
        assert not any(b[5] == 0x31 for b in peer.writes)
    finally:
        manager.stop()


def test_rejected_write_does_not_reset_or_stop_capture(tmp_path):
    manager, peer, _ = manager_peer(tmp_path)
    peer.ack_status = 2
    try:
        before = manager._metadata_version
        manager.pause()
        with pytest.raises(RuntimeError, match='failed|unsupported'):
            manager.write_symbol('gain', generation=1, value=2.0)
        manager._thread.join(timeout=1)
        assert manager.get_status()['state'] == 'stopped'
        assert manager._metadata_version == before
        assert manager.get_status()['write_events'] == []
    finally: manager.stop()


def test_stopping_worker_rejects_idle_write(tmp_path):
    from unittest.mock import Mock
    device, operations = _symbol_write_device(tmp_path)
    manager = SuperWatchStreamManager()
    manager._device = device
    manager._thread = Mock()
    manager._thread.is_alive.return_value = True
    manager._stop_event.set()
    with pytest.raises(RuntimeError, match='stopping'):
        manager.write_symbol('gain', generation=1, value=2.0)
    assert operations == []


def test_hpm_capability_and_target_ram_intersection(tmp_path):
    manager, peer, operations = manager_peer(tmp_path, hpm=True)
    try:
        epoch = (manager._thread, manager._origin_us, manager._metadata_version)
        result = manager.write_symbol('gain', generation=1, value=3.125)
        assert result['mode'] == 'cdc-mux'
        assert result['acknowledged'] and not result['verified'] and result['value'] == 3.125
        assert manager._live_write_ranges == ((0x01200020, 0x01200024),)
        assert manager.get_status()['live_write_supported'] is True
        assert epoch == (manager._thread, manager._origin_us, manager._metadata_version)
    finally:
        manager.stop()


@pytest.mark.parametrize('address,size,allowed', [
    (0x01200020, 1, True), (0x01200020, 2, True),
    (0x01200020, 4, True), (0x01200020, 8, True),
    (0x012BFFFC, 8, False), (0x012C0000, 4, False),
    (0x80000000, 4, False), (0xF0000000, 4, False),
    (0x20000020, 4, False), (0x01200020, 3, False),
])
def test_hpm_session_rejects_unsupported_ranges_before_transmit(address, size, allowed):
    from mklink.dump_memory import HPM_WRITE_RANGES
    peer = Peer()
    session = DumpMemoryStreamSession(peer, [(0x01200020, 4)], .001, write_ranges=HPM_WRITE_RANGES)
    session.start()
    before = len(peer.writes)
    if allowed:
        # Peer decodes float writes only; use the real framing with a raw sink.
        session.request_write(address, bytes(size), Future())
        assert len(peer.writes) == before + 1
    else:
        with pytest.raises(ValueError):
            session.request_write(address, bytes(size), Future())
        assert len(peer.writes) == before
    session.stop()


@pytest.mark.parametrize('mode', ['cdc-mux'])
def test_write_without_readback_preserves_worker_and_next_write(tmp_path, monkeypatch, mode):
    from mklink.mux_watch import MuxWatchSession
    manager, peer, operations = manager_peer(tmp_path, live=mode == 'cdc-mux')
    writes = []
    def read(address, size):
        pytest.fail('write must not read back')
    if mode == 'cdc-mux':
        def write(address, data):
            writes.append(data)
            peer.value = struct.unpack('<f', data)[0]
        transport = SimpleNamespace(write_memory=write, read_memory=read)
        mux = MuxWatchSession(transport, [(0x20000020, 4)], .001)
        monkeypatch.setattr(DumpMemoryStreamSession, 'request_write',
                            lambda self, address, data, future: mux.write(address, data, future))
    else:
        manager._device.read_memory = read
    try:
        identity = (manager._thread, manager._origin_us, manager._metadata_version)
        result = manager.write_symbol('gain', generation=1, value=1.5)
        assert result['acknowledged'] and result['verified'] is False and result['value'] == 1.5
        assert result['mode'] == mode
        assert len(writes if mode == 'cdc-mux' else operations) == 1
        assert manager.running and manager.get_status()['error'] is None
        cycles = manager.get_status()['read_cycles']
        deadline = time.monotonic() + 1
        while manager.get_status()['read_cycles'] <= cycles and time.monotonic() < deadline:
            time.sleep(.001)
        assert manager.get_status()['read_cycles'] > cycles
        result = manager.write_symbol('gain', generation=1, value=3.5)
        assert result['acknowledged'] and not result['verified'] and result['value'] == 3.5
        assert identity == (manager._thread, manager._origin_us, manager._metadata_version)
        assert [event['verified'] for event in manager.get_status()['write_events']] == [False, False]
    finally:
        manager.stop()


def test_mux_write_transport_failure_remains_fatal_and_is_not_retried():
    from mklink.mux_watch import MuxWatchSession
    from mklink.mux import MuxError
    calls = []
    def write(address, data):
        calls.append(data)
        raise MuxError('outcome unknown')
    def read(address, size):
        pytest.fail('write must not read back')
    session = MuxWatchSession(SimpleNamespace(write_memory=write, read_memory=read), [(0x20000020,4)], .001)
    future = Future()
    with pytest.raises((RuntimeError, MuxError), match='unknown') as error:
        session.write(0x20000020, b'1234', future)
    assert future.exception() is error.value and len(calls) == 1


def test_idle_write_acknowledges_without_readback(tmp_path):
    device, operations = _symbol_write_device(tmp_path)
    device.read_memory = lambda *args: pytest.fail('write must not read back')
    manager = SuperWatchStreamManager()
    manager._device = device
    result = manager.write_symbol('gain', generation=1, value=1.5)
    assert result['acknowledged'] and result['verified'] is False and result['value'] == 1.5
    assert len(operations) == 1


@pytest.mark.parametrize('paused', [False, True])
@pytest.mark.parametrize('hpm', [False, True])
def test_missing_live_write_capability_preserves_stream_and_requests_upgrade(tmp_path, paused, hpm):
    from mklink.remote.dashboards import SuperWatchTransactionError
    manager, peer, operations = manager_peer(tmp_path, live=False, hpm=hpm)
    try:
        if paused:
            manager.pause()
        before = (manager._thread, manager._origin_us, manager._metadata_version)
        sent = len(peer.writes)
        with pytest.raises(SuperWatchTransactionError) as error:
            manager.write_symbol('gain', generation=1, value=1.5)
        detail = error.value.to_detail()
        assert detail['code'] == 'firmware_upgrade_required'
        assert '升级' in detail['message'] and 'upgrade' in detail['message']
        assert peer.writes[sent:] == [] and operations == []
        assert (manager._thread, manager._origin_us, manager._metadata_version) == before
        assert manager.get_status()['state'] == ('paused' if paused else 'running')
        assert not manager._write_requests and manager.get_status()['write_events'] == []
    finally:
        manager.stop()


def test_live_write_invalid_range_is_not_misreported_as_old_firmware(tmp_path):
    from mklink.remote.dashboards import SuperWatchTransactionError
    manager, peer, operations = manager_peer(tmp_path)
    try:
        manager._live_write_ranges = ()
        sent = len(peer.writes)
        with pytest.raises(SuperWatchTransactionError) as error:
            manager.write_symbol('gain', generation=1, value=1.5)
        assert error.value.to_detail()['code'] == 'superwatch_transaction_failed'
        assert 'RAM' in str(error.value) and 'upgrade' not in str(error.value)
        assert peer.writes[sent:] == [] and operations == [] and manager.running
    finally:
        manager.stop()

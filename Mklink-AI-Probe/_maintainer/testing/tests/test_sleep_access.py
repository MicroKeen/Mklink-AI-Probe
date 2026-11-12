import struct
from types import SimpleNamespace
import pytest

from mklink.device import Device, DeviceError
from mklink.mux import MuxError, MuxTargetError, MuxTransport, SLEEP_ACCESS_COMMAND, packet


def test_busy_status_does_not_claim_debugger_ownership_and_keeps_opcode():
    error = MuxTargetError(6, SLEEP_ACCESS_COMMAND)
    assert error.status == 6 and error.op == SLEEP_ACCESS_COMMAND
    assert 'access preparation incomplete' in str(error)
    assert 'not confirmed' in str(error) and 'opcode 0x17' in str(error)
from mklink.sleep_debug import DHCSR, configure, halted, halted_snapshot
from mklink.capture_clock import V3_CLOCKS


class Core:
    def __init__(self, cpuid=0x410cc200, stopped=False):
        self._bridge = SimpleNamespace(idcode=0x1ba01477, _ctx=SimpleNamespace(clock_interface='SWD'),
            _firmware_capabilities={'SWD_CLOCK_ACK=1', 'MUX_TARGET=1',
                                    'SWD_CLOCKS='+','.join(map(str,V3_CLOCKS))})
        self.clock_hz = 10_000_000
        self._bridge.enable_multiplex = lambda: self
        self.cpuid = cpuid
        self.dhcsr = 0x20003 if stopped else 0
        self.writes = []

    def set_debug_clock(self, clock, *, interface):
        assert interface == 'SWD'
        self.clock_hz = clock
        self._bridge._sleep_debug_previous_clock = None

    def read_memory(self, address, size):
        assert size == 4 and address in (0xe000ed00, DHCSR)
        return (self.cpuid if address == 0xe000ed00 else self.dhcsr).to_bytes(4, 'little')

    def write_memory(self, address, value):
        assert address == DHCSR and self.clock_hz == 100_000
        v = int.from_bytes(value, 'little')
        self.writes.append(v)
        self.dhcsr = (v & 3) | (0x20000 if v & 2 else 0)


@pytest.mark.parametrize('cpuid', [0x410cc200, 0x411fc231, 0x410fc241, 0x411fc271, 0x410fd213])
def test_opt_in_uses_negotiated_clock_and_never_writes_target(cpuid):
    device = Core(cpuid)
    assert configure(device, True)['clock_hz'] == 100_000
    assert configure(device, True)['previous_clock_hz'] == 10_000_000
    assert configure(device, False)['clock_hz'] == 10_000_000
    assert device.writes == []


def test_bad_core_id_restores_clock_and_jtag_is_not_touched():
    device = Core(0xffffffff)
    with pytest.raises(ValueError, match='identified'):
        configure(device, True)
    assert device.clock_hz == 10_000_000 and device.writes == []
    device._bridge._ctx.clock_interface = 'JTAG'
    with pytest.raises(ValueError, match='SWD'):
        configure(device, True)
    assert device.clock_hz == 10_000_000 and device.writes == []


@pytest.mark.parametrize('stopped', [False, True])
def test_verify_error_preserves_prior_halt_and_clock(stopped):
    device = Core(stopped=stopped)
    with pytest.raises(RuntimeError, match='readback'):
        with halted(device):
            assert device.clock_hz == 10_000_000 and device.dhcsr & 0x20000
            raise RuntimeError('readback failed')
    assert device.clock_hz == 10_000_000 and bool(device.dhcsr & 0x20000) == stopped
    assert device.writes == ([] if stopped else [0xa05f0003, 0xa05f0000])


def test_uncertain_programming_does_not_resume_incomplete_image():
    device = Core()
    with pytest.raises(RuntimeError, match='programming'):
        with halted(device, release_on_error=False):
            raise RuntimeError('programming failed')
    assert device.writes == [0xa05f0003] and device.clock_hz == 10_000_000


def test_debugger_pending_clock_refuses_before_core_writes():
    device = Core()
    device._bridge._ctx.clock_apply_state = 'configured'
    with pytest.raises(RuntimeError, match='handoff'):
        with halted(device):
            pytest.fail('No flash operation should start')
    assert device.writes == [] and device.clock_hz == 10_000_000


@pytest.mark.parametrize('stale', [0x01010000, 0x00050000, 0x411fc271])
def test_repeated_drw_across_addresses_is_not_a_core_witness(stale):
    device = Core(stale)
    device.dhcsr = stale
    with pytest.raises(ValueError):
        configure(device, True)
    with pytest.raises(ValueError), halted(device):
        pytest.fail('Stale AP reads must not admit memory access')
    assert device.writes == [] and device.clock_hz == 10_000_000


def test_snapshot_rejects_loss_of_halt_before_returning_data():
    device = Core()
    with pytest.raises(RuntimeError, match='did not remain halted'), halted_snapshot(device):
        device.dhcsr = 0
    assert device.writes == [0xa05f0003]


class AtomicPeer:
    def __init__(self):
        self.frames = []
        self.writes = []
        self.status = 0
        self.short = False
        self.ordinary = []
        self.mux = MuxTransport(self.receive)
        self.mux.handshake()

    def receive(self, wire):
        _, _, op, n, _, seq = struct.unpack_from('<4sBBHII', wire)
        payload = wire[16:16+n]
        status = 0
        if op == 1:
            reply = struct.pack('<IHH', 3 | (1 << 6) | (1 << 12), 256, 1)
        elif op == 4:
            reply = payload
        elif op in (0x11, 0x16, 0x12, 0x20, 0x32):
            self.ordinary.append(op)
            if op in (0x11, 0x16):
                addr, size = struct.unpack_from('<IH', payload, 8)
                reply = bytes((addr + i) & 255 for i in range(size))
            else:
                reply = b''
        else:
            assert op == SLEEP_ACCESS_COMMAND
            assert payload[:8] == self.mux.nonce and len(wire) <= 512
            kind, addr, size = struct.unpack_from('<BIH', payload, 8)
            self.frames.append((kind, addr, size))
            status = self.status
            if kind == 2:
                reply = struct.pack('<I', 0x411fc271)
            elif kind == 0:
                reply = bytes((addr + i) & 255 for i in range(size))
                if self.short:
                    reply = reply[:-1]
            else:
                assert kind == 1 and len(payload[15:]) == size
                self.writes.append(bytes(payload[15:]))
                reply = b''
        body = bytes([status]) + reply
        if op == 0x16:
            import zlib
            raw = struct.pack('<4sBBHII', b'MLX1', 1, 0x96, len(body), 9, seq) + body
            answer = raw + struct.pack('<I', zlib.crc32(raw))
        else:
            answer = packet(op | 0x80, 9, seq, body)
        self.mux.feed(answer[:19])
        self.mux.feed(answer[19:])
        return len(wire)


def atomic_device(peer):
    device = Core()
    device._bridge.enable_multiplex = lambda: peer.mux
    device._bridge._mux = peer.mux
    device._require_connected = lambda: None
    device._target_ram_contains = lambda addr, n: 0x24000000 <= addr < addr + n <= 0x24001000
    return device


def test_capability_alone_keeps_default_memory_and_stream_commands():
    peer = AtomicPeer()
    device = atomic_device(peer)
    for selected in (False, True):
        if selected:
            configure(device, True)
            configure(device, False)
        assert Device.read_memory(device, 0x24000000, 4096) == bytes(range(256)) * 16
        Device.write_memory(device, 0x40000000, b'word')
        peer.mux.request(0x20)
        peer.mux.request(0x32)
    assert peer.frames == [(2, 0, 0)]
    assert peer.ordinary == [0x16, 0x12, 0x20, 0x32] * 2
    assert device.clock_hz == 10_000_000


@pytest.mark.parametrize('interface', ['JTAG', 'unknown'])
def test_non_swd_interface_never_enters_mux_or_changes_clock(interface):
    device = Core()
    device._bridge._ctx.clock_interface = interface
    device._bridge.idcode = 0
    device._bridge.enable_multiplex = lambda: pytest.fail('Unexpected MUX entry')
    with pytest.raises(ValueError, match='SWD'):
        configure(device, True)
    assert device.writes == [] and device.clock_hz == 10_000_000


def test_busy_stream_is_not_interrupted_to_enable_sleep_access():
    peer = AtomicPeer()
    device = atomic_device(peer)
    peer.mux.watch_running = True
    with pytest.raises(RuntimeError, match='Stop acquisition'):
        configure(device, True)
    assert peer.frames == [] and peer.mux.watch_running and not peer.mux.sleep_access


@pytest.mark.parametrize('dashboard', ['rtt', 'superwatch', 'systemview'])
def test_atomic_session_rejects_live_start_before_claim_or_worker(dashboard):
    import asyncio
    from fastapi import HTTPException
    from mklink.remote.api import start_dashboard_manager

    state = {'device': atomic_device(AtomicPeer())}
    configure(state['device'], True)
    manager = SimpleNamespace(running=False, worker_alive=False)
    with pytest.raises(HTTPException) as failure:
        asyncio.run(start_dashboard_manager(state, dashboard, manager,
                    lambda: pytest.fail('No acquisition worker should start')))
    assert failure.value.status_code == 409 and 'sleep access' in failure.value.detail


def test_lost_atomic_capability_does_not_fall_back_to_ordinary_read_or_write():
    peer = AtomicPeer()
    device = atomic_device(peer)
    configure(device, True)
    peer.mux.capabilities &= ~MuxTransport.ATOMIC_SLEEP_CAPABILITY
    with pytest.raises(RuntimeError, match='unavailable'):
        Device.read_memory(device, 0x24000000, 4)
    with pytest.raises(RuntimeError, match='unavailable'):
        Device.write_memory(device, 0x24000000, bytes(4))
    assert peer.frames == [(2, 0, 0)] and not peer.ordinary


def test_legacy_flush_cannot_bypass_atomic_write_receipts():
    from mklink.memory_write import execute_flush
    peer = AtomicPeer()
    device = atomic_device(peer)
    configure(device, True)
    with pytest.raises(ValueError, match='verified RAM writes'):
        execute_flush(device, [(0x40000000, b'word')])
    assert peer.frames == [(2, 0, 0)] and not peer.writes


def test_atomic_mode_uses_original_clock_and_segments_only_validated_ram():
    peer = AtomicPeer()
    device = atomic_device(peer)
    assert configure(device, True)['clock_hz'] == 10_000_000
    assert peer.frames == [(2, 0, 0)]
    addr = 0x24000000
    data = Device.read_memory(device, addr, 1024)
    assert data == bytes(range(256))*4
    assert peer.frames[1:] == [(0, addr, 480), (0, addr+480, 480), (0, addr+960, 64)]
    with pytest.raises(DeviceError, match='known writable RAM'):
        Device.write_memory(device, 0x24000fff, bytes(2))
    with pytest.raises(DeviceError, match='known writable RAM'):
        Device.write_memory(device, 0x40000000, bytes(4))
    Device.write_memory(device, addr, data)
    assert b''.join(peer.writes) == data
    assert peer.frames[4:] == [(1, addr, 477), (1, addr+477, 477), (1, addr+954, 70)]
    with pytest.raises(RuntimeError, match='Asynchronous'):
        peer.mux.request(0x20)
    assert configure(device, False)['clock_hz'] == 10_000_000
    assert not peer.mux.sleep_access and not device.writes


def test_atomic_failure_does_not_retry_activate_fallback_or_repeat_a_write():
    peer = AtomicPeer()
    device = atomic_device(peer)
    peer.status = 5
    with pytest.raises(MuxTargetError, match='restoration'):
        configure(device, True)
    assert peer.frames == [(2, 0, 0)] and device.clock_hz == 10_000_000
    peer.status = 0
    configure(device, True)
    peer.status = 5
    with pytest.raises(MuxTargetError):
        Device.write_memory(device, 0x24000000, bytes(480))
    assert len(peer.writes) == 1


def test_short_atomic_read_poisons_session_without_partial_result():
    peer = AtomicPeer()
    peer.short = True
    with pytest.raises(MuxError, match='Invalid sleep access response'):
        peer.mux.read_atomic_memory(0x08000000, 512)
    assert peer.frames == [(0, 0x08000000, 480)]
    peer.mux.capabilities = 3
    with pytest.raises(ValueError, match='advertise'):
        peer.mux.probe_sleep_core()


@pytest.mark.parametrize('op, atomic, selected, seconds', [
    (0x17, True, False, 12), (0x17, True, True, 12),
    (0x15, True, False, 12), (0x15, True, True, 12),
    (0x15, False, False, 3), (0x15, False, True, 4.8),
    (0x11, True, False, 3), (0x12, True, False, 3), (0x02, True, True, 4.8),
])
def test_command_deadline_only_changes_for_negotiated_sleep_operations(monkeypatch, op, atomic, selected, seconds):
    import mklink.mux as protocol
    now = [100.0]
    monkeypatch.setattr(protocol, 'time', SimpleNamespace(monotonic=lambda: now[0]))
    frames = []
    mux = MuxTransport(frames.append)
    mux.sleep_access = selected
    mux.capabilities = MuxTransport.ATOMIC_SLEEP_CAPABILITY if atomic else 0
    mux._send(op, b'')
    assert mux._pending[2] == 100.0 + seconds
    now[0] = mux._pending[2] - 0.001
    mux.tick()
    mux._check()
    now[0] += 0.002
    mux.tick()
    with pytest.raises(MuxError, match='outcome unknown, no replay'):
        mux._check()
    assert len(frames) == 1

from types import SimpleNamespace
import pytest

from mklink.sleep_debug import DHCSR, configure, halted
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


@pytest.mark.parametrize('cpuid', [0x410cc200, 0x411fc231, 0x411fc271])
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

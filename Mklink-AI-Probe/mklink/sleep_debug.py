"""Bounded Cortex-M control transfers over the probe's negotiated SWD clocks."""
from contextlib import contextmanager
from functools import wraps
import time

from mklink.capture_clock import active_clock_interface, firmware_lines, clock_options

DHCSR = 0xE000EDF0
DEBUG_KEY = 0xA05F0000
C_DEBUGEN = 1
C_HALT = 2
S_HALT = 1 << 17


def control_clock(device):
    """Select a supported clock for control transfers that may span a sleeping tick."""
    bridge = device._bridge
    hz = getattr(device, 'clock_hz', None)
    if active_clock_interface(bridge) != 'SWD' or type(hz) is not int or hz <= 0:
        return None
    if not {'SWD_CLOCK_ACK=1', 'MUX_TARGET=1'} <= firmware_lines(bridge):
        return None
    return max((v for v in clock_options(bridge)['clocks_hz']
                if v <= min(hz, 100_000)), default=None)


def require_applied(device):
    if getattr(getattr(device._bridge, '_ctx', None), 'clock_apply_state', None) == 'configured':
        raise RuntimeError('SWD clock is pending debugger handoff; release the debugger before sleep access')


@contextmanager
def slow_control(device):
    previous = device.clock_hz
    slow = control_clock(device)
    if not slow:
        raise ValueError('Sleep control requires a negotiated SWD clock and MUX memory access')
    if slow == previous:
        require_applied(device)
        yield
        return
    saved_mode = getattr(device._bridge, '_sleep_debug_previous_clock', None)
    device.set_debug_clock(slow, interface='SWD')
    try:
        require_applied(device)
        yield
    finally:
        device.set_debug_clock(previous, interface='SWD')
        device._bridge._sleep_debug_previous_clock = saved_mode


def preserve_access_clock(operation):
    """Native flashing can temporarily choose its own FLM programming rate."""
    @wraps(operation)
    def run(device, *args, **kwargs):
        bridge = device._bridge
        previous = getattr(bridge, '_sleep_debug_previous_clock', None)
        clock = device.clock_hz if previous is not None else None
        try:
            return operation(device, *args, **kwargs)
        finally:
            if clock and device.connected and device._bridge is bridge:
                if device.clock_hz != clock:
                    device.set_debug_clock(clock, interface='SWD')
                bridge._sleep_debug_previous_clock = previous
    return run


def read_word(device, address):
    data = device._bridge.enable_multiplex().read_memory(address, 4)
    if len(data) != 4:
        raise RuntimeError(f'Incomplete control register at 0x{address:08X}')
    return int.from_bytes(data, 'little')


def write_word(device, address, value):
    device._bridge.enable_multiplex().write_memory(address, value.to_bytes(4, 'little'))


def wait_halt(device, halted):
    deadline = time.monotonic() + 1.0
    while True:
        if bool(read_word(device, DHCSR) & S_HALT) == halted:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Cortex-M halt/run state could not be confirmed')
        time.sleep(.01)


def identify_core(device):
    cpuid = read_word(device, 0xE000ED00)
    if cpuid in (0, 0xffffffff) or ((cpuid >> 16) & 15) not in (12, 15):
        raise ValueError('Cortex-M debug registers could not be identified')
    return cpuid


@contextmanager
def halted(device, *, release_on_error=True):
    """Keep an existing halt; release only a halt requested by this operation."""
    restore = None
    try:
        with slow_control(device):
            identify_core(device)
            old = read_word(device, DHCSR)
            if old & (C_HALT | S_HALT):
                if not old & S_HALT:
                    raise RuntimeError('Another halt is pending')
            else:
                if old & 0x2c:
                    raise RuntimeError('Core is stepping or has special debug controls active')
                restore = old & C_DEBUGEN
                write_word(device, DHCSR, DEBUG_KEY | C_DEBUGEN | C_HALT)
                wait_halt(device, True)
        try:
            yield
        except Exception:
            if not release_on_error:
                # The loader may have partially programmed Flash. Do not run
                # a possibly incomplete image as part of exception cleanup.
                restore = None
            raise
    finally:
        if restore is not None:
            with slow_control(device):
                if read_word(device, DHCSR) & (C_HALT | S_HALT):
                    write_word(device, DHCSR, DEBUG_KEY | restore)
                    wait_halt(device, False)


def configure(device, enabled):
    bridge = device._bridge
    previous = getattr(bridge, '_sleep_debug_previous_clock', None)
    if not enabled:
        if previous is not None:
            device.set_debug_clock(previous, interface='SWD')
            bridge._sleep_debug_previous_clock = None
        return {'enabled': False, 'clock_hz': device.clock_hz}
    slow = control_clock(device)
    if not slow:
        raise ValueError('Sleep access requires a negotiated SWD clock and MUX memory access')
    if previous is None:
        previous = device.clock_hz
        device.set_debug_clock(slow, interface='SWD')
        bridge._sleep_debug_previous_clock = previous
        try:
            require_applied(device)
            identify_core(device)
        except Exception:
            bridge._sleep_debug_previous_clock = None
            device.set_debug_clock(previous, interface='SWD')
            raise
    return {'enabled': True, 'clock_hz': device.clock_hz, 'previous_clock_hz': previous}

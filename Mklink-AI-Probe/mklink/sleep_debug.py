"""Bounded Cortex-M control transfers over the probe's negotiated SWD clocks."""
from contextlib import contextmanager
from functools import wraps
import time

from mklink.capture_clock import active_clock_interface, firmware_lines, clock_options

DHCSR = 0xE000EDF0
CPUID = 0xE000ED00
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


def advertised_atomic_sleep(bridge):
    """Passive capability lookup for a text-mode command on this connection."""
    from mklink.mux import MuxTransport
    caps = getattr(bridge, '_mux_capabilities', None)
    if type(caps) is int:
        return bool(caps & MuxTransport.ATOMIC_SLEEP_CAPABILITY)
    return 'MUX_ATOMIC_SLEEP=1' in firmware_lines(bridge)


def atomic_transport(device):
    bridge = device._bridge
    if active_clock_interface(bridge) != 'SWD' or 'MUX_TARGET=1' not in firmware_lines(bridge):
        return None
    mux = bridge.enable_multiplex()
    return mux if getattr(mux, 'supports_atomic_sleep', False) is True else None


def selected_clock(bridge):
    clock = getattr(bridge, '_sleep_debug_previous_clock', None)
    return clock if type(clock) is int and clock > 0 else None


def memory_transport(device):
    """An explicitly selected sleep mode must not silently switch protocols."""
    bridge = device._bridge
    mux = bridge.enable_multiplex()
    if selected_clock(bridge) is not None:
        atomic = getattr(bridge, '_sleep_debug_atomic', False)
        if mux is None or (getattr(mux, 'supports_atomic_sleep', False) is True) != atomic:
            raise RuntimeError('Selected sleep access is unavailable on this connection')
    return mux


def set_mode(bridge, previous_clock=None, *, atomic=False):
    bridge._sleep_debug_previous_clock = previous_clock
    bridge._sleep_debug_atomic = atomic
    mux = getattr(bridge, '_mux', None)
    if mux is not None:
        mux.sleep_access = previous_clock is not None


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
    saved_mode = selected_clock(device._bridge)
    atomic = getattr(device._bridge, '_sleep_debug_atomic', False)
    device.set_debug_clock(slow, interface='SWD')
    try:
        require_applied(device)
        yield
    finally:
        device.set_debug_clock(previous, interface='SWD')
        set_mode(device._bridge, saved_mode, atomic=atomic)


def preserve_access_clock(operation):
    """Native flashing can temporarily choose its own FLM programming rate."""
    @wraps(operation)
    def run(device, *args, **kwargs):
        bridge = device._bridge
        previous = selected_clock(bridge)
        atomic = getattr(bridge, '_sleep_debug_atomic', False)
        clock = device.clock_hz if previous is not None else None
        try:
            return operation(device, *args, **kwargs)
        finally:
            if clock and device.connected and device._bridge is bridge:
                if device.clock_hz != clock:
                    device.set_debug_clock(clock, interface='SWD')
                set_mode(bridge, previous, atomic=atomic)
    return run


def read_word(device, address):
    data = device._bridge.enable_multiplex().read_memory(address, 4)
    if len(data) != 4:
        raise RuntimeError(f'Incomplete control register at 0x{address:08X}')
    return int.from_bytes(data, 'little')


def write_word(device, address, value):
    device._bridge.enable_multiplex().write_memory(address, value.to_bytes(4, 'little'))


def core_state(device, *, expected_cpuid=None):
    """Bracket DHCSR with CPUID reads to reject a stale AP data register."""
    cpuid = read_word(device, CPUID)
    validate_cpuid(cpuid)
    state = read_word(device, DHCSR)
    if state == cpuid or read_word(device, CPUID) != cpuid or (
            expected_cpuid is not None and cpuid != expected_cpuid):
        raise ValueError('Cortex-M register reads are inconsistent; target state is unconfirmed')
    return cpuid, state


def validate_cpuid(cpuid):
    if cpuid >> 24 != 0x41 or ((cpuid >> 16) & 15) not in (12, 15):
        raise ValueError('Cortex-M debug registers could not be identified')


def wait_control(device, cpuid, expected):
    deadline = time.monotonic() + 1.0
    while True:
        _, state = core_state(device, expected_cpuid=cpuid)
        if state & (S_HALT | C_HALT | C_DEBUGEN) == expected:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Cortex-M halt/run state could not be confirmed')
        time.sleep(.01)


@contextmanager
def halted(device, *, release_on_error=True):
    """Keep an existing halt; release only a halt requested by this operation."""
    restore = None
    try:
        with slow_control(device):
            cpuid, old = core_state(device)
            if old & (C_HALT | S_HALT):
                if not old & S_HALT or not old & C_DEBUGEN:
                    raise RuntimeError('Existing halt or debugger transition is unconfirmed')
            else:
                if old & 0x2c:
                    raise RuntimeError('Core is stepping or has special debug controls active')
                restore = old & C_DEBUGEN
                write_word(device, DHCSR, DEBUG_KEY | C_DEBUGEN | C_HALT)
                wait_control(device, cpuid, S_HALT | C_HALT | C_DEBUGEN)
        try:
            yield cpuid
        except Exception:
            if not release_on_error:
                # The loader may have partially programmed Flash. Do not run
                # a possibly incomplete image as part of exception cleanup.
                restore = None
            raise
    finally:
        if restore is not None:
            try:
                with slow_control(device):
                    _, state = core_state(device, expected_cpuid=cpuid)
                    if state & (S_HALT | C_HALT | C_DEBUGEN) != restore:
                        write_word(device, DHCSR, DEBUG_KEY | restore)
                        wait_control(device, cpuid, restore)
            except Exception as error:
                raise RuntimeError(f'Original Cortex-M run state is unconfirmed: {error}') from error


@contextmanager
def halted_snapshot(device):
    """Only return an application memory result while the observed core is still halted."""
    with halted(device) as cpuid:
        yield
        _, state = core_state(device, expected_cpuid=cpuid)
        if state & (S_HALT | C_DEBUGEN) != (S_HALT | C_DEBUGEN):
            raise RuntimeError('Cortex-M did not remain halted; memory result is unconfirmed')


def configure(device, enabled):
    bridge = device._bridge
    previous = selected_clock(bridge)
    if enabled != (previous is not None) and getattr(getattr(bridge, '_mux', None), 'sampling', False) is True:
        raise RuntimeError('Stop acquisition before changing sleep access mode')
    if not enabled:
        if previous is not None:
            if not getattr(bridge, '_sleep_debug_atomic', False) or previous != device.clock_hz:
                device.set_debug_clock(previous, interface='SWD')
            set_mode(bridge)
        return {'enabled': False, 'clock_hz': device.clock_hz}
    if previous is None:
        previous = device.clock_hz
        if type(previous) is not int or previous <= 0:
            raise ValueError('Sleep access requires an acknowledged SWD clock')
        require_applied(device)
        mux = atomic_transport(device)
        if mux is not None:
            validate_cpuid(mux.probe_sleep_core())
            set_mode(bridge, previous, atomic=True)
            return {'enabled': True, 'clock_hz': previous, 'previous_clock_hz': previous}
        slow = control_clock(device)
        if not slow:
            raise ValueError('Sleep access requires a negotiated SWD clock and MUX memory access')
        device.set_debug_clock(slow, interface='SWD')
        set_mode(bridge, previous)
        try:
            require_applied(device)
            core_state(device)
        except Exception:
            set_mode(bridge)
            device.set_debug_clock(previous, interface='SWD')
            raise
    return {'enabled': True, 'clock_hz': device.clock_hz, 'previous_clock_hz': previous}

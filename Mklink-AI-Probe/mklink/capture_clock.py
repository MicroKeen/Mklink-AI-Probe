"""Cached acquisition-clock capabilities and truthful setting acknowledgements.

The application clock is separate from a debugger's borrowed DAP clock.
No helper in this module enumerates USB, queries the target, or stops a stream.
"""
from __future__ import annotations

import re

V3_CLOCKS = (1000, 5000, 10000, 20000, 50000, 100000, 200000, 500000,
             1000000, 2000000, 5000000, 10000000, 20000000, 30000000)
LEGACY_SWD_CLOCKS = (4000000, 10000000, 20000000, 30000000)
HPM_CLOCKS = (4000000, 10000000, 20000000, 30000000)


def firmware_lines(bridge):
    lines = getattr(bridge, '_firmware_capabilities', None)
    return lines if isinstance(lines, (set, frozenset)) else frozenset()


def clock_options(bridge, *, hpm=False):
    """Advertised V3 options must never leak into HPM or legacy V2/V4 modes."""
    lines = firmware_lines(bridge)
    context = getattr(bridge, '_ctx', None)
    hpm = hpm or getattr(bridge, 'idcode', None) == 0x1000563D or getattr(context, 'clock_interface', None) == 'JTAG'
    advertised = 'SWD_CLOCKS=' + ','.join(map(str, V3_CLOCKS))
    v3 = (not hpm and 'SWD_CLOCK_ACK=1' in lines and advertised in lines
          and any(re.fullmatch(r'V3\.\d+\.\d+', line) for line in lines)
          and not any(re.match(r'V[24]\.', line) for line in lines))
    return {'interface': 'JTAG' if hpm else 'SWD',
            'clocks_hz': list(HPM_CLOCKS if hpm else V3_CLOCKS if v3 else LEGACY_SWD_CLOCKS),
            'clock_source': 'v3-advertised' if v3 else 'hpm-profiles' if hpm else 'legacy',
            'live_change_supported': False}


def invalidate_clock(bridge):
    context = bridge._ctx
    context.swd_clock_hz = 0
    context.applied_clock_hz = 0
    context.clock_apply_state = 'unknown'


def _clock_reply(response):
    """Parse unique acknowledgement lines, excluding command echoes/diagnostics."""
    response = response if isinstance(response, str) else ''
    lines = [line.strip() for line in response.splitlines()]
    settings = [line for line in lines if line.startswith('set clock ')]
    profiles = [line for line in lines if line.startswith(('SWD profile=', 'JTAG profile='))]
    states = [line for line in lines if line.startswith(('SWD clock_state=', 'JTAG clock_state='))]
    if (any(line == '-1' or line.lower().startswith('error') for line in lines)
            or len(settings) > 1 or len(profiles) > 1 or len(states) > 1):
        raise ValueError('Probe did not acknowledge a unique clock setting')
    setting = re.fullmatch(r'set clock (\d+)', settings[0]) if settings else None
    profile = re.fullmatch(r'(SWD|JTAG) profile=(\d+)(?:[ \t]+.*)?', profiles[0]) if profiles else None
    state = re.fullmatch(r'SWD clock_state=(configured|applied)', states[0]) if states else None
    if (settings and not setting) or (profiles and not profile) or (states and not state):
        raise ValueError('Probe returned a malformed clock acknowledgement')
    return (int(setting.group(1)) if setting else None,
            (profile.group(1), int(profile.group(2))) if profile else None,
            state.group(1) if state else None)


def acknowledge_clock(bridge, hz, response):
    """Confirm the active interface; a JTAG profile never proves application.

    SWD_CLOCK_ACK describes SWD support globally, including on JTAG-capable
    probes. JTAG has no applied/configured state and may defer to an IDE.
    """
    setting, profile, reported_state = _clock_reply(response)
    context = bridge._ctx
    expected = ('JTAG' if getattr(bridge, 'idcode', None) == 0x1000563D
                else getattr(context, 'clock_interface', 'unknown'))
    interface = profile[0] if profile else expected
    modern_swd = 'SWD_CLOCK_ACK=1' in firmware_lines(bridge)
    if (setting is not None and setting != hz) or (profile and profile[1] != hz):
        raise ValueError('Probe did not acknowledge the requested clock setting')
    if expected in ('SWD', 'JTAG') and profile and profile[0] != expected:
        raise ValueError('Probe acknowledged a different debug clock interface')
    if modern_swd and setting != hz:
        raise ValueError('Probe did not acknowledge the requested clock setting')
    if interface == 'JTAG':
        if hz not in HPM_CLOCKS or not profile or reported_state is not None:
            raise ValueError('Probe did not acknowledge a supported JTAG profile')
        state = 'acknowledged'
    else:
        if setting != hz and not profile:
            raise ValueError('Probe did not acknowledge the requested clock setting')
        if modern_swd and reported_state is None:
            raise ValueError('Probe did not acknowledge configured/applied clock state')
        state = reported_state or 'acknowledged'
        if modern_swd or reported_state:
            interface = 'SWD'
    context.swd_clock_hz = hz
    context.clock_apply_state = state
    context.applied_clock_hz = hz if state == 'applied' else 0
    context.clock_interface = interface
    return {'clock_hz': hz, 'configured_hz': hz,
            'applied_hz': hz if state == 'applied' else None,
            'apply_state': state, 'interface': interface,
            'profile_confirmed': bool(profile)}


def requested_clock(config):
    from mklink.debug_speed import PROFILES
    raw = config.get('swd_clock')
    if raw is None or raw == '':
        return PROFILES.get(config.get('debug_speed') or 'medium')
    try:
        return int(raw, 0) if isinstance(raw, str) else raw if type(raw) is int else None
    except ValueError:
        return None


def clock_snapshot(device, config):
    bridge = getattr(device, '_bridge', None)
    options = clock_options(bridge, hpm=str(getattr(device, '_mcu_hint', '')).upper().startswith('HPM'))
    context = getattr(bridge, '_ctx', None)
    connected = bool(device and device.connected)
    hz = getattr(context, 'swd_clock_hz', 0) if connected else 0
    hz = hz if type(hz) is int and hz > 0 else None
    state = getattr(context, 'clock_apply_state', 'unknown') if hz else 'unknown'
    requested = requested_clock(config)
    migration = None
    if options['clock_source'] == 'v3-advertised' and (requested == 4000000 or hz == 4000000):
        migration = {'from_hz': 4000000, 'to_hz': 2000000, 'pending': True}
    return {**options, 'connected': connected, 'requested_hz': requested,
            'clock_hz': hz, 'configured_hz': hz, 'apply_state': state,
            'applied_hz': hz if state == 'applied' else None, 'migration': migration,
            'warning': getattr(device, 'clock_warning', None)}

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


def prepare_clock_capabilities(bridge):
    """Negotiate once on the command bridge before a first clock write.

    Raw probe-info queries do not fill this cache, even on the same bridge.
    Status-only helpers deliberately never call this function.
    """
    if getattr(bridge, '_firmware_capabilities', frozenset()) is not None:
        return
    from mklink._types import DeviceState
    if bridge.state != DeviceState.READY:
        raise ValueError('Stop acquisition before preparing debug clock capabilities')
    loader = getattr(bridge, '_get_firmware_capabilities', None)
    if not callable(loader):
        raise ValueError('Cannot read firmware capabilities before setting the clock')
    lines = loader()  # Transport failures propagate; never replay a clock write.
    if (not isinstance(lines, (set, frozenset))
            or not any(re.search(r'\bV\d+\.\d+\.\d+\b', line) for line in lines)):
        bridge._firmware_capabilities = None
        raise ValueError('Probe did not return a valid firmware version; clock was not changed')


def jtag_multiclock(bridge):
    lines = firmware_lines(bridge)
    return ('JTAG_CLOCK_ACK=1' in lines
            and 'JTAG_CLOCKS=' + ','.join(map(str, V3_CLOCKS)) in lines)


def active_clock_interface(bridge):
    """Cached firmware mode only; a UI preference never changes this value."""
    context = getattr(bridge, '_ctx', None)
    mode = getattr(context, 'clock_interface', None)
    if mode in ('SWD', 'JTAG'):
        return mode
    identity = getattr(bridge, 'idcode', None)
    if identity == 0x1000563D:
        return 'JTAG'
    if type(identity) is int and identity & 0xFFF == 0x477:
        return 'SWD'
    return 'unknown'


def clock_options(bridge, *, hpm=False, interface=None):
    """Capabilities describe each interface, independently of the active mode."""
    lines = firmware_lines(bridge)
    active = active_clock_interface(bridge)
    if interface:
        hpm = interface == 'JTAG'
    elif active != 'unknown':
        hpm = active == 'JTAG'
    advertised = 'SWD_CLOCKS=' + ','.join(map(str, V3_CLOCKS))
    modern = not hpm and 'SWD_CLOCK_ACK=1' in lines and advertised in lines
    v3 = modern and any(re.fullmatch(r'V3\.\d+\.\d+', line) for line in lines)
    modern_jtag = hpm and jtag_multiclock(bridge)
    return {'interface': 'JTAG' if hpm else 'SWD',
            'clocks_hz': list(V3_CLOCKS if modern_jtag or modern else HPM_CLOCKS if hpm else LEGACY_SWD_CLOCKS),
            'clock_source': 'jtag-advertised' if modern_jtag else 'v3-advertised' if v3 else 'swd-advertised' if modern else 'hpm-profiles' if hpm else 'legacy',
            'live_change_supported': False}


def configuration_clock_options(bridge, *, hpm=False, interface=None):
    """Offer the full offline catalog without asserting probe capabilities."""
    options = clock_options(bridge, hpm=hpm, interface=interface)
    if bridge is None:
        options.update(clocks_hz=list(V3_CLOCKS), clock_source='configuration')
    return options


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
    state = re.fullmatch(r'(SWD|JTAG) clock_state=(configured|applied)', states[0]) if states else None
    if (settings and not setting) or (profiles and not profile) or (states and not state):
        raise ValueError('Probe returned a malformed clock acknowledgement')
    if state and ((profile and state.group(1) != profile.group(1))
                  or (state.group(1) == 'JTAG' and not profile)):
        raise ValueError('Probe returned mixed or incomplete clock interface acknowledgement')
    return (int(setting.group(1)) if setting else None,
            (profile.group(1), int(profile.group(2))) if profile else None,
            state.group(2) if state else None)


def acknowledge_clock(bridge, hz, response):
    """Confirm interface-specific state only when its firmware contract exists.

    SWD_CLOCK_ACK describes SWD support globally, including on JTAG-capable
    probes. Legacy JTAG profiles have no state and may defer to an IDE.
    """
    setting, profile, reported_state = _clock_reply(response)
    context = bridge._ctx
    expected = ('JTAG' if getattr(bridge, 'idcode', None) == 0x1000563D
                else getattr(context, 'clock_interface', 'unknown'))
    interface = profile[0] if profile else expected
    modern_swd = 'SWD_CLOCK_ACK=1' in firmware_lines(bridge)
    modern_jtag = 'JTAG_CLOCK_ACK=1' in firmware_lines(bridge)
    if (setting is not None and setting != hz) or (profile and profile[1] != hz):
        raise ValueError('Probe did not acknowledge the requested clock setting')
    if expected in ('SWD', 'JTAG') and profile and profile[0] != expected:
        raise ValueError('Probe acknowledged a different debug clock interface')
    if (modern_swd or modern_jtag) and setting != hz:
        raise ValueError('Probe did not acknowledge the requested clock setting')
    if interface == 'JTAG':
        supported = (*V3_CLOCKS, 4000000) if jtag_multiclock(bridge) else HPM_CLOCKS
        if hz not in supported or not profile:
            raise ValueError('Probe did not acknowledge a supported JTAG profile')
        if modern_jtag and reported_state is None:
            raise ValueError('Probe did not acknowledge configured/applied JTAG clock state')
        if not modern_jtag and reported_state is not None:
            raise ValueError('Probe returned JTAG clock state without the required capability')
        state = reported_state or 'acknowledged'
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


def requested_clock(config, interface=None):
    from mklink.debug_speed import PROFILES
    raw = config.get('swd_clock')
    if interface == 'JTAG':
        # Before split configuration, swd_clock was shared with JTAG. Preserve
        # that request once; new independent JTAG configurations default to 10M.
        raw = config.get('jtag_clock', raw if 'clock_interface' not in config else 10000000)
    if raw is None or raw == '':
        return PROFILES.get(config.get('debug_speed') or 'medium')
    try:
        return int(raw, 0) if isinstance(raw, str) else raw if type(raw) is int else None
    except ValueError:
        return None


def save_interface_clock(config, interface, hz=None):
    """Split legacy shared settings without overwriting either saved frequency."""
    if interface not in ('SWD', 'JTAG'):
        raise ValueError('Clock interface must be SWD or JTAG')
    previous = {mode: requested_clock(config, mode) for mode in ('SWD', 'JTAG')}
    for mode, value in previous.items():
        if value is not None:
            config.setdefault(mode.lower() + '_clock', str(value))
    config['clock_interface'] = interface
    if hz is not None:
        config[interface.lower() + '_clock'] = str(hz)
        if interface == 'SWD':
            from mklink.debug_speed import PROFILES
            matching = next((key for key, value in PROFILES.items() if value == hz), None)
            if matching:
                config['debug_speed'] = matching
            else:
                config.pop('debug_speed', None)


def clock_snapshot(device, config):
    connected = bool(device and device.connected)
    bridge = getattr(device, '_bridge', None) if connected else None
    options = configuration_clock_options(bridge, hpm=str(getattr(device, '_mcu_hint', '')).upper().startswith('HPM'))
    context = getattr(bridge, '_ctx', None)
    hz = getattr(context, 'swd_clock_hz', 0) if connected else 0
    hz = hz if type(hz) is int and hz > 0 else None
    state = getattr(context, 'clock_apply_state', 'unknown') if hz else 'unknown'
    requested = requested_clock(config, options['interface'])
    migration = None
    if options['clock_source'] in ('v3-advertised', 'swd-advertised') and (requested == 4000000 or hz == 4000000):
        migration = {'from_hz': 4000000, 'to_hz': 2000000, 'pending': True}
    interfaces = {mode: {**configuration_clock_options(bridge, interface=mode),
                         'requested_hz': requested_clock(config, mode)} for mode in ('SWD', 'JTAG')}
    selected = config.get('clock_interface')
    return {**options, 'connected': connected, 'requested_hz': requested,
            'active_interface': active_clock_interface(bridge) if connected else 'unknown',
            'selected_interface': selected if selected in interfaces else options['interface'],
            'interfaces': interfaces,
            'clock_hz': hz, 'configured_hz': hz, 'apply_state': state,
            'applied_hz': hz if state == 'applied' else None, 'migration': migration,
            'warning': getattr(device, 'clock_warning', None)}

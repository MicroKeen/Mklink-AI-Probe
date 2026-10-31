"""Named debug clock profiles shared by SDK, CLI, MCP and Web."""
from __future__ import annotations

PROFILES = {"low": 4_000_000, "medium": 10_000_000, "high": 20_000_000, "ultra": 30_000_000}


class ClockProfileUnavailable(ValueError):
    """Requested kernel is unavailable; a fallback setting was acknowledged."""


def validate_clock_hz(hz: int) -> int:
    """Keep legacy clocks up to 10 MHz and the two calibrated high kernels."""
    if type(hz) is not int or not (1 <= hz <= 10_000_000 or hz in (20_000_000, 30_000_000)):
        raise ValueError("clock must be an integer from 1 Hz to 10 MHz, or exactly 20 MHz / 30 MHz")
    return hz


def validate_hpm_clock_hz(hz: int, bridge=None) -> int:
    """HPM private JTAG has named DMI kernels, not arbitrary SWD timing."""
    from mklink.capture_clock import V3_CLOCKS, jtag_multiclock
    supported = (*V3_CLOCKS, 4_000_000) if jtag_multiclock(bridge) else PROFILES.values()
    if type(hz) is not int or hz not in supported:
        raise ValueError("HPM JTAG requires a 4/10/20/30 MHz debug profile; arbitrary SWD clocks do not set its TCK")
    return hz


def profile_clock(profile: str) -> int:
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError("debug speed must be low (4 MHz), medium (10 MHz), high (20 MHz), or ultra (30 MHz)")
    return PROFILES[profile]


def apply_profile(device, profile: str) -> dict:
    device._require_connected()
    return apply_bridge_profile(device._bridge, profile)


def apply_bridge_profile(bridge, profile: str) -> dict:
    return apply_bridge_clock(bridge, profile_clock(profile), profile=profile)


def apply_bridge_clock(bridge, hz: int, *, profile: str | None = None) -> dict:
    """Apply an explicit clock through the same ACK and idle-state guards."""
    from mklink._types import DeviceState
    from mklink.capture_clock import acknowledge_clock, invalidate_clock, firmware_lines, _clock_reply, prepare_clock_capabilities

    validate_clock_hz(hz)
    if bridge.state != DeviceState.READY:
        raise ValueError("Stop the active stream before changing debug speed")
    prepare_clock_capabilities(bridge)
    if (getattr(bridge, 'idcode', None) == 0x1000563D
            or getattr(bridge._ctx, 'clock_interface', None) == 'JTAG'):
        validate_hpm_clock_hz(hz, bridge)
    # Clock configuration belongs to the probe, not the attached MCU. V3 may
    # omit the optional profile line while its target scanner has no IDCODE.
    # Accept its exact setting acknowledgement for every supported clock;
    # retain profile_confirmed separately from the accepted setting.
    invalidate_clock(bridge)
    response = bridge.send_command(f"cmd.set_swd_clock({hz})")
    try:
        result = acknowledge_clock(bridge, hz, response)
    except ValueError:
        # Preserve only the legacy firmware's explicit profile=0 fallback.
        # Missing, mismatched, mixed or rejected replies are unknown outcomes:
        # do not issue another clock write. Modern firmware never falls back.
        if firmware_lines(bridge) & {'SWD_CLOCK_ACK=1', 'JTAG_CLOCK_ACK=1'}:
            raise
        setting, rejected_profile, reported_state = _clock_reply(response)
        expected = ('JTAG' if getattr(bridge, 'idcode', None) == 0x1000563D
                    else getattr(bridge._ctx, 'clock_interface', 'unknown'))
        if (not rejected_profile or rejected_profile[1] != 0 or reported_state
                or setting not in (None, hz)
                or expected in ('SWD', 'JTAG') and rejected_profile[0] != expected):
            raise
        interface = rejected_profile[0]
        jtag = interface == 'JTAG'
        fallback_hz = 4_000_000 if jtag else 1_000_000
        fallback = bridge.send_command(f"cmd.set_swd_clock({fallback_hz})")
        try:
            fallback_setting, fallback_profile, _ = _clock_reply(fallback)
            if (fallback_setting != fallback_hz
                    or jtag and fallback_profile != ('JTAG', fallback_hz)
                    or fallback_profile and fallback_profile[0] != interface):
                raise ValueError('Mismatched fallback acknowledgement')
            acknowledge_clock(bridge, fallback_hz, fallback)
        except ValueError as error:
            invalidate_clock(bridge)
            raise ValueError(f"Probe firmware did not confirm {interface} profile or fallback clock") from error
        raise ClockProfileUnavailable(f"Probe firmware does not confirm this {interface} profile; restored {fallback_hz // 1_000_000} MHz")
    qualification = (f"{result['interface']} profile confirmed; exact target and board stability not identified by IDCODE"
                     if result['profile_confirmed'] else 'Probe accepted clock setting; target timing not verified')
    if result['interface'] == 'JTAG' and result['apply_state'] == 'acknowledged':
        qualification += '; application timing and IDE clock are not confirmed'
    elif result['interface'] == 'JTAG':
        qualification += '; IDE clock is independent; requested timing is not measured TCK'
    return {**result, "profile": profile,
            "qualification": qualification}

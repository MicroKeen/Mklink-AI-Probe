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


def validate_hpm_clock_hz(hz: int) -> int:
    """HPM private JTAG has named DMI kernels, not arbitrary SWD timing."""
    if type(hz) is not int or hz not in PROFILES.values():
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
    from mklink._types import DeviceState
    import re

    hz = profile_clock(profile)
    if bridge.state != DeviceState.READY:
        raise ValueError("Stop the active stream before changing debug speed")
    # Clock configuration belongs to the probe, not the attached MCU. V3 may
    # omit the optional profile line while its target scanner has no IDCODE.
    # Accept its exact setting acknowledgement for every supported clock;
    # retain profile_confirmed separately from the accepted setting.
    bridge._ctx.swd_clock_hz = 0
    response = bridge.send_command(f"cmd.set_swd_clock({hz})")
    lines = response.splitlines() if isinstance(response, str) else []
    match = re.search(r"(?m)^(SWD|JTAG) profile=(\d+)\b", response if isinstance(response, str) else "")
    interface = match.group(1) if match else "unknown"
    rejected = any(line.strip() == '-1' or line.strip().lower().startswith('error') for line in lines)
    confirmed = bool(match and int(match.group(2)) == hz and not rejected)
    accepted = match is None and not rejected and any(line.strip() == f"set clock {hz}" for line in lines)
    if not confirmed and not accepted:
        # An explicit mismatch/rejection or missing setting ACK is still a
        # failure. Never treat the command echo or diagnostic counters as ACK.
        # HPM's generic C JTAG shifter uses a fixed delay. A legacy 1 MHz
        # setting ACK (JTAG profile=0) does not establish a 1 MHz TCK. Only
        # restore a named JTAG kernel, and require its explicit profile ACK.
        jtag = interface == 'JTAG' or (interface == 'unknown' and getattr(bridge, 'idcode', None) == 0x1000563D)
        fallback_hz = 4_000_000 if jtag else 1_000_000
        fallback = bridge.send_command(f"cmd.set_swd_clock({fallback_hz})")
        fallback_lines = fallback.splitlines() if isinstance(fallback, str) else []
        fallback_ok = any(line.strip() == f"set clock {fallback_hz}" for line in fallback_lines)
        fallback_ok = fallback_ok and not any(line.strip() == '-1' or line.strip().lower().startswith('error') for line in fallback_lines)
        if jtag:
            fallback_ok = fallback_ok and bool(re.search(r"(?m)^JTAG profile=4000000\b", fallback if isinstance(fallback, str) else ''))
        if not fallback_ok:
            bridge._ctx.swd_clock_hz = 0
            raise ValueError(f"Probe firmware did not confirm {interface} profile or fallback clock")
        bridge._ctx.swd_clock_hz = fallback_hz
        raise ClockProfileUnavailable(f"Probe firmware does not confirm this {interface} profile; restored {fallback_hz // 1_000_000} MHz")
    bridge._ctx.swd_clock_hz = hz
    return {"profile": profile, "clock_hz": hz, "profile_confirmed": confirmed,
            "interface": interface,
            "qualification": f"{interface} profile confirmed; exact target and board stability not identified by IDCODE" if confirmed else "Probe accepted clock setting; target timing not verified"}

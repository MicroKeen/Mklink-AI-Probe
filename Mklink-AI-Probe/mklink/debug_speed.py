"""Named debug clock profiles shared by SDK, CLI, MCP and Web."""
from __future__ import annotations

PROFILES = {"low": 4_000_000, "medium": 10_000_000, "high": 20_000_000}


def profile_clock(profile: str) -> int:
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError("debug speed must be low (4 MHz), medium (10 MHz), or high (20 MHz)")
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
    # 20 MHz is qualified only on this target and the new three-profile probe
    # firmware. ARM's existing SWD delay calibration is not a 20 MHz guarantee.
    hpm = bridge.idcode == 0x1000563D
    if not hpm and profile == "high":
        raise ValueError("20 MHz currently requires HPM5301; ARM high speed awaits hardware qualification")
    response = bridge.send_command(f"cmd.set_swd_clock({hz})")
    confirmed = False
    if hpm:
        match = re.search(r"JTAG profile=(\d+)\b", response)
        confirmed = bool(match and int(match.group(1)) == hz)
        legacy = match is None and profile != "high" and f"set clock {hz}" in response
        if not confirmed and not legacy:
            # The command completed but this firmware lacks the exact timing
            # kernel. Restore a conservative clock, never label fallback as high.
            bridge.send_command("cmd.set_swd_clock(1000000)")
            bridge._ctx.swd_clock_hz = 1_000_000
            raise ValueError("Probe firmware does not confirm this JTAG profile; restored 1 MHz")
    bridge._ctx.swd_clock_hz = hz
    return {"profile": profile, "clock_hz": hz, "profile_confirmed": confirmed,
            "interface": "JTAG" if hpm else "SWD",
            "qualification": "HPM5301" if confirmed else "legacy timing not hardware-qualified"}

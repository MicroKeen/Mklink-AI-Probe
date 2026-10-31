# Independent SWD/JTAG clock configuration — 2026-10-31

Source changes: `edca358c` (configuration split) and `7c6c5c99` (negotiated
JTAG clocks). This is source and isolated-SDK qualification, not an installation
or hardware qualification. Windows remains product source `76d669de`; the full
Skill and all previously delivered SDK candidates remain unchanged.

## Behavior

- Configuration → Local Device now has SWD/JTAG and frequency dropdowns.
  `swd_clock` and `jtag_clock` persist separately, with a 10 MHz default.
  `clock_interface` remembers which configuration is being edited. On the first
  split, preserve the previous shared request for both interfaces; subsequent
  edits cannot overwrite the other interface's frequency.
- Selecting a configuration sends no hardware command. The screen separately
  shows the cached actual interface. Matching connected clock changes require
  an exact interface/clock acknowledgement before saving; an inactive interface
  is only saved. Reconnection selects the saved frequency matching cached target
  identity. Unknown identity leaves USB connected with an actionable warning
  and applies neither independent clock. SDK flashing reads the matching setting.
- Firmware has no public safe `set_interface` command. This selector does not
  force SWD/JTAG switching. Identity/mode observations are cached, not proof of
  live wiring, physical TCK or IDE clock application. Status polling adds no
  hardware queries or enumeration.
- SWD's full 14-clock capability now works on declaring V4 firmware as well as
  V3. Unadvertised legacy firmware retains its prior options. Global SWD
  capabilities never unlock JTAG options.
- New JTAG firmware must declare both `JTAG_CLOCK_ACK=1` and the exact
  `JTAG_CLOCKS=1000,5000,10000,20000,50000,100000,200000,500000,1000000,2000000,5000000,10000000,20000000,30000000`
  to expose those 14 menu choices. Legacy JTAG keeps 4/10/20/30 MHz. Numeric
  4 MHz remains compatible on new firmware, without being offered in its menu.
- A new JTAG acknowledgement requires one exact `set clock N`, `JTAG profile=N`
  and `JTAG clock_state=applied` or `configured`. Old JTAG remains
  `acknowledged`, with no claimed applied frequency. Mixed, duplicate, malformed,
  missing, mismatched or error replies invalidate confirmation without a replay
  or modern-firmware fallback. SWD retains its own state contract. Active capture
  prevents applying a clock and is left running.

## Verification

- 383 targeted Python tests passed: independent persistence, migration,
  reconnect selection, unknown/mismatched interface rejection, all 14 clocks and
  states, old firmware, flash selection, shared admission and legacy ACK paths.
- 59 GUI tests passed; Vue TypeScript checks passed.
- Built production resources for an isolated ConfigView/Dashboard fixture in
  `F:/MKLink-Build/artifacts/clock-interfaces-20261031/dist`. Tracked `gui/dist`
  was not changed. Existing optional-esbuild resolution and fixture chunk-size /
  static-dynamic import warnings were reported; build completed successfully.
- Real IAB browser exercised production component bundles against the real
  clock/config HTTP routes with simulated probes: separate saved frequencies,
  refresh persistence, matching SWD application, legacy JTAG confirmation,
  new JTAG 14-clock menu and configured-but-not-applied state. No browser errors.
  Screenshots and JUnit reports are in the same local artifact directory.
  This fixture does not prove electrical timing or real target behavior.
- Temporary preview/backend processes and browser tabs were closed. No device,
  VCC, OTP, firmware, installed package or official asset was changed here.

## Fixed SDK for the firmware owner

The authorized firmware chat supplied the new contract and retains exclusive
hardware ownership for calibration. Its current firmware work is not declared
qualified by this report.

New immutable candidate:
`F:/MKLink-Build/artifacts/clock-interfaces-20261031/candidate-7843-7c6c5c99-jtag-multiclock-verified`.
ZIP: `source-7843-7c6c5c99-jtag-multiclock.zip`.
SHA256: `2148cdcc5dc40369206f143b57bc51691fcd2307406d2e6652de015c8387728a`.

It uses the [prior ACK candidate](hpm-jtag-clock-ack-20261031.md) as its immutable
base. Four clock-related files differ; 1,259 other files are byte-identical:

- `capture_clock.py` / `debug_speed.py`: new clock capability and ACK handling.
- `flash.py`: supply the connected bridge to clock validation.
- `remote/api.py`: add strict `clock_hz` as an alternative to the existing named
  profile and preserve captures while rejecting busy clock changes.

Device, MUX, Watch timing/stats and all capture paths remain the fixed base.
The candidate excludes the product's independent GUI configuration change.
The export script records its exact overlays; its README gives the isolated
launch instructions and preserves global physical locks.

```python
result = client.call('set_debug_speed', {'clock_hz': 2000000, 'save': False})
```

794 tests passed using actual candidate imports, covering old/new clock handling
and the existing capture/timing/statistics/security suite. All loaded `mklink`
module paths were checked against candidate source. Candidate source/ZIP and
the prior delivered candidate were hash-verified before/after tests. One existing
anyio pre-import assertion-rewrite warning was reported. The old Device flash
test is pinned to `a8aa8a16` because GUI configuration changes are deliberately
excluded from this candidate. There is no hardware-pass claim.

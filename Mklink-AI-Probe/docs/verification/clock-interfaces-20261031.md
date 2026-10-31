# Independent SWD/JTAG clock configuration — 2026-10-31

Source changes: `edca358c` (configuration split) and `7c6c5c99` (negotiated
JTAG clocks). Host verification covers source and isolated SDKs; subsequent
firmware-owner hardware evidence is recorded below. Windows remains product source `76d669de`; the full
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

## First-use capability correction

The firmware owner subsequently reported a real first-use failure on candidate1
firmware with both new JTAG declarations. In the unchanged `7c6c5c99` SDK,
`RuntimeClient.connect → probe_version → probe_idcode → set_debug_speed(10 MHz)`
rejected the new JTAG state because the command bridge's capability cache was
still `None`. The failed matrix contains zero completed rows; it is retained as
failure evidence. The preceding 794 offline passes did not cover this cold-cache
path and do not qualify that candidate for first-use hardware success.

Code inspection confirmed that `runtime_probe._query` can reuse the connected
bridge but returns raw version text without filling its capability cache. The
fixed SDK's older Device connection path also lacks the product's eager capability
read. Reading memory/MUX first could mask the bug and is not the required workflow.

Source `bd636750` prepares capabilities on the actual command bridge before
frequency validation or a first clock write. It queries only when the cache is
`None` and the bridge is READY, then reuses the cache. Numeric, named and direct
Flash clock paths are covered, as are the product Device validation paths.
Busy capture or a failed/unrecognized version query sends no clock write.
Passive status polling stays cached and adds no device enumeration or queries.
Existing clock-write ACK validation, invalidation and no-replay behavior remain.

408 affected source tests passed. The separate immutable correction candidate is
`F:/MKLink-Build/artifacts/clock-first-use-20261031/candidate-7843-bd636750-clock-first-use-verified`.
ZIP: `source-7843-bd636750-clock-first-use.zip`.
SHA256: `2058e1ca87a268beda66479eadf2d066b5420e287e88b9d71179c07e6357b360`.
Only `capture_clock.py`, `debug_speed.py` and the `flash.set_swd_clock` method
differ from the prior 7c6 candidate; 1,260 files including Device, runtime API,
MUX, Watch timing and statistics are byte-identical.

813 tests passed with actual correction-candidate imports, including cold-cache
numeric/named/Flash/shared changes, raw-version-before-clock, cache reuse, legacy
version formats, query failures and busy-stream preservation. All loaded mklink
module paths and old/new source/ZIP hashes were verified. The firmware owner
received the new candidate for a fresh-backend test without memory/MUX warmup.
Hardware confirmation remains pending; no installed package or previous candidate
was modified by this correction.

## Subsequent limited hardware confirmation

The firmware owner reported a fresh-backend run using the bd636750 SDK:
connect → raw probe_version → probe_idcode → first set_debug_speed(10 MHz),
without a preceding read_memory/MUX warmup. The first reply is JTAG `applied`.
The host independently inspected its `candidate3-clocks.json` report,
SHA256 `db71d1aa700adb3756a64bb024d7bfbcec86f8715edb1371d32a2c599f4b792d`:
`passed=true`, 15 completed rows covering all 14 advertised frequencies plus
compatibility 4 MHz, matching requested/configured/applied values, and every
write's `verified=true`. The owner confirms known-RAM read/write comparisons.
The report ends with 10 MHz restored and a confirmed device close; ownership of
the continuing hardware investigation remains with that firmware chat.

This closes the reported first-clock capability-cache failure for that tested
setup. It does not complete electrical calibration or general firmware release
qualification. The owner reports roughly correct 10/20/30 MHz continuous shifting
on private JTAG and CMSIS-DAP, with independent IDE/acquisition clock contexts,
but continues frequency tuning and has found a compatibility-4-MHz throughput
regression in the low-clock generic path. That regression remains open; no
regressing firmware is accepted for delivery here. The host did not independently
operate the logic analyzer, inspect all waveforms or perform target writes.

## Candidate9 calibration and independent-stream results

The firmware owner subsequently installed HPMLink V4.7.2, build
`Oct 31 2026 17:41:04`, while continuing to use the immutable bd636750 SDK.
The host independently hashed its local `probe-candidates/candidate9/HPMLink.uf2`:
`ebbc11f2d429e815e6c1a2b67ac1a53c821b17af89aed38ab29677be1f7ecec0`, matching the
owner's reported final candidate. This is not a public firmware release.

Completed `qualified-*` reports were inspected read-only:

| Evidence | Checked result |
| --- | --- |
| `qualified-clocks.json` | Passed, 15 rows (14 advertised clocks + compatibility 4 MHz); each JTAG applied/configured/requested value matches, each RAM write reports verified; first 10 MHz clock also applied. |
| `qualified-dap-physical.json` | Passed, 15 rows, exit code 0; the owner reports all corresponding CMSIS-DAP reads passed. |
| `qualified-clocks-decoded.json` | All 14 advertised clocks present; maximum absolute continuous-shift frequency error 0.548608%. Compatibility 4 MHz measures 4.000176 MHz separately. |
| `qualified-dap-physical-decoded.json` | All 14 advertised clocks present; maximum absolute error 0.581625%. Compatibility 4 MHz measures 4.081396 MHz (+2.034909%), outside the new menu. |
| `qualified-rtt30-final.json` | Two 10 MiB runs, 1024/2048-byte chunks; both complete-byte sequences verified. Target-timed rates 647.818/646.793 KiB/s; host-timed rates 646.372/645.404 KiB/s. |
| `qualified-systemview.json` | Passed, 63.117 seconds, 13 stored status samples, up to 852991 events; sampled target-overflow, parser/transport loss and event-gap counters all zero. |

The decoded frequency window is DMI bits 2..29, using intervals within ±10% of
nominal for frequency calculation and counting interruptions separately. Maximum
reported stretched-interval counts are 60 (application) / 14 (DAP). These results
qualify continuous shifting frequency, not every edge interval, total bus
throughput, or a uniform acquisition period. The host checked the decoded reports,
not a second independent waveform decoding or a new physical measurement.

Report SHA256 values, in table order:

```text
5a0f160aee0fc0f257d99669a947689fae2cf4ee8fdb1119df261d020e37fa56
727635dd3833a68244579dc581be86f044ac5596e6c7ddf4d9050ff827e5e73a
e17a38a7aa963262c95f04554664899724c45aa32d717810dc8790b4e24291aa
48cb99e1028a816897cf26373936322fd8a8a63bc9a45d981a9545935e1272c9
2a7f95f3810db2eaf2ebdec9b98e1e5b1a41b3da9439a39fc47a2c0d05634375
1e37876bcc54ca06dd5d48a58fb2b3861016e4ade4cf932a77a51ec689cc31b5
```

The owner reports the earlier compatibility-4-MHz throughput regression resolved
(about +1% over baseline), with 10 MHz +6.5–7.5%, 20 MHz +4.2–5.1%, and 30 MHz
−0.06–+0.33%. `qualified-bench.json` is passed with 24 rows; these comparative
percentages remain the owner's analysis. The reported RTT regression was resolved
by placing DMI/SBA control functions in ILM; the completed RTT data checks above
are corroborating evidence for this tested configuration.

At that checkpoint, application 30 MHz + DAP 20 MHz concurrent operation and final
1 ms / 0.5 ms sampling regressions were still running. The then-inspected
`qualified-parallel.json` was incomplete (`passed=false`, no final error), rather
than a completed failure or success. The final results below supersede that
pending status; previous candidates and failure evidence remain unchanged.

## Final HPM5301 qualification and hardware release

The firmware owner completed the remaining HPM5301 matrix with the same bd636750
SDK and V4.7.2 build `Oct 31 2026 17:41:04`. The archived
`HPMLink-V4.7.2-jtag-clock-20261031/HPMLink.uf2` hashes to
`ebbc11f2d429e815e6c1a2b67ac1a53c821b17af89aed38ab29677be1f7ecec0`, independently
checked against its README, manifest and prior candidate. The host inspected the
following final reports read-only; physical tests were performed by the firmware
owner, without host-side probe use or additional measurements.

| Report | Checked result |
| --- | --- |
| `qualified-parallel.json` | Passed. Owner reports application 30 MHz + DAP 20 MHz concurrency; 50 DAP reads of 64 bytes, write/restore, halt/step/resume and hardware breakpoint set/list/hit/clear. RTT/SV/Watch coexistence, pause/resume, stop/rejoin and startup ordering checked; 367616 RTT bytes passed full sequence verification. |
| `qualified-period.json` | Passed. Both requested periods recorded for over 60 seconds, with raw sample captures summarized below. Parser loss, firmware read/CRC errors and sample-drop flags were zero. |
| `qualified-postflight.json` | Passed. Image hash matches the test image, load/SV flags are zero, RTT/SystemView/SuperWatch are stopped, target tick advances (507472 → 507582), JTAG is restored to 10 MHz and device close is confirmed. Owner also reports RAM restoration. |

| Requested period | Recording elapsed | Raw samples | Mean | P99 | Maximum | Gaps > 1.5 periods |
| --- | --- | --- | --- | --- | --- | --- |
| 1 ms | 60.127 s | 30091 | 1000 µs | 1000 µs | 1012 µs | 0 |
| 0.5 ms | 60.142 s | 30046 | 500 µs | 507 µs | 530 µs | 0 |

Raw captures cover approximately 30 and 15 seconds respectively within the
longer recording runs; sample statistics do not represent every sample in the
full 60-second recording. Report SHA256 values, in report-table order:

```text
ae7f24f57cdaefc8a491d1d2a79d5be87657ce568746b6e19124491d67f02d55
0c4ba9aca4abff0b26ffbcab311939c680ce72a1f1c5290ec0a9c550f4f9bc5b
1b05a1cff4f5cfd64effe414367c83b5244d0a3266e881168f4270e0ebd13d29
```

The first postflight assertion incorrectly expected a compile date in
`get_version`; the owner corrected that check to use the USB README and retained
the original internal failure. No firmware change was made for that correction.

This closes the remaining reported gates for this HPM5301 setup, and the firmware
owner has released the hardware. It does not establish qualification on other
MCUs; in particular, no STM32H7 physical retest was performed in this round.
Installed Windows source 76d669de, full Skill, official release assets and older
candidates remain unchanged. Source and verification updates do not constitute a
new installation, firmware publication or authorization to publish.

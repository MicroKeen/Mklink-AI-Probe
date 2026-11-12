# SystemView restart metadata and timeline inspection

## Findings and changes

The reported loss of every task name on later starts was not reproduced on the
available ordinary V4 / STM32F103RC / RT-Thread board. Three baseline starts and
three more with an RTT observer all returned nine names. Source and browser
inspection did establish related defects:

- A shared RTT observer can keep the target recorder active. Starting another
  SystemView consumer then does not resend target START/INIT. Each new consumer
  now requests system description (including INIT) and then TASKLIST, with a
  drain between metadata bursts. Unknown writes are not retried.
- The partial-name fallback stopped after receiving any name. MUX sessions now
  allow bounded, validated RT-Thread RAM resolution of remaining IDs without
  stopping the recorder; legacy transport keeps its existing safeguard.
- Zero RAM base or ID shift was replaced with Cortex defaults. Explicit zero
  values now survive project/profile defaults and dashboard parser creation.
- The GUI always started CH1, even after attaching to a CH2 capture. This was
  reproduced on the physical board: a GUI restart produced no task contexts.
  The shared status now reports the selected channel; the GUI displays it,
  adopts it when attaching, and preserves it for restart and remount. Users can
  explicitly choose CH0–CH7 before starting, matching CLI/SDK/MCP parameters.
- The canvas blocked explicit redraws while display was paused, and wheel zoom
  re-enabled follow mode. Pause now permits zoom/pan inspection, with bounded
  Worker requests and no acquisition pause. New Zoom In/Out buttons supplement
  Ctrl/Command + wheel. Zoom resolution is one timestamp tick instead of a
  fraction of accumulated history; manual history ranges remain selected.

No reset, target flash or power change is part of these fixes. The source Skill
reference documents channel selection and the shared metadata refresh behavior.

## Software verification

Windows PowerShell 7, UTF-8, Python 3.14, Node 26. Commands run through
`scripts/build_workspace.ps1` with the designated external build root.

- Related SystemView, RTT, shared-runtime/device, sleep and compatibility tests:
  651 passed after zero-encoding changes. Final channel/status regression:
  30 passed (overlapping coverage).
- GUI full suite: all 1,226 tests passed after channel changes. Focused
  channel/settings run passed 38 tests (overlapping coverage).
- Final TypeScript/Vite production build passed, including the small final
  channel-selector layout adjustment. All 43 built Web files match the committed
  production files. CI now includes the metadata, defaults and zoom regressions.
- Code commit `54e03336` passed [shared runtime and GUI CI](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43252607177)
  and [feedback checks](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43252607145).

## Hardware and real browser

Probe: ordinary V4, V4.7.4 / 2026-11-10 13:55:55. Target: STM32F103RC,
RT-Thread, 72 MHz timestamp clock, SystemView RTT CH2. The ELF SHA-256 was
`3a63715eaad61949bebc90fdf03175b08f80e008912c9cc6127f11f337694f77`.
Each scripted attachment verified 117,760 flash bytes against its ELF segments.

After the metadata fix, five roughly five-second restarts with RTT CH0/CH2
still active returned all nine names. Event counts were 79,786 / 80,376 / 78,993 /
75,762 / 75,517. Reported target overflow and MUX event gaps/dropped bytes were
zero. Parser alignment discard bytes were 17 / 26 / 21 / 24 / 34; the baseline
also had nonzero discards. These figures do not establish lossless decoding or
a complete throughput comparison.

The real production browser showed named task lanes. Paused zoom narrowed a
10-second window to approximately 19 microseconds, remained near the selected
historical time, and supported dragging and zooming back out while collection
continued. This run also exposed the CH2-to-CH1 GUI restart defect described
above. After its correction, the browser adopted CH2, restarted with nine task
names, and retained CH2 after a full page reload and another successful start.
The final layout and paused zoom were also checked in the production page.

## Windows overwrite installation, 2026-11-12/13

Source commit: `54e03336d19993e2ef817b38e589d8fecd85660e`. The standard NSIS was
built with the maintainer builder's `--local-bundle`, without updater signing.
It replaced the previously installed `c66523b8` candidate and therefore also
includes the earlier firmware capability guidance fixes.

| Candidate | SHA-256 |
| --- | --- |
| `MKLink-0.4.3-54e03336-current-user-x64.exe` | `5ddb2a9b4045112a76f8befcd0afcc375a3bd7530c3ec577a88bd6ed055047e2` |
| `MKLink-Skill-0.4.3-54e03336.zip` | `1fc25456cc8c58b80a507f797a11f80f2cb1a31851015c6a349eb778459d1ce2` |

- Extracted NSIS payload passed frozen CLI and actual stdio MCP checks before
  overwrite. The installer and uninstaller request `asInvoker`; the actual
  installer and desktop process tokens were medium integrity (RID 8192).
- Silent overwrite exited 0. All 3,676 installed payload files matched,
  including the complete `_internal` tree. Six existing configuration files,
  USB port names and existing machine registration remained unchanged.
- Installed CLI and actual MCP initialization/58 tools, `inspect_mcu`,
  `security_status`, and STM32F407VE peripheral lookup passed with Windows-only
  PATH. Validated assets contain 7,059 FLM targets/2,224 blobs and 4,800 SVD
  targets. Skill and installed FLM, Pack and Web resources match byte-for-byte.
- Native desktop `/api/health` returned `ok`, probe enumeration returned one
  device, and its process tree used the frozen sidecar with no Python process.
  The installed production Web page displayed nine names on CH2 and zoomed
  while paused. The native app closed normally; app/sidecar processes and both
  test listener ports were absent afterward.
- Installed-sidecar flash reads again matched all 117,760 ELF bytes. Three
  five-second CH2 starts returned nine names each: 75,435 / 75,259 / 75,294
  events, with 31 / 28 / 12 parser discard bytes. The isolated installed-app
  workspace used a 30 MHz probe clock; these results are correctness checks,
  not a same-clock performance comparison with the 10 MHz source harness.

Candidate files and local test evidence are retained under
`F:/MKLink-Build/artifacts/v050-systemview-20261112`. The installation remains
versioned 0.4.3 as a local development candidate; Windows binaries are unsigned
and may show an unknown-publisher warning. No release/update index was changed.

## Limits

The customer's exact target/RTOS and stream are not yet available. No HPM or
FreeRTOS physical reproduction has been claimed. Parser alignment discards were
present before and after the fix. Occasional implausible ISR/runtime intervals
observed in the long GUI run have not been attributed to a cause; they need
separate raw-stream investigation. The repeat-start harness retained status
snapshots, not a complete raw event stream, so it cannot settle this timing
question. This task does not certify all SystemView timing statistics.
Full hardware performance, external CMSIS-DAP
coexistence and other platforms were not requalified by these focused tests.

This is development work on `codex/v0.5.0-fixes` / PR #79, not a formal release.

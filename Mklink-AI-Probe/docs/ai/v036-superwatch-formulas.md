# 0.3.6 SuperWatch file lifetime and curve settings

Source: `870471b6` on `codex/hpm-isp-deployment-ux`.
Local integration: `e7c49b04`; production Web: `bcdc8474`.

## Behavior

- AXF/ELF loading and explicit reload work without an attached probe. They stop target capture workers before rebinding symbols and leave capture stopped. A worker that fails to exit blocks parsing; failed parsing retains the prior catalog and selection.
- Disconnect retains the file/catalog and selected program variables, including array snapshot selection. It clears acquired samples and retires transport/session state. Reconnecting without a new file prioritizes the current offline file over older connection history.
- Each selected signal has a curve-settings button for a formula and color. `x` is its raw numeric sample; blank means identity. Bounded arithmetic supports parentheses, powers, constants and a small math-function allowlist. No JavaScript evaluation or object access. Invalid expressions are rejected; nonfinite results display a dash.
- Raw values remain in transport/history/export. Curve rendering, Y-axis fitting and min/max decimation use the converted result; hover displays raw and calculated values. Replay shares the parser and transformation-aware extrema selection.
- Detached groups have merge buttons in the selected-signal panel and on the plot. Formula and color use the existing revision-checked project workspace preferences.
- Short Chinese/English 0.3.6 version notes added. No probe firmware changes.

## Verification

- 188 focused Python tests passed: offline loading, no probe discovery during file loading, stop-before-parse for three routes, failed-stop and failed-parse behavior, selection retention, source reload and runtime/session gates.
- Full GUI suite: 99 files / 1083 tests passed. Final display/refinement checks: 8 files / 189 tests passed. TypeScript and Vite production builds passed.
- The first full GUI run caught an optional-argument regression and an existing navigation assertion inconsistent with the intended Online-before-Offline order. Both were corrected; the complete rerun passed without unhandled errors.
- Real Chromium against an isolated source backend: offline ELF parsed 1480 variables; selected a variable while disconnected; saved `x / 1000` and `#00aaff`; reloaded page and retained preferences; split and merged the plot through its shortcut. A local CSV with raw 0..5000 rendered as 0..5 with the converted Y range and selected color. Screenshots stay in the local build artifacts.
- NSIS built with verified builtin FLM (7059 targets/2224 blobs) and Pack payloads. Extracted qualification passed with Windows-only PATH: 206 Python files, 41 Web files and shared formula/replay modules match source; real frozen MCP/CLI/SVD/HTTP; offline ELF loading, selection and formula/color persistence; combined HEX geometry regression; no host Python child; clean shutdown.

## Local package

`v036-watch-formulas-e7c49b04/Mklink-AI-Probe-0.3.6-local-e7c49b04-Setup.exe` under the configured build artifacts root.

SHA-256: `818035c005e02978b0729facd7cafcfba91babc659aa209e6bbc6409495b202b`.

Unsigned local candidate; no channel, tag or release update. The first elevation prompt was cancelled before installation. The user requested retry; the second overwrite completed with exit code 0. Installed payloads and the frozen checks above all passed again. Native WebView startup and production Web loading passed, and the owned native window/backend exited normally with ports released. The global Skill was not changed.

## Limits

No physical capture, reset, Flash, OTP or power operation was performed for this change. Hardware protocol behavior remains covered by previous evidence and regression tests, not newly certified across V2/V3/V4 or ARM/HPM. Formula conversion changes visualization only and does not write target memory. The current package does not alter the global Skill installation.

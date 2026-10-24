# 0.3.6 readable USART ISP failures

Verified on Windows 11 on 2026-10-21. Implementation `2506e93c`, production Web `9b056ed1`, compact-footer test correction `a8250c25`, on PR [48](https://github.com/MicroKeen/Mklink-AI-Probe/pull/48). Local combined installer source `9c80b12a8690369f7c2c89a0cbcb79a9e377f2f9`, assets `1b6661df`; combined branch also retains the serial-lock fix from PR49 and prior RTT/SuperWatch fixes. No merge or publication was performed.

## Behavior

Generated scripts describe all existing firmware return codes (-1 through -12), including `USART ISP timeout` for -3 and `USART ISP Cancelled` for -8. Configuration errors use `USART ISP config:`. Unknown nonzero values produce `Unknown ISP error`. Success remains silent; errors do not retry, advance to programming after failed configuration, alter the return code, or change download arguments.

The running-output panel maps structured error codes and legacy numeric text to readable reasons. It accepts the new script output, known firmware timeout-stage text and recovery hints, while continuing to hide script echoes and protocol JSON. Structured machine results remain intact for success/failure matching. When CDC JSON omits a timeout stage, the UI displays a generic timeout rather than inventing the failed stage or progress percentage.

Updating the application changes future generated scripts. Existing SD scripts are not automatically rewritten and generally need regeneration/deployment to change LCD script output. The firmware chat separately patched the user's current SD script; this task did not write the physical SD card or operate target hardware.

## Validation

- 102 Python ISP tests passed. New executable-script tests cover all twelve codes plus an unknown code, in both configuration and programming, and success with no error output (27 additions). They verify preserved return values, no retries and bounded script line lengths. These run under CPython with fake `hpm`, not on the embedded interpreter.
- 72 ISP/output GUI tests passed. An expanded run including App and version popover passed 90 tests (overlapping, not additive).
- GitHub GUI CI exposed a stale pre-existing App test expecting the removed build-hash prop. Its initial failed assertion left the mounted wrapper alive and caused two further polling-count failures. The test now checks the requested compact version props; local expanded tests passed. No product change was needed for this correction.
- Vue/TypeScript, frozen sidecar and standard NSIS production builds passed.
- Chrome exercised the actual host preview/deployment/trigger path using an isolated mock SD directory and simulated firmware. Timeout displayed `ISP: timeout`; cancellation displayed `ISP: Cancelled`. The output panel remained visible, excluded script/JSON, and neither result appeared as successful completion.
- Initial elevation was cancelled. After the user explicitly requested retry, administrator overwrite completed with exit code zero.
- Installed qualification with Windows-only PATH matched 199 Python sources, 40 Web assets and all four installed payloads. Frozen CLI/MCP/SVD/HTTP, healthy native window, Chrome `/dashboard`, no host Python and normal process/port/endpoint cleanup passed.

No firmware repository files were changed. No target flashing was performed. The local Windows installer is unsigned, without Authenticode or updater signature. Final PR checks are tracked on GitHub; this report does not claim merge/release qualification.

## Artifacts

- Installer: `F:/MKLink-Build/artifacts/v036-local-isp-9c80b12a/Mklink-AI-Probe-0.3.6-local-9c80b12a-Setup.exe`
- SHA-256: `5643727373f86486df353373220f766029a653ee2dde6c9114f6179361108319`
- The archive contains installation/installed/native qualification JSON and native screenshot.
- Browser fixture/evidence: `F:/MKLink-Build/reports/hpm-isp-errors-browser/`.
- Logs: `isp-error-python.log`, `isp-error-gui.log`, `isp-error-app-gui.log`, `isp-error-web-build.log`, `v036-isp-errors-build.log`, `isp-errors-installed-qualification.log` under `F:/MKLink-Build/reports/`.
- Test-link scratch `F:/MKLink-Build/runs/run-20261021-144112-483623e9` was retained by the workspace launcher for manual inspection, without forced deletion.

# 0.3.6 serial ownership cleanup

Verified on Windows 11 on 2026-10-21. Fix source: `dad4bf69`; PR [49](https://github.com/MicroKeen/Mklink-AI-Probe/pull/49). Local installer source: `b3878ee5c5a8fda954fc859c333e6a0438831e7e` on `codex/v036-isp-ux-local`, preserving the previously installed RTT, SuperWatch and ISP UI fixes. PRs 46 and 48 remain separate. No merge or public release was performed.

## Findings and changes

- A retained `serial_*.lock` file with PID zero is normal after release. OS file locking is authoritative; neither file existence nor runtime discovery alone proves a live owner.
- Direct bridge callers now clean up after failures anywhere in connection setup, including buffer resets, reader startup, writes and interruption.
- Once the serial worker has exited, a pipe-close failure no longer prevents closing the other pipes or releasing serial/HIL ownership. Failure to clear PID metadata also no longer strands the parent cleanup sequence.
- If worker exit remains unconfirmed, ownership stays held. Failed construction retains the transport for later cleanup; a connection retry cannot overwrite it with another worker. Cleanup handles the race where the worker exits just before termination.
- Lock-directory/file I/O failures are distinguished from lock contention. Persistent lock files are never deleted to bypass ownership; a live OS lock still blocks acquisition even when PID metadata is zero or absent.

## Verification

`scripts/build_workspace.ps1` ran 213 affected Python tests successfully: serial cleanup fault injection, isolated worker/loop transport, real cross-process serial and Modbus exclusion, normal/crash exit and HIL reacquisition, identity binding, shared device, runtime discovery/reconnect/idle/shutdown and transport recovery. Fifteen new fault regressions were added. Two existing serial mocks were corrected to set `is_open=False` when closed; the first broader run had six failures from those inaccurate mock states, and the final run passed all 213.

The source commit passed GitHub `feedback-contract`, `shared-gui-contract` and `shared-runtime-contract`. Production Vue/TypeScript, frozen sidecar and standard local NSIS builds succeeded. No new GUI source changes were needed.

Administrator overwrite installation completed with NSIS exit code zero. Qualification of the installed binaries, with only Windows directories on PATH, confirmed:

- 199 bundled Python source files, 40 Web assets and all four installed payloads match the archived package/source.
- Frozen CLI, real stdio MCP initialization/tools, bundled SVD queries, health, probe enumeration and served Web assets work without host Python.
- Installed native window and Chrome `/dashboard` display version 0.3.6 and a healthy backend.
- Normal closure leaves zero MKLink processes, zero listeners on the application ports and zero runtime endpoint files in the isolated qualification registry.

No target hardware was opened or flashed during qualification. Fault tests used isolated temporary locks and test subprocesses. This is not a reproduction on the reporting customer's computer, nor a claim about all driver/hardware failures. If a worker genuinely remains alive, refusing takeover is intentional. Windows package is unsigned (no Authenticode/updater signature) and is a local test build.

## Local artifacts

- Installer: `F:/MKLink-Build/artifacts/v036-local-isp-b3878ee5/Mklink-AI-Probe-0.3.6-local-b3878ee5-Setup.exe`
- SHA-256: `bc3b4c5ec4d37931b9397a60c3428f1a94d7be8eabfccd132dafd6af2e5779f7`
- Same archive directory contains manifest, installed qualification, native qualification, installer result, extracted payloads and native screenshot.
- Test/build logs: `F:/MKLink-Build/reports/serial-lock-cleanup-tests.log`, `v036-lock-cleanup-build.log`, `serial-lock-installed-qualification.log`.

The workspace launcher retained test-link directories for manual inspection, without forced deletion: `run-20261021-140927-ad8abd53`, `run-20261021-141021-31a386b7`, `run-20261021-141158-6fcfbe5a` under `F:/MKLink-Build/runs`. Earlier read-only audit runs also remain as documented locally.

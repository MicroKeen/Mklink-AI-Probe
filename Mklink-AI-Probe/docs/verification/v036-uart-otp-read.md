# HPM5301 UART OTP read-only and ISP round connection state

Host implementation `b5e4f7ea`, production assets `bb181a94`, PR [48](https://github.com/MicroKeen/Mklink-AI-Probe/pull/48). Windows verification on 2026-10-21. Local combined source `24d9d020` retains the installed RTT/SuperWatch changes and PR49 serial-lock corrections. This is a local candidate, not a release or merge.

## Behavior

The offline V4 USART ISP view exposes a collapsed HPM5301 read-only OTP panel, including the HPM5301XEGX alias. Reading does not require BIN files, SD deployment, or JTAG connection. It displays CHIP_ID, raw HARD_LOCK and user words 69 through 79. Shared table rendering is reused from JTAG. ROM reads do not establish fuse-versus-shadow origin or current lock state; unavailable fields remain unknown. No write, lock, arbitrary-address, reset or power controls are added.

The bound runtime route `/api/device/configuration/hpm-isp-otp/read` takes only a supported part and V4 model. It reserves all conflicting resources without preemption, rejects independent UART clients, and retains leases until the worker ends even after HTTP cancellation. The bridge checks firmware capability and executes one nonce-bound read. The parser rejects duplicate, stale, partial, malformed, mismatched-chip or mismatched-memory results, without retry or JTAG fallback. Switching target, protocol, probe or leaving the view clears the snapshot.

The host preserves the connected state after `cycle_done`; a subsequent firmware `disconnected` event changes it to waiting. The delegated firmware implements actual loss detection: maintain selected baud while waiting, require three timeouts before declaring loss, use 115200 for the next handshake, and then apply selected baud. Task completion, cancellation and errors release the session. A host display change alone does not prove this physical sequence.

## Host verification

- 221 Python tests passed across UART OTP, existing JTAG OTP, ISP offline and runtime UART coverage. Includes fixed read command/nonce validation, unsupported firmware, strict read-only request validation, no-SD/no-JTAG operation, existing-owner protection, cancellation lease lifetime and runtime identity/generation checks.
- 81 GUI tests passed across ISP output, shared JTAG OTP panel, UART OTP panel and offline view. Covers no-firmware read, stale-result invalidation, busy controls and retained connection until a disconnect event.
- TypeScript and Vite production build passed.
- Chrome exercised the production Web and actual host read route/parser with a simulated CDC bridge, no SD and no JTAG. The final firmware schema returned all eleven rows and unknown shadow/lock state, with zero console errors. Captured commands contained only the capability query and the fixed nonce read. This browser fixture is not physical hardware evidence.

## Installation and physical verification

The first elevation attempt was cancelled by Windows. After the user explicitly requested another attempt, administrator overwrite completed with exit code zero at 18:38:56 +08:00. Installed qualification under Windows-only PATH matched 201 Python sources, 40 Web files and all four installed payloads. Frozen CLI/MCP/SVD/HTTP, probe enumeration without target access, no host Python, and graceful test-backend exit passed.

The delegated firmware task upgraded its final candidate (UF2 SHA-256 `e81059d05ab7caac5b469ca14c71cd2556b4b63220b3ec4e552010544383188c`) and invoked the actual installed sidecar's OTP route through the shared backend. It returned all eleven words in about 0.6 seconds; device status was disconnected before and after, without a JTAG connection. The user-facing installed Web was then exercised in the in-app browser: choose HPM5301, V4 and USART ISP, expand the read-only panel and click Read OTP without adding BIN files. It displayed CHIP_ID `0x11705142`, raw HARD_LOCK and all eleven user values, with unknown shadow/lock state and no console errors. No OTP write, lock, reset, target Flash or voltage operation was performed by this host task.

The physical OTP operation succeeded; the multi-round disconnect/baud transitions are covered by firmware unit tests and host event tests, not a new physical board-swap acceptance run. Native WebView visual/normal-window-close qualification was not repeated in this run; the installed production Web and frozen backend were checked directly. After browser verification the shared test backend was disconnected/stopped normally: no remaining test process, endpoint or listener on 18788.

## Artifacts and limits

- Installer: `F:/MKLink-Build/artifacts/v036-local-isp-24d9d020/Mklink-AI-Probe-0.3.6-local-24d9d020-Setup.exe`.
- SHA-256: `7ae3f0163959eaf8d9aa3b9ee845f2e5d9c4497bfcf642954865ba92ebb5ae54`.
- Archive contains install result, extracted/installed qualification, production Web and hardware UI qualification records.
- Build/test logs: `v036-uart-otp-build.log`, `uart-otp-combined-python.log`, `uart-otp-combined-gui.log`, `uart-otp-extracted-qualification.log` and `uart-otp-installed-qualification.log` under the build reports directory.
- Test-link scratch `F:/MKLink-Build/runs/run-20261021-183315-ca55ce0f` was retained for manual inspection, without forced cleanup. Earlier OTP test runs `run-20261021-175418-9430d2f1`, `run-20261021-181201-708d0e16` and `run-20261021-181417-480cf3ff` were also retained.

The firmware owner separately verified the physical HPM5301 ROM read-memory protocol: OTP addresses use word indices while length uses bytes. ROM fuse-versus-shadow semantics remain unknown. No OTP write or lock operation is authorized or tested.

Local logs and fixtures reside under `F:/MKLink-Build/reports/`; firmware build and hardware evidence remain in the delegated firmware checkout. Windows local NSIS is unsigned, with no Authenticode or updater signature. No official tags, channels, public release or global Skill installation are changed.

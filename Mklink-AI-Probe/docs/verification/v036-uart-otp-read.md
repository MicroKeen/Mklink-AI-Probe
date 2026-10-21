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

## Evidence boundaries

The firmware owner separately verified the physical HPM5301 ROM read-memory protocol: OTP addresses use word indices while length uses bytes. The final firmware API and installed application end-to-end results are recorded separately below once completed. No OTP write or lock operation is authorized or tested.

Local logs and fixtures reside under `F:/MKLink-Build/reports/`; firmware build and hardware evidence remain in the delegated firmware checkout. Windows local NSIS is unsigned, with no Authenticode or updater signature. No official tags, channels, public release or global Skill installation are changed.

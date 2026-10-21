# HPM5301 UART OTP settings preflight — 2026-10-21

Host source `f2075267`, PR [48](https://github.com/MicroKeen/Mklink-AI-Probe/pull/48).
This implements configuration preview and guarded host integration. **Actual UART
OTP programming is not implemented in the current firmware or qualified on a
target.** The installed read-only host package is unchanged in this step.

## Implemented behavior

After reading, the UART panel accepts user Word 69–79 and a complete desired
32-bit value. It reuses JTAG value/range validation, rejects clearing existing
bits and no-op changes, and shows expected/current/desired values and added bits.
Preview sends commit=0. Unknown ROM read semantics or lock state produces a
specific unavailable reason, no write button and no server execution token.

The host also contains a future qualified-firmware execution path. Qualification
requires a matching chip, change, direct fuse semantics, known unlocked state,
and explicit firmware support. Only then may a server-owned, 60-second,
single-use token be created. The token binds the exact change, probe, port,
generation and part. Read/new preview invalidates prior tokens; target switches,
expiry, failed attempts and successful use prevent reuse. Execution requires
explicit irreversible confirmation, a fresh firmware preflight and an exact
verified result. No automatic retries, JTAG fallback, arbitrary addresses, lock
configuration, target reset or voltage changes are introduced.

All operations retain exclusive resource leases through worker completion,
including cancellation, and reject competing UART clients. UI inputs and stale
results are invalidated on the relevant selection changes. Actual programming
cannot currently pass the qualification gate, even via direct API calls.

## Verification

- 291 Python tests passed: UART OTP/API/plans, existing JTAG OTP, offline OTP,
  ISP generation and shared UART runtime. Includes no execution token for
  unqualified firmware, unchanged fuse requirement, bit/lock checks, expiry,
  binding, consumed tokens, incomplete response and no retry behavior.
- 84 GUI tests passed across UART/JTAG OTP panels, offline view and ISP output.
  TypeScript and Vite production builds passed. Existing chunk-size warnings
  remain.
- Chrome loaded the production assets and exercised real host routes/parsers
  with simulated CDC, without SD/BIN/JTAG. Read and preview displayed the
  expected values and unavailable reason. Editing desired value removed the
  preview; no write button appeared. Captured commands were only capability,
  read and commit=0 preflight. Final browser console had no errors, the server
  exited normally with no leases, and the test tab was closed.
- The first browser fixture omitted probe identity metadata, causing its disk
  status endpoint to raise KeyError. The fixture was corrected and the final
  production-asset check repeated successfully; this was not a product failure.
- The user confirmed the previously installed UART read feature works. The
  delegated firmware task then verified the developing **source** host API
  against its new physical candidate: read followed by Word69 expected0,
  desired1 preflight returned before0, qualified=false, write_supported=false,
  plan_id=null, expires_in=0. No program call was sent; JTAG remained disconnected.

Local logs: `uart-otp-settings-python.log`, `uart-otp-settings-gui.log`,
`uart-otp-settings-production.log` and browser fixture/command records under
`F:/MKLink-Build/reports`. Test scratch containing links was retained for manual
inspection, including `run-20261021-190534-4a9409ac`; no forced cleanup.

## Hardware blocker and next implementation

Firmware source [278b67c](https://github.com/Aladdin-Wang/MicroLink_Plus/commit/278b67c)
is in draft [PR9](https://github.com/Aladdin-Wang/MicroLink_Plus/pull/9), unmerged.
Its candidate UF2 SHA256 is
`0445f0fa8e3d206facfb7f6fceb7f7d96d2c68a145f639203c7acadc5542f935`.
The delegated task upgraded the probe and released its backend normally.

The tested ROM reports 128 KiB SRAM for system-memory reads. Fixed OTP fuse,
shadow and lock register reads all return invalid-memory-range status 1001001;
OTP memory reads continue to succeed. Consequently the current UART ROM path
cannot verify the write protection state or prove its OTP read source is fuse.
The firmware refuses commit and never issues a ROM OTP write.

See the firmware [contract](https://github.com/Aladdin-Wang/MicroLink_Plus/blob/278b67c/microlink_app/docs/hpm-uart-otp-user-contract.md)
and [hardware report](https://github.com/Aladdin-Wang/MicroLink_Plus/blob/278b67c/microlink_app/docs/verification/hpm-uart-otp-preflight-20261021.md).
Completion requires vendor evidence for ROM OTP provider/read/write/lock
semantics, or a new UART-loaded RAM helper with audited image/startup/UART
handoff, direct fuse/lock checks, atomic guarded programming and readback.
The existing JTAG OTP and SDK application examples are not qualified UART
load-image helpers. None was uploaded or executed during this task.

No target OTP, permanent lock or Flash was written, and no target voltage was
changed. There is no new installer, overwrite, public release or merge for this
preflight step; it must not be represented as completed OTP settings support.

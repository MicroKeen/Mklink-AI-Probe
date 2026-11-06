# S3 shared-runtime port: 2026-11-06 regression

Candidate branch: `codex/s3-main-regression`, based on fetched
`microkeen/main` `4f3be7a46651c305792eb0a45fa6f0cad5fd2669` (0.4.2).
This ports PR #65 and separates reusable transport policies from S3 framing.
It is not a release qualification or a claim that all transports pass.

## Software evidence

All checks used the same Python 3.11 test environment through
`scripts/build_workspace.ps1`. No installed runtime was replaced.

- 219 focused transport, acquisition, flash, security and S3 tests passed.
- Expanded affected-surface run: **1442 passed, 18 failed** (476.59 seconds).
  Coverage includes bridge/MUX, volume isolation, shared runtime, remote
  client/site/MCP/agent, capture ownership, real loopback WebSocket and dependency
  isolation. The focused tests are included in this count, not additional tests.
- All 18 failures reproduced on a separate, pristine `4f3be7a4` worktree in the
  same environment: 12 Windows symlink/abort-counterfactual tests lack symlink
  privilege; two MCP lifespan tests and one UART MCP result-shape test fail in
  the installed MCP environment; three shutdown tests compare wrapper and
  actual backend process IDs on Windows. These remain failures, not skips.
- Final documentation, project-memory and public-skill boundary checks:
  **79 passed** (including the ten remote documentation checks).

Private evidence is retained under the ignored build workspace: expanded run
`run-20261106-221245-2402a7ff.log`, pristine baseline
`run-20261106-222208-8027f89c.log`. Raw device data and credentials are not part
of this change.

## Hardware evidence

The user confirmed the original S3 → V4 → STM32F411 bench online. These runs
used candidate source in both the workbench and spawned backend/MCP processes,
with isolated per-process runtime/configuration directories. The installed
GUI/MCP runtime and computer Wi-Fi configuration were preserved.
Firmware observed: S3 `0.7.2-recovery1`, V4 `V4.7.2`; target Flash size 512 KiB.

| Check | Current result |
|---|---|
| HTTP local + remote shared target identity/Flash-prefix read | Passed; two clients, one backend; remote read survives workbench detach |
| Already-running stdio MCP discovers newly registered site | Passed over HTTP and BLE |
| MCP target identity through existing Site Agent | Passed over HTTP and BLE |
| RTT subscriber shares the same session after workbench detach | Passed over HTTP and BLE; actual target status text continues |
| Host RTT drops/missing batches in those short windows | Zero reported; not a sustained throughput qualification |
| BLE complete current Flash backup | 524288 bytes saved before any programming |
| BLE bounded memory sampling | 84 complete samples, zero parser drops/CRC errors/firmware read errors; 64 samples after warmup, approximately 100 Hz |
| BLE shared remote flash job | Current APP (475136 bytes at `0x0800C000`) written back once with verified FLM delivery and full APP verification; 291.30 seconds including upload/verification |
| Independent post-flash comparison | All 524288 Flash bytes match the pre-write backup, including Boot; option bytes unchanged; target not halted |
| HTTP continuous Flash backup | **Failed**: MUX epoch/session expired during a read; programming was never submitted |

The first RTT attempt lacked a trusted RAM profile and was rejected before
capture. A second asserted data before asynchronous startup completed and
observed empty data. The corrected harness supplied the STM32F411 profile and
waited for the actual control-block/streaming state before subscribing and
checking payload. Neither attempt was silently reclassified as a pass.

Immediate backend-stop requests after the last borrowed RTT subscriber detached
returned `409 capture_active`. The normal idle shutdown then completed and the
HTTP/BLE backend logs both show process termination. A subscriber's detach is
not permission to stop another client's capture.

The HTTP long-read failure occurred on opcode `0x16`, request 38; the last reply
was about 1.53 seconds earlier. An epoch mismatch does not establish whether
the cause is network delay, gateway behavior or probe firmware. No automatic
reconnect, command replay, local-USB fallback or timeout extension was used to
hide it. The gateway retained `outcome_unknown`; a subsequent BLE connection
correctly refused the unready probe. A separate explicit management recovery
proved fresh MUX HELLO/EXIT and probe identity, advanced the gateway generation,
then released its lease. It did not replay the failed target operation. The
subsequent BLE full backup and bounded sampling passed.

The BLE flash job journal records `succeeded`, `verified=true`, `replay=false`.
The harness initially asserted `success` on the outer result envelope instead
of its nested `result`, so it failed after the successful operation. The flash
was not resubmitted: a separate read-only run checked the saved job receipt and
compared every Flash byte with the original backup, then checked option bytes
and the CPU halt flag. Both complete-image SHA-256 values matched. Original
backups and unsuccessful harness reports remain private in the build workspace.
Final management status was `ready`, no owner, not busy, and no active stream;
the final verification backend also completed normal shutdown. The target
application remains the backed-up current application.

## Remaining qualification

HTTP long-read stability needs investigation before treating this candidate as
ready to merge. AP/C6, fresh GUI/native packaging, sustained throughput,
SystemView and physical USB regressions were not run for this candidate.
Historical October 28 results in `docs/ai/s3-shared-adapter.md` belong only to
the old PR #65 baseline and do not fill those gaps.

No S3/V4 firmware, voltage, protection or computer network settings were changed.

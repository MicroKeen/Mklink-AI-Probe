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

### Follow-up: repair the 18 baseline failures

The two MCP lifecycle failures exposed a product defect: the in-memory
FastMCP transport cancels its task group before exiting the server lifespan,
so cancellation interrupted the awaited detach. The shared MCP lifespan now
shields that cleanup with the existing AnyIO dependency. The original tests
verify that its session disappears while the other client's RTT keeps running,
and that rejected probe switching never submits an operation.

Three Windows shutdown tests now compare authenticated discovery/control PIDs
and verify that the same backend PID logs normal termination, instead of
assuming the venv launcher's PID equals the child interpreter's PID. Endpoint
removal, process exit and owner-lock release assertions are retained.

The UART test now checks raw MCP `structuredContent` for both list and object
results. FastMCP 2.14.7's convenience `.data` conversion for this union schema
produced empty model instances even though the wire payload retained the fields.
No UART response or public tool schema was changed.

The remaining 12 failures needed the Windows symlink prerequisite. With the
user's explicit permission, Developer Mode was enabled temporarily. All real
symlink and junction scenarios ran unchanged; none were skipped or replaced
with mocks. The fixture error now explains the prerequisite, and the maintainer
development guide documents it. MCP/shutdown/UART: 81 passed; upload-security:
62 passed. System-setting restoration and the expanded rerun are recorded below.

The same expanded selection then passed **1460 tests, zero failures/skips** in
412.54 seconds (`run-20261106-230552-91dd6702.log`). The original 18 failures
above remain historical evidence. After this run, the temporary Developer Mode
value was removed to restore its original absence, verified by a separate read;
the elevated helper exited. Future unprivileged Windows runs must still satisfy
the documented symlink prerequisite. The tests do not weaken that boundary.

## Hardware evidence

The user confirmed the original S3 → V4 → STM32F411 bench online. These runs
used candidate source in both the workbench and spawned backend/MCP processes,
with isolated per-process runtime/configuration directories. The installed
GUI/MCP runtime and computer Wi-Fi configuration were preserved.
Firmware observed: S3 `0.7.2-recovery1`, V4 `V4.7.2`; target Flash size 512 KiB.
Hardware evidence below belongs to `b192952b`, before the active shared-MCP
lifespan follow-up. That follow-up does not change the S3 transport, remote MCP
or flashing path; it is covered by the software lifecycle regressions above.

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

The original HTTP failure and the bounded follow-up below are both retained.
AP/C6, fresh GUI/native packaging, sustained throughput,
SystemView and physical USB regressions were not run for this candidate.
Historical October 28 results in `docs/ai/s3-shared-adapter.md` belong only to
the old PR #65 baseline and do not fill those gaps.

No S3/V4 firmware, voltage, protection or computer network settings were changed.

## Follow-up: HTTP long-read receive stalls

The original CRC-valid epoch mismatch is not a host command timeout. A read-only
control experiment reproduced the same error by holding delivery of one HTTP
read response for five seconds: the next native USB write followed the previous
one by 5.528 seconds, and V4 replied with a new epoch and status 3. S3's own
generation did not change. The original adapter also completed one unmodified
512 KiB read, so a successful run alone does not invalidate the initial failure.
The initial natural failure lacks the detailed timestamps needed to identify
its exact network trigger. No V4 firmware source was available.

The host fix reuses HTTP connections, honors negotiated stream lease renewal,
and uses S3's advertised independent pull sequence on a second HTTP connection.
The only native reader still parses bytes in order. The shared MUX can opt into
a bounded PING window while retaining one target-command slot: PING replies
have distinct request IDs, CRC/epoch/status checks and deadlines. A transport
timer services that window while its receive path waits. Ordinary USB, BLE and
non-advertising nodes retain the original scheduling. No target request is
replayed, and an invalid or missing reply still invalidates the session.

Read-only verification on the original S3/V4/STM32F411 bench:

| Case | Result |
|---|---|
| Original adapter, one natural 512 KiB read | Byte-for-byte match; 140.766 seconds including connect/close; maximum read RPC 3.812 seconds |
| HTTP pooling/lease optimization only | Byte-for-byte match; 48.172 seconds; this alone is not the stall fix |
| Complete fix, same 5-second delivery pause | Full 512 KiB match; epoch unchanged; 4 PINGs sent/acknowledged; maximum native USB write gap 1.146 seconds |
| Complete fix, three 10-second pauses before reading HTTP response bodies | Full 512 KiB match; epoch unchanged; 27 PINGs sent/acknowledged; maximum native USB write gap 1.209 seconds |
| Actual shared backend and authenticated Site Agent | Three consecutive 512 KiB reads matched the original backup; 22.031/23.047/24.641 seconds; two clients shared one backend and the remote client continued after workbench detach |
| Real stdio MCP over HTTP and BLE after the fix | Live site discovery, exact target identity, shared RTT payload and continued capture after workbench detach passed on both routes |

Expanded affected software regression: **1628 passed**, zero failures/skips,
401.76 seconds (`run-20261106-234509-63cd7530.log`). This selection adds capture,
diagnostic and RTT coverage; it does not rerun the unchanged symlink-dependent
remote review-repair suite from the earlier 1460-pass run. Developer Mode was
not re-enabled. Dependency deprecation warnings remain.
Final checks after the bounded-window test and documentation updates:
**103 passed** (24 focused HTTP/MUX cases and 79 documentation, memory and
public-skill boundary cases). These overlap the expanded run and are not an
additional independent 103-case qualification suite.

Both MCP runs initially rejected immediate backend stop with `409 capture_active`
after the borrowed subscriber detached, as required by shared capture ownership.
Normal idle shutdown completed and both backend logs confirm process exit.
The final independent USB management check reports ready, no owner, not busy,
and no active stream.

These wall times are bounded observations on one network, not controlled
throughput benchmarks. Delaying response consumption tests slow receiving;
it does not simulate loss of both network directions. USB timestamps describe
S3 write calls, not V4 execution time or a physical bus trace. A failed control
channel, stale epoch or exceeded deadline remains a fail-closed condition.

Private traces and original failures are retained under the ignored
`http-long-read-20261106` build workspace. No target Flash, firmware, voltage,
protection or PC network setting was changed for this fix. The explicit cleanup
after reproducing the old failure did not replay that command or resolve its
old outcome; subsequent fixed runs shut down normally.

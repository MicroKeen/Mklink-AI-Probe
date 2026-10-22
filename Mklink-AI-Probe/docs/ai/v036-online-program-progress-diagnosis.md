# Online programming 100% pause diagnosis

## Scope and result

2026-10-22: the user reported a several-second pause between PROGRAM 100% and
`program complete`. The installed task succeeded. Its event timestamps show a
6.660705 s interval between two 100% events; the final 100% to `program complete`
interval is approximately 0.011 ms. Event numbers alone do not identify the
underlying programming phase.

The user authorized exactly one repeat programming operation using the same
HEX and addresses on the connected STM32F103. A scratch diagnostic used the
source backend, the STM32F10x_512 FLM, 1 MHz SWD, halt connection and default
completion reset. The saved HEX was checked against the original task digest;
its payload is 113152 bytes at 0x08005000–0x08020A00 (exclusive end). Only its
covered Flash sectors were erased. Programming and full readback verification
passed. No OTP, option-byte or supply-voltage changes were made. This one-shot
authorization is consumed; do not automatically repeat it.

## Measured cause

The earlier inference that `UnInit` caused the multi-second pause was incorrect.
Both inspected default FLMs have a short, loop-free `UnInit`. The physical trace
measured its call plus interrupt-mask restoration at about 24 ms.

| Operation | Diagnostic elapsed time |
| --- | ---: |
| Explicit image-covered sector erase | 2.409 s |
| Internal repeated sector erase within `program()` | 2.270 s |
| Actual double-buffer programming, including cleanup | 5.585 s |
| `program()` total, including internal erase | 7.892 s |
| Full readback verification | 1.693 s |
| Completion reset | 0.119 s |

These are instrumented source-backend measurements, not performance numbers for
a corrected installation. The original installed task's 6.66 s and this run's
5.59 s are separate observations, not a before/after improvement claim.

The installed dependency range is pyOCD 0.44.x. Its `MemoryLoader.commit()` runs
two loops: all builders' `erase()`, then all builders' `program()`. Both send a
0→1 sequence through the same progress callback. The MKLink backend passes this
callback directly to `FileProgrammer`. Thus internal erase completion is emitted
as PROGRAM 100%. `JobManager.report_program_progress()` records 100 as its maximum
and suppresses subsequent values below it. Actual page programming continues,
but its 0→99% events disappear. The apparent pause is primarily hidden real
programming, not a long algorithm exit or UI polling delay.

There is also genuine redundant work: `JobManager` first calls `erase_sectors()`,
then `FileProgrammer.commit()` erases the same covered sectors again. With custom
FLMs, smart flash is explicitly disabled, so the second erase is not skipped.

## Proposed correction, not implemented

- Give erase and program callbacks explicit phase ownership. Do not infer phases
  from a numerical regression in progress; sparse/multiple-region plans must
  also work. Reserve PROGRAM 100% for completed programming.
- Arrange exactly one image-covered sector erase. Preserve coverage validation,
  sparse-image behavior, standalone erase/program backend contracts, failure
  handling and the prohibition on escalating to whole-chip erase.
- Deduplicate repeated completion notifications, while retaining algorithm
  cleanup and full verification. Do not remove `UnInit` or shorten its timeout
  to mask this issue.
- Add a regression reproducing erase 0→1 followed by program 0→1, plus multi-bank
  and failure cases, then verify the corrected installed task on hardware with
  appropriate authorization.

No product code, firmware or installer was changed during the initial diagnosis.
The diagnostic backend released the probe. The installed runtime was explicitly
rebound to the same device; connection, RTT channels and SuperWatch were restored
and confirmed running, with zero Watch read errors in the restoration check.
Raw traces, original image and hardware identities remain in ignored local
build storage and are not committed.

## Authorized correction and hardware verification

The subsequent request to fix the problem is implemented in `35f7da59`.
The backend remembers only successfully erased sector ranges on its current
connection. A program operation consumes this evidence once and bypasses the
loader's erase loop only if every padded programming page is covered. Reset,
security operations, erase attempts, disconnect and failures invalidate it.
Standalone program still erases sectors. The phase adapter retains pyOCD page
programming, cleanup, Pack completion sequences and multi-region aggregation;
erase callbacks cannot reach PROGRAM progress, and final 100% follows cleanup.
The job manager suppresses duplicate PROGRAM completion events.

391 tests passed, including real pyOCD loader/builder/eraser tests with simulated
target I/O: single/double buffering, standalone and pre-erased programming,
sparse two-bank HEX, exact sector selection, repeated operations, failed erase,
page or cleanup failure, and whole-page coverage. These tests are not hardware
evidence.

The user separately authorized one more identical HEX burn after the correction.
The actual source `OnlineFlashJobManager` and backend completed that single run,
including full readback and the original completion reset. The trace shows:

- Explicit sector erase: 2.360 s; no internal erase during `program()`.
- Program stage: 5.595 s, compared with the earlier instrumented 7.892 s.
- Verify: 1.686 s; complete job: 11.54 s.
- PROGRAM 100% appears once; `program complete` follows 0.796 ms later.
- Intermediate PROGRAM progress continues throughout actual page programming.

This second burn authorization is consumed. No OTP, option-byte or supply
changes occurred. The installed GUI connection was restored; RTT and SuperWatch
were left stopped as the user had stopped them before this run. The installed
application still needs the corrected package; this source hardware result is
not an installed-build validation.

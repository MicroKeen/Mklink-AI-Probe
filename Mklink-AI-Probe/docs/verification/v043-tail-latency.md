# Read latency tails — 2026-11-03

Stable sub-millisecond public reads remain **unachieved**. This investigation
extends [phase 2](v043-memory-latency.md), using the same source checkout at
`5d8193ca`, ordinary V4/V4.7.2, H743 and applied 10 MHz SWD. It focuses on P95,
maximum and 300 ms-spaced reads, rather than accepting a faster median.
No firmware, product version, installed application or global Skill changed.

## Measurement boundaries

Each sample times one public `SharedDevice.read_memory` call and checks its
bytes. RAM, discrete addresses, Flash, sequential triples and verified scratch
writes are retained in the raw reports. The complete Flash image matches the
target AXF before writes; scratch is restored and checked. First use includes
connection/MUX setup and is reported separately. No cached target values, batched
averages or estimated firmware time count as individual read latency.

Local evidence is retained under artifact directory
`v043-tail-latency-20261103`, including failed runs and diagnostic prototypes.
Detailed traces are for localization; their instrumentation adds overhead, so
their timings are not substituted for uninstrumented qualification. P95 is the
nearest-rank percentile; maxima include all observed outliers.

## Large-sample experiments before the error-preservation fix

All three rows below have 1,000 continuous and 200 spaced 4-byte samples.

| Candidate | Continuous median / P95 / max, ms | Spaced median / P95 / max, ms | Continuous / spaced below 1 ms |
| --- | ---: | ---: | ---: |
| Unchanged phase 2 (`tail-baseline-2`) | 0.922 / 1.219 / 2.092 | 1.685 / 1.891 / 2.272 | 713/1000; 0/200 |
| Combined scheduling/transport prototype (`tail-combined`) | 0.904 / 1.156 / 7.225 | 1.610 / 1.847 / 2.734 | 778/1000; 0/200 |
| All owned processes on one CPU (`tail-single-cpu`) | 0.825 / 1.202 / 7.764 | 1.593 / 2.130 / 8.657 | 873/1000; 0/200 |

The combined prototype removes extra SDK receive-thread dispatch, replaces the
parent data-pipe reader with overlapped I/O, reduces task scheduling and uses a
specialized admission prototype. Its modest median change does not justify
shipping four architectural changes: P95 remains above 1 ms, spaced samples
never reach 1 ms, and maximum latency is worse in this run. CPU affinity is
rejected because spaced P95 and maximum regress despite a faster hot median.

Smaller screening rounds, all with checked data and successful cleanup:

| Diagnostic candidate | Hot / spaced samples | Continuous P95, ms | Spaced P95, ms |
| --- | ---: | ---: | ---: |
| Selector event loop | 200 / 30 | 1.295 | 1.994 |
| Synchronous SDK WebSocket receive | 200 / 30 | 1.213 | 1.925 |
| Selector plus synchronous receive | 200 / 30 | 1.142 | 2.194 |
| Fewer task scheduling steps | 300 / 40 | 1.219 | 1.859 |
| Native overlapped parent pipe | 300 / 40 | 1.202 | 1.903 |
| Native pipe plus task changes | 300 / 40 | 1.247 | 1.993 |
| Existing short MUX read command | 300 / 40 | 1.211 | 2.016 |
| Explicit HighQoS on backend/worker | 300 / 40 | 1.195 | 1.926 |
| Explicit HighQoS on all owned processes | 300 / 40 | 1.197 | 1.821 |
| Specialized read admission | 500 / 40 | 1.201 | 1.861 |

These are screening observations, not statistically established improvements.
None is incorporated into product code. No global power plan or persistent
affinity/QoS setting was changed. Existing authentication, ownership and
session/generation gates remain on the product path.

The first native-pipe prototype failed during backend startup because its
global Popen replacement conflicted with asyncio's Windows subprocess class.
No hardware operation occurred in that run. The corrected prototype confines
the replacement to the isolated-serial module; its results appear above.
That startup failure is retained as `tail-native-pipe` rather than overwritten.

## Where time remains

`tail-baseline-trace` contains 300 continuous and 60 spaced 4-byte reads, plus
8/32-byte groups. The analyzer also selects the actual slowest 5% of complete
requests; it does not add independent stage percentiles.

| Selected stage | Continuous median / P95, ms | Spaced median, ms |
| --- | ---: | ---: |
| SDK send | 0.048 / 0.067 | 0.115 |
| SDK send end to backend receive | 0.047 / 0.089 | 0.142 |
| Backend receive to identity check | 0.061 / 0.114 | 0.142 |
| Identity check | 0.008 / 0.015 | 0.016 |
| Admitted request to executor entry | 0.049 / 0.095 | 0.101 |
| Driver write | 0.076 / 0.113 | 0.108 |
| Driver write end to read return | 0.265 / 0.370 | 0.420 |
| Driver read return to complete parent reply | 0.128 / 0.183 | 0.165 |
| Device read end to WebSocket send | 0.137 / 0.239 | 0.208 |

For the slowest 15 continuous reads, median driver write-end/read-return time
is 0.320 ms, parent delivery 0.163 ms and device-return/backend-send 0.273 ms.
One device-entry/write-start interval reaches 5.538 ms. This localizes delay;
it does not identify GC, CPU power state or firmware as its cause. After idle,
multiple host stages are slower. The earlier multi-millisecond foreground
identity scan is no longer the usual spaced-read bottleneck.

The driver interval includes USB, probe execution and Windows scheduling.
It is not a wire-level SWD measurement. These results do not resolve the
customer's different F407/ST-Link comparison.

## Reliability defect exposed during scheduling stress

The 0.5 ms Python thread-switch diagnostic (`tail-gil-short`) failed after 249
checked Flash reads with `CDC queued read failed (WinError 0)`, followed by
`Device not connected`. No scratch write had begun. Logs and the failure are
retained. The device remained enumerated; this is not evidence of physical
unplugging or a firmware defect.

The read queue previously called a native API and later called native
`GetLastError`. That leaves its status exposed to intervening native work while
Python reacquires the GIL. Losing `ERROR_IO_INCOMPLETE` could both report a false
failure and incorrectly retire a still-live request. Private bindings now use
`WinDLL(..., use_last_error=True)` and `ctypes.get_last_error()` for ReadFile,
GetOverlappedResult and WaitForSingleObject. Other pyserial bindings are not
modified. Queue depth, buffer size, completion ordering, cancellation and
backpressure are unchanged. See [Python's error-preservation contract](https://docs.python.org/3.14/library/ctypes.html).

Native-API tests deliberately overwrite the OS last-error value between failure
and inspection and verify that pending-read, read-failure and wait-failure codes
survive. Existing queue tests cover live-buffer retention on delayed cancel,
ordered completion and reset. The 34 focused queue/isolated-worker tests pass.
The first test run exposed a fixture mistake: Windows handle -1 is a valid
current-process pseudo-handle for waiting; the invalid-handle test now uses NULL.

The next probe-only query correctly refused the stream mode left by the failed
test. After checking identity and absence of other users, the ordinary explicit
connection flow recovered this test session. No firmware update or write replay
was used. With the fix, the same short-switch stress (`tail-last-error-gil-2`)
completed: 1,000 hot reads at P95 1.231 ms and 100 spaced reads at P95 1.994 ms,
all read/write checks and restoration passed, and disconnect closed the device.
The short-switch setting is not retained as a performance optimization.

Two more diagnostics with backend GC callbacks enabled did not establish a
latency improvement (1,000 hot / 200 spaced samples each): a paired, process-owned
1 ms timer-resolution request gave hot P95 1.232 ms / spaced P95 1.974 ms;
default scheduling gave 1.277 / 1.941 ms. Neither timer-resolution nor GC settings
are changed in the product. In these rounds and the completed short-switch
stress, none of the slowest 5% of hot or spaced reads contains a backend GC start.
This does not cover every process or exclude all GC interference, but provides
no evidence to justify disabling GC as a tail-latency fix.

## Final qualification

`tail-final-plain` uses default scheduling and no experimental flags or GC/trace
callbacks. All checks and cleanup pass. Each size has 1,000 continuous samples
and 60 samples separated by 300 ms:

| Bytes | Continuous median / P95 / max, ms | Spaced median / P95 / max, ms | Continuous / spaced below 1 ms |
| ---: | ---: | ---: | ---: |
| 4 | 1.007 / 1.309 / 1.730 | 1.678 / 1.983 / 2.118 | 482/1000; 0/60 |
| 8 | 1.002 / 1.313 / 2.087 | 1.709 / 1.893 / 2.283 | 497/1000; 0/60 |
| 32 | 1.041 / 1.314 / 2.080 | 1.752 / 1.987 / 2.439 | 372/1000; 0/60 |

This round is slower than the earlier phase-2 hot medians; it must not be
described as another sub-ms success. The reliability fix is not a demonstrated
latency optimization. An adjacent old/fixed native-binding comparison is recorded
below to distinguish run-to-run effects from the code change.

`tail-last-error-streams` passes 15-second RTT, SystemView, Watch and combined
windows, with byte-checked interleaved memory reads. All checked target, parser,
stream and read-drop counters remain zero. Fastest Watch with a binary subscriber
checking every value, timestamp order and frame sequence gives:

| Variables | Previous phase-2 cycles/s | Current cycles/s | Current checked rows |
| ---: | ---: | ---: | ---: |
| 1 | 145176.57 | 145615.94 | 2331720 |
| 15 discrete | 1348.50 | 1347.17 | 21574 |

The rates remain at the prior level (approximately +0.30% / -0.10%); median
target periods remain 6 us / 744 us. All 2,353,294 rows pass, with no sequence
gaps, read errors or reported drops. These finite windows do not prove unlimited
long-duration behavior. Ordinary Watch interleaved 4-byte reads have median
2.033 ms / P95 2.783 ms. Combined-stream 4-byte reads have P95 447.632 ms;
concurrent acquisition is not claimed to meet the sub-ms target.

The initial 10 MiB RTT transfers measured 706.17 / 652.38 KiB/s for 1024/2048-byte
chunks. An independent repeat measured 678.24 / 659.87 KiB/s. All bytes pass in
both rounds, but these rates are lower than parts of the earlier phase-2 record.
The adjacent old/fixed/old binding comparison isolates this change without
reverting the source branch. Only the worker's native binding factory is replaced
by its pre-fix implementation for the finite old-code measurements. All three
rounds pass byte checks, restoration and device shutdown:

| Native bindings | RTT 1024 / 2048 B, KiB/s | 4 B continuous median / P95, ms | 4 B spaced median / P95, ms |
| --- | ---: | ---: | ---: |
| Old, first (`tail-rtt-old-api-1`) | 697.72 / 678.34 | 0.966 / 1.230 | 1.761 / 1.977 |
| Fixed (`tail-rtt-fixed-api`) | 686.82 / 687.19 | 0.975 / 1.223 | 1.727 / 1.953 |
| Old, second (`tail-rtt-old-api-2`) | 687.83 / 669.81 | 0.973 / 1.239 | 1.743 / 2.218 |

Each adjacent read matrix has 500 continuous and 60 spaced samples; its report
name appends `-reads`. Each RTT cell transfers and checks 10 MiB. Including the
initial and repeat rounds, all 100 MiB are verified. Old code also exhibits the
lower throughput; this limited adjacent comparison does not show a consistent
new regression from preserving native errors. It does not establish why the
earlier phase-2 throughput was higher, nor demonstrate a sub-ms improvement.
The full uninstrumented 1,000-sample matrix above remains reported alongside
these smaller adjacent rounds, including its slower hot median/P95.

This source remains a draft candidate. No build, packaging, signing, merge or
release was performed. Official application, Skill, firmware and tags remain
unchanged. Stable sub-ms P95, idle-spaced reads and the customer's F407 comparison
remain open.

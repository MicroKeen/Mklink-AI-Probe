# Serial worker event notification — 2026-11-03

This records **phase 1 only**, before the first-byte driver mode and guarded
memory channel. Current implementation, timings and remaining sub-millisecond
limits are in [phase 2](v043-memory-latency.md). The 0.104 ms delivery stage below
is not the public request latency or the probe's execution time.

The parent now uses two bounded blocking pipe readers and condition notifications
instead of polling control replies every 1 ms and receive data every 0.5 ms.
Data and control remain independent under backpressure. The data inbox adds at
most 1 MiB, the control inbox 64 KiB; neither grows with an unread acquisition.
Frame parsing/reset epochs stay in the consumer. Missing/malformed replies still
reap the worker without replay. Physical ownership is released only after exit.
The worker USB read queue, timeouts, firmware and SuperWatch scheduling are unchanged.

## Matched source comparison

Baseline is branch head `eedfad72`, already containing the previous HTTP/session
optimization; it is not formal 0.4.2. Both arms use the same current source client,
backend, Python and scripts, switching only the saved baseline serial module
(Git blob `791bf15ab9bf19e93346800f99a6edea65c3aa2d`) versus this change.
Order is baseline, candidate, candidate, baseline. V4/V4.7.2, H743,
SWD configured/applied 10 MHz, same AXF matched against the complete Flash image
before writes. The user released the previously occupied probe before tests.
All finite reads are byte-checked; dedicated scratch writes are independently
read back and restored. Unknown operations are never replayed.

Pooled medians/P95 in ms from two runs, 100 samples per hot-read group per run.
Spaced groups have eight samples/run; writes twelve/run. Write times exclude
independent verification/restoration. Full raw rows and outliers are retained.

| Operation | Bytes | n per arm | Baseline median / P95 | Events median / P95 | Events max |
| --- | ---: | ---: | ---: | ---: | ---: |
| read_flash_discrete | 4 | 200 | 5.417 / 7.138 | 4.235 / 5.329 | 10.468 |
| read_flash_discrete | 16 | 200 | 5.446 / 6.228 | 4.620 / 6.516 | 13.511 |
| read_flash_discrete | 128 | 200 | 5.472 / 6.269 | 5.097 / 6.368 | 15.292 |
| read_flash_discrete | 4096 | 200 | 11.998 / 14.030 | 11.656 / 13.521 | 19.489 |
| read_same | 4 | 200 | 5.496 / 6.455 | 4.307 / 5.788 | 43.584 |
| read_discrete | 4 | 200 | 5.463 / 6.117 | 4.501 / 6.068 | 12.545 |
| read_spaced | 4 | 16 | 12.691 / 14.517 | 11.361 / 14.212 | 14.212 |
| read_same | 16 | 200 | 6.033 / 7.263 | 4.905 / 6.007 | 11.029 |
| read_discrete | 16 | 200 | 5.688 / 6.988 | 4.712 / 5.772 | 12.608 |
| read_spaced | 16 | 16 | 12.894 / 15.127 | 11.346 / 12.797 | 12.797 |
| read_same | 128 | 200 | 5.844 / 7.066 | 4.550 / 5.500 | 10.610 |
| read_discrete | 128 | 200 | 5.783 / 7.250 | 4.567 / 5.584 | 11.292 |
| read_spaced | 128 | 16 | 12.512 / 13.208 | 11.696 / 13.655 | 13.655 |
| read_same | 4096 | 200 | 12.574 / 14.884 | 11.656 / 13.309 | 18.927 |
| read_discrete | 4096 | 200 | 12.346 / 14.116 | 11.600 / 13.599 | 18.277 |
| read_spaced | 4096 | 16 | 19.127 / 21.530 | 18.485 / 20.464 | 20.464 |
| three_reads_contiguous | 4 | 200 | 16.970 / 21.520 | 13.237 / 18.455 | 23.453 |
| three_reads_discrete | 4 | 200 | 17.263 / 22.813 | 13.947 / 19.079 | 26.261 |
| write_verified | 4 | 24 | 9.447 / 33.087 | 7.041 / 29.377 | 31.699 |
| write_verified | 16 | 24 | 9.239 / 15.051 | 6.900 / 13.320 | 15.279 |
| write_verified | 128 | 24 | 9.644 / 10.437 | 7.859 / 12.567 | 14.104 |
| write_verified | 4096 | 24 | 46.157 / 51.481 | 43.729 / 45.847 | 46.056 |

The two independent 4-byte hot-read medians are 5.450/5.520 ms baseline and
4.241/4.543 ms candidate. This is a repeated improvement, not a sub-millisecond
claim. Three-read operations are independent sequential requests, not snapshots.
First-request and spaced-refresh costs remain. These H743 measurements do not
prove the customer's F407 43 ms case is resolved.

## SuperWatch correctness and performance

Each arm has two 15-second observation windows for each combination below, with
one-second warmup. The binary subscriber validates every received Float32 sample
against the known target words converted to the public Float32 representation,
frame sequence continuity, and sample timestamp deltas. Separate memory reads
check the original bytes. All sixteen windows have zero value errors, sequence
gaps, read errors, read drops and binary publication drops.

| Variables | Requested interval | Baseline cycles/s (two runs) | Events cycles/s (two runs) |
| ---: | ---: | ---: | ---: |
| 1 | 1000 us | 1002.91 / 997.80 | 996.65 / 999.53 |
| 1 | 100 us | 10008.38 / 10027.77 | 10001.96 / 9993.88 |
| 15 | 1000 us | 998.51 / 1000.12 | 998.90 / 1001.18 |
| 15 | 100 us | 1350.49 / 1351.18 | 1352.12 / 1352.53 |

Total validated rows: 853,285. At 15 discrete variables/100 us, both arms
achieve roughly 1350 cycles/s with a 0.742 ms median target period; the requested
10 kHz is not achieved by either arm. Other median periods remain 1 ms/0.1 ms.
These finite matched windows show no SuperWatch rate regression; they do not
establish a long-duration or all-board guarantee. Host batch gaps include the
existing approximately 100 ms publication batching and are not target sample gaps.

RTT, SystemView and Watch run separately and together for 15-second windows with
interleaved, byte-checked 4/16/128/4096-byte memory reads. The baseline initial
script completed these stages before a later harness error (retained below).
All checked stream/parser/target-drop/read-error counters are zero and SV events
and Watch cycles advance. RTT sequence and payload bytes are fully checked.
The 4-byte request median with Watch stays about 75 ms; scheduling is not changed.
SystemView-only request median/P95 varies from 28.43/187.10 ms baseline to
36.41/381.58 ms candidate in these windows: concurrent request tails are not
claimed to improve. Three-stream 4-byte medians are 69.89/55.42 ms respectively.

Two saturated 10 MiB RTT transfers per arm, at 30 MHz, verify every payload byte:
1024-byte chunks 735.67 -> 747.11 KiB/s; 2048-byte chunks 767.95 -> 757.89 KiB/s.
There is no general throughput-improvement claim. Speed returns to 10 MHz,
producer controls and scratch contents are restored, and owned backends exit.

## Backend path assessment

Instrumentation is external and excluded from the matched timing tables above.
One empty worker trace from the preliminary version query is preserved/excluded;
the measured read group's driver trace must have complete coverage below.
Per-stage medians are not additive and some intervals overlap. Driver read-return
does not measure physical USB arrival or on-probe execution time.

| Stage, hot 4-byte reads | Median ms |
| --- | ---: |
| client_start__backend_received | 0.2349 |
| backend_received__asgi_init | 0.4515 |
| asgi_init__asgi_init_done | 0.0515 |
| asgi_init_done__inner_received | 0.1142 |
| inner_received__identity_start | 0.0253 |
| identity_start__identity_end | 0.0090 |
| identity_end__admitted | 0.0557 |
| admitted__device_start | 0.4323 |
| device_start__serial_write_start | 0.0297 |
| serial_write_start__serial_write_end | 0.1840 |
| serial_write_end__complete_reply | 1.7755 |
| complete_reply__notify | 0.0132 |
| notify__device_end | 0.0277 |
| device_end__client_end | 0.7916 |
| driver_write_start__driver_write_end | 0.0847 |
| driver_write_end__driver_read_return | 1.7128 |
| driver_read_return__complete_reply_delivered | 0.1041 |
| http_send_end__backend_received | 0.1395 |

The next candidate is a shared guarded memory service used by both HTTP routes
and runtime calls, removing the internal ASGI request/response construction.
Authentication, argument validation, session/identity generations, operation
admission, cancellation ownership and thread-pool execution must remain equivalent.
Do not invoke a raw device handler on the event loop or bypass lifecycle guards.
Client construction alone was only tens of microseconds; optimizing that alone
is not worthwhile. This step assesses the path only; no backend route change is
included. Driver/USB/probe time still prevents claiming a sub-ms public call.

## Validation boundaries and retained failures

- Final affected suite: 99 files, 2413 passed, two skips, 34 dependency
  deprecation warnings; unhandled-thread warnings are treated as errors.
  The focused serial/ownership suite passes all 35 tests.
- Real process tests cover wake on data/close, full-data-pipe backpressure with
  independent control, split old-generation framing across reset, malformed/EOF/
  oversized control replies, no replay, and worker/reader cleanup.
- The first baseline harness resolved its worker next to the saved module and
  failed before opening the port. Its worker path was corrected. An initial
  stream harness used a conflicting `name` argument; its earlier completed stream
  evidence is retained, but the whole run is not called passing.
- One mocked pipe fixture lacked `read`, causing thread warnings in the initial
  28-test run. The fixture was updated and warnings are errors in subsequent tests.
- The first broad run had 2411 passes, one failed new assertion that incorrectly
  required a full-length serial read, and setup/teardown errors for one oversized
  pytest parameter ID exceeding Windows' environment-variable limit. The test
  now collects legal short reads and uses short parameter IDs. The complete
  affected suite was rerun successfully; production code did not change.
- This is source qualification. Previous NSIS/Skill/GUI/Keil evidence belongs to
  the earlier candidate and is not reused to qualify this changed transport.
  No installer/global Skill replacement, firmware edit, version change, merge,
  signing, publication or cloud operation is included. PR 69 remains draft.
- The prior intermittent proxy shutdown issue, F407 high-address issue, Watch
  scheduling delays and other documented limits remain open.

Raw scripts, data, hashes and logs: local artifact directory
`v043-serial-events-20261103`. Retain test-linked scratch for manual inspection.
See [previous candidate qualification](v043-request-latency.md).

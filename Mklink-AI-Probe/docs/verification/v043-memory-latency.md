# Read-memory latency, phase 2 — 2026-11-03

The [P95 and spaced-read follow-up](v043-tail-latency.md) records larger samples,
rejected scheduling/transport experiments and the Windows error-preservation fix.

The public call now measures below 1 ms **at the median for continuous small
reads**. This does not establish every request below 1 ms: P95 still exceeds
1 ms, spaced reads remain slower, and first use includes channel/MUX setup.
The earlier approximately 0.10 ms measurement covered only delivery from the
serial worker. It was never an end-to-end result or a firmware execution time.

## Implementation and boundaries

- Phase 1 replaces parent pipe polling with bounded event notification; its
  matched A-B-B-A evidence remains in [the phase 1 report](v043-serial-events.md).
- The Windows overlapped queue uses the documented first-byte COMMTIMEOUTS mode
  (MAXDWORD interval/multiplier, 100 ms constant). Eight 16 KiB requests,
  submission order, cancellation/reaping, reset generations and backpressure
  remain. It does not use empty-read spinning or change probe firmware.
- Internal memory calls pass the existing RuntimeGate and then the same leased,
  executor-backed read handler. Internal HTTP encoding/routing is removed;
  authentication, argument checks, identity, sessions, captures, jobs, lifecycle
  admission and cancellation ownership remain. Admission is released before
  returning the outer response.
- New target attachments optionally advertise `memory_transport=websocket-v1`.
  The existing public SDK read API uses one ordered authenticated loopback
  channel bound to session, runtime instance and probe. Every read passes the
  gate. Other capabilities remain on HTTP; old backends without the advertisement
  use HTTP. Failure never retries or falls back after attempting the channel.
  Detach/disconnect/reconnect closes it; expired idle sessions cannot retain it.
- While memory channels are attached, one passive identity refresher per backend
  moves device enumeration off the request path. The existing 250 ms freshness
  limit is unchanged and measured from enumeration **start**. Results from an
  old connection generation, a newer observation, or an overlong enumeration
  cannot refresh the cache. Missing probes/errors invalidate it. Expired results
  still require the existing foreground check. No target reads are prefetched.

Windows timeout semantics: [Microsoft COMMTIMEOUTS documentation](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-commtimeouts).

## Actual public-call measurements

Source client and backend, ordinary V4/V4.7.2, H743, configured/applied SWD
10 MHz, same target AXF checked against the complete Flash image before writes.
The user released the occupied probe. Every finite read is byte-checked; scratch
writes are read back and restored. No cache of target values, averaging within
a batched request, or estimated firmware time is used as a public-call result.
These H743 measurements do not prove the customer's different F407/ST-Link
comparison is resolved or that MKLink now beats ST-Link.

Two final uninstrumented rounds, `product-prefetch-1` (200 continuous samples
per group) and `product-prefetch-2` (300), both passed. The 4 B hot medians are
0.92 and 0.93 ms, compared with phase 1's 4.24/4.54 ms and branch baseline
5.45/5.52 ms. The second final round also adds the customer's 8/32 B sizes:

| Bytes | Continuous median / P95 / max, ms (n=300) | 300 ms spaced median / P95 / max, ms (n=30) |
| ---: | ---: | ---: |
| 4 | 0.933 / 1.184 / 1.374 | 1.684 / 1.836 / 2.023 |
| 8 | 0.937 / 1.198 / 1.467 | 1.705 / 1.866 / 1.908 |
| 16 | 0.957 / 1.164 / 1.393 | 1.673 / 1.904 / 2.237 |
| 32 | 0.960 / 1.208 / 1.542 | 1.687 / 1.912 / 2.231 |
| 128 | 1.121 / 1.397 / 1.883 | 1.869 / 2.177 / 2.292 |
| 4096 | 8.191 / 8.494 / 9.149 | 8.534 / 8.978 / 9.225 |

Read-discrete, Flash, first-call, sequential triples, writes and all raw outliers
remain in the local JSONs. The first request includes lazy channel setup and MUX
negotiation and is not represented by the hot-read median.

## Why the remaining latency is real

External trace `product-memory-trace`, before identity prefetch, contains all
30 hot and eight spaced 4 B samples. Per-stage medians are not additive:

| Stage | Hot / spaced, ms |
| --- | ---: |
| Public call start to backend memory invocation | 0.143 / 0.356 |
| Passive identity admission | 0.008 / 5.975 |
| Admitted operation to executor read | 0.049 / 0.082 |
| Driver write | 0.081 / 0.105 |
| Driver write end to driver read return | 0.258 / 0.379 |
| Driver read return to complete parent reply | 0.127 / 0.125 |
| Device read end to public call return | 0.252 / 0.316 |

This isolated the roughly 6 ms identity-enumeration penalty in spaced reads;
prefetch reduced their public median from roughly 8 ms to 1.68 ms. Driver return
includes USB, probe and host scheduling; it is not a wire-level timing measurement.
Stable sub-ms P95 and spaced requests remain unachieved. SystemView/concurrent
stream request tails, the prior intermittent proxy shutdown issue and
F407-specific issues remain open.

## SuperWatch and shared streams

`product-prefetch-streams` passes RTT, SystemView, SuperWatch, all three together,
the fastest Watch matrix, and two saturated RTT transfers. Each mixed-stream
window lasts 15 seconds and interleaves byte-checked 4/16/128/4096 B reads. All
checked target/parser/stream/read-drop counters are zero; Watch cycles and SV
events advance. RTT sequence and payload bytes are checked completely.

At a requested 4 us interval, with a binary subscriber checking every Float32
row, target timestamp and frame sequence, the latest 15-second Watch windows are:

| Variables | Branch baseline cycles/s | Final cycles/s | Final checked rows |
| ---: | ---: | ---: | ---: |
| 1 | 145216.32 | 145176.57 | 2323719 |
| 15 discrete | 1349.99 | 1348.50 | 21582 |

All 2,345,301 rows match, without sequence gaps/read errors/publication drops.
Median target periods are 6 us and 744 us respectively. These finite measurements
show no material Watch rate regression; neither arm achieves the requested 4 us
period. Earlier final-channel idle windows also pass after the socket fix.

With ordinary 1 ms Watch and interleaved reads, the new 4 B public median/P95
is 1.783/2.538 ms, compared with phase 1's roughly 75 ms median. The old 75 ms
result therefore is not carried forward as the current Watch-only result.
SystemView-only median/P95 is 14.350/225.914 ms; with all three streams it is
12.110/467.510 ms. There is no sub-ms claim during acquisition.

Saturated RTT at 30 MHz, 10 MiB per 1024/2048 B block size, checks all bytes.
The initial final-source run measured 726.62/716.55 KiB/s. A focused crossover
with identity prefetch disabled measured 747.39/795.30; reenabled measured
770.05/770.25. The initial low result is retained; these runs do not establish
a repeatable prefetch penalty or a general throughput improvement. No acquisition
scheduling or firmware was changed. Speed returns to 10 MHz; producer controls
and scratch bytes are restored, and each owned backend exits.

## Validation and retained experiments

Focused identity/channel/native-queue checks: 103 passed. They cover origin/token/
session/instance/probe rejection, old-backend HTTP behavior, target changes while
waiting for messages, idle expiry, malformed input, capture/lifecycle rejection,
lost replies without replay, exact payloads, and admission/target ownership until
the executor finishes even after cancellation or WebSocket disconnect. Identity
tests include expiry, failed discovery, changed handles and stale async results.

Final affected suite: 100 files, **2456 passed / 2 skipped**, with
unhandled thread exceptions treated as errors. Dependency deprecation warnings
are retained in the log. This suite and the hardware windows above qualify
the current source; phase 1 and the older package results remain separate.
Public Skill/maintainer boundary checks: 65 passed. Project memory render and
validation and `git diff --check` pass.

All intermediate evidence is retained, including failures:

- The direct HTTP read shortcut failed with 409 because a response could precede
  gate release. It was discarded. The retained MemoryCall awaits full completion.
- Early first-byte **experimental wrappers** mishandled pyserial's timeout
  restoration structure during close. The wrapper was fixed and complete driver
  traces saved; the product sets COMMTIMEOUTS directly without this wrapper.
- Alternative larger bridge reads, merged HTTP sends and optional native HTTP
  parsing did not give a repeatable gain and were discarded. The optional HTTP
  wheel exists only under the local experiment artifacts; no dependency was added.
- Experimental WS 4 B medians 0.95 then 1.09 ms were not treated as stable success.
- The first product Watch run verified its data/rate but failed on the next
  memory read after an idle interval: the caller-owned socket retained its 3 s
  connect timeout. The client now clears that TCP timeout while retaining explicit
  handshake/response deadlines. `product-memory-fastest-2` passed, including reads
  after the idle Watch windows. The failed run is not called passing.
- Initial new WebSocket fixtures omitted the runtime Host/auth headers and were
  rejected before admission; corrected fixtures pass the positive and negative
  paths. Their failed logs are retained.

All work stays on `codex/v0.4.3-fixes` / draft PR 69. Product version remains
0.4.2. This is source qualification; no package, installer/global Skill update,
firmware change, signing, merge, release or cloud operation was performed.
Earlier packaged/GUI/Keil qualification is not reused for this changed code.

Raw evidence: local artifact directory `v043-serial-events-20261103`. Keep all
logs, trace files, failed runs and linked test scratch for inspection.

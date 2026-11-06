# 0.4.3 generic request latency candidate — 2026-11-03

The existing public memory API now reuses loopback HTTP connections and avoids
unnecessary path resolution and AXF toolchain diagnostics during admission.
The Windows candidate improves finite standalone requests on the tested V4/H743.
It does not promise a fixed deadline or improve every concurrent sampling load.
Product version remains 0.4.2; this is development work, not a release.

## Implementation and scope

Product commit `ea80b827`, packaged source `2cfda2e4`, based on main `4f3be7a4`.
Work remains on `codex/v0.4.3-fixes`, PR [69](https://github.com/MicroKeen/Mklink-AI-Probe/pull/69).
One connection per calling thread is keyed by port, backend instance, probe and
credentials. Requests use fresh headers, body and timeout. Idle connections are
retired after two seconds; an already-readable socket is retired before sending.
Transport failure closes the connection and never retries the operation.
Numeric loopback bypasses proxy environment settings and does not follow redirects.
The active AXF path has a cheap accessor; generation/fingerprint, epoch, project,
permission and physical ownership guards remain. Wire protocol and public calls
are unchanged. There is no customer-specific snapshot protocol or probe firmware change.

## Finite A/B measurement

Same Windows host, ordinary V4 formal V4.7.2 (2026-11-01 21:06:26), STM32H743,
SWD configured and reported applied at 10 MHz outside Keil. Baseline uses the
installed formal 0.4.2 runtime and Skill. Candidate uses the actual NSIS-extracted
sidecar and its complete packaged Skill, without instrumentation. Each frozen
server runs with Windows-only PATH. Before writes, the script rechecks probe
identity, MCU ID, the complete loaded Flash image against the current AXF and
the dedicated 4096-byte qualification buffer. Every measured read is byte-checked;
each write is followed by independent readback, restoration and full-buffer check.
The write timing below is the public write call, excluding those extra checks.

Medians / nearest-rank P95 in milliseconds. Hot/Flash groups use 100 samples;
spaced reads use eight samples with 300 ms gaps; writes use twelve samples.

| Operation | Bytes | Formal median / P95 | Candidate median / P95 | Candidate max |
| --- | ---: | ---: | ---: | ---: |
| read_same | 4 | 8.490 / 20.051 | 5.687 / 6.649 | 13.423 |
| read_same | 16 | 8.410 / 19.559 | 5.669 / 6.383 | 11.565 |
| read_same | 128 | 17.811 / 19.735 | 5.737 / 6.384 | 12.755 |
| read_same | 4096 | 24.720 / 27.786 | 12.455 / 13.886 | 19.920 |
| read_discrete | 4 | 8.745 / 19.646 | 5.720 / 6.572 | 12.626 |
| read_discrete | 16 | 9.046 / 19.288 | 5.826 / 6.407 | 11.635 |
| read_discrete | 128 | 11.956 / 19.935 | 5.630 / 6.437 | 12.607 |
| read_discrete | 4096 | 23.629 / 30.023 | 12.486 / 13.999 | 19.303 |
| read_flash_discrete | 4 | 11.415 / 20.103 | 5.700 / 6.836 | 12.732 |
| read_flash_discrete | 16 | 13.817 / 19.939 | 5.763 / 6.702 | 12.743 |
| read_flash_discrete | 128 | 15.861 / 19.662 | 5.708 / 6.580 | 43.276 |
| read_flash_discrete | 4096 | 24.571 / 27.738 | 12.433 / 13.316 | 19.019 |
| read_spaced | 4 | 14.542 / 15.429 | 12.777 / 13.750 | 13.750 |
| read_spaced | 16 | 15.228 / 24.389 | 13.525 / 14.005 | 14.005 |
| read_spaced | 128 | 16.005 / 17.076 | 12.542 / 13.643 | 13.643 |
| read_spaced | 4096 | 21.539 / 32.734 | 20.050 / 22.263 | 22.263 |
| three_reads_contiguous | 4 | 35.119 / 52.688 | 16.751 / 21.157 | 24.059 |
| three_reads_discrete | 4 | 35.668 / 55.888 | 16.845 / 22.407 | 25.058 |
| write_verified | 4 | 21.209 / 41.594 | 9.410 / 43.809 | 43.809 |
| write_verified | 16 | 12.231 / 22.647 | 9.475 / 15.155 | 15.155 |
| write_verified | 128 | 12.049 / 28.117 | 9.308 / 10.378 | 10.378 |
| write_verified | 4096 | 57.781 / 60.493 | 46.605 / 53.785 | 53.785 |

`read_discrete` rotates offsets inside the scratch buffer; at 4096 bytes it
necessarily uses offset zero. `read_flash_discrete` separately rotates complete
blocks across Flash, including truly discrete 4096-byte reads. Triple rows issue
three sequential independent calls, not one coalesced read. They are not atomic.
The first 4-byte request after connecting was 41.151 ms formal and 40.501 ms candidate.
A separate cold-connection run leaves 2.2 seconds between reads (three per size),
so the candidate must establish a new connection and refresh target identity.
Cold, old-client compatibility and Keil captures use the first packaged backend.
All seven relevant frozen runtime modules are bytecode-identical in the native
rebuild; its standalone 100-sample and stream matrices are repeated above/below.

| Cold connection bytes | Formal median / max | Candidate median / max |
| ---: | ---: | ---: |
| 4 | 15.260 / 15.575 | 13.423 / 13.665 |
| 16 | 15.766 / 16.129 | 13.390 / 15.051 |
| 128 | 14.916 / 15.341 | 12.895 / 21.779 |
| 4096 | 21.895 / 22.959 | 19.715 / 20.011 |

Both final runs reject wrong credentials with 401 and missing size with 422,
then successfully read again. Scratch restoration and explicit physical disconnect
pass. A separate installed-old-client/new-frozen-server run passes the same byte,
write/restore and error checks. Lost-write-response no-replay is covered using a
real loopback HTTP server; no unknown-write fault was injected into the MCU.

## Layer attribution

Temporary external instrumentation separately measures client HTTP, backend
admission, identity checks, MUX, worker pipe and serial-driver returns. The
intermediate `connection-path-candidate` trace includes connection/path changes
before removal of AXF status diagnostics; it is not the final timing table above.
Fresh loopback connection setup showed approximately 10 ms tail events; repeated
path resolution and optional AXF/toolchain status work added sub-millisecond work.
For 4-byte hot reads, traced driver write was about 0.10 ms, write-end to driver
read-return 2.18 ms, worker delivery 0.58 ms, parse/notify 0.015 ms and condition
wake 0.020 ms. Identity cache hits were about 0.01 ms; idle refresh remains several
milliseconds. The existing 250 ms identity TTL was not widened. Per-stage medians
are not additive. Serial-driver return is not electrical USB arrival or on-probe
execution timing; these measurements do not justify a firmware change.

## Streams, Keil and recovery

Final packaged RTT, SystemView and SuperWatch each run alone and together, with
finite public memory requests. RTT sequence/payload checks pass; SystemView
events and Watch cycles grow with zero tested parser/target-drop/Watch-error
counters. Formal stream windows are eight seconds and final candidate windows
twelve seconds. The following 4-byte median / P95 values show the scheduling boundary:

| Active streams | Formal ms | Candidate ms |
| --- | ---: | ---: |
| rtt | 13.10 / 29.35 | 6.47 / 7.72 |
| systemview | 64.66 / 107.51 | 25.06 / 86.01 |
| superwatch | 74.91 / 110.97 | 74.73 / 76.47 |
| rtt + systemview + superwatch | 48.58 / 98.22 | 43.44 / 99.30 |

These are finite runs, not a long-duration or all-load guarantee. High-frequency
SuperWatch still produces roughly 75 ms request medians; this scheduling wait
was not changed. Source and frozen runs show throughput variability, so no
general throughput increase is claimed. All saturated payload bytes are verified.

| RTT 10 MiB, chunk bytes | Formal 30 MHz KiB/s | Candidate 30 MHz KiB/s | Formal + Keil KiB/s | Candidate + Keil KiB/s |
| ---: | ---: | ---: | ---: | ---: |
| 1024 | 725.54 | 736.26 | 379.08 | 379.06 |
| 2048 | 789.24 | 717.22 | 379.22 | 379.14 |

Keil UI is set to 10 MHz; while Keil owns DAP the shared backend reports only
configured frequency, not applied frequency. Do not interpret that as a physical
clock measurement. Native IDE build reports zero errors/warnings and download
reports `Verify OK` / application running; subsequent full Flash comparison and
all three stream tests pass against that newly built AXF.
The earlier candidate run hit the explicitly set breakpoint at `0x0801B176`;
that test breakpoint was cleared. Final recovery capture halts at `0x0801B12C`,
steps to `0x0801B176`, resumes after about 13.7 seconds, and continues all streams.
Post-resume SystemView events and Watch cycles increase; all RTT sequence bytes
are retained. This deliberate halt appears as a 13.7-second host arrival gap.
It is not a transport drop and is excluded from uninterrupted throughput claims.

Preserved failed/limited harness runs: an initial duplicate `name` argument;
two configured-vs-applied clock assertions under Keil; the first candidate
1024-byte throughput sample contaminated by a deliberate long halt; a subsequent
90-second saturation timeout while still halted; and a restarted-target SystemView
test waiting for events before enabling its fixture producer. The latter harness
ordering was corrected before the final successful recovery run. These failures
were not removed or counted as passing evidence. No uncertain operation was replayed.

## Software and package checks

- Full Python run: 6460 passed, two optional skips, one stale UART fixture failed.
  The fixture was updated for the active AXF accessor; all 143 affected tests then
  passed without a further production-code change. Do not call that one clean full run.
- Full GUI suite: 1182 tests in 104 files passed. Production Web, PyInstaller, Rust
  and unsigned local NSIS builds passed. Source CI feedback/runtime/GUI checks passed.
- NSIS extraction matches the frozen sidecar and all 3643 support files. The native
  launcher has the expected three-byte Tauri bundle-type patch. Catalog validation
  covers 7059 targets / 2224 FLM blobs and the complete checked SVD payload.
- Actual frozen stdio MCP initializes with 56 tools and passes `inspect_mcu` and
  read-only `security_status`; packaged Web health/assets and F407 peripheral targets
  pass. Real browser dashboard and native launcher checks use Windows-only runtime
  PATH; successful normal shutdown checks are retained alongside the exception below.
  No external Python is needed by the payload.
- This is isolated package-payload qualification. The formal installation/global
  Skill are preserved; signed in-place upgrade and installer UI were not retested.
  No merge, version bump, signing, tag, release or cloud change is included.

The first locally built native executable displayed a directory listing because
the temporary absolute `frontendDist` was interpreted as a URL. It is a failed
candidate, preserved separately. The local build script now uses an unambiguous
Windows filesystem path; the rebuilt native UI is checked and the actual rebuilt
NSIS payload reruns the finite benchmark and standalone/concurrent streams.
No tracked product build configuration was changed. Earlier backend-only evidence
retains its original package identity; the final table uses the corrected package.

One browser-driven proxy shutdown failed to exit within 30 seconds after a
Windows Proactor connection-reset callback exception. The listener and shared
backend had stopped; only that identified test proxy was later terminated.
A matched formal/candidate repeat exited normally in 0.265/0.291 seconds.
A separate formal-runtime run with twenty deliberate client TCP resets also
exited in 0.300 seconds; it did not reproduce the first failure.
Frozen Proactor, proxy, Uvicorn server/WebSocket and legacy WebSocket client/protocol
module code hashes match formal 0.4.2. This identifies unchanged relevant code,
but does not by itself establish the cause of the intermittent failure.
The initial failure remains unresolved and is not relabeled as a passing result;
keep it as a shutdown follow-up before release qualification. Native close and
HTTP-only proxy shutdown are separately checked. The PR remains a draft.
The corrected native window rendered configuration and dashboard views, then
closed normally with all eleven recorded processes released. Final memory and
public-Skill boundary checks pass (67 tests); test-linked scratch is retained.

Local candidate names and SHA-256 (first failed native bundle remains archived):

| Artifact | SHA-256 |
| --- | --- |
| candidate-2cfda2e4-fixed/MKLink-local-2cfda2e4.exe | `d8264f66856e92b56ade2b957a771bb032c1e96e98ee9bd03b70f2b02f3789e0` |
| MKLink-Skill-local-2cfda2e4.zip | `c708c2310d1bff9a669d4da895a75c59cd10ed25db6c46be26cc5061513317a9` |

Raw scripts, timings, traces, bytes, build logs and failure evidence stay in the
local build artifact directory `v043-request-latency-20261103`; device identities
and local hardware paths are not committed. Retain the separate F407 high-address
fast-path issue, historical V3 dropouts, cold-plug/long-duration tests and other
limits in [known-limits-20261030.md](../ai/known-limits-20261030.md).

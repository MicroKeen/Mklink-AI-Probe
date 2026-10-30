# MUX block reads and host latency — 2026-10-30

Product source `836d8ea3`, shared `codex/v0.4.2-fixes`, draft PR #66.
Version remains 0.4.1. This work does not authorize a formal release or firmware publication.

## Behavior and compatibility

The first ordinary memory read/write already negotiated MUX in `d59dbceb`.
This follow-up uses HELLO capability bit 6 and command 0x16 for one 1–4096-byte
read. Its 0x96 reply is CRC-protected version 1, with one status byte plus exactly
the requested data, at most 4097 payload bytes. USB segmentation is transport
framing, not additional target commands. Old firmware keeps 128-byte 0x11 reads;
0x12 writes retain their 128-byte limit. Errors do not trigger fallback or replay.
Shared SDK/CLI/MCP APIs and the public 4096-byte snapshot limit are unchanged.
One target lock does not make a running MCU's changing memory an atomic snapshot.

Repeated memory requests reuse a successful identity check for at most 250 ms
while the exact same connected bridge, serial handle, OS lock, probe identity and
device generation remain live. Errors, closure, recovery or replacement invalidate
the cache. Lifecycle and other operations still enumerate. The cache deadline is
not extended on hits; an observed missing/changed probe invalidates it immediately.
Authentication, leases, capture ownership and unknown-result handling remain intact.

The Windows queued reader consumes a signalled completion immediately and uses
a 1 ms inter-byte timeout instead of 2 ms. Its eight pending read buffers,
cancellation lifetime and 100 ms total timeout remain unchanged.

Temporary stage tracing identified roughly 6 ms of repeated enumeration overhead
before MUX send. IPC delivery to the serial worker was about 0.07 ms, so no IPC
rewrite was justified. The read interval change reduced measured small-reply
write-to-USB-completion time from about 3.2 ms to 2.1 ms. These stage measurements
are diagnostic experiments, not the final benchmark or latency guarantees.

**All temporary timing modules, imports, hooks and trace-specific tests were
deleted before the product commit.** Only offline JSONL evidence remains under
the local build artifacts. Existing ordinary error diagnostics are retained.
This cleanup requirement also applies to the separately owned V3 firmware port.

## Validation

- 1,224 relevant Python tests passed: MUX framing, 1-byte through whole-frame
  fragmentation, capability compatibility, bounds/CRC/epoch/request failures,
  identity expiry/invalidation, runtime ownership/recovery, serial cancellation,
  RTT and dump lifecycle. Skill quick validation and memory validation passed.
- Windows/H7 hardware used the ordinary V4 private firmware built on Oct 30 at
  14:55:53 with the agreed block-read capability. Firmware was upgraded by its
  designated session, not by this host session. This differs from the previous
  HPMLINK/HPM5301 XML test and from the customer's F407 motor test.
- Flash matched 216,776 bytes from the AXF before writes. Writes touched only the
  first 128 bytes of the dedicated 4 KiB test buffer. Every phase restored and
  compared the entire buffer, then disconnected with `device_closed=true`.
  No target Flash write, VCC, OTP, halt or reset was performed here.
- Four 4 KiB continuous captures, two each at 10 and 30 MHz, sustained about
  121 and 199 complete samples/s over the measured windows. Parser dropped bytes,
  dropped frames, CRC errors and firmware error flags were zero. Every stop was
  followed by a successful read and subsequent restart. A duration-limited partial
  tail remains separately accounted; this is not a lossless/atomic guarantee.
  This round did not qualify concurrent RTT/Watch/UART operation.

Final clean-source shared SDK run, 20 sequential calls per row, zero failed calls.
P95 is nearest rank; the small sample count and scheduling jitter are explicit.
Connection, version queries and speed selection were outside the timed calls;
write acknowledgement timing excludes the subsequent independent readback.

| Operation | Bytes | Min ms | Median ms | P95 ms | Max ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Status | — | 3.249 | 4.385 | 15.119 | 15.525 |
| Read | 4 | 7.607 | 8.886 | 19.105 | 23.422 |
| Read | 32 | 6.562 | 8.835 | 19.473 | 20.063 |
| Read | 128 | 7.377 | 8.490 | 19.708 | 24.773 |
| Read | 4096 | 10.365 | 22.303 | 28.269 | 29.507 |
| Write acknowledgement | 4 | 7.413 | 8.414 | 19.281 | 20.101 |
| Write acknowledgement | 32 | 6.847 | 8.897 | 20.213 | 25.936 |
| Write acknowledgement | 128 | 7.682 | 8.844 | 20.356 | 25.582 |
| Write plus readback | 128 | 10.017 | 12.082 | 23.197 | 23.305 |

The earlier `d59dbceb` run used an older firmware: read4/read4096/write128 medians
16.73/173.11/16.41 ms. The new measurements reflect both host and firmware changes;
do not attribute the entire improvement to the host or compare them to unrelated
ST-Link boards/call paths. Keep setup/first-call, persistent-call, batch and
continuous-capture measurements separate in any customer comparison.

Local evidence root: `mux-block-latency-20261030`, including
`clean-source/source-hardware.json`, `final-source-statistics.json`,
`source-capture.json`, `focused-tests.log` and experimental phase JSONL files.
Fixture-link scratch directories were retained by the build wrapper for safe
inspection; no forced recursive deletion of linked paths.

## Scope limits

HPM block reads and the V3 port need their own board/firmware qualification.
Previous HPM5301 XML six-register reads and 193 samples with zero errors remain
valid historical evidence in `hpm-svd-dump-stop-20261030.md`; they do not qualify
this new block-read firmware on HPM. The customer F407/F411 reproductions,
long-duration V3 connection stability and full concurrency matrix remain open.
Older Linux/macOS candidates have not been rebuilt with these follow-up changes.

## Installed candidate qualification

Both candidates use product source `836d8ea3767d2b343dfb25b714052edca4edaf68`:

- Windows NSIS `Mklink-AI-Probe-v0.4.1-836d8ea3-block-read-x64-Setup.exe`, 185,920,601 bytes;
  SHA-256 `c7da398e94f415dddafe853c7adedab91afec19f344b9529ce1f2be0bdc58806`.
- Full Skill `Mklink-AI-Probe-v0.4.1-block-read-test-836d8ea3.zip`, 99,668,695 bytes;
  SHA-256 `683c417f65d6721e7352718328da43d540a136de9123142bbe607756a005481b`.

Overwrite installation exited 0, preserved user settings, and matched all
3,640 payload files. The global Skill matched all 2,638 archive files, retained
5,339 user files and exposed 47 MCP tools. The complete 7,059-target/2,224-blob FLM,
4,800-SVD-target Pack and nine original-hash XML catalogs passed validation.

Frozen CLI/MCP, catalog/security queries, health, 38 compiled assets and all
41 native Web files passed. The real browser dashboard loaded. The native app
ran with Windows-only PATH, without host Python in its process tree, and exited
normally, releasing its listeners. It remained disconnected during UI checks.

Archive and source checks found no temporary timing module/hooks; the frozen
PYZ was also inspected for the module and timing names in each affected code
object. Normal error diagnostics remain. Evidence: `native-qualification.json`.

Installed frozen MCP independently established MUX on the first read and first
write, verified the 128-byte write/readback and entire 4 KiB restoration, then
physically disconnected. A persistent installed SDK client attached to this
frozen backend performed the same finite latency cases (20 calls each, zero
failed calls); the idle MCP client was attached during this run. This is an
additional installed result, not a replacement selected to improve the source
benchmark. Jitter remains substantial; P95 below is descriptive for n=20 only.

| Operation | Bytes | Min ms | Median ms | P95 ms | Max ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| status | 0 | 2.957 | 4.085 | 14.973 | 15.341 |
| read | 4 | 6.864 | 15.093 | 19.728 | 20.337 |
| read | 32 | 7.226 | 8.861 | 20.238 | 25.294 |
| read | 128 | 7.138 | 18.017 | 20.828 | 25.117 |
| read | 4096 | 10.640 | 21.568 | 29.159 | 48.573 |
| write | 4 | 7.314 | 18.523 | 19.819 | 42.243 |
| write | 32 | 7.495 | 8.471 | 18.869 | 19.033 |
| write | 128 | 7.538 | 18.024 | 19.089 | 27.574 |
| write_verified | 128 | 11.370 | 21.716 | 23.772 | 23.962 |

The final buffer was restored, `device_closed=true`, and this host session
released the probe to the firmware session for the separately requested
SuperWatch period/throughput comparison. No merge, version bump, signing, tag,
release, update pointer or firmware publication. The product-source Feedback
and Shared runtime CI runs both passed; documentation commits are separate.

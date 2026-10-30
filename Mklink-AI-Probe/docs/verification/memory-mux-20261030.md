# Memory MUX preference — 2026-10-30

Product source: `d59dbceb`, shared branch `codex/v0.4.2-fixes`, draft PR #66.
Version remains 0.4.1; this is local candidate work, not a formal release.

## Behavior

Ordinary `Device.read_memory` and `write_memory` previously used native memory
frames only after another operation had established MUX. They now negotiate on
the first operation and reuse the same bridge. Shared API request/response shapes,
optional write verification, target leases and capture ownership remain intact.
Variables, named peripheral snapshots and batched reads use this same reader.

Only firmware without the advertised capability uses the legacy path. Capability
query errors, failed handshakes, native timeouts and uncertain writes propagate;
they never trigger text fallback or replay. Cached capability support cannot
switch an active legacy stream or failed command port into MUX. Explicit
`flush_memory` retains its existing batch and ownership contract.

The shared client now budgets ordinary writes for either legacy 30-byte batches
or native 128-byte frames, including optional readback. This addresses the legacy
4 KiB write whose HTTP deadline expired while backend work was still in progress.
An expired request is still not replayed.

Local HTTP openers are reused per thread. Each request retains its own endpoint,
token and body. Proxy routing remains disabled; default TLS verification remains
enabled. This removes repeated Windows certificate-context construction even
though the destination is loopback HTTP.

Skill guidance directs AI to the shared APIs and automatic transport selection,
without a dummy capture or raw serial commands. No firmware change is needed for
these native memory opcodes.

## Regression evidence

- Related-suite run: 2,155 passed; one existing HPM project fixture still selected
  unsupported 1 MHz. Updated that fixture to supported 4 MHz. The complete flash
  test file, bridge capabilities and new HTTP reuse tests subsequently passed
  (26 tests). The runtime/MUX change does not modify the clock validation rule.
- Final focused run: 207 passed, covering memory negotiation, HTTP reuse,
  flush compatibility, shared SDK/CLI/MCP and Skill instruction boundaries.
- New tests cover first read and first write, one claim and bounded native chunks,
  old firmware, capability-query errors, handshake/read/write timeout poisoning,
  uncertain target writes, legacy stream conflicts, real API write/readback,
  per-thread HTTP isolation, fresh credentials and single-attempt failures.
- Skill quick validation and builder prerequisites passed.

Test runs that contain fixture links were retained under the configured build
root by the repository wrapper, rather than recursively deleting linked paths.

## Source hardware evidence

Ordinary V4 with existing private candidate firmware and STM32H7; 30 MHz profile.
This is a different probe/target from the preceding HPMLINK/HPM5301 XML test.
The firmware session released ownership before this run. No firmware/Flash, VCC,
OTP, halt or reset operation was performed.

The board's 216,776 Flash bytes were compared to the project's AXF before writes.
Only the first 128 bytes of the user's dedicated 4 KiB `memory_test` buffer were
modified. The entire 4 KiB was verified against its original pattern afterward.
Both first-read and first-write tests started after an explicit legacy version
query had removed the MUX marker; each operation established `MLX1` without any
capture. The shared client disconnected with `device_closed=true`.

End-to-end source shared SDK measurements, 20 repetitions per case:

| Operation | Bytes | Median ms |
| --- | ---: | ---: |
| Device status | — | 3.79 |
| Read | 4 | 16.73 |
| Read | 32 | 15.95 |
| Read | 128 | 15.23 |
| Read | 4096 | 173.11 |
| Write acknowledgement | 4 | 17.52 |
| Write acknowledgement | 32 | 21.38 |
| Write acknowledgement | 128 | 16.41 |
| Write plus readback | 128 | 21.33 |

The preceding firmware-session A/B used the same public APIs and hardware:
text read 4 bytes 74.01 ms and write 128 bytes 1,563.06 ms; pre-fix MUX read 4
bytes 41.62 ms and write 128 bytes 45.12 ms. These finite sequential runs are
latency evidence, not sustained-throughput guarantees. Its separate offline
measurement found opener construction at 23.83 ms versus ASGI at 0.117 ms.

Local raw artifacts: `memory-mux-20261030/source-hardware.json`, focused JUnit
reports and the coordinated firmware session's `latency-20261030` reports.

The new MUX preference was not re-tested on an HPM target in this run because
the connected board was STM32H7. Existing HPM XML and CPU/capture evidence remains
in `hpm-svd-dump-stop-20261030.md` and `hpm-skill-audit-20261029.md`.

## Candidate and installed qualification

Both local candidates use product source `d59dbceb`:

- Windows NSIS: `Mklink-AI-Probe-v0.4.1-d59dbceb-mux-x64-Setup.exe`, 185,919,353 bytes,
  SHA-256 `02f3a3e1a6f8f084a4be925ea822d29d03fdcade6db19e0b4c7560b4e830d12b`.
- Full Skill: `Mklink-AI-Probe-v0.4.1-mux-test-d59dbceb.zip`, 99,667,921 bytes,
  SHA-256 `7215c18bfe7db46a5febb84a3c72e65c50ebf011d206580342314e9d19fd34d5`.

NSIS overwrite exited 0 and preserved user settings; all 3,640 installed files
matched. The installed Skill matched all 2,638 archive files, retained 5,339 user
files and exposed 47 MCP tools. Both packages retained validated 7,059 FLM targets,
2,224 blobs, 4,800 Pack/SVD targets and nine original-hash HPM XML series.

Windows-only PATH qualification passed frozen CLI/MCP, peripheral catalog and
security metadata, health and production assets. Native UI showed a healthy
backend; a real browser loaded the packaged dashboard. All 41 native Web files
matched and no host Python process was in the native process tree. Normal close
released all MKLink processes and listeners.

The installed frozen MCP/backend independently passed first read and first write
MUX negotiation without capture, 128-byte write/readback, full 4 KiB restoration,
and explicit disconnect with `device_closed=true`. Raw evidence is in
`installed-hardware.json`; package, install, smoke and shutdown reports are in the
same local artifact directory. No official asset, update pointer, tag or firmware
was published; no version bump. Existing Windows unknown-publisher and Unix
qualification limits remain.

## Follow-up boundary

The user subsequently requested stage timing/IPC optimization and a single
4 KiB native read. Those changes are a new follow-up; this candidate still uses
the original 128-byte native read chunks. The firmware session owns protocol and
firmware changes. Host/firmware must agree on capability bit 6 and opcode 0x16,
validate bounded large CRC replies and preserve old-firmware compatibility before
claiming this follow-up complete. The installed `d59dbceb` candidate is the
verified baseline and should not be confused with unbuilt follow-up source.

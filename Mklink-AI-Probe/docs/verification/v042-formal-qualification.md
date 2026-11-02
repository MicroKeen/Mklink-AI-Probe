# 0.4.2 formal release qualification

Candidate qualification passed; this document does not declare publication.
The maintainer explicitly authorized Windows/Skill and the four probe firmware
releases after acceptance. Public relay and new Linux/macOS builds are outside
this release task. Existing 0.4.1 artifacts remain immutable.

## Source and installation

Product source `1ca9b8fd`; candidate source `90e676db` adds documentation only.
The full final suites passed: 6,453 Python tests, two optional skips, and 1,182
GUI tests. Production Web, frozen backend, Rust and NSIS builds passed.
All three required checks passed on the exact candidate commit.

The unsigned candidate was installed over the existing Windows application.
Its 3,647 payload files matched; two settings files were preserved. The complete
Skill update matched 2,647 managed files and preserved 5,340 user files. The
installed host and Skill agreed on protocol 53, 56 MCP tools and 126 capabilities.
All 42 current Web files matched the compiled output. Frozen startup and MCP
worked with a Windows-only PATH and without a host Python child process.

## Real UI and target checks

- All three SuperWatch controls use the search-variable Eye/EyeOff paths, 15 px
  icons, 24 px transparent buttons and matching visible/hidden colors. Hiding
  and showing from each surface synchronized the other two without deselecting
  the four variables or stopping acquisition.
- RTT titles, encoding, display mode, counters, log controls, pause and collapse
  occupy one toolbar row at the tested desktop size, including two channels.
- Single/rising, normal/falling, auto/both, auto-timeout, manual-force and disabled
  trigger states were exercised in the real browser. Original trigger settings
  were restored. Observation timeouts are retained in the evidence, not counted
  as application failures or silently discarded.
- Real RTT and serial JSONL files were loaded through the browser file chooser,
  played at 10x, sought to beginning/end and exited. Sending was disabled while
  replaying. RTT replay contained 49 frames; serial replay contained two.
- On HPMLink V4/HPM5301, all 14 advertised JTAG settings acknowledged and read
  the expected Flash bytes. The original 30 MHz setting was restored. This is
  command/read validation, not a new electrical frequency measurement.
- The complete 52,988-byte target image matched its binary. RAM pattern and
  360 MHz core-clock checks passed. Built-in HPM5300 and manual vendor XML both
  resolved and read six GPIO input/output/enable registers. No GPIO drive change
  was performed.
- Concurrent RTT and four-channel SuperWatch passed: 71,680 binary RX bytes and
  286 TX bytes matched exactly; local logs preserved their bytes and reported no
  loss. SuperWatch recorded 8,334 samples with no read errors and continued after
  recording stopped.
- A virtual Windows serial pair passed 4,096 bytes in each direction. Actual GUI
  recording then preserved a 27-byte send/echo exactly. This does not establish
  physical UART or RS485 wiring qualification.

## Final candidate acceptance

SystemView passed three standalone and three concurrent rounds, each requesting
60 seconds with one START and natural STOP/drain. Each recorded exactly one
TRACE_START and TRACE_STOP, no parser loss, no new target drops and no MUX loss.
The concurrent rounds also ran four-channel SuperWatch with zero read errors.
The firmware chat completed the standalone rounds; the host chat completed
concurrent rounds after confirming exclusive device ownership. No target reset,
counter clearing or clock writes were used during these rounds.
The previous startup overflow and target drop-count failure remain retained.
Two new preflight failures
(wrong status endpoint, then the GUI's old STM32 ELF after reconnect) occurred
before target I/O. The harness endpoint was corrected; the matching HPM ELF was
explicitly selected in the GUI. These are not counted as capture rounds.

Native directory selection and local RTT recording passed: 13 RX records,
819 bytes, zero loss and a complete end marker. One real GUI flash completed
erase/program/verify/reset, automatically restored RTT, SuperWatch and Trace,
and each stream made progress afterward. The full 52,988-byte image read back
exactly. Its one temporary file was deleted, with no retained files or cleanup
errors; the pre-existing root files and MICROKEEN volume label were unchanged.
The validation harness initially used the wrong cleanup-receipt field; its
failure was preserved and the remaining read-only checks were completed without
another flash. Normal native exit released all 13 owned processes, both backend
ports and the startup record.

Final signed artifacts must be rebuilt from clean reviewed main,
installed and verified before publishing. Cloud and Git update indexes activate
only after all corresponding immutable downloads pass hash checks.

## Firmware evidence and limits

The four pinned candidates are MicroLink V2.9.3, V3.6.8, V4.7.2 and HPMLink
V4.7.2. Their source integrations and hashes are tracked in the release catalog
and designated firmware chat's release audit. Earlier V2/V3/ordinary V4 tests
remain bounded to their recorded host and fixtures; they are not relabeled as
new-host hardware tests. See the existing release matrix and traffic reports.

No blanket claim is made for every MCU, fresh physical cold-plug on every final
firmware, long-duration soak, physical serial/RS485, offline-button execution,
ISP, power switching or OTP. Existing confirmations and visible loss accounting
remain in force. Shanghai protection stays at 90 GiB warning / 95 GiB stop,
with the existing cycle, ledger and November 26 expiry preserved.

Raw logs, images, local device identities and build artifacts remain outside Git
in the formal qualification archive. No new private keys are created.

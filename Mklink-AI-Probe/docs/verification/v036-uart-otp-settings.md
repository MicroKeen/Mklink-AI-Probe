# HPM5301 UART OTP settings — 2026-10-21

Host implementation: PR [48](https://github.com/MicroKeen/Mklink-AI-Probe/pull/48).
The UART settings workflow is implemented through ROM `write-memory` with
explicit confirmation and ROM readback. **No physical OTP programming was
performed by either task.** Simulation, physical read-only preflight and
installation checks below are distinct evidence.

## Behavior and protocol

After reading, the UART panel accepts user Word 69–79 and a complete desired
32-bit value. JTAG value/range validation is reused. No-op changes and clearing
existing bits are rejected; the preview shows expected, current, desired and
added bits. No BIN, SD or JTAG connection is needed.

Firmware API v2 is required for writing. API v1 remains usable for read-only
preflight and cannot authorize programming. Each qualified result must match
HPM5301 CHIP_ID, ROM 0x56010200, SoC 0x56010000, OTP memory ID 0x20000,
`write_method=rom_write_memory`, and `verification_source=rom_otp`. The raw
HARD_LOCK group bit blocks writing when set. Unknown transient locks and
fuse/shadow read provenance stay unknown; ROM enforces write protection.

The server stores the exact change behind a 60-second single-use token, bound
to probe, port, generation and part. New reads/previews invalidate old tokens;
expiry, selection changes and failed or successful consumption prevent reuse.
The user must confirm the displayed irreversible change. Before execution the
host reruns preflight, and firmware rechecks expected value while owning the
same UART operation. One command writes the complete desired value; delta is
only the change preview. ROM success and matching complete readback are both
required. Success means ROM OTP readback matches, not independent direct-fuse
verification. No automatic retry, JTAG fallback, permanent-lock command, target
reset or VCC change is introduced.

If an attempted write fails, the UI reports that OTP may already have changed
and instructs reading before any further operation. ROM rejection, unknown
write outcome, failed readback and mismatched readback have distinct messages;
available ROM write status is preserved.

## Corrected implementation decision

The initial preflight-only source f2075267/Web04cc85e9 required direct fuse and
all transient lock states before writing. The user clarified in the firmware
chat that OTP uses `write-memory`. This supersedes that overly restrictive
host policy: lack of direct register access does not establish that the ROM
write command is unsupported. Source 64da676d/Web1bc5e76e implements API v2;
the combined source 2b99001f also includes explicit uncertain-write errors.
The historical invalid-register-range trace remains valid evidence about that
read path only. No RAM helper is needed or executed for this implementation.

## Automated and browser verification

- Initial direct-write source: 316 affected Python and 84 GUI tests passed.
  Combined candidate including error messages: 330 Python tests passed across
  OTP, offline ISP, shared UART and runtime logging. Final parser refinement:
  111 tests passed; combined GUI repeat: 84 passed. Counts overlap.
- Tests cover API capability downgrade, stale expected values, known locks,
  invalid bit changes, exact target/protocol fields, single-use tokens,
  cancellation resource lifetime, unknown outcomes, ROM failure, readback
  mismatch and no retries. The previously failing CI windowless logging case
  passed locally with the full logging file; CI evidence is recorded separately.
- TypeScript/Vite and local NSIS builds passed. Existing Pack overlap,
  dependency deprecation and chunk-size warnings remain.
- Chrome used production Web and real host routes/parsers with simulated CDC.
  It displayed unknown locks, enabled confirmation after a valid preview and
  completed a simulated write with the ROM-readback success message. Commands
  showed initial preview, fresh preflight and exactly one commit. Console had
  no errors; the simulated server exited with no leases and the tab closed.
  Earlier browser checks cover unavailable v1 preview and edit invalidation.
- The first preflight fixture omitted probe identity metadata, causing a disk
  status KeyError. It was corrected and final production checks repeated.

Logs and local fixtures are under `F:/MKLink-Build/reports` with prefixes
`uart-otp-write-` and `uart-otp-settings-`. Linked test scratch was retained for
manual inspection, including run-20261021-192313-edb24f09 and
run-20261021-192408-5e18af21; no forced cleanup.

## Physical firmware validation

Firmware [62d4bd6](https://github.com/Aladdin-Wang/MicroLink_Plus/commit/62d4bd6),
draft [PR9](https://github.com/Aladdin-Wang/MicroLink_Plus/pull/9), implements
the bounded write command, full desired-value payload, final ROM status and
readback. Native firmware build and production C protocol/ownership tests pass.
UF2 SHA256:
`a1110d7453b3753cf47f0c5e3be9818e2d0131770acdc95e97d511b4e8f81556`.

The delegated task upgraded the probe, then invoked the source host API
read/plan for Word69 expected0/desired1. The plan was qualified with a
60-second token and truthful unknown lock/read semantics. Another read
invalidated the token and confirmed all eleven values remained zero. No
program request was sent; JTAG remained disconnected, and the backend stopped
normally. See its [contract](https://github.com/Aladdin-Wang/MicroLink_Plus/blob/62d4bd6/microlink_app/docs/hpm-uart-otp-user-contract.md)
and [report](https://github.com/Aladdin-Wang/MicroLink_Plus/blob/62d4bd6/microlink_app/docs/verification/hpm-uart-otp-write-20261021.md).

Physical programming needs the user to choose and confirm an exact word and
value. No target OTP/lock/Flash or voltage was changed during this host task.
Multi-round physical board-swap testing was not repeated. No public release,
official tag/channel, signing, global Skill update or PR merge is performed.

## Local package qualification

Installation details are appended after the candidate qualification completes.

## Official-style OTP workspace

Source 8ebc017c / Web 19eb1329 follows the read/write views, indexed Word grid,
column count, custom start/count/value editor and word,value CSV format in the
[official article](https://doc.hpmicro.com/service-support/technical-articles/216)
and local v0.6.0 manual section 2.1.3. UART uses a separate wide dialog; HPM JTAG
configuration now renders a separate HPM component, sharing the Word grid.
ARM option-byte forms remain separate. Only HPM5301 user words 69–79 are writable;
boot/security/key templates outside that range are not enabled.

A batch preview stores all exact changes in one bound, single-use token. All
words are preflighted again before the first write; each word also gets the
existing immediate preflight and firmware guard. Programming is sequential,
not atomic. The first failure stops later words and reports completed words,
the failed/uncertain word and untouched remaining words. Drafts are consumed
on dispatch; there is no automatic replay. Single-word and batch tokens cannot
be interchanged. Unchanged imported values are omitted from the write plan;
CSV zero/empty values are skipped like the official format. Unsupported words,
duplicate indices, invalid lengths and bit clearing are rejected.

125 OTP Python tests and 194 affected GUI tests passed; TypeScript/Vite passed.
Production Chrome against simulated CDC verified the independent dialog,
unknown lock display, two-word custom editor, exact diff, explicit confirmation
and success for words 69/70; zero console errors. The first screenshot exposed
a global CSS margin reset; explicit dialog centering was added. CSV chooser
automation timed out and reset the browser tool, so native chooser completion
is not claimed. CSV parsing/roundtrip is covered by unit tests. Fixture stopped
normally with no resource leases; no physical target was accessed.

## 2026-10-21 独立页签和覆盖安装

OTP 已从弹窗改为独立页签（源935746c4/Web a8f14d95）。组合338 Python、194 GUI及TS/Vite通过；IAB生产页面模拟双字写入成功，切换镜像/OTP页签会作废旧令牌。原生CSV选择器未完成自动验收。

组合源73fccac2/Web f1695c2c已管理员覆盖安装，2026-10-21 20:42:52+08退出0。归档目录为构建根artifacts/v036-local-isp-73fccac2，安装包SHA256为20c211f4628e21e73131054b66eb55082e3f1c390d792f14f324f4d8e17c703e。提取和实装检查通过：202 Python源、41 Web资源、四载荷一致，冻结CLI/SVD/MCP/HTTP、无宿主Python和正常退出通过。Windows包未签名，未公开发布。用户已打开测试；未实际烧写OTP、锁或改变VCC。

用户随后要求重新组织整个脱机页：左侧共享下载器/芯片/协议和参数，右侧镜像与OTP页签，并按官方工具扩展HPM型号和OTP功能。这是后续开发范围，不能把上述安装验收当作扩展功能已完成。

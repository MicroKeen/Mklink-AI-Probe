# 0.4.2 formal release — 2026-11-02

The Windows application, complete Skill, standard Site Agent assets and four
probe firmwares are published. The formal Windows installer was installed over
the local test build; the global Skill was replaced with the same released
payload. Cloud, GitHub and Gitee update indexes are active and publicly verified.

## Source and installation

- PR [66](https://github.com/MicroKeen/Mklink-AI-Probe/pull/66) merged reviewed
  head `5f3cc497b5e34bcef0654307bce6431a0696c46b`. Required feedback, GUI and
  runtime checks passed at that head.
- The formal build source is clean main
  `0e82ba6f47096e1cb1589726f630446af792c0c3`, equal to the fetched remote.
  Annotated tag `v0.4.2` points to that source and must not move.
- Qualification remains scoped to
  [the final candidate report](v042-formal-qualification.md): 6,453 Python tests
  with two optional skips, 1,182 GUI tests, production builds, affected browser,
  native and hardware acceptance. The final main differs from the qualified
  candidate only in three documentation files.
- Rebuilt Web files are not byte-identical to the candidate: commit labels,
  newline-sensitive Vue scope/animation IDs and dependent asset hashes differ.
  All 42 files passed a comparison allowing only those consistently mapped
  build differences; the formal native and browser smoke tests also passed.
- Existing updater-key signing and signature verification passed. This is not
  Windows Authenticode signing. No new private key was created.
- NSIS overwrite installation exited successfully. All 3,647 managed payload
  files matched; two saved settings were preserved. The complete global Skill
  matched all 2,647 archive files and retained 5,340 user-owned files.
- Installed frozen runtime: protocol 53, 56 MCP tools, 126 capabilities;
  HPM catalog, JTAG connection, browser dashboard and bundled SVD queries passed.
  Normal native exit released all 13 owned processes and both backend ports.

## Immutable assets

[GitHub release](https://github.com/MicroKeen/Mklink-AI-Probe/releases/tag/v0.4.2)
contains the standard seven files. The same files are on Tencent COS.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| Mklink-AI-Probe-v0.4.2-x64-Setup.exe | 186039108 | `5ff079bbac008b518d1db409940e95bbfb7102c8e8070f22d4e0b6d610abd766` |
| Mklink-AI-Probe-v0.4.2-Skill.zip | 100274310 | `14af7a5facd84cdb2892c810606c12483840e17529383eff6c716c5385cebc2c` |
| Mklink-AI-Probe-v0.4.2-x64-Setup.exe.sig | 428 | `9cc9bf326fc14fb80c1750696582fbd694e393a3b4428aeaf370079e2a0ca648` |
| MKLink-Site-Agent-v0.4.2-windows-x86_64-portable.zip | 67247542 | `3a6ae485491d90ee0b187e9531737630b739d07764ac796051a273e2489cbc82` |
| MKLink-Site-Agent-v0.4.2-windows-x86_64-portable.manifest.json | 2391 | `a4633072454e51f4f9fc7f5e03ac56cc38a3c6ec314f978e429554405f8630e0` |
| release-manifest.json | 1276 | `71aa9a7bbf379d4a5696441c849d3763c894ef9013c0221fca7918d76407ccaf` |
| SHA256SUMS.txt | 562 | `05634612e005c5e0f1fdc8f77abb866c830f1bee42cf4f663f37d1585a63c7fa` |

The Skill is actually hosted on Gitee. The installer upload was attempted and
Gitee explicitly rejected its size above 100 MB; its index uses the verified
GitHub installer fallback. Signatures, Site Agent and integrity files remain
GitHub-hosted according to the existing Gitee attachment policy.

All four original firmware files are public on Tencent, GitHub and Gitee:

| File | Original build ID | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| MicroLink_V2.9.3.rbl | 2026-11-01T19:34:48 | 366268 | `08ab4061834af5256b6f258c3fa0be5bedeb53c302791064b35733148c9bcbd5` |
| MicroLink_V3.6.8.uf2 | 2026-11-01T21:53:19 | 826368 | `44b1aff26e1d0330fb5d657f1c11412dd5f2ef25010c440dbc782c9e9142c56c` |
| MicroLink_V4.7.2.uf2 | 2026-11-01T21:06:26 | 1540096 | `79a72f682e56cbeac830f5ba4d91adf4ba3ece183fd427b1198b40f08b76db86` |
| HPMLink_V4.7.2.uf2 | 2026-11-01T22:37:10 | 1617920 | `f06af5979cec580e9d6d48050d3705e825c6a7851d978be249acbac830e0117c` |

Firmware sources were integrated separately: V2 `ac0c780b` (PR 6), V3
`8c162351` (PR 8), V4/HPMLink `840ce328` (PR 17). Their original bytes and
build IDs were preserved. Existing firmware attachments and index-branch
history were retained. MicroLink V4 and HPMLink V4 remain distinct families.

## Public acceptance and cloud protection

- Full public downloads of all released files matched size and SHA-256.
  All eleven Tencent files passed signed direct and public-domain GET, HEAD
  and Range checks, with the public domain proven to redirect to COS.
- Cloud stable, GitHub `release` and Gitee `updates` indexes agree on 0.4.2,
  signatures, installer/Skill hashes and source. Both firmware indexes match
  on all three providers. Indexes activated after their downloads were verified.
  Preview remains absent (404); old 0.4.1 assets were not replaced.
- The unchanged official 0.4.1 Skill updater installed public 0.4.2 twice in
  isolated environments: normal Tencent defaults, and actual Gitee fallback
  with cloud/GitHub manifest requests unavailable. Each verified all 2,647
  files, preserved a user file, reported no update on the next check, and
  passed MCP/SVD queries without opening hardware.
- A one-second resolver outage test verified all eleven Nginx fallback routes;
  the service restarted in `finally`. Subsequent GET/HEAD checks again selected
  COS for all eleven files. Public Git backup bytes also matched.
- The [download center](https://download.microkeenai.com/) was checked in a
  real browser: latest host/Skill 0.4.2, all four firmware entries, correct family
  labels and download links. Historical catalog entries remained unchanged.
- SCF retains its previous logic and role, with eleven exact asset read grants
  added. The served asset count is 39 (previously 28). No permanent credentials,
  public bucket exposure, ledger reset or alarm changes were introduced.
- Shanghai remains 90 GiB warning / 95 GiB stop. Subscription expiry remains
  Beijing 2026-11-26 00:00; without verified renewal it does not automatically
  reopen. Monitoring delay means this is not an absolute billing cap.

The expanded signed health document reached about 72 KB. The server's old
64 KiB read bound therefore rejected it and correctly selected Git fallback.
The resolver bound was raised to 256 KiB while retaining bounded reads and all
lease, expiry, cycle and host checks. Oversized/malformed/fetch failures still
clear cached health. Nineteen guard/resolver tests passed, and deployed resolver
SHA-256 is `0396ceab7be33b1ea0146507cc2d0208881446fd5b41737936fe34728012dc0d`.
This maintainer-only correction does not change the immutable desktop/Skill tag
or require replacing the released assets. Old server configurations were backed
up outside the web root before changes. An initial oversized console activation
command did not run; the final compact command checked both before/after catalog
hashes, preserved history and completed with exit code zero.

## Evidence and limits

The local formal archive `v042-formal-20261102` retains qualification, signed
build/install, public-download hashes, channel proofs, both updater tests,
server deployment/fallback results and website screenshots. Its final
`publication/release-complete.json` passed. Raw logs, local hardware identities,
screenshots, temporary signed URLs and binaries are not committed.

Earlier V2/V3/ordinary V4 hardware tests keep their recorded host/fixture scope;
they are not relabeled as new formal-host cold-plug tests. The final HPMLink/HPM
qualification includes six Trace rounds and GUI flash with automatic
RTT/SuperWatch/Trace recovery, complete readback and temporary-file cleanup.
Retain historical loss/failure evidence and the other bounds in the qualification
report. No new Linux/macOS builds, public relay work, VCC, OTP or security writes
were included. Restart an existing AI client to load the replaced global Skill.

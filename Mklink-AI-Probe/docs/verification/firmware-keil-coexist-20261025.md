# MicroLink Keil coexist firmware publication — 2026-10-25

The maintainer authorized independent formal firmware publication of MicroLink
V4.7.1, V3.6.7 and V2.9.2. HPMLink remains V4.7.0. Application/Skill 0.3.6
release assets, tags and update pointers were not rebuilt or changed.

## Change and qualification boundary

The delivered firmware preserves bounded per-AP CSW/TAR tracking across Keil
AP switches and avoids treating debug-register writes as programming. Actual
RAM writes and uncertain/error/evicted AP state retain the capture protection.
This addresses RTT/SuperWatch status 6 during Keil coexistence.

The firmware delivery reports SES 8.24 builds, 17 software suites each for V4
and V3, and 13 for V2. UF2/RBL framing and checksums were independently checked
again before upload. The core logic had previous V4/H743/Keil hardware evidence;
these three exact upgraded binaries were **not reflashed in this publication**.
V3/V2 qualification here is software/build only. No hardware was operated.

| Product | Build identity | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| MicroLink V4.7.1 | 2026-10-25T17:32:28 | 1545216 | 018586f97a9a40cbf2bdbbfb60522640a2f6a84c14ca89ebae2a824d79c8f597 |
| MicroLink V3.6.7 | 2026-10-25T17:31:51 | 815104 | 49a58fd7df1542bda179b8b4fa19cf2ed92cef4564f6029ee3085d67dd5175b6 |
| MicroLink V2.9.2 | 2026-10-25T17:32:00 | 365384 | 6a4d13ce3dc29633645c6674ea2bb34f2f09a6e0a9231edb0865ee1103d66563 |

Build identities were extracted from the actual delivered firmware strings,
not inferred from file timestamps. Source commits recorded by delivery:
V4 `6e20f640f2f0338d9faedb74817eed4c2abf503f`,
V3 `5fd4c204dca75e5fc77ebeabfbb2ee273c17dbc0`,
V2 `7144d0abd6764d71cbeeeef094fd69f6d105bbf4`.

## Published channels and ordering

All three immutable assets were appended to the existing `firmware-assets`
Release in both `MicroKeen/Mklink-AI-Probe` and `Aladdin-Wang/Mklink-AI-Probe`,
and to the existing Gitee release. All nine mirror downloads passed complete
size/SHA-256 verification. No existing asset or tag was replaced.

Tencent objects use `/mklink/firmware/releases/20261025/` below the stable
`https://download.microkeenai.com` domain. All three new files and unchanged
HPMLink passed complete GET/SHA-256 and signed HEAD/size validation.
Unsigned direct COS reads of the new files return 403.

`latest.json` and `latest-v2.json` were published only after their assets were
verified. Both documents were read back identically from Tencent, both GitHub
raw channels and Gitee (eight public index checks). Channel commits:

- MicroKeen firmware: `fb0869df6ec83b0c7a1e3d84320e5e6dd167c058`.
- Aladdin-Wang firmware: `91e30a4df8e9ea03493c5a163435259b1232121b`.
- Gitee firmware: `4cda45e` (normal fast-forward push).

## Existing traffic protection preserved

The existing Shanghai guard now covers 14 assets, retaining all 11 earlier
assets. Its IAM policy adds only exact GET/HEAD access to the three new files.
The guard code is unchanged apart from this asset list. Budget cycle, counters,
private state, 8 GiB warning, 9 GiB stop, expiry latch and 180-second leases are
unchanged; the state was never reset. No new key or SSH access was created.

Three exact Nginx routes and resolver fallback entries were appended. The
HEAD/cache fix remains present. Nginx configuration validation passed. A brief
resolver-stop exercise verified GET and HEAD for each new route redirect to
the exact Gitee asset; the service was restored in a finally block. Public
health then reported ready with all 14 resources.

## Source checks and remaining integration

49 firmware publication/upgrade/revision tests passed. An initial metadata
check rejected a descriptive build ID; this was corrected to the binary's
actual timestamp before any index was published. HPMLink metadata is unchanged.

The source catalog and delivery pin assertion are submitted via a normal PR;
this publication does not authorize merging other desktop changes. The source
catalog PR does not repack the existing application or Skill: their live remote
firmware indexes already expose the new versions.

Dot was notified to update the website's current firmware entries and preserve
old versions, images, categories and backup links. Notification is confirmed;
website deployment is tracked separately. The separate Thunder download-client
compatibility investigation is not changed by this firmware publication.

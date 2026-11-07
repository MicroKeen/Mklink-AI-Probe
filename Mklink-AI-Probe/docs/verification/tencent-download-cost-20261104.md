# Tencent download traffic and latest-only Lighthouse service

## Final authorized behavior

On 2026-11-04 the owner requested 99% of the newly expanded COS traffic budget,
cost diagnosis, latest-only storage on the Shanghai Lighthouse server, and
default latest-version checks for desktop/Skill. The owner subsequently chose
to remove only the package calendar cutoff, retaining COS and the 99% budget,
acknowledging possible pay-as-you-go charges after package expiry.

- Warning: 189 GiB / 202,937,204,736 bytes.
- Stop: 207.9 GiB / 223,230,925,209 bytes, integer floor of 99% of 210 GiB.
- SCF and resolver: `enforce_package_expiry: false`. No calendar reset, usage
  reset, stop-latch clearing, automatic package discovery, or credential change.
- Every-minute SCF and 180-second GET/HEAD leases remain enabled. Native error
  alarm retains the same object, recipients and daily repeat; its name/remark
  now describe the revised policy.
- Latest formal assets are served directly by the existing Shanghai Lighthouse
  server. Historical paths and missing-local-file fallback continue to COS,
  then existing verified Git sources if the COS lease is unavailable.
- Stable remains 0.4.2; local 0.4.3 development was not published. Existing
  manifests, signed artifacts, website links and client endpoints are unchanged.

## Traffic and cost evidence

The COS console showed three mainland external-outbound packages: 10 + 100 +
100 GiB. The first 110 GiB expire at the end of November 25, the new 100 GiB at
the end of December 4. Cancelling our date cutoff does not extend those packages.

Downloaded resource-package deduction details total **99.85389809 GiB through
November 3**, rather than a current-day final bill. Daily totals:

| Date | Deducted GiB |
| --- | ---: |
| Oct 25 | 4.04087487 |
| Oct 26 | 8.80065761 |
| Oct 27 | 14.06973883 |
| Oct 28 | 8.33886014 |
| Oct 29 | 9.99235380 |
| Oct 30 | 4.30405956 |
| Oct 31 | 3.61305022 |
| Nov 1 | 2.65104544 |
| Nov 2 | 32.82202239 |
| Nov 3 | 11.22123523 |

The Nov 2 peak coincides with the 0.4.2 release. Nginx logs from Oct 24–Nov 4
contained 3,059 relevant release/firmware requests from 528 distinct IPs,
including 274 GETs for the 0.4.2 installer and 126 for its Skill ZIP. The files
are 186,039,108 and 100,274,310 bytes; these download counts plausibly explain
substantial traffic, but redirect counts are not completed-download counts.
The highest-IP request count was 132; no single IP dominated those logs.
Small firmware-index checks accounted for many requests and are not equivalent
to downloading full packages.

COS access logging was off. Historical direct-COS accesses and actual transferred
bytes per client cannot be reconstructed from redirect logs, so abuse is not
ruled out. Do not claim a proved bot/hotlink attack or a precise completion rate.
The raw monitor-derived cumulative total was below the settled package deduction
total; its cause was not established. A verified checkpoint now uses
107,217,306,669 bytes (ceiling of the billed GiB converted to bytes), exclusive
boundary 2026-11-04 00:00 Asia/Shanghai. Subsequent monitoring is added without
clearing prior high-water usage.

The existing Lighthouse console showed unlimited traffic, 200 Mbps peak, and
40 GiB disk, with about 32.08 GiB free before migration and 31.75 GiB afterward.
Same-region COS resolved to internal address 169.254.0.47 on that host. Serving
popular latest files locally removes their normal COS external-download usage,
using the already purchased server bandwidth. Historical/fallback COS downloads,
storage, requests and SCF remain separately billable. No CDN or new package was
purchased. A Hong Kong/overseas 10 GiB storage package showed zero use while the
only bucket is Shanghai; review its renewal/refund eligibility separately.

Official billing context: [COS traffic/package FAQ](https://cloud.tencent.com/document/faq/436/30747)
explains that packages add quota rather than extend duration and same-region
internal traffic is free. This does not imply every billing item is free.

## Deployment and verification

Eleven current formal files (seven 0.4.2 assets plus four Nov 2 firmware files)
were copied from COS over the server's internal route. Every byte size and
SHA-256 matched `v042-release-handoff.md`. Total: 357,916,269 bytes / 341.34 MiB.
Staging stayed outside the web root, and Nginx was backed up, syntax-tested and
reloaded. Backup: `/opt/mklink-latest-cache/20261104-224628/nginx-before.conf`.
Three local latest-index hashes were unchanged. Pre-existing unique legacy
files totaling about 100 MiB were preserved; no full history was copied locally.

- All eleven public HEAD responses: 200, exact advertised size, source header
  `lighthouse-latest`. All eleven GET Range checks: 206, correct 16-byte range.
- Historical 0.4.1 installer and 0.4.0 Skill: HEAD 302 to Shanghai COS.
- Temporarily moving the small current signature outside the web root caused
  real GET and HEAD fallback to COS; signed HEAD and 16-byte Range succeeded.
  The file was restored in `finally`, then local HEAD returned 200 again.
- Deployed resolver compiled/restarted successfully, reported active with
  package expiry disabled, and retained historical COS HEAD routing.
- Final SCF bundle was read back from the console after deployment and compared
  to the generated source. Fresh public health remained open/ready, with no
  signed URLs logged in evidence.
- Guard/resolver unit suite: 25 passed, including optional-date behavior, exact
  99% boundary, short-lease expiry, no-reset latching, billing calibration, and
  69 days of checkpoint advancement. The last seven days remain re-queryable;
  gaps beyond 30 days fail closed pending verified billing reconciliation.
- GUI startup/updater checks: 18 passed. Python updater checks: 32 passed and
  one pre-existing release-version consistency failure because this development
  branch has application 0.4.3 and Site Agent 0.4.2. No version was changed to
  hide that unrelated development/release mismatch.
- The installed 0.4.2 Skill performed a fresh live default-source check, found
  stable 0.4.2 and correctly reported no update. No installation or downgrade.

During the earlier SCF console diagnostic attempt, focus on the wrong editor
briefly deployed test-event JSON as function source. Full generated code was
restored immediately and subsequently replaced by the verified final bundle;
fresh leases, public routes and deployment readback were checked afterward.
Short-lived lease and fallback behavior limited the interruption; no claim is
made that every client request during that interval was observed.

Local detailed evidence is under `F:/MKLink-Build/reports/cos-audit-20261104/`;
raw private logs, account configuration, screenshots and deployment scripts are
not committed. No firmware/device operation, signing, new release or merge.

## Limits and maintenance

99% is a soft cumulative budget, not a guaranteed billing cap: monitoring and
settlement lag, already-issued links and in-flight transfers can cause overage.
The seven-day monitoring overlap cannot recover corrections older than its
anchor; reconcile with actual billed deductions when necessary. The usage
limit remains fixed until another reviewed change; purchasing a new package
does not automatically alter it, and crossing a month boundary never resets it.

Future formal publications must replace the managed latest local set and verify
archives before retiring the preceding files. Desktop and Skill continue to
discover stable latest by default. This change does not make a development
checkout a formal release or authorize future publications automatically.

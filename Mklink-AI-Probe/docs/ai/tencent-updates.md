# Tencent download service and preview qualification

The primary download origin is `https://download.microkeenai.com`.
Windows installers and the complete public Skill ZIP use immutable version
directories under `/mklink/releases/`. GitHub and Gitee remain fallback manifest
sources; keeping their URLs does not imply a new candidate was uploaded there.

## Channels

- Stable: `/mklink/stable/latest.json`. Do not create or advance this pointer
  without explicit formal publication authorization.
- Preview: `/mklink/preview/latest.json`. Only an explicitly opted-in client
  checks this pointer. Preview publication does not create Git tags or Releases.
- Skill/CLI/MCP: set `MKLINK_UPDATE_CHANNEL=preview` in the test process only,
  or pass the standalone updater's `--manifest-url` arguments explicitly.
  Unset the variable to return to stable. The cache records the ordered source
  list, so switching channels or source priority forces a new check.
- Desktop: build with `--preview-updates` together with `--bundle` (signed)
  or `--local-bundle` (unsigned). The builder changes only the test build's
  first manifest endpoint and restores the tracked stable configuration even
  when the build fails. Do not distribute this opted-in installer as stable.

The two fallback endpoints retain their existing release-channel URLs. During
0.3.6 preview qualification they still describe the latest formal release;
clients must not downgrade merely because a fallback is older.

## Deployment

The existing server uses BT Nginx. The independent virtual host is
`/www/server/panel/vhost/nginx/download.microkeenai.com.conf`, serving
`/www/wwwroot/download.microkeenai.com`. Existing website configuration is
unchanged. The download host uses its own Let's Encrypt certificate and
`/etc/cron.d/mklink-download-cert-renew` runs the root-only
`/opt/mklink-download/renew-cert.py` daily, renewing with 30 days remaining.
Private keys and ACME account material stay on their owning machines.

Use the existing Tencent console/TAT access; do not provision SSH credentials.
Stage the latest approved files directly on the Shanghai host in a non-served
directory using the existing authorized publication transfer. COS is the
historical archive. When restoring an existing archived file, use the same-region
internal endpoint after verifying its DNS. Never print signed COS query strings.
Check byte sizes, SHA-256 values, installer signature, and Skill payload before
moving the complete directory into an unused immutable release path. Build
the standard updater JSON using `build_latest_document`, with identical binary
and advertised versions, and atomically replace only the explicitly authorized channel pointer after
HTTPS GET/hash and Range checks succeed. JSON responses use `Cache-Control:
no-store`; immutable files use long-lived caching. Directory listing is off.

## Latest-only Lighthouse delivery (2026-11-04)

The owner requires the Shanghai server to keep the latest formal application,
complete Skill, Site Agent and latest firmware per supported model. Historical
versions stay in COS and the verified GitHub/Gitee archives. The existing
Lighthouse package has unlimited traffic and a 200 Mbps peak; current latest
files occupy 357,916,269 bytes (341.34 MiB). This does not change formal versions,
file contents, signatures, or client-facing URLs.

Exact latest-file Nginx locations serve the verified local file with `try_files`
and `X-MKLink-Download-Source: lighthouse-latest`. Missing local files enter a
named resolver location with the existing COS/Git fallbacks. Historical exact
locations continue through the resolver. Keep `proxy_cache off` and
`proxy_cache_convert_head off` in resolver locations and preserve their static
Git fallback on 502/503/504. Keep TLS and certificate renewal unchanged.

For each later authorized publication, stage and hash-check the new complete
asset set first, verify HEAD/GET/Range, and publish the stable index last. Then
retire the preceding managed local set only after its COS/Git copies and exact
historical routes are verified. Do not accumulate full version history on the
server or purge unknown/unique legacy files. The initial migration preserved
about 100 MiB of pre-existing legacy files; it did not add historical packages.
Keep only small configuration/inventory backups outside the web root. This is
a release operation, not a new automatic release or permission to advance tags.

Desktop `App.vue` checks for updates at startup; its first manifest endpoint is
the stable download-domain index. The installed Skill already checks on first
load using `ping(force_update_check=True)` or `skill_update.py check --force`.
These checks discover the latest formal release by default; preview remains
opt-in. Installation still follows the existing user-consent flow.

The COS budget is currently 189 GiB warning / 207.9 GiB stop (99% of the reviewed
210 GiB). The owner explicitly cancelled the package-date cutoff on 2026-11-04:
both SCF and resolver use `enforce_package_expiry: false`, while 180-second
leases, cumulative accounting and the stop latch remain. Packages themselves
still expire, so later downloads can incur pay-as-you-go charges. Lighthouse
latest-file service is independent of this COS budget and calendar policy.
See `docs/verification/tencent-download-cost-20261104.md` for evidence and limits.

Use the existing updater signing key locally for authorized signed update
tests. Never upload that key. Only Windows NSIS and the complete Skill ZIP are
required unless the maintainer explicitly requests other platform installers.

## Test requirements

Verify TLS, size/hash, partial download, missing-file behavior and both fallback
manifest paths. Exercise the standalone Skill updater on an isolated older
installation and preserve all bundled FLM and Packs. Exercise the native Tauri
updater from a genuinely older test build, including signature validation,
installation, relaunch and a second no-update check. A current 0.3.6 client
correctly reports no update for a 0.3.6 manifest; do not fake a higher manifest
version to force an update. For preview-only qualification, verify all formal
Tencent/GitHub/Gitee pointers retain their previously published contents.

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

Upload files to a non-served staging directory through authenticated SSH/SFTP.
Check byte sizes, SHA-256 values, installer signature, and Skill payload before
moving the complete directory into an unused immutable release path. Build
the standard updater JSON using `build_latest_document`, with identical binary
and advertised versions, and atomically replace only the preview pointer after
HTTPS GET/hash and Range checks succeed. JSON responses use `Cache-Control:
no-store`; immutable files use long-lived caching. Directory listing is off.

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
version to force an update. Verify the formal Tencent pointer remains absent
and the GitHub/Gitee formal pointers do not change.

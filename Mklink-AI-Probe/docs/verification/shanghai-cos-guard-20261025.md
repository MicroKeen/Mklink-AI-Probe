# Shanghai COS download migration and budget guard

## Scope

The maintainer authorized moving the existing 0.3.6 assets to Shanghai, warning
at 8 GB, stopping COS release downloads at 9 GB, retaining GitHub/Gitee fallbacks,
and never automatically resuming after an unrenewed package expires. No new
private key, SSH login, firmware operation, binary rebuild or release/tag update.

## Deployed infrastructure

- Private bucket: `mklink-downloads-shanghai-1300298079`, `ap-shanghai`.
- 11 immutable formal files: seven application/Skill/Site Agent release files
  plus the four previously published V2/V3/V4 firmware files.
- SCF: `mklink-shanghai-download-guard`, default namespace, Python 3.10, 128 MB,
  reserved concurrency one, 120-second timeout, no CLS, zero async retries.
- Timer: `mklink-budget-every-minute`, enabled, every minute.
- Runtime role: `MKLinkShanghaiGuardRole`; exact asset GET/HEAD, two state writes,
  monitoring reads only. Obsolete custom-alarm permission removed.
- Native alarm: `MKLink-Shanghai-COS-8GB-9GB`, `policy-olhpcalo`, SCF version
  `$LATEST`, error count > 0, one minute, daily repeat, owner's email/SMS template.
- The existing download domain routes exact release paths to a loopback resolver
  at 18736; Nginx has static backup redirects for service failures.
- Service: `mklink-cos-resolver`, unprivileged, `/opt/mklink-cos-resolver`.
  Previous Nginx config archived outside the web root before syntax-tested reload.
- Public update manifests, website paths and formal signatures remain unchanged.
- The purchased mainland 10 GB package runs from 2026-10-25 00:00:00 through
  2026-11-25 23:59:59 Asia/Shanghai. Exclusive expiry is 1795622400. No calendar
  reset or automatic renewal is implemented. Thresholds use 8/9 GiB.

## Verification

- 14 targeted tests passed: warning/stop boundaries, monotonic usage, latched
  stop, expiry/no reset, API shape failures, lease expiry, write order, native
  warning preserving downloads, stop closing them, malicious URL/path rejection.
  The guard suite is also included in shared-runtime CI. The 70 feedback/Skill
  boundary tests and repository-memory validation passed locally.
- Controlled warning test produced an actual Tencent alarm-history entry at
  10:05. Production warning/stop thresholds were restored afterward. Notification
  configuration verified; this does not prove delivery to the owner's phone.
- All 11 Shanghai objects downloaded in full and matched the formal local
  SHA-256 and size; signed HEAD passed. Initial HEAD 403 was traced to the
  separate `cos:HeadObject` action and fixed on the same exact resource set.
- The resolver's initial directory permission issue was fixed by placing only
  the public code/config in a separate readable directory; root-only deployment
  archive permissions were preserved.
- Server DNS resolved COS to 169.254.0.47 (same-region internal route).
- Public release/Skill/firmware URLs returned Shanghai signed redirects;
  unknown release path returned 404.
- Stopping the resolver in a try/finally test caused Nginx to redirect to GitHub
  and Gitee, then the service restarted successfully.
- Temporarily disabling the timer let a real issued lease expire. COS returned
  403 for the expired URL, and the public download host selected GitHub/Gitee.
  The every-minute trigger was re-enabled afterward.
- At 10:22, fresh production health showed `open: true`, `reason: ready` and
  354,955,902 measured bytes, including the full-download verification traffic.
  This also confirms the observed monitoring delay; usage was not immediately
  visible after the downloads.
- Dot was notified at 10:21 and acknowledged the requested scope. The
  request keeps stable download-domain paths, GitHub/Gitee backups and historical
  versions, and prohibits hard-coded COS signed URLs or infrastructure changes.
  Dot's earlier deployment report identifies website commit
  `fccbfd41843e5817d77da2fe9ce45c6099dcb980` and MicroBoot draft PR #12; its
  follow-up confirmed 20 stable-domain links, retained backups/history/model
  separation, matching metadata, and nine historical downloads returning 200
  with matching sizes. Dot reported no website changes were needed.
- Stable application/Skill and both firmware indexes returned 200 and retained
  stable download-domain paths, so the existing clients use the new resolver.

## Remaining closure

- Closing the old Hong Kong bucket's public ACL requires Tencent's account
  identity verification. The console was left at the owner's WeChat QR prompt.
  Do not report the old bucket private until the save completes and public reads
  are rejected. The retired Shanghai `kk-1300298079` also requires identity
  verification. Its two 2020 files (`start.png`, `timg.jpg`) remain untouched;
  permanent deletion requires action-time confirmation under the browser policy.
- Monitor data is delayed; ongoing transfers and issued URLs can finish, so this
  is a budget guard with a buffer, not a strict total-cost cap. Health reads,
  storage, requests and SCF costs remain separate.

Local evidence and deployment config live under the configured build root's
`artifacts/shanghai-download-guard`; screenshots and signed URLs are not committed.

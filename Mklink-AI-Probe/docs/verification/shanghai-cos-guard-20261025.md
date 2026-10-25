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

## Old-bucket closure and review

- The owner completed Tencent identity verification. The Hong Kong bucket is
  now private; anonymous HEAD requests to all 11 old formal resource paths
  returned 403. It remains a private archive, not an active download source.
- The retired Shanghai `kk-1300298079` was first made private; both `start.png`
  and `timg.jpg` returned 403. After the owner's explicit action-time confirmation,
  the two files were permanently cleared and the empty bucket deleted. The
  console reported success and the bucket list contains only the Hong Kong
  archive and the new Shanghai download bucket.
- PR #53 head `96b6818edbc610db5b6354b2022c6d572646a259` passed all three CI
  jobs (feedback, GUI and runtime). Later closure-record edits change documents
  only. The PR remains open for maintainer integration; no release/tag changed.
- Final public HEAD verification found inherited Nginx `proxy_cache cache_one`
  converting HEAD to GET: loopback HEAD and direct signed HEAD returned 200,
  but public HEAD received a GET signature and returned 403. All 11 resolver
  locations now explicitly disable proxy caching and HEAD conversion. The
  original config was archived, `nginx -t` passed and reload succeeded.
  All 11 public HEAD redirects now return 200 with exact file sizes; public
  GET Range redirects return 206 with matching first 16 bytes. This supplements
  the earlier complete SHA-256 checks rather than repeating large downloads.
  A subsequent resolver-down test confirmed GET and HEAD both select the exact
  GitHub/Gitee backups; the service restarted successfully in the test's finally
  block. Dot was sent the final old-bucket and proxy-fix status at 11:49.
- After deleting the old Shanghai bucket, its URL returned 404/NoSuchBucket.
  Later protection runs remained `ready` with cumulative usage 355,040,478 bytes;
  the deleted bucket's monitoring dimension did not break the current cycle.
- Monitor data is delayed; ongoing transfers and issued URLs can finish, so this
  is a budget guard with a buffer, not a strict total-cost cap. Health reads,
  storage, requests and SCF costs remain separate.

Local evidence and deployment config live under the configured build root's
`artifacts/shanghai-download-guard`; screenshots and signed URLs are not committed.

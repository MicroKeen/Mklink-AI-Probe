# COS download budget guard

Maintainer infrastructure only. These files must not enter the installed Skill
or desktop runtime. The formal release binaries and signatures are unchanged.

## Components

- `index.py`: SCF entry `index.main_handler`. Reads the persisted budget state,
  sums COS `InternetTraffic` over the purchased package's actual validity window,
  saves the usage high-water mark and any stop latch, then publishes a short lease.
- `cloud_api.py`: stdlib TC3/COS clients using SCF temporary role credentials.
  No SSH key, permanent API secret, or public function URL is needed.
- `bundle.py`: combines the source and a reviewed deployment config into one
  inline-editable Python file. This avoids requiring a separate public code bucket.
- `resolver.py`: loopback HTTP redirect service on port 18736. Refreshes the
  public health object every ten seconds. Unknown paths return 404. Missing,
  stale, closed, wrong-cycle or malformed leases use the configured backup URL.
- `test_guard.py`: boundaries, latching, expiry, API failure, write ordering,
  native alert handling and redirect validation.

## Required deployment configuration

Keep account-specific configuration outside the repository. Guard config fields:
`appid`, `host`, `cycle_id`, `starts_at`, `expires_at`, `warn_bytes`, `stop_bytes`,
`lease_seconds`, `enabled`, `asset_keys`, and `metered_buckets` (bucket/region).
Use epoch seconds for the real purchased package validity interval, not the
calendar month. Provision `_guard/state.json` once with the matching `cycle_id`
and `used_bytes: 0` before the first run. Never reset a live state to unblock it.

The resolver config contains `host`, `cycle_id`, `expires_at`, and an exact
`assets` mapping of request path to a verified GitHub/Gitee fallback URL.
Install it beside `resolver.py`. Both files contain no private credentials.

Run the SCF in the bucket's region, Python 3.10, 128 MB, reserved concurrency one,
120-second timeout, zero asynchronous retries, every-minute timer. No provisioned
concurrency, public function URL, VPC or extra acceleration is required.

The execution role must allow only:

- `monitor:GetMonitorData` on `*` (the API does not provide per-bucket resources).
- `cos:GetObject` and `cos:HeadObject` on exact approved release objects and state.
- `cos:PutObject` on `_guard/state.json` and `mklink/guard/health.json` only.

Keep the bucket private. Its policy allows anonymous `cos:GetObject` on only
`mklink/guard/health.json`. That object includes GET/HEAD URLs valid at most 180
seconds; no permanent secret is included. Do not log signed query strings.

Configure a native SCF-version alarm for invocation error count > 0 in one
one-minute interval, bound to this function and `$LATEST`, with the owner's
verified notification channels. The handler intentionally raises *after* saving
health when usage reaches the warning threshold. This leaves the lease open at
8 GiB and closes it at 9 GiB. Actual execution errors also fail closed and alarm.
The `run` alarm callback is a test seam; production notification is the native
SCF alarm, not the legacy custom-alarm API. Set a daily repeat interval to avoid
per-minute notification spam. Do not infer SMS receipt merely from policy setup.

On the existing download host, run the resolver as an unprivileged service in a
readable dedicated directory (not inside a root-only deployment archive). Confirm
the COS hostname resolves through Tencent's same-region internal network. Route
only exact published file paths through the resolver. Nginx must also have static
known backup redirects for resolver 502/503/504 failures, with `Cache-Control:
no-store`. Set `proxy_cache off;` and `proxy_cache_convert_head off;` explicitly
in every resolver location: an inherited proxy cache otherwise converts HEAD
to GET, producing a GET signature which COS rejects for the client's HEAD.
Preserve the update manifests, website, TLS and certificate renewal.
Save the previous Nginx config outside the web root; validate with `nginx -t`
before reload and restore on validation failure.

## Budget behavior and limitations

The production thresholds are `8 * 1024**3` and `9 * 1024**3` bytes. The state
uses the maximum observed cumulative usage and never resets on month boundaries.
Once quota/expiry stops downloads, increasing the package expiry or restarting
the function does not clear that latch. Renewal requires an operator to verify
the new entitlement and deliberately provision a new cycle/config/state.

This is not a billing hard cap: Tencent monitoring is delayed, already-issued
URLs remain usable for their short lifetime, and in-flight downloads can finish.
The 1 GiB margin reduces risk but cannot guarantee zero overage under arbitrary
load. Storage, requests, SCF execution and other billing items remain separate.
Anonymous health reads still exist after closure; only release download access
is stopped. Retired public buckets/object ACLs must be closed separately.

## Verification and operation

Use `scripts/build_workspace.ps1` with the configured build root to run
`python -m unittest discover -s _maintainer/release/cos_guard -p test_guard.py -v`.
Generate an inline deployment with `python _maintainer/release/cos_guard/bundle.py
CONFIG OUTPUT` through the same wrapper.

Before cutover, verify all signed GET/HEAD downloads and their full SHA-256
against immutable formal artifacts. Also follow both GET and HEAD redirects
through the public download domain, checking HEAD size and a small GET Range;
direct signed-URL checks alone cannot detect proxy method conversion.
Exercise the native alarm using an explicit
temporary test threshold, then restore production thresholds. Test resolver-down
fallback and a real lease-expiry cycle. Restore the timer and verify fresh health
and the public download host after tests. Do not simulate quota by downloading
gigabytes or fabricate production usage measurements.

To close downloads immediately, deploy `enabled: false`, invoke once, and verify
empty URLs/closed health; previously issued URLs still expire normally. To pause
renewal without deployment, disable the timer and wait out the lease. A resolver
failure also selects backups. Restarting after a real stop does not resume COS.

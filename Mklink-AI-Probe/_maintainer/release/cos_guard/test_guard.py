import copy
import unittest
import json
import io
from unittest.mock import patch
import index
import resolver
from index import decide, run, sum_points, STATE_KEY, HEALTH_KEY
from resolver import select_url, LeaseCache, MAX_HEALTH_BYTES


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.config = {"cycle_id": "test", "starts_at": 0, "expires_at": 1000,
                       "warn_bytes": 80, "stop_bytes": 90, "enabled": True,
                       "lease_seconds": 180, "asset_keys": ["release.zip"]}
        self.state = {"cycle_id": "test", "used_bytes": 0}

    def test_warning_and_stop_boundaries(self):
        self.assertFalse(decide(self.config, self.state, 1, 79)["warning"])
        self.assertTrue(decide(self.config, self.state, 1, 80)["warning"])
        self.assertEqual(decide(self.config, self.state, 1, 90)["stop_reason"], "traffic_limit")

    def test_100gb_package_90gb_warning_95gb_stop_preserves_cycle(self):
        gib = 1024**3
        config = {**self.config, "warn_bytes": 90*gib, "stop_bytes": 95*gib}
        previous = {**self.state, "used_bytes": 4*gib}
        self.assertEqual(decide(config, previous, 1, 1)["used_bytes"], 4*gib)
        self.assertFalse(decide(config, previous, 1, 90*gib-1)["warning"])
        warning = decide(config, previous, 1, 90*gib)
        self.assertTrue(warning["warning"])
        self.assertEqual(warning["stop_reason"], "")
        self.assertEqual(decide(config, previous, 1, 95*gib)["stop_reason"], "traffic_limit")
        expired = decide(config, previous, config["expires_at"], 1)
        extended = {**config, "expires_at": 2000}
        self.assertEqual(decide(extended, expired, 1100, 0)["stop_reason"], "package_expired")

    def test_stop_latches_when_metrics_decrease(self):
        stopped = decide(self.config, self.state, 1, 90)
        self.assertEqual(decide(self.config, stopped, 2, 0)["stop_reason"], "traffic_limit")

    def test_210gb_package_99_percent_boundary_preserves_usage(self):
        config = {**self.config, "warn_bytes": 189*1024**3,
                  "stop_bytes": 210*1024**3*99//100}
        state = {**self.state, "used_bytes": 100*1024**3}
        self.assertEqual(decide(config, state, 1, 0)["used_bytes"], state["used_bytes"])
        self.assertEqual(decide(config, state, 1, config["stop_bytes"]-1)["stop_reason"], "")
        self.assertEqual(decide(config, state, 1, config["stop_bytes"])["stop_reason"], "traffic_limit")

    def test_billing_checkpoint_adds_only_subsequent_monitoring(self):
        config = {**self.config, "appid": "test", "billing_checkpoint_at": 300,
                  "billing_checkpoint_bytes": 1000,
                  "metered_buckets": [{"bucket": "a", "region": "test"},
                                      {"bucket": "b", "region": "test"}]}
        def monitor(action, payload, region):
            self.assertEqual(payload["StartTime"], index.iso(300))
            bucket = payload["Instances"][0]["Dimensions"][1]["Value"]
            return {"DataPoints": [{"Dimensions": [{"Name": "bucket", "Value": bucket}],
                                   "Timestamps": [0, 300, 600], "Values": [999, 5, 7]}]}
        with patch.object(index, "cloud_call", side_effect=monitor):
            self.assertEqual(index.measure(config, 600), 1010)
        for changes in ({"billing_checkpoint_at": 601}, {"billing_checkpoint_bytes": -1},
                        {"billing_checkpoint_bytes": float("nan")}):
            with self.assertRaises(ValueError):
                index.measure({**config, **changes}, 600)
        config.pop("billing_checkpoint_bytes")
        with self.assertRaises(ValueError):
            index.measure(config, 600)

    def test_no_calendar_or_expiry_reset(self):
        stopped = decide(self.config, self.state, 1000, 1)
        self.assertEqual(stopped["stop_reason"], "package_expired")
        self.assertEqual(decide(self.config, stopped, 2000, 0)["stop_reason"], "package_expired")
        with self.assertRaises(ValueError):
            decide({**self.config, "cycle_id": "renewed"}, stopped, 2001, 0)

    def test_no_package_deadline_still_caps_lease_and_budget(self):
        config = {**self.config, "enforce_package_expiry": False, "expires_at": 50}
        storage, _, result = self.exercise(79, config=config)
        self.assertTrue(result["open"])
        self.assertEqual(result["expires_at"], 280)
        self.assertEqual(storage[STATE_KEY]["used_bytes"], 79)
        _, _, stopped = self.exercise(90, config=config)
        self.assertEqual(stopped["reason"], "traffic_limit")
        self.assertFalse(stopped["open"])

    def test_rolling_checkpoint_retains_over_31_days_without_reset(self):
        day = 86400
        config = {**self.config, "enforce_package_expiry": False}
        state = dict(self.state)
        def meter(c, end):
            # Two bytes/second, including a nonzero previously settled balance.
            return c["billing_checkpoint_bytes"] + (end-c["billing_checkpoint_at"])*2
        for n in range(1, 70):
            now = n*day
            used, checkpoint = index.meter_with_checkpoint(config, state, now, meter)
            self.assertEqual(used, now*2)
            self.assertLessEqual(now-checkpoint["at"], 7*day)
            state["monitor_checkpoint"] = checkpoint
        # A later authoritative correction supersedes the old derived baseline.
        corrected = {**config, "billing_checkpoint_at": 68*day,
                     "billing_checkpoint_bytes": 200*day}
        used, _ = index.meter_with_checkpoint(corrected, state, 69*day, meter)
        self.assertEqual(used, 202*day)

    def test_missing_history_and_corrupt_checkpoint_fail_closed(self):
        meter = lambda c, n: 0
        for partial in ({"billing_checkpoint_at": 1}, {"billing_checkpoint_bytes": 1}):
            with self.assertRaisesRegex(ValueError, "incomplete billing"):
                index.meter_with_checkpoint({**self.config, **partial}, self.state, 100, meter)
        with self.assertRaisesRegex(ValueError, "history gap"):
            index.meter_with_checkpoint(self.config, self.state, 31*86400, meter)
        state = {**self.state, "monitor_checkpoint": {"basis": [0, 0], "at": 1, "bytes": -1}}
        with self.assertRaisesRegex(ValueError, "invalid persisted"):
            index.meter_with_checkpoint(self.config, state, 100, meter)

    def test_high_water_and_invalid_usage(self):
        self.assertEqual(decide(self.config, {**self.state, "used_bytes": 70}, 1, 20)["used_bytes"], 70)
        for value in (float("inf"),):
            with self.assertRaises(ValueError):
                decide(self.config, self.state, 1, value)

    def test_monitor_failures_never_zero(self):
        for row in ({}, {"DataPoints": []}, {"DataPoints": [{"Dimensions": []}]}):
            with self.assertRaises(ValueError):
                sum_points(row, "bucket", 0, 300)

    def test_period_boundaries_and_empty_series(self):
        row = {"Dimensions": [{"Name": "bucket", "Value": "bucket"}],
               "Timestamps": [0, 300, 600], "Values": [1, 2, 3]}
        self.assertEqual(sum_points({"DataPoints": [row]}, "bucket", 0, 600), 3)
        row.update(Timestamps=[], Values=[])
        self.assertEqual(sum_points({"DataPoints": [row]}, "bucket", 0, 600), 0)

    def exercise(self, usage, state=None, config=None):
        storage = {STATE_KEY: copy.deepcopy(state or self.state)}
        events = []
        def write(key, value):
            events.append(key)
            storage[key] = copy.deepcopy(value)
        result = run(config or self.config, 100, lambda k: storage[k], write,
                     lambda c, n: usage, lambda k, m, e: "signed-" + m,
                     lambda level, s: events.append(level))
        return storage, events, result

    def test_lease_and_latch_write_order(self):
        storage, events, result = self.exercise(90)
        self.assertEqual(events[:2], [STATE_KEY, HEALTH_KEY])
        self.assertFalse(result["open"])
        self.assertEqual(storage[HEALTH_KEY]["urls"], {})
        self.assertIn("stopped", events)

    def test_alert_not_repeated_and_disabled_not_open(self):
        storage, _, _ = self.exercise(80)
        _, events, _ = self.exercise(80, storage[STATE_KEY])
        self.assertNotIn("warning", events)
        _, _, result = self.exercise(0, config={**self.config, "enabled": False})
        self.assertFalse(result["open"])

    def test_expiry_caps_signed_lease(self):
        storage, _, result = self.exercise(0, config={**self.config, "expires_at": 150})
        self.assertEqual(result["expires_at"], 150)
        self.assertEqual(storage[HEALTH_KEY]["urls"]["/release.zip"], {"GET": "signed-GET", "HEAD": "signed-HEAD"})

    def test_missing_state_cannot_reinitialize(self):
        with self.assertRaises(KeyError):
            run(self.config, 100, lambda k: {}[k], lambda k, v: None, None, None, None)

    def test_native_warning_keeps_lease_but_stop_closes_it(self):
        for usage, opened in ((80, True), (90, False)):
            storage = {STATE_KEY: copy.deepcopy(self.state)}
            def io(host, key, value=None):
                if value is None:
                    return storage[key]
                storage[key] = copy.deepcopy(value)
            config = {**self.config, "host": "test.invalid"}
            with patch.object(index.Path, "read_text", return_value=json.dumps(config)), \
                 patch.object(index.time, "time", return_value=100), \
                 patch.object(index, "cos_json", side_effect=io), \
                 patch.object(index, "measure", return_value=usage), \
                 patch.object(index, "signed_url", return_value="signed"):
                with self.assertRaisesRegex(RuntimeError, "budget alert"):
                    index.main_handler({}, None)
            self.assertEqual(storage[HEALTH_KEY]["open"], opened)
            self.assertNotEqual(storage[HEALTH_KEY]["reason"], "guard_error")


class LeaseCacheTests(unittest.TestCase):
    def refresh_once(self, payload, *, failure=None):
        class EndRound(BaseException):
            pass

        class Body(io.BytesIO):
            requested = None

            def read(self, size=-1):
                self.requested = size
                return super().read(size)

        body = Body(payload)
        cache = LeaseCache({"host": "example.invalid"})
        cache.health = {"old": "must not survive a failed refresh"}
        with patch.object(resolver.urllib.request, "urlopen", return_value=body,
                          side_effect=failure), \
             patch.object(resolver.time, "sleep", side_effect=EndRound):
            with self.assertRaises(EndRound):
                cache.refresh()
        if failure is None:
            self.assertEqual(body.requested, MAX_HEALTH_BYTES + 1)
        return cache.health

    def test_release_history_over_64_kib_is_accepted(self):
        health = {"schema": "mklink-cos-lease-v1", "urls": {
            f"/release-{i}.zip": {
                method: "https://example.invalid/release.zip?token=" + "x" * 900
                for method in ("GET", "HEAD")
            } for i in range(39)
        }}
        payload = json.dumps(health).encode()
        self.assertGreater(len(payload), 65536)
        self.assertLess(len(payload), MAX_HEALTH_BYTES)
        self.assertEqual(self.refresh_once(payload), health)

    def test_oversized_response_fails_closed(self):
        payload = json.dumps({"padding": "x" * MAX_HEALTH_BYTES}).encode()
        self.assertEqual(self.refresh_once(payload), {})

    def test_invalid_json_or_non_object_fails_closed(self):
        for payload in (b"{broken", b"[]", b"null"):
            with self.subTest(payload=payload):
                self.assertEqual(self.refresh_once(payload), {})

    def test_fetch_error_clears_cached_health(self):
        self.assertEqual(self.refresh_once(b"", failure=OSError("unavailable")), {})


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.config = {"host": "bucket.cos.ap-shanghai.myqcloud.com", "cycle_id": "test", "expires_at": 1000,
                       "assets": {"/release.zip": "https://github.com/example/release.zip"}}
        self.url = "https://" + self.config["host"] + "/release.zip?q-sign-time=0%3B200"
        self.health = {"schema": "mklink-cos-lease-v1", "cycle_id": "test", "checked_at": 100,
                       "expires_at": 200, "open": True, "urls": {"/release.zip": {"GET": self.url}}}

    def test_ready_and_expired_and_failure(self):
        self.assertEqual(select_url(self.config, self.health, "/release.zip", "GET", 110), self.url)
        for now in (99, 185, 1001):
            self.assertEqual(select_url(self.config, self.health, "/release.zip", "GET", now), self.config["assets"]["/release.zip"])
        self.assertEqual(select_url(self.config, {}, "/release.zip", "GET", 110), self.config["assets"]["/release.zip"])

    def test_no_open_redirect_or_path_traversal(self):
        self.health["urls"]["/release.zip"]["GET"] = "https://evil.example/release.zip?q-sign-time=0;200"
        self.assertEqual(select_url(self.config, self.health, "/release.zip", "GET", 110), self.config["assets"]["/release.zip"])
        self.assertIsNone(select_url(self.config, self.health, "/../secret", "GET", 110))

    def test_no_package_deadline_still_requires_fresh_signed_lease(self):
        config = {**self.config, "expires_at": 50, "enforce_package_expiry": False}
        self.assertEqual(select_url(config, self.health, "/release.zip", "GET", 110), self.url)
        self.assertEqual(select_url(config, self.health, "/release.zip", "GET", 200),
                         config["assets"]["/release.zip"])

    def test_bad_health_and_wrong_cycle(self):
        for changes in ({"open": False}, {"expires_at": None}, {"cycle_id": "old"}, {"urls": {}}):
            self.assertEqual(select_url(self.config, {**self.health, **changes}, "/release.zip", "GET", 110), self.config["assets"]["/release.zip"])


if __name__ == "__main__":
    unittest.main()

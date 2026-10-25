import copy
import unittest
import json
from unittest.mock import patch
import index
from index import decide, run, sum_points, STATE_KEY, HEALTH_KEY
from resolver import select_url


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

    def test_stop_latches_when_metrics_decrease(self):
        stopped = decide(self.config, self.state, 1, 90)
        self.assertEqual(decide(self.config, stopped, 2, 0)["stop_reason"], "traffic_limit")

    def test_no_calendar_or_expiry_reset(self):
        stopped = decide(self.config, self.state, 1000, 1)
        self.assertEqual(stopped["stop_reason"], "package_expired")
        self.assertEqual(decide(self.config, stopped, 2000, 0)["stop_reason"], "package_expired")
        with self.assertRaises(ValueError):
            decide({**self.config, "cycle_id": "renewed"}, stopped, 2001, 0)

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

    def test_bad_health_and_wrong_cycle(self):
        for changes in ({"open": False}, {"expires_at": None}, {"cycle_id": "old"}, {"urls": {}}):
            self.assertEqual(select_url(self.config, {**self.health, **changes}, "/release.zip", "GET", 110), self.config["assets"]["/release.zip"])


if __name__ == "__main__":
    unittest.main()

"""Fail-closed COS download leases. Deploy with reserved concurrency one.

No periodic reset: a renewed package requires a newly reviewed config/cycle ID.
Monitor data is delayed, so this is a budget guard, not a billing hard cap.
"""
import datetime as dt
import json
import math
import time
from pathlib import Path
from cloud_api import cloud_call, cos_json, signed_url

STATE_KEY = "_guard/state.json"
HEALTH_KEY = "mklink/guard/health.json"


def iso(timestamp):
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def decide(config, state, now, measured):
    if state.get("cycle_id") != config["cycle_id"]:
        raise ValueError("cycle mismatch: manual provisioning required")
    if not math.isfinite(measured) or measured < 0 or not math.isfinite(state.get("used_bytes", 0)) or state.get("used_bytes", 0) < 0:
        raise ValueError("invalid usage")
    usage = max(state.get("used_bytes", 0), measured)
    reason = state.get("stop_reason", "")
    if not reason and now >= config["expires_at"]:
        reason = "package_expired"
    if not reason and now < config["starts_at"]:
        reason = "package_not_started"
    if not reason and usage >= config["stop_bytes"]:
        reason = "traffic_limit"
    return {**state, "used_bytes": usage, "stop_reason": reason,
            "warning": usage >= config["warn_bytes"], "checked_at": now}


def sum_points(response, bucket, start, end):
    rows = response.get("DataPoints")
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("missing monitor instance")
    row = rows[0]
    dimensions = {x["Name"]: x["Value"] for x in row.get("Dimensions", [])}
    if dimensions.get("bucket") != bucket:
        raise ValueError("unexpected monitor bucket")
    stamps, values = row.get("Timestamps"), row.get("Values")
    if not isinstance(stamps, list) or not isinstance(values, list) or len(stamps) != len(values):
        raise ValueError("invalid monitor points")
    points = {}
    for stamp, value in zip(stamps, values):
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("invalid monitor value")
        if stamp in points:
            raise ValueError("duplicate monitor timestamp")
        if start <= stamp < end:
            points[stamp] = value
    # A successful empty series means no traffic; API/shape errors never become zero.
    return sum(points.values())


def measure(config, now):
    total = 0
    for item in config["metered_buckets"]:
        # Five-minute summed periods, paginated below the API's 7200-point limit.
        start = config["starts_at"]
        while start < now:
            end = min(start + 7 * 86400, now)
            result = cloud_call("GetMonitorData", {
                "Namespace": "QCE/COS", "MetricName": "InternetTraffic", "Period": 300,
                "StartTime": iso(start), "EndTime": iso(end),
                "Instances": [{"Dimensions": [{"Name": "appid", "Value": config["appid"]},
                                                {"Name": "bucket", "Value": item["bucket"]}]}]}, item["region"])
            total += sum_points(result, item["bucket"], start, end)
            start = end
    return total


def run(config, now, read, write, meter, sign, alarm):
    state = read(STATE_KEY)  # A missing/corrupt state must never reset the budget.
    state = decide(config, state, now, state.get("used_bytes", 0))
    if not state["stop_reason"]:
        state = decide(config, state, now, meter(config, now))
    expires = min(now + config["lease_seconds"], config["expires_at"])
    opened = not state["stop_reason"] and config.get("enabled") is True
    # Persist threshold latch before publishing new links.
    write(STATE_KEY, state)
    health = {"schema": "mklink-cos-lease-v1", "cycle_id": config["cycle_id"],
              "checked_at": now, "expires_at": expires if opened else now,
              "open": opened, "used_bytes": state["used_bytes"],
              "reason": state["stop_reason"] or ("ready" if opened else "disabled"), "urls": {}}
    if opened:
        for key in config["asset_keys"]:
            health["urls"]["/" + key] = {method: sign(key, method, expires) for method in ("GET", "HEAD")}
    write(HEALTH_KEY, health)
    level = "stopped" if state["stop_reason"] else "warning" if state["warning"] else ""
    if level and state.get("notified") != level:
        alarm(level, state)
        state["notified"] = level
        write(STATE_KEY, state)
    return {k: v for k, v in health.items() if k != "urls"}


def main_handler(event, context):
    config = json.loads(Path(__file__).with_name("config.json").read_text())
    now = int(time.time())
    host = config["host"]
    try:
        result = run(config, now, lambda key: cos_json(host, key),
                     lambda key, data: cos_json(host, key, data), measure,
                     lambda key, method, end: signed_url(host, key, method, end, now),
                     lambda level, state: None)
        print(json.dumps(result))  # Never log signed URLs or role credentials.
    except Exception as error:
        # Revoke the published lease immediately where possible. Previous URLs
        # expire on COS even if this write or the whole function fails.
        try:
            cos_json(host, HEALTH_KEY, {"schema": "mklink-cos-lease-v1", "open": False,
                "expires_at": now, "reason": "guard_error", "urls": {}})
        except Exception:
            pass
        print("guard_error: " + type(error).__name__)
        raise RuntimeError("COS guard failed closed") from None
    # Use SCF's native invocation-error metric and its notification policy.
    # Raise outside the fail-closed handler: the 8 GiB warning must leave the
    # current download lease open; the 9 GiB/expiry latch already closes it.
    if result["used_bytes"] >= config["warn_bytes"] or result["reason"] not in ("ready", "disabled"):
        raise RuntimeError("MKLink COS budget alert: " + result["reason"] +
                           "; used_GiB=" + str(round(result["used_bytes"] / 1024**3, 3)))
    return result

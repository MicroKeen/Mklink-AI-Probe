"""Small stdlib-only Tencent clients; credentials come only from the SCF role."""
import datetime as dt
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request


def credentials():
    return tuple(os.environ[k] for k in (
        "TENCENTCLOUD_SECRETID", "TENCENTCLOUD_SECRETKEY", "TENCENTCLOUD_SESSIONTOKEN"))


def mac(key, value, algorithm="sha256", hex=False):
    result = hmac.new(key, value.encode(), algorithm)
    return result.hexdigest() if hex else result.digest()


def cloud_call(action, payload, region="ap-shanghai"):
    sid, secret, token = credentials()
    host = "monitor.tencentcloudapi.com"
    timestamp = int(time.time())
    date = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).strftime("%Y-%m-%d")
    body = json.dumps(payload, separators=(",", ":")).encode()
    content_type = "application/json; charset=utf-8"
    canonical = "POST\n/\n\ncontent-type:" + content_type + "\nhost:" + host + "\n\ncontent-type;host\n" + hashlib.sha256(body).hexdigest()
    scope = date + "/monitor/tc3_request"
    to_sign = "TC3-HMAC-SHA256\n" + str(timestamp) + "\n" + scope + "\n" + hashlib.sha256(canonical.encode()).hexdigest()
    key = mac(mac(mac(("TC3" + secret).encode(), date), "monitor"), "tc3_request")
    headers = {"Content-Type": content_type, "X-TC-Action": action,
               "X-TC-Version": "2018-07-24", "X-TC-Timestamp": str(timestamp),
               "X-TC-Region": region, "X-TC-Token": token,
               "Authorization": "TC3-HMAC-SHA256 Credential=" + sid + "/" + scope + ", SignedHeaders=content-type;host, Signature=" + mac(key, to_sign, hex=True)}
    with urllib.request.urlopen(urllib.request.Request("https://" + host, body, headers), timeout=15) as response:
        result = json.load(response)["Response"]
    if "Error" in result:
        raise RuntimeError("monitor: " + result["Error"]["Code"])
    return result


def signed_url(host, key, method, expires, now=None):
    sid, secret, token = credentials()
    now = int(time.time()) if now is None else int(now)
    key_time = str(now - 30) + ";" + str(int(expires))
    # COS signs the decoded object path, with URL encoding applied to parameters.
    quote = lambda value: urllib.parse.quote(value, safe="-_.~")
    params = {"x-cos-security-token": token}
    query = "&".join(quote(k).lower() + "=" + quote(v) for k, v in sorted(params.items()))
    canonical = method.lower() + "\n/" + key + "\n" + query + "\nhost=" + quote(host) + "\n"
    to_sign = "sha1\n" + key_time + "\n" + hashlib.sha1(canonical.encode()).hexdigest() + "\n"
    sign_key = mac(secret.encode(), key_time, "sha1", hex=True).encode()
    auth = {"q-sign-algorithm": "sha1", "q-ak": sid, "q-sign-time": key_time,
            "q-key-time": key_time, "q-header-list": "host", "q-url-param-list": "x-cos-security-token",
            "q-signature": mac(sign_key, to_sign, "sha1", hex=True), **params}
    return "https://" + host + "/" + urllib.parse.quote(key, safe="/-_.~") + "?" + urllib.parse.urlencode(auth)


def cos_json(host, key, value=None):
    method = "GET" if value is None else "PUT"
    body = None if value is None else json.dumps(value, separators=(",", ":")).encode()
    request = urllib.request.Request(signed_url(host, key, method, int(time.time()) + 60), body,
                                    {"Content-Type": "application/json", "Cache-Control": "no-store"}, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response) if method == "GET" else None

"""Loopback-only download redirector, deployed on the existing download host."""
import json
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def select_url(config, health, path, method, now):
    fallback = config["assets"].get(path)
    if not fallback:
        return None
    try:
        if (health.get("schema") == "mklink-cos-lease-v1" and health.get("open") is True
                and health["cycle_id"] == config["cycle_id"]
                and 0 <= now - health["checked_at"] <= 180
                and now + 15 < min(health["expires_at"], config["expires_at"])):
            url = health["urls"][path][method]
            parsed = urllib.parse.urlsplit(url)
            query = urllib.parse.parse_qs(parsed.query)
            signed_end = int(query["q-sign-time"][0].split(";")[1])
            if (parsed.scheme == "https" and parsed.netloc == config["host"]
                    and urllib.parse.unquote(parsed.path) == path and not parsed.fragment
                    and now + 15 < signed_end <= health["expires_at"]):
                return url
    except (KeyError, ValueError, TypeError):
        pass
    return fallback


class LeaseCache:
    def __init__(self, config):
        self.config = config
        self.health = {}
        self.lock = threading.Lock()

    def refresh(self):
        while True:
            try:
                req = urllib.request.Request("https://" + self.config["host"] + "/mklink/guard/health.json",
                                             headers={"Cache-Control": "no-cache"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = response.read(65537)
                if len(data) > 65536:
                    raise ValueError("oversized health response")
                health = json.loads(data)
                if not isinstance(health, dict):
                    raise ValueError("invalid health")
            except Exception:
                health = {}
            with self.lock:
                self.health = health
            time.sleep(10)


def main():
    config = json.loads(Path(__file__).with_name("resolver-config.json").read_text())
    cache = LeaseCache(config)
    threading.Thread(target=cache.refresh, daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            with cache.lock:
                url = select_url(config, cache.health, path, self.command, int(time.time()))
            self.send_response(302 if url else 404)
            if url:
                self.send_header("Location", url)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_HEAD = do_GET

        def log_message(self, format, *args):
            pass  # Request query strings could contain signed credentials.

    ThreadingHTTPServer(("127.0.0.1", 18736), Handler).serve_forever()


if __name__ == "__main__":
    main()

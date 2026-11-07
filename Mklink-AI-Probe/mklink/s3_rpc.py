"""Authenticated S3 RPC owned by one shared backend. No radio reconfiguration."""
import asyncio
import http.client
import json
import threading
import time
import uuid
from urllib.parse import urlsplit


class Endpoint:
    def __init__(self, node):
        self.node = node
        self.loop = None
        self.thread = None
        self.ble = None
        self.operation_timeout = 30
        self.settled = threading.Event()
        self.settled.set()
        self.inflight = None
        self.http = None
        self.http_lock = threading.Lock()
        self.http_last_use = 0.0

    def open(self):
        if self.node['transport'] != 'ble':
            return
        from mklink.s3_ble import BleEndpoint
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True, name='s3-ble')
        self.thread.start()
        self.ble = BleEndpoint(self.node['address'], self.node['token'])
        self._await(self.ble.__aenter__())

    def _await(self, coroutine):
        if not self.settled.is_set():
            coroutine.close()
            raise ConnectionError('S3 operation still owns IO; no second request')
        self.settled.clear()
        async def bounded():
            try:
                # Covers all fragment writes, metadata reads and response waits.
                return await asyncio.wait_for(coroutine, self.operation_timeout)
            finally:
                self.settled.set()
        self.inflight = asyncio.run_coroutine_threadsafe(bounded(), self.loop)
        try:
            return self.inflight.result(timeout=self.operation_timeout + 5)
        except TimeoutError:
            if not self.settled.is_set():
                self.inflight.cancel()
                self.settled.wait(5)
            # Cancellation ends local work; it never proves the device did nothing.
            raise ConnectionError('S3 operation timeout; outcome unknown, no replay') from None

    def rpc(self, method, params):
        http_status = None
        try:
            if self.ble:
                return self._await(self.ble.rpc(method, params))
            ident = uuid.uuid4().hex
            body = json.dumps(dict(v=1, id=ident, method=method, params=params), separators=(',', ':')).encode()
            with self.http_lock:
                # Retire idle connections before submission, never retry a POST.
                if self.http is None or time.monotonic() - self.http_last_use > 1:
                    if self.http is not None:
                        self.http.close()
                    origin = urlsplit(self.node['address'])
                    cls = {'http': http.client.HTTPConnection, 'https': http.client.HTTPSConnection}[origin.scheme]
                    self.http = cls(origin.hostname, origin.port, timeout=self.operation_timeout)
                try:
                    self.http.request('POST', '/api/v1/rpc', body,
                                      {'Authorization': 'Bearer ' + self.node['token'],
                                       'Content-Type': 'application/json'})
                    with self.http.getresponse() as response:
                        http_status = response.status
                        if not 200 <= http_status < 300:
                            raise ConnectionError('S3 HTTP request rejected')
                        expected = response.length
                        payload = response.read(65537)
                        if len(payload) > 65536 or (expected is not None and len(payload) != expected):
                            raise ValueError('Oversized or incomplete S3 response')
                    result = json.loads(payload)
                    if result.get('v') != 1 or result.get('id') != ident:
                        raise ValueError('S3 reply identity mismatch')
                    if not result.get('ok'):
                        raise ValueError('S3 rejected ' + method)
                    self.http_last_use = time.monotonic()
                    return result['data']
                except BaseException:
                    self.http.close()
                    self.http = None
                    raise
        except Exception:
            # Credential-bearing request/response objects never enter runtime logs.
            status = f'; HTTP {http_status}' if http_status is not None and not 200 <= http_status < 300 else ''
            raise ConnectionError('S3 RPC failed: ' + method + status + '; no replay') from None

    def close(self):
        with self.http_lock:
            if self.http is not None:
                self.http.close()
                self.http = None
        if self.loop is not None:
            if not self.settled.wait(5):
                raise ConnectionError('S3 IO has not exited; ownership retained')
            if self.ble:
                self._await(self.ble.__aexit__(None, None, None))
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                raise ConnectionError('S3 event loop has not exited; ownership retained')
            self.loop.close()
            self.loop = None

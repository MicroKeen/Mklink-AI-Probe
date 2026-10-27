"""Authenticated S3 RPC owned by one shared backend. No radio reconfiguration."""
import asyncio
import json
import threading
import uuid
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ConnectionError('S3 redirects are refused; credentials were not forwarded')


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
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

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
        try:
            if self.ble:
                return self._await(self.ble.rpc(method, params))
            ident = uuid.uuid4().hex
            body = json.dumps(dict(v=1, id=ident, method=method, params=params), separators=(',', ':')).encode()
            request = Request(self.node['address'] + '/api/v1/rpc', data=body,
                              headers={'Authorization': 'Bearer ' + self.node['token'],
                                       'Content-Type': 'application/json'})
            with self.opener.open(request, timeout=30) as response:
                payload = response.read(65537)
            if len(payload) > 65536:
                raise ValueError('Oversized S3 response')
            result = json.loads(payload)
            if result.get('v') != 1 or result.get('id') != ident:
                raise ValueError('S3 reply identity mismatch')
            if not result.get('ok'):
                raise ValueError('S3 rejected ' + method)
            return result['data']
        except Exception:
            # Credential-bearing request/response objects never enter runtime logs.
            raise ConnectionError('S3 RPC failed: ' + method + '; no replay') from None

    def close(self):
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

"""Read-memory adapters sharing the runtime gate and existing target handler.

Only an in-process MemoryCall can avoid internal HTTP encoding. It still passes
through RuntimeGate and its normal session, identity, capture and job admission.
"""
from __future__ import annotations

import asyncio
import json
import time

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse


class MemoryCall:
    def __init__(self, control, arguments, session_id):
        self.control, self.arguments, self.session_id = control, arguments, session_id
        self.result = None
        self.status = None
        self.error_body = bytearray()

    async def execute(self, scope, send):
        from mklink.remote.resource_manager import ResourceError
        from mklink.remote.api import _resource_error_detail
        try:
            self.result = await self.control.app.state.shared_memory_read(
                address=self.arguments['address'], size=self.arguments['size'])
        except ResourceError as error:
            raise HTTPException(409, _resource_error_detail(error)) from error
        # Preserve operation status accounting; no internal JSON response needed.
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})

    async def receive(self):
        # RuntimeGate reads the trusted arguments object, not a synthetic body.
        return {'type': 'http.disconnect'}

    async def send(self, message):
        if message['type'] == 'http.response.start':
            self.status = message['status']
        elif message['type'] == 'http.response.body':
            self.error_body.extend(message.get('body', b''))

    async def run(self):
        from mklink.runtime_api import RuntimeGate
        info = self.control.info
        scope = {
            'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
            'method': 'POST', 'path': '/api/device/read-memory',
            'raw_path': b'/api/device/read-memory', 'root_path': '',
            'query_string': b'', 'scheme': 'http',
            'server': ('127.0.0.1', info['port']), 'client': ('127.0.0.1', 0),
            'headers': [(b'host', f"127.0.0.1:{info['port']}".encode()),
                        (b'x-auth-token', info['token'].encode()),
                        (b'x-mklink-session', self.session_id.encode())],
            'mklink_memory_call': self,
        }
        # The fallback must not execute hardware if a gate path unexpectedly
        # bypasses the explicit MemoryCall operation below.
        async def unexpected(scope, receive, send):
            raise RuntimeError('Memory operation was not admitted')
        await RuntimeGate(unexpected, control=self.control)(scope, self.receive, self.send)
        if self.status is not None and self.status >= 400:
            # Match the existing inner HTTP response's nested error detail.
            raise HTTPException(self.status, json.loads(self.error_body))
        if self.status != 200 or self.result is None:
            raise RuntimeError('Memory operation returned no result')
        return self.result


async def dispatch_read_call(app, control, scope, receive, send):
    """Skip FastAPI/HTTP adaptation for SDK reads, after outer authentication.

    Other capabilities and malformed envelopes use the original application.
    Hardware admission is fully settled before the outer response is sent.
    """
    chunks = bytearray()
    while True:
        message = await receive()
        if message['type'] != 'http.request':
            return
        chunks.extend(message.get('body', b''))
        if len(chunks) > 65536:
            await JSONResponse({'detail': 'Control request exceeds 64 KiB'}, status_code=413)(scope, receive, send)
            return
        if not message.get('more_body', False):
            break
    try:
        body = json.loads(chunks)
    except (ValueError, UnicodeError):
        body = None
    if isinstance(body, dict) and body.get('capability') == 'read_memory':
        try:
            session_id, capability, arguments = control.prepare_call(body)
            result = await control.invoke('POST', '/api/device/read-memory', arguments, session_id=session_id)
            response = JSONResponse(result)
        except HTTPException as error:
            response = JSONResponse({'detail': error.detail}, status_code=error.status_code)
        await response(scope, receive, send)
        return
    replayed = False
    async def replay():
        nonlocal replayed
        if not replayed:
            replayed = True
            return {'type': 'http.request', 'body': bytes(chunks), 'more_body': False}
        return await receive()
    await app(scope, replay, send)


async def refresh_memory_identity(control):
    """Prefetch passive discovery without extending the existing 250 ms TTL.

    A lifecycle change or a newer foreground observation discards this result.
    Expired/missing observations still force normal synchronous admission.
    """
    from mklink.probes import inventory
    key = control._memory_identity_key()
    if key is None:
        return
    revision = getattr(control, '_presence_revision', 0)
    started = time.monotonic()
    try:
        probes = await asyncio.to_thread(inventory)
    except Exception:
        if revision == getattr(control, '_presence_revision', 0):
            control._memory_identity_cache = None
        return
    if (key != control._memory_identity_key()
            or revision != getattr(control, '_presence_revision', 0)):
        return
    presence = control._record_presence(probes)
    if presence['status'] == 'present' and time.monotonic() < started + .25:
        control._memory_identity_cache = (key, started + .25)


def install_memory_channel(api, control):
    """One ordered, read-only channel; each message reenters the full gate."""
    users = 0
    refresher = None

    async def refresh():
        while True:
            await refresh_memory_identity(control)
            await asyncio.sleep(.1)

    @api.websocket('/memory')
    async def memory_channel(ws: WebSocket):
        nonlocal users, refresher
        session_id = ws.headers.get('x-mklink-session')
        probe_id = control.info.get('probe_id') or ''
        instance_id = control.info['instance_id']
        if (ws.headers.get('x-mklink-probe') != probe_id
                or ws.headers.get('x-mklink-instance') != instance_id):
            await ws.close(code=1008)
            return
        try:
            control.validate_session(session_id)
        except HTTPException:
            await ws.close(code=1008)
            return
        await ws.accept()
        users += 1
        if refresher is None:
            refresher = asyncio.create_task(refresh())
        try:
            while True:
                # Idle channels cannot renew a lease or retain an abandoned
                # backend. The ordinary heartbeat remains the only idle renewal.
                session = control.sessions.get(session_id)
                if (session is None or session.expires <= time.monotonic()
                        or control.stopping or (control.info.get('probe_id') or '') != probe_id
                        or control.info['instance_id'] != instance_id):
                    await ws.close(code=1008)
                    return
                try:
                    raw = await asyncio.wait_for(ws.receive_bytes(), timeout=2)
                except asyncio.TimeoutError:
                    continue
                except KeyError:
                    await ws.close(code=1003)
                    return
                if ((control.info.get('probe_id') or '') != probe_id
                        or control.info['instance_id'] != instance_id):
                    await ws.close(code=1008)
                    return
                try:
                    if len(raw) > 16384:
                        raise HTTPException(413, 'Memory request exceeds 16 KiB')
                    try:
                        arguments = json.loads(raw)
                    except (ValueError, UnicodeError) as error:
                        raise HTTPException(422, 'Invalid memory request') from error
                    _, _, arguments = control.prepare_call({
                        'session_id': session_id, 'capability': 'read_memory', 'arguments': arguments})
                    result = await control.invoke('POST', '/api/device/read-memory', arguments,
                                                  session_id=session_id)
                    response = {'status': 200, 'result': result}
                except HTTPException as error:
                    response = {'status': error.status_code, 'detail': error.detail}
                # invoke settles executor ownership and admission before replying.
                await ws.send_bytes(json.dumps(response).encode())
        except WebSocketDisconnect:
            pass
        finally:
            users -= 1
            if not users:
                task, refresher = refresher, None
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

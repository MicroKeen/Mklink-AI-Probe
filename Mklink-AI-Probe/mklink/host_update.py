"""Short, hardware-free admission reservation for an explicit desktop update."""
from __future__ import annotations

import asyncio
import secrets
import time

from fastapi import Body, HTTPException
from starlette.responses import JSONResponse


PREFIX = '/api/runtime/host-update'


class HostUpdateGate:
    TTL = 120.0

    def __init__(self, app):
        self.owner = app
        self.token = None
        self.expires = 0.0
        self.pending = 0

    @property
    def reserved(self):
        if self.token and time.monotonic() >= self.expires:
            self.token = None
        return self.token is not None

    def prepare(self):
        # Runs on the event loop without an await between inspection/reservation.
        from mklink.remote.dashboards import get_managers
        state = self.owner.state.mklink_state
        runtime = getattr(self.owner.state, 'shared_runtime', None)
        device = state.get('device')
        busy = self.pending or (device and device.connected) or any(m.running for m in get_managers().values())
        if runtime:
            busy = busy or runtime.job_busy() or runtime.operation_lock.locked() or runtime.lifecycle_pending or runtime.uart_operations
        if self.reserved or busy:
            raise HTTPException(409, 'Stop acquisition, disconnect the probe and wait for firmware updates or other device operations to finish before updating the app.')
        self.token = secrets.token_hex(24)
        self.expires = time.monotonic() + self.TTL
        return {'token': self.token}

    def renew(self, token):
        if not self.reserved or not secrets.compare_digest(token, self.token):
            raise HTTPException(409, 'App update reservation expired; check device activity again.')
        self.expires = time.monotonic() + self.TTL


class UpdateAdmission:
    def __init__(self, app, gate):
        self.app, self.gate = app, gate

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        method = scope.get('method', 'GET')
        # Heartbeats, detaches, and read-only polling remain available. A held
        # reservation never stops a stream or disconnects a device on its own.
        exempt = path.startswith(PREFIX) or path.startswith('/api/browser-session/') or path in {
            '/_runtime/heartbeat', '/_runtime/detach', '/api/runtime/heartbeat',
        }
        mutation = scope['type'] == 'http' and not exempt and (
            (path.startswith(('/api/', '/_runtime/')) and method not in {'GET', 'HEAD', 'OPTIONS'})
            or path == '/api/probe/firmware-check'
        )
        if not mutation:
            return await self.app(scope, receive, send)
        if self.gate.reserved:
            return await JSONResponse({'detail': 'App update in progress; retry after the app restarts.'}, status_code=409)(scope, receive, send)
        self.gate.pending += 1
        try:
            return await self.app(scope, receive, send)
        finally:
            self.gate.pending -= 1


def install_host_update_gate(app):
    gate = HostUpdateGate(app)
    app.state.host_update_gate = gate
    app.add_middleware(UpdateAdmission, gate=gate)

    @app.post(PREFIX + '/prepare')
    async def prepare():
        result = gate.prepare()
        try:
            runtime = getattr(app.state, 'shared_runtime', None)
            if runtime:
                from mklink.runtime import running_runtimes
                peers = await asyncio.to_thread(running_runtimes)
                if any(peer.get('instance_id') != runtime.info.get('instance_id') for peer in peers):
                    raise HTTPException(409, 'Close other MKLink windows and idle backends before updating the app; never interrupt their firmware jobs.')
            return result
        except BaseException:
            gate.token = None
            raise

    @app.post(PREFIX + '/renew')
    async def renew(token: str = Body()):
        gate.renew(token)
        return {'status': 'reserved'}

    @app.post(PREFIX + '/release')
    async def release(token: str = Body()):
        if gate.reserved and secrets.compare_digest(token, gate.token):
            gate.token = None
        return {'status': 'released'}

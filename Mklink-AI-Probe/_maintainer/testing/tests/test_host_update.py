import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from mklink.host_update import PREFIX, install_host_update_gate


def fixture_app(monkeypatch):
    app = FastAPI()
    app.state.mklink_state = {'device': None}
    monkeypatch.setattr('mklink.remote.dashboards.get_managers', lambda: {})
    install_host_update_gate(app)
    return app


def test_update_admission_is_atomic_with_firmware_work_and_released_after_failure(monkeypatch):
    async def run():
        app = fixture_app(monkeypatch)
        started, finish = asyncio.Event(), asyncio.Event()
        calls = []

        @app.post('/api/probe/firmware-upgrade')
        async def firmware():
            calls.append(1)
            started.set()
            await finish.wait()
            raise HTTPException(400, 'fixture failure')

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as web:
            job = asyncio.create_task(web.post('/api/probe/firmware-upgrade'))
            await started.wait()
            assert (await web.post(PREFIX + '/prepare')).status_code == 409
            finish.set()
            assert (await job).status_code == 400
            reply = await web.post(PREFIX + '/prepare')
            assert reply.status_code == 200
            token = reply.json()['token']
            assert (await web.post('/api/probe/firmware-upgrade')).status_code == 409
            assert len(calls) == 1
            assert (await web.post(PREFIX + '/prepare')).status_code == 409
            assert (await web.post(PREFIX + '/renew', json='wrong')).status_code == 409
            await web.post(PREFIX + '/release', json='wrong')
            assert app.state.host_update_gate.reserved
            assert (await web.post(PREFIX + '/renew', json=token)).status_code == 200
            await web.post(PREFIX + '/release', json=token)
            assert not app.state.host_update_gate.reserved
            assert (await web.post('/api/probe/firmware-upgrade')).status_code == 400
    asyncio.run(run())


@pytest.mark.parametrize('activity', ['connected', 'stream', 'job', 'operation', 'uart', 'lifecycle'])
def test_update_never_stops_active_work(monkeypatch, activity):
    app = fixture_app(monkeypatch)
    runtime = SimpleNamespace(job_busy=lambda: activity == 'job', operation_lock=asyncio.Lock(),
                              lifecycle_pending=int(activity == 'lifecycle'), uart_operations={'x': 1} if activity == 'uart' else {})
    app.state.shared_runtime = runtime
    if activity == 'connected':
        app.state.mklink_state['device'] = SimpleNamespace(connected=True)
    elif activity == 'stream':
        monkeypatch.setattr('mklink.remote.dashboards.get_managers', lambda: {'rtt': SimpleNamespace(running=True)})
    elif activity == 'operation':
        asyncio.run(runtime.operation_lock.acquire())
    with pytest.raises(HTTPException) as error:
        app.state.host_update_gate.prepare()
    assert error.value.status_code == 409
    assert not app.state.host_update_gate.reserved


def test_abandoned_reservation_expires_without_device_io(monkeypatch):
    gate = fixture_app(monkeypatch).state.host_update_gate
    gate.prepare()
    gate.expires = -1
    assert not gate.reserved
    assert gate.prepare()['token']


def test_real_shared_backend_routes_auth_and_blocks_new_connect(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from mklink.remote.api import create_app
    from mklink.runtime_api import install_runtime
    app = create_app(project_root=str(tmp_path))
    install_runtime(app, {'port': 8765, 'token': 'fixture', 'instance_id': 'fixture'})
    monkeypatch.setattr('mklink.runtime.running_runtimes', lambda: [])
    with TestClient(app, base_url='http://127.0.0.1:8765') as web:
        assert web.post(PREFIX + '/prepare').status_code == 401
        web.headers['X-Auth-Token'] = 'fixture'
        result = web.post(PREFIX + '/prepare')
        assert result.status_code == 200, result.text
        assert web.get('/api/device/status').status_code == 200
        assert web.post('/api/device/connect', json={}).status_code == 409
        assert web.post('/_runtime/attach', json={}).status_code == 409
        assert web.post(PREFIX + '/release', json=result.json()['token']).status_code == 200
        monkeypatch.setattr('mklink.runtime.running_runtimes', lambda: [{'instance_id': 'another-window'}])
        assert web.post(PREFIX + '/prepare').status_code == 409
        assert not app.state.host_update_gate.reserved

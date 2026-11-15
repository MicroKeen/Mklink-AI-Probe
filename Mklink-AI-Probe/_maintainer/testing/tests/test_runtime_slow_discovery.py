"""Slow passive OS discovery must not stall leases or weaken identity admission."""
import asyncio
from functools import partial
import threading
import time

import pytest

from test_shared_runtime import runtime, attach
from test_online_flash_api import services


def bind(control):
    control.info['probe_id'] = 'usb-fixture'
    return [{'probe_id': 'usb-fixture', 'port': 'COM9'}]


@pytest.mark.parametrize('switch_during_discovery', [False, True])
def test_online_probe_inventory_does_not_block_gui_lease(runtime, services, monkeypatch, switch_during_discovery):
    import httpx
    from mklink.remote.online_flash_api import create_online_flash_router

    client, control, _, _, app = runtime
    app.include_router(create_online_flash_router(services))
    session = client.post('/_runtime/attach', json={'scope': 'uart'}).json()['session_id']
    rows = bind(control)
    rows[0]['serial_number'] = 'mk'
    entered, release = threading.Event(), threading.Event()

    def inventory():
        entered.set()
        release.wait(4)
        return rows

    monkeypatch.setattr('mklink.probes.inventory', inventory)

    async def enumerate_probes():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8765') as http:
            return await http.get('/api/online-flash/probes', headers={'X-Auth-Token': 'test-secret'})

    pending = client.portal.start_task_soon(enumerate_probes)
    try:
        assert entered.wait(2)
        started = time.monotonic()
        response = client.post('/_runtime/heartbeat', json={'session_id': session})
        assert response.status_code == 200
        assert time.monotonic() - started < 1
        assert not pending.done()
        if switch_during_discovery:
            async def switch():
                app.state.mklink_state['device_generation'] = 1
            client.portal.call(switch)
    finally:
        release.set()
    response = pending.result(3)
    if switch_during_discovery:
        assert response.status_code == 409
        assert 'changed during discovery' in response.json()['detail']
        return
    assert response.status_code == 200
    assert [row['unique_id'] for row in response.json()] == ['mk']


def test_slow_identity_admission_keeps_heartbeat_responsive(runtime, monkeypatch):
    client, control, calls, _, _ = runtime
    session = attach(client)
    rows = bind(control)
    entered, release = threading.Event(), threading.Event()
    def inventory():
        entered.set()
        assert release.wait(5)
        return rows
    monkeypatch.setattr('mklink.probes.inventory', inventory)
    pending = client.portal.start_task_soon(partial(control.invoke, 'POST', '/api/dash/rtt/start', {}, session_id=session))
    try:
        assert entered.wait(2)
        for _ in range(3):
            started = time.monotonic()
            assert client.post('/_runtime/heartbeat', json={'session_id': session}).status_code == 200
            assert time.monotonic() - started < 1.5
            assert not pending.done() and not calls
    finally:
        release.set()
    assert pending.result(3)['status'] == 'started'
    assert calls == ['start']


def test_slow_heartbeat_inventory_is_single_flight_and_missing_probe_revokes(runtime, monkeypatch):
    client, control, _, _, _ = runtime
    session = attach(client)
    bind(control)
    release = threading.Event()
    queries = []
    def inventory():
        queries.append(True)
        assert release.wait(5)
        return []
    monkeypatch.setattr('mklink.probes.inventory', inventory)
    try:
        for _ in range(3):
            assert client.post('/_runtime/heartbeat', json={'session_id': session}).status_code == 200
        assert len(queries) == 1
    finally:
        release.set()
    assert client.post('/_runtime/heartbeat', json={'session_id': session}).status_code == 409
    assert session not in control.sessions


def test_detach_during_heartbeat_discovery_does_not_restore_lease(runtime, monkeypatch):
    client, control, _, _, _ = runtime
    session = attach(client)
    rows = bind(control)
    entered, release = threading.Event(), threading.Event()
    def inventory():
        entered.set()
        assert release.wait(5)
        return rows
    monkeypatch.setattr('mklink.probes.inventory', inventory)
    async def heartbeat():
        import httpx
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=control.app), base_url='http://127.0.0.1:8765') as http:
            return await http.post('/_runtime/heartbeat', json={'session_id': session}, headers={'X-Auth-Token': 'test-secret'})
    pending = client.portal.start_task_soon(heartbeat)
    try:
        assert entered.wait(2)
        assert client.post('/_runtime/detach', json={'session_id': session}).status_code == 200
    finally:
        release.set()
    assert pending.result(3).status_code == 409
    assert session not in control.sessions


@pytest.mark.parametrize('change', ['generation', 'port', 'disconnect'])
def test_changed_connection_during_discovery_never_reaches_hardware(runtime, monkeypatch, change):
    client, control, calls, _, app = runtime
    session = attach(client)
    rows = bind(control)
    entered, release = threading.Event(), threading.Event()
    def inventory():
        entered.set()
        assert release.wait(5)
        return rows
    monkeypatch.setattr('mklink.probes.inventory', inventory)
    pending = client.portal.start_task_soon(partial(control.invoke, 'POST', '/api/dash/rtt/start', {}, session_id=session))
    try:
        assert entered.wait(2)
        async def change_connection():
            if change == 'generation': app.state.mklink_state['device_generation'] = 1
            elif change == 'port': app.state.mklink_state['device'].port = 'COM10'
            else: app.state.mklink_state['device'].connected = False
        client.portal.call(change_connection)
    finally:
        release.set()
    with pytest.raises(Exception, match='changed during discovery'):
        pending.result(3)
    assert not calls

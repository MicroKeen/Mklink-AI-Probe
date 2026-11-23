"""Offline concurrency regressions: real ASGI routes and injected slow disk I/O."""
import asyncio
import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from mklink import frontend_layout, frontend_intents, runtime_frontend
from test_runtime_frontend import broker, report, BASE
from test_frontend_storage import intent


def application(broker):
    app = FastAPI()
    app.state.mklink_state = broker.control.app.state.mklink_state
    broker.control.app = app
    current = runtime_frontend.install_frontend(app, broker.control)
    current.exchange({'report': report(current), 'receipts': []})

    @app.get('/health')
    async def health():
        return {'ok': True}

    return app, current


@pytest.mark.parametrize('operation', ['layout', 'intents', 'intent', 'reply', 'save_layout', 'save_intent', 'layouts', 'named_layout', 'save_named_layout'])
def test_slow_storage_keeps_heartbeat_and_other_window_responsive(broker, monkeypatch, operation):
    app, current = application(broker)
    current.submit_intent(intent(current))
    frontend_layout.save_named_layout(current.target['project_root'], {'name': 'test', 'revision': 0, 'layout': {'version': 1, 'revision': 0, 'panels': []}})
    routes = {
        'layout': (runtime_frontend, 'load_layout', 'GET', '/layout', None),
        'layouts': (runtime_frontend, 'search_layouts', 'GET', '/layouts?query=test', None),
        'named_layout': (runtime_frontend, 'load_named_layout', 'GET', '/layouts/item?name=test', None),
        'save_named_layout': (runtime_frontend, 'save_named_layout', 'POST', '/layouts', {'name': 'test', 'revision': 1, 'layout': {'version': 1, 'revision': 0, 'panels': []}}),
        'intents': (frontend_intents, 'load_intents', 'GET', '/intents', None),
        'intent': (frontend_intents, 'find_intent', 'GET', '/intent?request_id=intent_one', None),
        'reply': (frontend_intents, 'reply_intent', 'POST', '/reply', {'request_id': 'intent_one', 'revision': 0, 'reply': 'checked'}),
        'save_layout': (runtime_frontend, 'save_layout', 'PUT', '/layout', {'version': 1, 'revision': 0, 'panels': []}),
        'save_intent': (frontend_intents, 'save_intent', 'POST', '/intent', intent(current, request_id='second')),
    }
    module, name, method, path, value = routes[operation]
    original = getattr(module, name)

    def slow(*args, **kwargs):
        time.sleep(0.4)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, slow)

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            started = time.perf_counter()
            pending = asyncio.create_task(client.request(method, BASE + path, json=value))
            await asyncio.sleep(0.02)
            assert (await client.get('/health')).status_code == 200
            assert (await client.post(BASE + '/exchange', json={'report': report(current, page_id='other_window'), 'receipts': []})).status_code == 200
            assert time.perf_counter() - started < 0.25
            assert not pending.done()
            assert (await pending).status_code == 200

    asyncio.run(run())


@pytest.mark.parametrize('change', ['target', 'revision'])
def test_intent_revalidates_after_slow_fsync_without_persisting_stale_context(broker, monkeypatch, change):
    app, current = application(broker)
    original = frontend_layout.os.fsync

    async def run():
        entered = asyncio.Event()
        loop = asyncio.get_running_loop()

        def slow(fd):
            loop.call_soon_threadsafe(entered.set)
            time.sleep(0.15)
            return original(fd)

        monkeypatch.setattr(frontend_layout.os, 'fsync', slow)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            pending = asyncio.create_task(client.post(BASE + '/intent', json=intent(current)))
            await asyncio.wait_for(entered.wait(), 2)
            if change == 'target':
                app.state.mklink_state['device_generation'] += 1
            else:
                current.exchange({'report': report(current, revision=2), 'receipts': []})
            response = await pending
            assert response.status_code == 409
            assert response.json()['detail']['code'] == ('WRONG_TARGET' if change == 'target' else 'STALE_REVISION')
            assert frontend_intents.load_intents(current.target['project_root'])['requests'] == []
            assert not list(Path(current.target['project_root']).rglob('*.tmp'))

    asyncio.run(run())


def test_concurrent_layout_and_reply_writes_preserve_revision_cas(broker):
    app, current = application(broker)
    current.submit_intent(intent(current))

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            layouts = await asyncio.gather(*[client.put(BASE + '/layout', json={'version': 1, 'revision': 0, 'panels': []}) for _ in range(4)])
            assert sorted(response.status_code for response in layouts) == [200, 409, 409, 409]
            replies = await asyncio.gather(*[client.post(BASE + '/reply', json={'request_id': 'intent_one', 'revision': 0, 'reply': f'answer {index}'}) for index in range(4)])
            assert sorted(response.status_code for response in replies) == [200, 409, 409, 409]
            winner = next(response.json() for response in replies if response.status_code == 200)
            duplicate = await client.post(BASE + '/reply', json={'request_id': 'intent_one', 'revision': 0, 'reply': winner['reply']})
            assert duplicate.json()['duplicate']
            assert (await client.get(BASE + '/layout')).json()['revision'] == 1

    asyncio.run(run())


@pytest.mark.parametrize('method', ['GET', 'PUT', 'POST'])
def test_storage_never_returns_or_commits_into_a_changed_target(broker, monkeypatch, method):
    app, current = application(broker)
    root = current.target['project_root']
    original = runtime_frontend.load_layout if method == 'GET' else frontend_layout.os.fsync

    async def run():
        entered = asyncio.Event()
        loop = asyncio.get_running_loop()

        def slow(*args):
            loop.call_soon_threadsafe(entered.set)
            time.sleep(0.15)
            return original(*args)

        if method == 'GET':
            monkeypatch.setattr(runtime_frontend, 'load_layout', slow)
        else:
            monkeypatch.setattr(frontend_layout.os, 'fsync', slow)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            payload = {'version': 1, 'revision': 0, 'panels': []}
            pending = asyncio.create_task(client.request(method, BASE + ('/layouts' if method == 'POST' else '/layout'),
                json={'name': 'test', 'revision': 0, 'layout': payload} if method == 'POST' else payload))
            await asyncio.wait_for(entered.wait(), 2)
            app.state.mklink_state['project_root'] = str(Path(root) / 'other_project')
            response = await pending
            assert response.status_code == 409 and response.json()['detail']['code'] == 'WRONG_TARGET'
            assert not (Path(root) / '.mklink/frontend_layout.json').exists()
            assert not (Path(root) / '.mklink/frontend_layouts.json').exists()
            assert not Path(current.target['project_root']).exists()

    asyncio.run(run())

@pytest.mark.parametrize('change,code', [('target', 'WRONG_TARGET'), ('revision', 'STALE_REVISION')])
def test_slow_exchange_keeps_streams_live_and_checks_current_page(broker, monkeypatch, change, code):
    import threading
    from mklink.remote.stream_hub import StreamHub

    app, current = application(broker)
    entered, release = threading.Event(), threading.Event()
    validate = runtime_frontend.validate_report

    def slow(report):
        if report['title'] == 'Slow window':
            entered.set()
            release.wait(2)
        validate(report)

    monkeypatch.setattr(runtime_frontend, 'validate_report', slow)

    async def run():
        hub = StreamHub(2)
        queues = [hub.subscribe(), hub.subscribe()]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            pending = asyncio.create_task(client.post(BASE + '/exchange', json={
                'report': {**report(current, 2), 'title': 'Slow window'}, 'receipts': []}))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                assert (await client.get('/health')).status_code == 200
                for n in range(6):
                    await asyncio.to_thread(hub.publish, bytes([n]), 1)
                    for queue in queues:
                        assert bytes(await asyncio.wait_for(queue.get(), 1)) == bytes([n])
                        queue.task_done()
                assert not pending.done(), 'window validation blocked independent consumers'
                if change == 'target':
                    app.state.mklink_state['device_generation'] += 1
                else:
                    newer = await client.post(BASE + '/exchange', json={'report': report(current, 3), 'receipts': []})
                    assert newer.status_code == 200
            finally:
                release.set()
                response = await pending
                for queue in queues:
                    hub.unsubscribe(queue)
            assert response.status_code == 409 and response.json()['detail']['code'] == code
            assert hub.stats().dropped_batches == 0
    asyncio.run(run())

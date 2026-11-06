import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastmcp import Client

from mklink import runtime, runtime_gui, runtime_mcp
from test_shared_runtime import runtime as backend, attach, call


def info(root, key='a', probe='lobby'):
    return dict(runtime_id='local-' + key * 24, instance_id=key, probe_id=probe,
                project_root=str(root), port=8765, token='long-lived-secret')


def test_selection_reuses_bound_backend_before_lobby(monkeypatch, tmp_path):
    bound, lobby = info(tmp_path, 'a', 'chosen'), info(tmp_path, 'b')
    monkeypatch.setattr(runtime, 'running_runtimes', lambda: [lobby, bound])
    monkeypatch.setattr('mklink.probes.select_probe', lambda selector: {'probe_id': 'chosen'})
    monkeypatch.setattr(runtime, 'ensure_runtime', lambda **kw: pytest.fail('duplicate backend'))
    selected, result = runtime_gui.select_gui_runtime(probe='alias')
    assert selected is bound and result == {'requested_probe': 'chosen'}


def test_endpoint_without_project_is_enriched_from_same_live_instance(monkeypatch, tmp_path):
    current = info(tmp_path)
    del current['project_root']
    monkeypatch.setattr(runtime, 'running_runtimes', lambda: [current])
    monkeypatch.setattr(runtime, 'request', lambda *a, **k: {
        'instance_id': current['instance_id'], 'probe_id': 'lobby', 'project_root': str(tmp_path)})
    selected, _ = runtime_gui.select_gui_runtime(project_root=str(tmp_path))
    assert selected['project_root'] == str(tmp_path)
    assert 'project_root' not in current


def test_multiple_lobbies_require_explicit_identity_and_never_return_secrets(monkeypatch, tmp_path):
    entries = [info(tmp_path, 'a'), info(tmp_path, 'b')]
    monkeypatch.setattr(runtime, 'running_runtimes', lambda: entries)
    selected, result = runtime_gui.select_gui_runtime()
    assert selected is None and result['status'] == 'select_runtime'
    assert 'secret' not in str(result) and 'token' not in str(result)
    assert runtime_gui.select_gui_runtime(runtime_id=entries[1]['runtime_id'])[0] is entries[1]
    with pytest.raises(runtime.RuntimeErrorResponse):
        runtime_gui.select_gui_runtime(runtime_id='local-missing')


def test_existing_project_and_current_probe_are_not_replaced(monkeypatch, tmp_path):
    current = info(tmp_path, probe='one')
    monkeypatch.setattr('mklink.probes.select_probe', lambda selector: {'probe_id': selector})
    with pytest.raises(runtime.RuntimeErrorResponse, match='project differs'):
        runtime_gui.select_gui_runtime(current=current, project_root=str(tmp_path / 'other'))
    with pytest.raises(runtime.RuntimeErrorResponse, match='another probe'):
        runtime_gui.select_gui_runtime(current=current, probe='two')
    with pytest.raises(runtime.RuntimeErrorResponse, match='another probe'):
        runtime_gui.select_gui_runtime(current=current, runtime_id=current['runtime_id'], probe='two')


def test_new_gui_requires_project_and_is_hardware_free(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, 'running_runtimes', lambda: [])
    create = Mock(return_value=info(tmp_path))
    monkeypatch.setattr(runtime, 'ensure_runtime', create)
    with pytest.raises(ValueError, match='project_root'):
        runtime_gui.select_gui_runtime()
    with pytest.raises(ValueError, match='existing directory'):
        runtime_gui.select_gui_runtime(project_root=str(tmp_path / 'missing'))
    runtime_gui.select_gui_runtime(project_root=str(tmp_path))
    create.assert_called_once_with(project_root=str(tmp_path.resolve()), allow_lobby=True, new_window=True)


@pytest.fixture
def launch(monkeypatch, tmp_path):
    current = SimpleNamespace(info=info(tmp_path), session_id='session')
    windows, requests = [], []
    clock = [10.0]
    def request(_info, method, path, payload=None, **kwargs):
        requests.append((method, path, payload))
        if path == '/_runtime/status':
            return {**current.info, 'gui_launch': 1}
        if path == '/api/runtime/control/windows':
            return {'windows': list(windows)}
        if path == '/_runtime/gui-link':
            return {'ticket': 'gui-once', 'expires_in': 60}
        pytest.fail(path)
    monkeypatch.setattr(runtime, 'request', request)
    monkeypatch.setattr(runtime_gui.time, 'monotonic', lambda: clock[0])
    browser = Mock(return_value=False)
    monkeypatch.setattr(runtime_gui.webbrowser, 'open', browser)
    return runtime_gui.GuiLaunch(), current, windows, requests, clock, browser


def test_launch_ack_is_separate_and_pending_open_is_not_replayed(launch):
    gui, client, windows, requests, clock, browser = launch
    first = gui.open(client)
    assert first['status'] == 'awaiting_window' and first['browser_requested'] is False
    assert 'long-lived-secret' not in str(first)
    assert first['open_url'].endswith('#gui-once')
    assert gui.open(client)['status'] == 'awaiting_window'
    assert browser.call_count == 1
    assert sum(path == '/_runtime/gui-link' for _, path, _ in requests) == 1
    clock[0] += 61
    # Late page registration is observable; inspection never starts another browser.
    windows.append({'window_id': 'late', 'name': 'GUI'})
    assert gui.inspect(client)['status'] == 'ready'
    assert gui.open(client)['window_id'] == 'late' and browser.call_count == 1


def test_headless_link_can_be_opened_once_and_explicitly_renewed(launch):
    gui, client, windows, requests, clock, browser = launch
    first = gui.open(client, open_browser=False)
    assert not browser.called
    assert gui.open(client)['open_url'] == first['open_url']
    assert browser.call_count == 1
    clock[0] += 61
    gui.open(client, open_browser=False)
    assert sum(path == '/_runtime/gui-link' for _, path, _ in requests) == 2
    assert browser.call_count == 1


def test_window_choice_and_browser_failure_are_bounded(launch):
    gui, client, windows, requests, clock, browser = launch
    windows.extend([{'window_id': 'a'}, {'window_id': 'b'}])
    assert gui.open(client)['status'] == 'select_window'
    assert gui.open(client, window_id='b')['window_id'] == 'b'
    with pytest.raises(runtime.RuntimeErrorResponse, match='unavailable'):
        gui.open(client, window_id='missing')
    assert not browser.called
    windows.clear()
    browser.side_effect = OSError('private URL must not appear')
    result = gui.open(client)
    assert not result['browser_requested'] and 'private URL' not in str(result)


def test_old_or_replaced_backend_does_not_open_browser(launch, monkeypatch):
    gui, client, windows, requests, clock, browser = launch
    monkeypatch.setattr(runtime, 'request', lambda _i, _m, path, **kw:
                        dict(instance_id='a') if path == '/_runtime/status' else {'windows': []})
    with pytest.raises(runtime.RuntimeErrorResponse, match='lacks GUI launch'):
        gui.open(client)
    monkeypatch.setattr(runtime, 'request', lambda *a, **k: {'instance_id': 'replacement'})
    with pytest.raises(runtime.RuntimeErrorResponse, match='instance changed'):
        gui.inspect(client)
    assert not browser.called


def test_login_ticket_is_authenticated_one_use_and_not_the_runtime_token(backend):
    http, control, hardware, managers, _ = backend
    session = http.post('/_runtime/attach', json={'scope': 'uart'}).json()['session_id']
    ticket = http.post('/_runtime/gui-link', json={'session_id': session}).json()['ticket']
    assert ticket != control.info['token']
    http.headers.pop('X-Auth-Token')
    assert http.post('/_runtime/gui-link', json={'session_id': session}).status_code == 401
    assert http.get('/api/runtime/control/windows').status_code == 401
    reply = http.post('/_runtime/login', json={'token': ticket})
    assert reply.status_code == 200 and 'httponly' in reply.headers['set-cookie'].lower()
    assert http.get('/api/runtime/control/windows').status_code == 200
    assert http.post('/_runtime/login', json={'token': ticket}).status_code == 401
    assert http.post('/_runtime/login', json={'token': '非ASCII'}).status_code == 401
    assert hardware == []


def test_login_tickets_expire_and_are_bounded(backend, monkeypatch):
    from mklink import runtime_api
    http, control, hardware, managers, _ = backend
    session = http.post('/_runtime/attach', json={'scope': 'uart'}).json()['session_id']
    clock = [runtime_api.time.monotonic()]
    monkeypatch.setattr(runtime_api.time, 'monotonic', lambda: clock[0])
    tickets = [http.post('/_runtime/gui-link', json={'session_id': session}).json()['ticket'] for _ in range(8)]
    assert len(set(tickets)) == 8
    assert http.post('/_runtime/gui-link', json={'session_id': session}).status_code == 429
    clock[0] += 61
    assert http.post('/_runtime/login', json={'token': tickets[0]}).status_code == 401
    assert http.post('/_runtime/gui-link', json={'session_id': 'expired'}).status_code == 409
    assert hardware == []


def test_gui_only_lease_can_present_but_cannot_read_hardware(backend):
    http, control, hardware, managers, _ = backend
    session = http.post('/_runtime/attach', json={'scope': 'uart'}).json()['session_id']
    assert call(http, session, 'gui_windows').json() == {'windows': []}
    assert call(http, session, 'read_memory', {'address': '0x20000000', 'size': 4}).status_code == 409
    assert hardware == []


@pytest.mark.parametrize('connect_fails', [False, True])
def test_mcp_gui_then_connect_keeps_same_backend_and_cleans_only_own_lease(monkeypatch, tmp_path, connect_fails):
    selected = info(tmp_path)
    events, clients = [], []
    class Adapter:
        def __init__(self, **kwargs):
            self.info = kwargs['info']; self.session_id = None
            clients.append(self)
        def connect(self, **kwargs):
            events.append(('connect', self, kwargs))
            if kwargs['scope'] == 'target' and connect_fails:
                raise runtime.RuntimeErrorResponse('target busy')
            self.session_id = str(len(clients))
            return {'connected': kwargs['scope'] == 'target'}
        def close(self): events.append(('close', self))
    monkeypatch.setattr(runtime_mcp, 'RuntimeClient', Adapter)
    monkeypatch.setattr(runtime_gui, 'select_gui_runtime', lambda **kw: (selected, {}))
    monkeypatch.setattr(runtime_gui.GuiLaunch, 'open', lambda *a, **kw: {'status': 'awaiting_window'})
    monkeypatch.setattr(runtime_gui.GuiLaunch, 'inspect', lambda *a, **kw: {'status': 'ready'})
    async def scenario():
        async with Client(runtime_mcp.build_server()) as mcp:
            assert (await mcp.call_tool('gui_open', {'action': 'status'})).data['status'] == 'not_open'
            await mcp.call_tool('gui_open', {'project_root': str(tmp_path), 'open_browser': False})
            assert len(clients) == 1
            result = await mcp.call_tool('connect', {'probe': 'chosen'}, raise_on_error=False)
            assert result.is_error == connect_fails
            assert clients[0].info is clients[1].info is selected
            assert events[-1] == ('close', clients[1] if connect_fails else clients[0])
            assert (await mcp.call_tool('gui_open', {'action': 'status'})).data['status'] == 'ready'
            await mcp.call_tool('detach', {})
            assert (await mcp.call_tool('gui_open', {'action': 'status'})).data['status'] == 'not_open'
    asyncio.run(scenario())
    assert events[-1] == ('close', clients[0] if connect_fails else clients[1])


def test_cli_probe_selection_connects_once_before_browser_handoff(monkeypatch):
    from mklink import cli
    selected = {'port': 8765}
    monkeypatch.setattr(runtime, 'ensure_runtime', lambda **kw: selected)
    connect = Mock()
    monkeypatch.setattr(runtime, 'connect_gui_target', connect)
    monkeypatch.setattr(runtime, 'handoff_gui', lambda info, prepare: (prepare(None), True)[1])
    args = SimpleNamespace(host='127.0.0.1', project_root='.', port=8765, probe='chosen',
                           device_port=None, axf=None, no_browser=True)
    cli._cli_gui(args)
    connect.assert_called_once_with(selected, {'axf': None})


@pytest.mark.parametrize('health', [None, {'instance_id': 'replaced'}])
def test_gui_handoff_never_spawns_another_backend_after_instance_loss(monkeypatch, tmp_path, health):
    def request(*args, **kwargs):
        if health is None:
            raise runtime.RuntimeErrorResponse('unavailable')
        return health
    monkeypatch.setattr(runtime, 'request', request)
    monkeypatch.setattr(runtime, 'ensure_runtime', lambda **kw: pytest.fail('unexpected replacement'))
    client = runtime.RuntimeClient(info=info(tmp_path))
    with pytest.raises(runtime.RuntimeErrorResponse, match='changed or exited'):
        client.connect(scope='uart', existing_only=True)

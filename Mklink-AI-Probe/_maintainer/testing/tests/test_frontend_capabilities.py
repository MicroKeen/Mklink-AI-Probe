"""Capability coverage and original-guard parity; device calls are explicit fixtures."""
import copy

import pytest

from mklink.frontend_capabilities import capability_catalog, panel_operations, offline_tools
from mklink.frontend_layout import save_layout, load_layout
from test_shared_runtime import runtime

PATH = '/api/runtime/capabilities/call'


@pytest.fixture(scope='module')
def catalog(tmp_path_factory):
    from mklink.remote.api import create_app
    from mklink.runtime_api import install_runtime
    app = create_app(auth_token='catalog-only', project_root=str(tmp_path_factory.mktemp('catalog')))
    install_runtime(app, {'port': 8765, 'token': 'catalog-only', 'instance_id': 'catalog'})
    from fastapi.testclient import TestClient
    response = TestClient(app, base_url='http://127.0.0.1:8765', headers={'X-Auth-Token': 'catalog-only'}).get('/api/runtime/capabilities')
    assert response.status_code == 200 and response.headers['content-type'].startswith('application/json')
    assert response.json() == capability_catalog(app)
    return {item['name']: item for item in response.json()['capabilities']}


@pytest.mark.parametrize('name', sorted(panel_operations().keys() | offline_tools().keys()))
def test_every_shared_capability_resolves_to_an_actual_route(catalog, name):
    item = catalog[name]
    assert item['available'], (name, item['path'])
    if name in panel_operations():
        assert (item['method'], item['path']) == panel_operations()[name]
    else:
        assert item['method'] == 'OFFLINE'
    assert len(item['revision']) == 64
    assert all(parameter['in'] != 'path' or '{' + parameter['name'] + '}' in item['path']
               for parameter in item['parameters'])


@pytest.mark.parametrize('name', sorted(panel_operations().keys() | offline_tools().keys()))
def test_every_capability_rejects_non_object_arguments_before_dispatch(runtime, monkeypatch, name):
    client, control, calls, _, _ = runtime
    invoked = []
    monkeypatch.setattr(control, 'invoke', lambda *args, **kwargs: invoked.append(args))
    response = client.post(PATH, json={'capability':name, 'arguments':[]},
                           headers={'X-MKLink-Frontend-Session':control.frontend.session_id})
    assert response.status_code == 422
    assert not invoked and not calls


def test_call_reuses_handler_and_target_fence(runtime, monkeypatch):
    client, control, calls, _, _ = runtime
    headers = {'X-MKLink-Frontend-Session':control.frontend.session_id}
    body = {'capability':'read_memory', 'arguments':{'address':'0x20000000','size':4}}
    response = client.post(PATH, json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['data_hex'] == '00000000' and calls == ['read']
    original = control.invoke
    async def changed_target(*args, **kwargs):
        control.app.state.mklink_state['device_generation'] = 7
        return await original(*args, **kwargs)
    monkeypatch.setattr(control, 'invoke', changed_target)
    assert client.post(PATH, json=body, headers=headers).status_code == 409
    assert calls == ['read']


def test_no_arbitrary_paths_or_missing_confirmation(runtime):
    client, control, calls, _, _ = runtime
    headers = {'X-MKLink-Frontend-Session':control.frontend.session_id}
    assert client.post(PATH, json={'capability':'/api/device/read-memory', 'arguments':{}}, headers=headers).status_code == 422
    assert client.post(PATH, json={'capability':'set_power_on', 'arguments':{'millivolts':3300}}, headers=headers).status_code == 422
    assert client.post(PATH, json={'capability':'device_status', 'arguments':{}}).status_code == 422
    assert client.post(PATH, json={'capability':'device_status', 'arguments':{}}, headers={**headers,'Origin':'https://example.com'}).status_code == 403
    assert calls == []


def test_capability_layout_roundtrip_only_restores_selection(tmp_path):
    layout = {'version':2,'revision':0,'docks':[], 'panels':[
        {'id':'cap_one','type':'capability','title':'Diagnostics','source':{},'x':0,'y':0,'w':6,'h':4,
         'view':{'capability':'fault_snapshot'}}]}
    saved = save_layout(tmp_path, copy.deepcopy(layout))
    assert load_layout(tmp_path) == saved
    assert saved['panels'][0]['view'] == {'capability':'fault_snapshot'}


def test_offline_analysis_uses_existing_tools_without_device_io(runtime):
    client, control, calls, _, _ = runtime
    headers = {'X-MKLink-Frontend-Session': control.frontend.session_id}
    def invoke(name, arguments):
        return client.post(PATH, json={'capability': name, 'arguments': arguments}, headers=headers)
    decoded = invoke('systemview_decode', {'hex_bytes': '00000000000000000000'})
    assert decoded.status_code == 200 and decoded.json()['bytes_read'] == 10
    assert decoded.json() == offline_tools()['systemview_decode'][0]('00000000000000000000')
    analyzed = invoke('systemview_analyze_events', {'events': decoded.json()['events']})
    assert analyzed.status_code == 200
    assert analyzed.json() == offline_tools()['systemview_analyze_events'][0](decoded.json()['events'])
    assert invoke('systemview_decode', {'hex_bytes': 'not hex'}).status_code == 422
    assert invoke('systemview_analyze_events', {'events': [], 'execute': True}).status_code == 422
    assert invoke('systemview_analyze_events', {'events': ['not an event']}).status_code == 422
    assert invoke('configuration_script', {'part_number': 'STM32F103xE', 'changes': {'RDP': 1}}).status_code == 422
    assert invoke('configuration_script', {'part_number': 'STM32F103xE', 'changes': {'DATA0': True}}).status_code == 422
    assert calls == []


def test_path_parameters_and_stable_job_id_reach_original_transport(runtime, monkeypatch):
    client, control, calls, _, _ = runtime
    headers = {'X-MKLink-Frontend-Session': control.frontend.session_id}
    invoked = []
    async def invoke(*args, **kwargs):
        invoked.append((args, kwargs))
        return {'job_id': 'original-job', 'state': 'queued'}
    monkeypatch.setattr(control, 'invoke', invoke)
    def call(name, arguments):
        return client.post(PATH, json={'capability': name, 'arguments': arguments}, headers=headers)
    for value in ('../unsafe', 'a?b', 'a#b', r'a\b', '..', ''):
        assert call('job_status', {'job_id': value}).status_code == 422
    assert call('flash_job_start', {}).status_code == 422 and invoked == []
    assert call('flash_job_start', {'request_id': 'stable-id', 'operation': 'flash'}).json()['job_id'] == 'original-job'
    assert invoked[-1] == (('POST', '/api/online-flash/jobs', {'operation': 'flash'}),
                          {'frontend_session': control.frontend.session_id, 'request_id': 'stable-id'})
    assert call('job_status', {'job_id': 'original-job'}).status_code == 200
    assert invoked[-1][0] == ('GET', '/api/runtime/jobs/original-job', {})
    assert calls == []


def test_query_parameters_are_not_silently_lost(runtime):
    from fastapi import Body
    client, control, _, _, app = runtime
    @app.delete('/api/online-flash/algorithms/{algorithm_id}')
    async def remove(algorithm_id: str, part_number: str):
        return {'algorithm_id': algorithm_id, 'part_number': part_number}
    @app.post('/api/dash/rtt/traffic-recording/stop')
    async def stop(channel: int = 0, channel_body: int = Body(default=None, embed=True)):
        return {'channel': channel if channel_body is None else channel_body}
    headers = {'X-MKLink-Frontend-Session': control.frontend.session_id}
    response = client.post(PATH, headers=headers, json={'capability': 'flash_algorithm_remove',
                           'arguments': {'algorithm_id': 'example', 'part_number': 'STM32F103C8'}})
    assert response.status_code == 200 and response.json()['part_number'] == 'STM32F103C8'
    response = client.post(PATH, headers=headers, json={'capability': 'rtt_recording_stop', 'arguments': {'channel': 3}})
    assert response.status_code == 200 and response.json()['channel'] == 3
    response = client.post(PATH, headers=headers, json={'capability': 'rtt_recording_stop', 'arguments': {'channel_body': 4}})
    assert response.status_code == 200 and response.json()['channel'] == 4


def test_panel_record_save_export_and_replay_uses_actual_recorder(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from mklink.remote import api, dashboards
    from mklink.runtime_api import install_runtime
    from test_superwatch_recording import manager, rows
    from test_recording_text import exported
    sw = manager()
    managers = {**dashboards.get_managers(), 'superwatch': sw}
    monkeypatch.setattr(dashboards, 'get_managers', lambda: managers)
    app = api.create_app(auth_token='recording-test', project_root=str(tmp_path))
    control = install_runtime(app, {'port': 8765, 'token': 'recording-test', 'instance_id': 'recording'})
    headers = {'X-Auth-Token': 'recording-test', 'X-MKLink-Frontend-Session': control.frontend.session_id}
    # Synthetic samples enter the real manager/worker; no physical acquisition is claimed.
    with TestClient(app, base_url='http://127.0.0.1:8765', headers=headers) as client:
        def call(name, arguments=None):
            response = client.post(PATH, json={'capability': name, 'arguments': arguments or {}})
            assert response.status_code == 200, response.text
            return response.json()
        call('superwatch_recording_start', {'directory': str(tmp_path)})
        for i in range(1200):
            sw._publish_sample_values_locked([i / 4], channel_count=1, sample_time=i * 5, break_before=1 if i == 600 else 0)
        result = call('superwatch_recording_stop')
        assert result['samples'] == 1200 and result['state'] == 'completed'
        recorded = rows(tmp_path)
        assert len(recorded) == 1201 and recorded[600] == {'event': 'discontinuity', 'reason': 1}
        assert recorded[0]['value'] == 0 and recorded[-1]['value'] == 299.75
        call('superwatch_recording_export', {'path': result['path']})
        assert exported(sw._recorder._export)['export_state'] == 'completed'
        response = client.post('/api/runtime/frontend/replay-file', json={'path': result['path']})
        from pathlib import Path
        assert response.status_code == 200 and response.content == Path(result['path']).read_bytes()
        assert sw.running
        sw.stop()

"""Semantic delivery and target fencing, without a browser or device worker."""
import copy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from mklink.frontend_contract import PROTOCOL, validate_args, validate_schema
from mklink.runtime_frontend import FrontendBroker
from test_shared_runtime import runtime, attach, call

BASE = '/api/runtime/frontend'
SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {
    'panel_id': {'type': 'string', 'maxLength': 80}, 'width': {'type': 'integer', 'minimum': 1, 'maximum': 12}},
    'required': ['panel_id', 'width']}


@pytest.fixture
def broker(tmp_path):
    control = SimpleNamespace(info={'instance_id': 'test-instance', 'probe_id': 'usb-test'},
                              app=SimpleNamespace(state=SimpleNamespace(mklink_state={
                                  'project_root': str(tmp_path), 'device_generation': 1})))
    result = FrontendBroker(control, clock=lambda: 100000)
    result.exchange({'report': report(result), 'receipts': []})
    return result


def report(broker, revision=1, page_id='page_one'):
    return {'protocol': PROTOCOL, 'session_id': broker.session_id, 'page_id': page_id,
            'title': 'MKLink workbench', 'catalog': {'panels': [{'id': 'wave_one'}]},
            'actions': {'panel_resize': {'description': 'Resize a panel', 'inputSchema': copy.deepcopy(SCHEMA)}},
            'state': {'revision': revision, 'value': {'panels': [{'id': 'wave_one', 'w': 6}]}}}


def command(broker, **overrides):
    return {'protocol': PROTOCOL, 'session_id': broker.session_id, 'page_id': 'page_one',
            'command_id': 'command_one', 'expect_revision': 1, 'deadline': broker.clock() + 10000,
            'action': 'panel_resize', 'args': {'panel_id': 'wave_one', 'width': 8}, **overrides}


def test_heartbeat_does_not_copy_historical_results_and_reads_remain_isolated(broker, monkeypatch):
    from unittest.mock import Mock

    submitted = command(broker)
    broker.call(submitted)
    result = {'command_id': 'command_one', 'action': 'panel_resize', 'status': 'completed',
              'result': {'samples': [1, 2, 3]}}
    broker.exchange({'report': report(broker), 'receipts': [result]})
    stored = broker.commands['command_one']['receipt']
    copier = Mock(wraps=copy.deepcopy)
    monkeypatch.setattr(copy, 'deepcopy', copier)
    broker.exchange({'report': report(broker), 'receipts': []})
    assert not any(call.args[0] is stored for call in copier.call_args_list)
    broker.read_receipt('command_one')['result']['samples'].clear()
    broker.call(submitted)['result']['samples'].clear()
    assert stored['result']['samples'] == [1, 2, 3]


def assert_error(code, fn, *args):
    with pytest.raises(HTTPException) as caught:
        fn(*args)
    assert caught.value.detail['code'] == code


def test_delivery_requires_receipt_and_idempotency_preserves_original(broker):
    submitted = command(broker)
    assert broker.call(submitted)['status'] == 'queued'
    assert broker.call(copy.deepcopy(submitted)) == {'command_id': 'command_one', 'action': 'panel_resize', 'status': 'queued', 'duplicate': True}
    assert_error('ID_CONFLICT', broker.call, {**submitted, 'args': {'panel_id': 'wave_one', 'width': 9}})
    assert broker.exchange({'report': report(broker), 'receipts': []})['command'] == submitted
    accepted = {'command_id': 'command_one', 'action': 'panel_resize', 'status': 'accepted', 'state': {'revision': 2, 'value': {}}}
    assert broker.exchange({'report': report(broker, 2), 'receipts': [accepted]})['command'] is None
    assert_error('BUSY', broker.call, command(broker, command_id='second', expect_revision=2))
    completed = {**accepted, 'status': 'completed', 'result': {'panel_id': 'wave_one', 'width': 8}}
    broker.exchange({'report': report(broker, 2), 'receipts': [completed]})
    assert broker.read_receipt('command_one')['status'] == 'completed'
    assert broker.call(submitted)['status'] == 'completed'
    assert broker.call(command(broker, command_id='second', expect_revision=2))['status'] == 'queued'


def test_page_reconnect_never_replays_unconfirmed_command(broker):
    broker.call(command(broker))
    broker.clock = lambda: 116000
    assert broker.exchange({'report': report(broker), 'receipts': []})['command'] is None
    assert broker.read_receipt('command_one')['status'] == 'unknown'
    assert broker.call(command(broker, deadline=110000))['duplicate']
    assert_error('BUSY', broker.call, command(broker, command_id='second'))
    # Only a genuine late terminal receipt resolves the original uncertainty.
    broker.exchange({'report': report(broker, 2), 'receipts': [
        {'command_id': 'command_one', 'action': 'panel_resize', 'status': 'completed'}]})
    assert broker.read_receipt('command_one')['status'] == 'completed'


def test_refresh_lifecycle_reclaims_reports_but_keeps_all_receipts(broker):
    original = command(broker)
    broker.call(original)
    for index in range(100):
        broker.clock = lambda index=index: 116000 + index * 16000
        page_id = f'refresh_{index}'
        assert not any(page['online'] for page in broker.discover()['pages'])
        assert broker.exchange({'report': report(broker, page_id=page_id), 'receipts': []})['command'] is None
        assert len(broker.pages) == 1
        submitted = command(broker, page_id=page_id, command_id=f'command_{index}')
        broker.call(submitted)
        broker.exchange({'report': report(broker, page_id=page_id), 'receipts': [
            {'command_id': submitted['command_id'], 'action': submitted['action'], 'status': 'completed'}]})
        assert broker.call(submitted)['duplicate']
    assert len(broker.commands) == 101
    assert broker.call(original)['status'] == 'unknown'
    assert broker.exchange({'report': report(broker), 'receipts': []})['command'] is None
    assert_error('BUSY', broker.call, command(broker, command_id='never_replay'))


def test_33rd_page_registration_after_expiry_is_not_a_session_limit(broker):
    for index in range(32):
        broker.clock = lambda index=index: 116000 + index * 16000
        assert not any(page['online'] for page in broker.discover()['pages'])
        broker.exchange({'report': report(broker, page_id=f'page_{index}'), 'receipts': []})
    assert len(broker.pages) == 1


def test_full_command_history_fails_closed_without_forgetting_duplicate_ids(broker):
    first = None
    for index in range(500):
        submitted = command(broker, command_id=f'command_{index}')
        if first is None:
            first = submitted
        broker.call(submitted)
        broker.exchange({'report': report(broker), 'receipts': [
            {'command_id': submitted['command_id'], 'action': submitted['action'], 'status': 'completed'}]})
    assert_error('SESSION_LIMIT', broker.call, command(broker, command_id='overflow'))
    assert broker.call(first)['duplicate']
    assert broker.read_receipt(first['command_id'])['status'] == 'completed'


def test_active_window_limit_and_target_switches(broker):
    original = command(broker)
    broker.call(original)
    for index in range(31):
        broker.exchange({'report': report(broker, page_id=f'window_{index}'), 'receipts': []})
    assert_error('SESSION_LIMIT', broker.exchange, {'report': report(broker, page_id='window_33'), 'receipts': []})
    old_report = report(broker)
    for generation in range(2, 70):
        broker.control.app.state.mklink_state['device_generation'] = generation
        broker.exchange({'report': report(broker, page_id=f'target_{generation}'), 'receipts': []})
        assert len(broker.pages) == 1
    assert broker.read_receipt(original['command_id'])['status'] == 'unknown'
    assert_error('WRONG_TARGET', broker.exchange, {'report': old_report, 'receipts': []})
    assert_error('WRONG_TARGET', broker.exchange, {'report': report(broker), 'receipts': []})


@pytest.mark.parametrize('change', ['instance_id', 'probe_id', 'device_generation', 'project_root'])
def test_target_changes_reject_old_page_and_preserve_unknown_receipt(broker, change):
    original_report = report(broker)
    submitted = command(broker)
    broker.call(submitted)
    if change in broker.control.info:
        broker.control.info[change] = 'other'
    else:
        broker.control.app.state.mklink_state[change] = 2 if change == 'device_generation' else '/different-project'
    assert broker.discover()['pages'] == []
    assert broker.read_receipt('command_one')['code'] == 'TARGET_CHANGED'
    assert_error('WRONG_TARGET', broker.call, submitted)
    assert_error('WRONG_TARGET', broker.exchange, {'report': original_report, 'receipts': []})
    assert_error('WRONG_TARGET', broker.exchange, {'report': report(broker), 'receipts': []})
    assert broker.exchange({'report': report(broker, page_id='new_page'), 'receipts': []}) == {'command': None}


@pytest.mark.parametrize('patch,code', [
    ({'expect_revision': 0}, 'STALE_REVISION'), ({'page_id': 'missing'}, 'PAGE_OFFLINE'),
    ({'deadline': 99999}, 'EXPIRED'), ({'deadline': 130001}, 'EXPIRED'),
    ({'action': 'arbitrary_fetch'}, 'UNKNOWN_ACTION'), ({'args': {'panel_id': 'wave_one', 'width': True}}, 'INVALID_INPUT'),
    ({'args': {'panel_id': 'wave_one', 'width': 13}}, 'INVALID_INPUT'),
    ({'args': {'panel_id': 'wave_one', 'width': 2, 'url': '/api/device/reset'}}, 'INVALID_INPUT'),
    ({'url': '/api/device/reset'}, 'INVALID_INPUT'), ({'protocol': 'anything/2'}, 'PROTOCOL_MISMATCH'),
])
def test_invalid_commands_never_enter_queue(broker, patch, code):
    assert_error(code, broker.call, command(broker, **patch))
    assert broker.commands == {}


def test_exchange_validation_is_atomic_and_reports_cannot_go_backwards(broker):
    broker.call(command(broker))
    original = broker.read('page_one')
    invalid = {'command_id': 'command_one', 'action': 'wrong_action', 'status': 'applied'}
    assert_error('INVALID_RECEIPT', broker.exchange, {'report': report(broker, 2), 'receipts': [invalid]})
    assert broker.read('page_one') == original
    assert broker.read_receipt('command_one')['status'] == 'queued'
    assert_error('STALE_REVISION', broker.exchange, {'report': report(broker, 0), 'receipts': []})
    changed = report(broker)
    changed['state']['value']['panels'][0]['w'] = 9
    assert_error('STALE_REVISION', broker.exchange, {'report': changed, 'receipts': []})
    bad_schema = report(broker)
    bad_schema['actions']['panel_resize']['inputSchema']['additionalProperties'] = True
    assert_error('SCHEMA_UNSUPPORTED', broker.exchange, {'report': bad_schema, 'receipts': []})


def test_terminal_receipt_cannot_be_overwritten(broker):
    broker.call(command(broker))
    receipt = {'command_id': 'command_one', 'action': 'panel_resize', 'status': 'failed', 'code': 'ACTION_FAILED', 'message': 'Panel missing'}
    broker.exchange({'report': report(broker, 2), 'receipts': [receipt]})
    broker.exchange({'report': report(broker, 2), 'receipts': [{**receipt, 'status': 'completed'}]})
    assert broker.read_receipt('command_one') == receipt


@pytest.mark.parametrize('schema', [
    {'type': 'object', 'properties': {}, 'required': []},
    {'type': 'string', 'pattern': '.*'}, {'type': 'array', 'items': {'type': 'string'}},
    {'type': 'integer', 'minimum': True}, {'type': 'array', 'maxItems': 501, 'items': {'type': 'string'}},
    {'type': 'object', 'additionalProperties': False, 'properties': {}, 'required': ['absent']},
])
def test_schema_contract_fails_closed(schema):
    assert_error('SCHEMA_UNSUPPORTED', validate_schema, schema)


def test_number_schema_matches_browser_finite_numbers_without_integer_overflow():
    from mklink.frontend_contract import bounded_json
    schema = {'type': 'number', 'maximum': 1e100}
    validate_schema(schema)
    validate_args(1e90, schema)
    bounded_json({'timestamp_ns': 1000000000000000000})
    assert_error('INVALID_INPUT', bounded_json, {'value': 10 ** 1000})
    assert_error('INVALID_INPUT', validate_args, float('nan'), schema)
    assert_error('INVALID_INPUT', validate_args, True, schema)


def test_discovery_layout_and_gui_call_use_existing_auth_without_hardware(runtime):
    client, control, calls, _, _ = runtime
    session = attach(client)
    response = call(client, session, 'gui_frontend_pages')
    assert response.status_code == 200
    assert response.json()['session_id'] == control.frontend.session_id
    current = report(control.frontend)
    assert client.post(BASE + '/exchange', json={'report': current, 'receipts': []}).status_code == 200
    assert call(client, session, 'gui_frontend_read', {'page_id': 'page_one'}).json()['state']['revision'] == 1
    result = call(client, session, 'gui_frontend_call', command(control.frontend))
    assert result.status_code == 200 and result.json()['status'] == 'queued'
    assert call(client, session, 'gui_frontend_receipt', {'command_id': 'command_one'}).json()['status'] == 'queued'
    assert client.get(BASE + '/pages', headers={'X-Auth-Token': 'invalid'}).status_code == 401
    assert client.get(BASE + '/pages', headers={'Origin': 'https://foreign.test'}).status_code == 403
    assert client.get(BASE + '/pages').headers['cache-control'] == 'no-store'
    assert calls == []


def test_gui_only_client_can_deliver_page_commands_without_connecting_hardware(runtime):
    client, control, calls, _, _ = runtime
    session = client.post('/_runtime/attach', json={'scope': 'uart'}).json()['session_id']
    control.frontend.exchange({'report': report(control.frontend), 'receipts': []})
    assert call(client, session, 'gui_frontend_pages').status_code == 200
    assert call(client, session, 'gui_frontend_call', command(control.frontend)).json()['status'] == 'queued'
    assert call(client, session, 'read_memory', {'address': '0x20000000', 'size': 4}).status_code == 409
    assert call(client, session, 'gui_frontend_call', command(control.frontend, session_id='stale')).status_code == 409
    assert call(client, 'expired', 'gui_frontend_call', command(control.frontend)).status_code == 409
    assert len(control.frontend.commands) == 1 and not calls


@pytest.mark.parametrize('uart', [False, True])
def test_semantic_target_checked_again_at_operation_admission(runtime, monkeypatch, uart):
    client, control, calls, _, app = runtime
    if uart:
        @app.post('/api/dash/serial/send')
        async def send(body: dict):
            calls.append('serial-send')
            return {'ok': True}
    old_session = control.frontend.session_id
    original = control.run_operation
    async def switch_then_admit(*args, **kwargs):
        app.state.mklink_state['device_generation'] = 2
        return await original(*args, **kwargs)
    monkeypatch.setattr(control, 'run_operation', switch_then_admit)
    path = '/api/dash/serial/send' if uart else '/api/device/read-memory'
    result = client.post(path, json={'address': '0x20000000', 'size': 4},
                         headers={'X-MKLink-Frontend-Session': old_session})
    assert result.status_code == 409 and result.json()['detail']['code'] == 'WRONG_TARGET'
    assert calls == []
    assert client.get('/api/device/status', headers={'X-MKLink-Frontend-Session': old_session}).status_code == 409


def test_invalid_json_and_large_control_request_fail_without_mutating(runtime):
    client, control, calls, _, _ = runtime
    assert client.post(BASE + '/call', content='{bad').status_code == 422
    assert client.post(BASE + '/call', content='x' * (65536 + 1)).status_code == 413
    assert client.post(BASE + '/call', json=[]).status_code == 422
    assert not control.frontend.commands and not calls


def test_workbench_presentation_is_advertised():
    from mklink.runtime_presentation import TABS, validate_action
    assert 'workbench' in TABS
    validate_action({'action': 'navigate', 'page': 'dashboard', 'tab': 'workbench'})


def test_symbol_reload_capability_preserves_query_parameters(runtime):
    client, control, calls, _, app = runtime
    @app.post('/api/symbols/reload-sources')
    async def reload_symbols(source_path: str, expected_axf: str):
        calls.append({'source_path': source_path, 'expected_axf': expected_axf})
        return {'symbols_reloaded': True}
    session = attach(client)
    arguments = {'source_path': 'firmware.axf', 'expected_axf': 'previous.axf'}
    response = call(client, session, 'symbol_reload_sources', arguments)
    assert response.status_code == 200 and response.json()['symbols_reloaded']
    assert calls == [arguments]
    assert call(client, session, 'symbol_reload_sources', {'source_path': [], 'url': 'http://example.test'}).status_code == 422


def test_c_layout_capability_keeps_existing_shared_client_exclusion(runtime):
    client, control, calls, _, app = runtime
    @app.post('/api/symbols/c-layout')
    async def c_layout(body: dict):
        calls.append('c-layout')
        return {'ok': True}
    session = attach(client)
    response = call(client, session, 'symbol_apply_c_layout', {'variable': 'motor', 'definition': 'struct Motor { int rpm; };'})
    assert response.status_code == 409 and 'shared_clients_attached' in response.text
    assert not calls

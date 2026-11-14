"""Workspaces and user intent persistence never change acquisition state."""
from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path

import pytest
from fastapi import HTTPException

from mklink.frontend_layout import load_layout, save_layout, normalize_layout, validate_component_manifest, COMPONENT_TYPES
from mklink.watch_preferences import PreferencesConflict
from test_runtime_frontend import BASE, broker, report, assert_error
from test_shared_runtime import runtime, attach, call


def layout():
    return {'version': 1, 'revision': 0, 'panels': [
        {'id': 'wave_one', 'type': 'watch', 'title': '波形', 'source': {'signals': ['motor.current']},
         'x': 0, 'y': 0, 'w': 6, 'h': 4, 'view': {'zoom': {'left': 0, 'right': 1}}},
        {'id': 'variables_one', 'type': 'variables', 'title': '变量', 'source': {'signals': []}, 'x': 6, 'y': 0, 'w': 6, 'h': 3},
        {'id': 'rtt_one', 'type': 'rtt', 'title': 'RTT', 'source': {'channel': 0}, 'x': 0, 'y': 4, 'w': 6, 'h': 3},
        {'id': 'serial_one', 'type': 'serial', 'title': '串口', 'source': {'port': ''}, 'x': 6, 'y': 4, 'w': 6, 'h': 3},
    ]}


def intent(broker, **overrides):
    return {'request_id': 'intent_one', 'session_id': broker.session_id, 'page_id': 'page_one',
            'revision': 1, 'intent': 'inspect', 'object_id': 'wave_one', 'message': '请检查电机波形异常', **overrides}


def test_layout_roundtrip_project_isolation_and_revision_conflicts(tmp_path):
    root = tmp_path / 'one'
    assert load_layout(root) == {'version': 1, 'revision': 0, 'panels': []}
    saved = save_layout(root, layout())
    assert saved == {**layout(), 'revision': 1}
    assert load_layout(root) == saved
    assert load_layout(tmp_path / 'two')['panels'] == []
    with pytest.raises(PreferencesConflict):
        save_layout(root, layout())
    assert (root / '.mklink' / 'frontend_layout.json').is_file()
    assert not (root / '.mklink' / 'superwatch_workspace.json').exists()


@pytest.mark.parametrize('patch', [
    {'version': 2}, {'revision': True}, {'panels': [layout()['panels'][0]] * 2},
    {'panels': [{**layout()['panels'][0], 'x': 11, 'w': 2}]},
    {'panels': [{**layout()['panels'][0], 'h': 0}]},
    {'panels': [{**layout()['panels'][0], 'source': {'signals': [], 'address': '0x20000000'}}]},
    {'panels': [{**layout()['panels'][0], 'device': 'other'}]},
    {'panels': [{**layout()['panels'][0], 'type': 'arbitrary_iframe'}]},
    {'panels': [{**layout()['panels'][2], 'source': {'channel': True}}]},
    {'panels': [{**layout()['panels'][3], 'source': {'port': 'COM1\n'}}]},
    {'panels': [{**layout()['panels'][0], 'view': {'value': float('nan')}}]},
    {'panels': [{**layout()['panels'][0], 'view': {'large': 'x' * (16 * 1024)}}]},
])
def test_layout_rejects_malformed_or_unbounded_input_without_write(tmp_path, patch):
    with pytest.raises(HTTPException):
        save_layout(tmp_path, {**layout(), **patch})
    assert not (tmp_path / '.mklink').exists()


@pytest.mark.parametrize('panel_id', ['dashboard', 'superwatch', 'workbench', 'SuperWatch', 'VOFA'])
def test_layout_rejects_ids_reserved_by_fixed_pages_or_legacy_renderers(tmp_path, panel_id):
    value = layout()
    value['panels'][0]['id'] = panel_id
    with pytest.raises(HTTPException, match='reserved'):
        save_layout(tmp_path, value)
    assert not (tmp_path / '.mklink').exists()


def test_layout_atomic_replace_failure_keeps_previous_document(tmp_path, monkeypatch):
    first = save_layout(tmp_path, layout())
    def fail_replace(*args):
        raise OSError('injected storage failure')
    monkeypatch.setattr('mklink.frontend_layout.os.replace', fail_replace)
    with pytest.raises(OSError):
        save_layout(tmp_path, {**first, 'panels': []})
    assert load_layout(tmp_path) == first
    assert list((tmp_path / '.mklink').glob('*.tmp')) == []


def test_layout_rejects_redirecting_preferences_path(tmp_path, monkeypatch):
    original = Path.is_symlink
    monkeypatch.setattr(Path, 'is_symlink', lambda self: self.name == '.mklink' or original(self))
    with pytest.raises(ValueError, match='redirect'):
        save_layout(tmp_path, layout())


def test_concurrent_layout_saves_have_one_winner(tmp_path):
    def save():
        try:
            return save_layout(tmp_path, layout())['revision']
        except PreferencesConflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: save(), range(2)))
    assert sorted(results, key=str) == [1, 'conflict']


def test_layout_api_and_shared_capability_preserve_running_captures(runtime):
    client, control, calls, managers, _ = runtime
    session = attach(client)
    for manager in managers.values():
        manager.running = True
    response = call(client, session, 'gui_frontend_save_layout', layout())
    assert response.status_code == 200 and response.json()['revision'] == 1
    assert client.get(BASE + '/layout').json() == response.json()
    assert client.put(BASE + '/layout', json=layout()).status_code == 409
    assert all(manager.running for manager in managers.values()) and calls == []


def controls_layout():
    result = layout()
    result.update(version=2, docks=[{'id': 'dock_one', 'panels': ['wave_one', 'variables_one'], 'active': 'variables_one'}])
    result['panels'].append({
        'id': 'controls_one', 'type': 'controls', 'title': '电机调试', 'source': {},
        'x': 6, 'y': 0, 'w': 6, 'h': 4, 'widgets': [
            {'id': 'pause_button', 'version': 1, 'type': 'button', 'title': '暂停显示',
             'x': 0, 'y': 0, 'w': 2, 'h': 1, 'binding': {
                 'panel_id': 'wave_one', 'action': 'waveform.pause', 'args': {'paused': True},
                 'contract': '{"args":{"type":"object"},"effect":"view"}'}},
            {'id': 'pause_value', 'version': 1, 'type': 'value', 'title': '暂停状态',
             'x': 2, 'y': 0, 'w': 2, 'h': 1, 'binding': {'panel_id': 'wave_one', 'state_path': 'view.paused'}},
            {'id': 'future_form', 'version': 1, 'type': 'form', 'title': '尚未绑定',
             'x': 0, 'y': 1, 'w': 4, 'h': 2, 'binding': {}},
        ],
    })
    return result


def test_v1_read_is_unchanged_and_upgrade_is_explicit_and_revision_checked(tmp_path):
    original = save_layout(tmp_path, layout())
    path = tmp_path / '.mklink' / 'frontend_layout.json'
    raw = path.read_bytes()
    assert load_layout(tmp_path) == original
    assert path.read_bytes() == raw
    upgraded = controls_layout()
    upgraded['revision'] = original['revision']
    saved = save_layout(tmp_path, upgraded)
    assert saved['version'] == 2 and saved['revision'] == 2
    assert load_layout(tmp_path) == saved
    with pytest.raises(PreferencesConflict):
        save_layout(tmp_path, original)
    assert load_layout(tmp_path) == saved


def test_v2_preserves_inactive_tabs_and_missing_binding_targets_without_substitution(tmp_path):
    value = controls_layout()
    # A hidden member's old rectangle can overlap and be smaller than its window.
    value['panels'][1].update(x=0, y=0, w=1, h=1)
    value['panels'][-1]['widgets'][0]['binding']['panel_id'] = 'closed_wave'
    saved = save_layout(tmp_path, value)
    assert load_layout(tmp_path) == saved
    assert saved['panels'][-1]['widgets'][0]['binding']['panel_id'] == 'closed_wave'
    assert saved['docks'][0]['active'] == 'variables_one'


@pytest.mark.parametrize('mutate', [
    lambda value: value.update(version=3),
    lambda value: value.update(execute='arbitrary()'),
    lambda value: value.pop('docks'),
    lambda value: value['docks'][0].update(active='missing'),
    lambda value: value['docks'][0].update(panels=['wave_one', 'missing']),
    lambda value: value['docks'][0].update(panels=['wave_one', 'wave_one']),
    lambda value: value['docks'][0].update(panels=['wave_one']),
    lambda value: value['docks'][0].update(id='wave_one'),
    lambda value: value['docks'][0].update(id='superwatch'),
    lambda value: value['docks'].append({'id': 'dock_two', 'panels': ['wave_one', 'rtt_one'], 'active': 'rtt_one'}),
    lambda value: value['panels'][2].update(w=2),
    lambda value: value['panels'][0].update(h=3),
    lambda value: value['panels'][2].update(y=0),
    lambda value: value['panels'][0].update(widgets=[]),
    lambda value: value['panels'][-1].update(source={'url': 'https://example.com'}),
    lambda value: value['panels'][-1]['widgets'][0].update(id='dock_one'),
    lambda value: value['panels'][-1]['widgets'][0].update(id='controls_one'),
    lambda value: value['panels'][-1]['widgets'][0].update(type='iframe'),
    lambda value: value['panels'][-1]['widgets'][0].update(version=True),
    lambda value: value['panels'][-1]['widgets'][0].update(w=1),
    lambda value: value['panels'][-1]['widgets'][0].update(x=11),
    lambda value: value['panels'][-1]['widgets'][1].update(x=0),
    lambda value: value['panels'][-1]['widgets'][2].update(h=1),
    lambda value: value['panels'][-1]['widgets'][0]['binding'].update(url='/api/unchecked'),
    lambda value: value['panels'][-1]['widgets'][0]['binding'].update(action='javascript:alert(1)'),
    lambda value: value['panels'][-1]['widgets'][0]['binding'].update(args=[]),
    lambda value: value['panels'][-1]['widgets'][0]['binding'].update(args={'large': 'x' * 8192}),
    lambda value: value['panels'][-1]['widgets'][0]['binding'].update(contract='x' * 16385),
    lambda value: value['panels'][-1]['widgets'][0]['binding'].pop('contract'),
    lambda value: value['panels'][-1]['widgets'][1]['binding'].update(state_path='view.__proto__.polluted'),
    lambda value: value['panels'][-1]['widgets'][1]['binding'].update(state_path='constructor.value'),
    lambda value: value['panels'][-1]['widgets'][1]['binding'].update(state_path='view..paused'),
    lambda value: value['panels'][-1]['widgets'][1]['binding'].update(state_path='view.\npaused'),
    lambda value: value['panels'][-1]['widgets'][1]['binding'].update(args={}),
])
def test_v2_rejects_unsafe_or_unreadable_compositions_without_overwriting(tmp_path, mutate):
    saved = save_layout(tmp_path, controls_layout())
    raw = (tmp_path / '.mklink' / 'frontend_layout.json').read_bytes()
    invalid = copy.deepcopy(saved)
    mutate(invalid)
    with pytest.raises(HTTPException):
        save_layout(tmp_path, invalid)
    assert (tmp_path / '.mklink' / 'frontend_layout.json').read_bytes() == raw


def test_v2_component_ids_are_global_and_count_is_bounded(tmp_path):
    value = controls_layout()
    second = copy.deepcopy(value['panels'][-1])
    second.update(id='controls_two', y=8)
    value['panels'].append(second)
    with pytest.raises(HTTPException, match='duplicate component'):
        save_layout(tmp_path, value)
    value = {'version': 2, 'revision': 0, 'panels': [], 'docks': []}
    for index in range(5):
        panel = copy.deepcopy(controls_layout()['panels'][-1])
        panel.update(id=f'controls_{index}', x=0, y=index * 4)
        panel['widgets'] = [dict(panel['widgets'][0], id=f'button_{index}_{number}', y=number)
                            for number in range(26)]
        value['panels'].append(panel)
    with pytest.raises(HTTPException, match='128 components'):
        save_layout(tmp_path, value)
    assert not (tmp_path / '.mklink').exists()


def test_v2_concurrent_saves_and_api_never_start_capture(tmp_path, runtime):
    def save():
        try:
            return save_layout(tmp_path / 'concurrent', controls_layout())['revision']
        except PreferencesConflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: save(), range(2)))
    assert sorted(results, key=str) == [1, 'conflict']
    client, _, calls, managers, _ = runtime
    session = attach(client)
    for manager in managers.values():
        manager.running = True
    result = call(client, session, 'gui_frontend_save_layout', controls_layout())
    assert result.status_code == 200 and result.json()['version'] == 2
    assert client.get(BASE + '/layout').json() == result.json()
    assert all(manager.running for manager in managers.values()) and calls == []


def test_manifest_indicator_roundtrips_through_existing_api_and_unknown_types_do_not_overwrite(runtime):
    client, _, calls, _, _ = runtime
    session = attach(client)
    value = controls_layout()
    indicator = value['panels'][-1]['widgets'][1]
    indicator.update(type='indicator', title='暂停状态灯')
    response = call(client, session, 'gui_frontend_save_layout', value)
    assert response.status_code == 200
    saved = client.get(BASE + '/layout').json()
    assert saved['panels'][-1]['widgets'][1] == indicator
    unknown = copy.deepcopy(saved)
    unknown['panels'][-1]['widgets'][1]['type'] = 'unregistered_led'
    assert client.put(BASE + '/layout', json=unknown).status_code == 422
    assert client.get(BASE + '/layout').json() == saved
    assert calls == []


def test_build_manifest_extension_controls_type_binding_and_dimensions_without_python_branch(tmp_path, monkeypatch):
    definitions = copy.deepcopy(COMPONENT_TYPES)
    definitions['temperature'] = {**definitions['value'], 'title': '温度', 'minW': 5, 'defaultW': 6}
    registry = validate_component_manifest({'version': 1, 'components': definitions})
    monkeypatch.setattr('mklink.frontend_layout.COMPONENT_TYPES', registry)
    value = controls_layout()
    widget = value['panels'][-1]['widgets'][1]
    widget.update(type='temperature', x=0, y=3, w=5)
    assert save_layout(tmp_path, value)['panels'][-1]['widgets'][1] == widget
    widget['w'] = 4
    with pytest.raises(HTTPException, match='minimum size'):
        normalize_layout(value)
    widget['w'] = 5
    widget['binding'] = copy.deepcopy(value['panels'][-1]['widgets'][0]['binding'])
    with pytest.raises(HTTPException):
        normalize_layout(value)


@pytest.mark.parametrize('mutate', [
    lambda manifest: manifest.update(version=True),
    lambda manifest: manifest.update(url='https://example.com/registry.json'),
    lambda manifest: manifest['components'].update({'__proto__': manifest['components']['value']}),
    lambda manifest: manifest['components']['value'].update(script='alert(1)'),
    lambda manifest: manifest['components']['value'].update(presentation='iframe'),
    lambda manifest: manifest['components']['value'].update(minW=0),
    lambda manifest: manifest['components']['value'].update(defaultW=1),
    lambda manifest: manifest['components']['value'].update(defaultH=13),
])
def test_component_manifest_rejects_code_and_invalid_design_contracts(mutate):
    manifest = {'version': 1, 'components': copy.deepcopy(COMPONENT_TYPES)}
    mutate(manifest)
    with pytest.raises(HTTPException):
        validate_component_manifest(manifest)


def test_intent_persists_exact_request_and_reply_with_idempotency(broker):
    from mklink.frontend_intents import load_intents, find_intent, reply_intent
    request = intent(broker)
    entry = broker.submit_intent(request)
    root = broker.target['project_root']
    assert entry['status'] == 'pending' and entry['revision'] == 0
    assert find_intent(root, 'intent_one') == entry
    assert entry['request'] == request and entry['target'] == broker.target
    broker.exchange({'report': report(broker, 2), 'receipts': []})
    assert broker.submit_intent(request)['duplicate']
    assert_error('ID_CONFLICT', broker.submit_intent, {**request, 'message': 'different'})
    reply = {'request_id': 'intent_one', 'revision': 0, 'reply': '已分析：请比较两组电流波形。'}
    result = reply_intent(root, reply, broker.session_id, 123456)
    assert result['revision'] == 1 and result['status'] == 'replied'
    assert reply_intent(root, reply, broker.session_id, 123457)['duplicate']
    assert_error('STALE_REVISION', reply_intent, root, {**reply, 'reply': 'different'}, broker.session_id, 123458)
    assert load_intents(root)['requests'][0] == result


def test_intent_requires_live_page_revision_and_target(broker):
    assert_error('STALE_REVISION', broker.submit_intent, intent(broker, revision=0))
    assert_error('WRONG_TARGET', broker.submit_intent, intent(broker, session_id='other'))
    assert_error('PAGE_OFFLINE', broker.submit_intent, intent(broker, page_id='missing'))
    assert_error('INVALID_INPUT', broker.submit_intent, intent(broker, intent='run_shell'))
    assert_error('NOT_FOUND', broker.submit_intent, intent(broker, object_id='not-in-catalog'))
    assert_error('INVALID_INPUT', broker.submit_intent, intent(broker, message=' ' * 4000 + 'x'))
    assert not (Path(broker.target['project_root']) / '.mklink').exists()


def test_oversize_reply_rejection_preserves_readable_inbox(broker):
    from mklink.frontend_intents import reply_intent, find_intent
    original = broker.submit_intent(intent(broker))
    root = broker.target['project_root']
    assert_error('INVALID_INPUT', reply_intent, root,
                 {'request_id': 'intent_one', 'revision': 0, 'reply': ' ' * 16000 + 'x'}, broker.session_id, 120000)
    assert find_intent(root, 'intent_one') == original


def test_intent_freezes_verified_object_and_state_before_page_changes(broker):
    from mklink.frontend_intents import find_intent
    request = intent(broker)
    original = broker.submit_intent(request)
    assert original['context'] == {'object': {'id': 'wave_one'},
                                    'state': {'id': 'wave_one', 'w': 6}, 'page_revision': 1}
    changed = report(broker, 2)
    changed['catalog']['panels'][0]['title'] = 'Renamed waveform'
    changed['state']['value']['panels'][0]['w'] = 12
    broker.exchange({'report': changed, 'receipts': []})
    assert broker.submit_intent(request)['context'] == original['context']
    assert find_intent(broker.target['project_root'], 'intent_one')['context'] == original['context']
    assert_error('INVALID_INPUT', broker.submit_intent, {**intent(broker, request_id='other', revision=2), 'context': {'forged': True}})


def test_intent_context_is_bounded_and_legacy_entries_remain_readable(broker):
    from mklink.frontend_intents import load_intents, FILENAME
    from mklink.frontend_layout import atomic_document
    original = broker.submit_intent(intent(broker))
    legacy = {key: value for key, value in original.items() if key != 'context'}
    atomic_document(broker.target['project_root'], FILENAME, {'version': 1, 'requests': [legacy]})
    assert load_intents(broker.target['project_root'])['requests'] == [legacy]
    large = report(broker, 2)
    large['state']['value']['panels'][0]['state'] = {'preview': 'x' * 65536}
    broker.exchange({'report': large, 'receipts': []})
    with pytest.raises(HTTPException) as caught:
        broker.submit_intent(intent(broker, request_id='large', revision=2))
    assert caught.value.status_code == 413
    assert load_intents(broker.target['project_root'])['requests'] == [legacy]


def test_intent_http_roundtrip_and_old_target_is_read_only(runtime):
    client, control, calls, _, app = runtime
    broker = control.frontend
    client.post(BASE + '/exchange', json={'report': report(broker), 'receipts': []})
    assert client.post(BASE + '/intent', json=intent(broker)).status_code == 200
    session = attach(client)
    pending = call(client, session, 'gui_frontend_intents').json()['requests']
    assert len(pending) == 1 and pending[0]['current_target']
    response = call(client, session, 'gui_frontend_reply', {'request_id': 'intent_one', 'revision': 0, 'reply': '检查完成'})
    assert response.status_code == 200 and response.json()['status'] == 'replied'
    assert client.get(BASE + '/intent', params={'request_id': 'intent_one'}).json()['reply'] == '检查完成'
    app.state.mklink_state['device_generation'] = 2
    assert client.get(BASE + '/intents').json()['requests'][0]['current_target'] is False
    assert client.post(BASE + '/reply', json={'request_id': 'intent_one', 'revision': 1, 'reply': '旧目标'}).status_code == 409
    assert calls == []

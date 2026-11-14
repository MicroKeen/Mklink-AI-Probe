"""Workspaces and user intent persistence never change acquisition state."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import HTTPException

from mklink.frontend_layout import load_layout, save_layout, normalize_layout
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

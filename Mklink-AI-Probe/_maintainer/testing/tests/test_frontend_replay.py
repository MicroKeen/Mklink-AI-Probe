"""Stream explicit recordings to the existing replay parser, never to a device."""
from pathlib import Path

import pytest

from test_shared_runtime import runtime

ROUTE = '/api/runtime/frontend/replay-file'


def replay(client, control, path, **kwargs):
    return client.post(ROUTE, json={'path': str(path)},
                       headers={'X-MKLink-Frontend-Session': control.frontend.session_id}, **kwargs)


@pytest.mark.parametrize('name,content', [
    ('capture.csv', b'timestamp,motor.current\n0,1\n0.1,2\n'),
    ('capture.txt', b'[2026-11-14 12:00:00.000] current=1\n'),
    ('capture.log', b'timestamp_ms;motor\n0;2\n'),
    ('capture.jsonl', b'{"_t":0,"motor.current":1}\n'),
    ('capture.ndjson', b'{"event":"discontinuity","reason":1}\n{"timestamp_us":100,"motor":2}\n'),
])
def test_replay_streams_original_bytes_in_supported_formats(runtime, tmp_path, name, content):
    client, control, calls, managers, _ = runtime
    path = tmp_path / name
    path.write_bytes(content)
    for manager in managers.values():
        manager.running = True
    response = replay(client, control, path)
    assert response.status_code == 200, response.text
    assert response.content == content
    assert int(response.headers['content-length']) == len(content)
    assert name in response.headers['content-disposition']
    assert response.headers['cache-control'] == 'no-store'
    assert calls == [] and all(manager.running for manager in managers.values())


@pytest.mark.parametrize('case,expected', [
    ('missing', 404), ('directory', 422), ('extension', 422), ('unrecognized', 422),
    ('binary', 422), ('relative', 422), ('empty', 413), ('oversize', 413),
])
def test_replay_rejects_nonrecording_paths_and_content(runtime, tmp_path, case, expected):
    client, control, calls, _, _ = runtime
    path = tmp_path / 'capture.csv'
    if case == 'directory':
        path.mkdir()
    elif case == 'extension':
        path = tmp_path / 'capture.exe'
        path.write_bytes(b'timestamp,current\n0,1\n')
    elif case == 'unrecognized':
        path.write_text('unrelated private text', encoding='utf-8')
    elif case == 'binary':
        path.write_bytes(b'\xff\xfe\x00\x00')
    elif case == 'empty':
        path.touch()
    elif case == 'oversize':
        with path.open('wb') as output:
            output.truncate(256 * 1024 * 1024 + 1)
    elif case == 'relative':
        path = Path('relative.csv')
    response = replay(client, control, path)
    assert response.status_code == expected, response.text
    assert calls == []


def test_replay_keeps_auth_origin_schema_and_target_checks(runtime, tmp_path):
    client, control, calls, _, app = runtime
    path = tmp_path / 'capture.csv'
    path.write_text('timestamp,current\n0,1\n', encoding='utf-8')
    body = {'path': str(path)}
    session = control.frontend.session_id
    assert client.post(ROUTE, json=body, headers={'X-Auth-Token': 'invalid'}).status_code == 401
    assert client.post(ROUTE, json=body, headers={'Origin': 'https://foreign.test'}).status_code == 403
    assert client.post(ROUTE, json=body).status_code == 422
    headers = {'X-MKLink-Frontend-Session': session}
    for invalid in ({'path': []}, {'path': str(path), 'execute': True}, {'path': 'x' * 4097}):
        assert client.post(ROUTE, json=invalid, headers=headers).status_code == 422
    app.state.mklink_state['device_generation'] = 2
    assert client.post(ROUTE, json=body, headers=headers).status_code == 409
    assert calls == []


def test_replay_rejects_redirected_parent_path(runtime, tmp_path, monkeypatch):
    client, control, calls, _, _ = runtime
    path = tmp_path / 'capture.csv'
    path.write_bytes(b'timestamp,current\n0,1\n')
    original = Path.lstat
    class Redirected:
        st_mode = 0o120777
        st_file_attributes = 0
    monkeypatch.setattr(Path, 'lstat', lambda self: Redirected() if self == path.parent else original(self))
    assert replay(client, control, path).status_code == 422
    assert calls == []


def test_replay_rechecks_target_after_disk_validation(runtime, tmp_path, monkeypatch):
    client, control, calls, _, app = runtime
    path = tmp_path / 'capture.csv'
    path.write_bytes(b'timestamp,current\n0,1\n')
    from mklink import frontend_replay
    original = frontend_replay.recording_file
    def changing_target(body):
        result = original(body)
        app.state.mklink_state['device_generation'] = 2
        return result
    monkeypatch.setattr(frontend_replay, 'recording_file', changing_target)
    response = replay(client, control, path)
    assert response.status_code == 409 and response.json()['detail']['code'] == 'WRONG_TARGET'
    assert calls == []

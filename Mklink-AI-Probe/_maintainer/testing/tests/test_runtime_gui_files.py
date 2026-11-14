import asyncio
from pathlib import Path
import pytest
from fastapi import HTTPException
from mklink.runtime_gui_files import GuiFiles


def test_file_delivery_is_once_and_window_bound(tmp_path):
    path = tmp_path / 'trace.jsonl'
    path.write_bytes(b'one\ntwo\n')
    files = GuiFiles()
    delivery = files.prepare(str(path), 'chosen')
    token = delivery['url'].rsplit('/', 1)[1]
    with pytest.raises(HTTPException): files.response(token, 'other')
    response = files.response(token, 'chosen')
    async def read():
        return b''.join([chunk async for chunk in response.body_iterator])
    assert asyncio.run(read()) == path.read_bytes()
    with pytest.raises(HTTPException): files.response(token, 'chosen')
    assert not files.files


def test_file_validation_and_expiry(tmp_path):
    files = GuiFiles()
    for path in ['relative.jsonl', str(tmp_path), str(tmp_path / 'missing')]:
        with pytest.raises(HTTPException): files.prepare(path, 'window')
    path = tmp_path / 'trace.jsonl'
    path.write_bytes(b'x')
    files.prepare(str(path), 'window')
    entry = next(iter(files.files.values()))
    entry['expires'] = 0
    files.prune()
    assert entry['file'].closed and not files.files


def test_unused_files_expire_without_another_request_and_release_by_window(tmp_path, monkeypatch):
    callbacks = []
    class Loop:
        def call_later(self, seconds, callback, token): callbacks.append((seconds, callback, token))
    monkeypatch.setattr(asyncio, 'get_running_loop', lambda: Loop())
    path = tmp_path / 'file'
    path.write_bytes(b'one')
    files = GuiFiles()
    files.prepare(str(path), 'a')
    first = next(iter(files.files.values()))['file']
    seconds, callback, token = callbacks[0]
    assert seconds == 60
    callback(token)
    assert first.closed and not files.files
    files.prepare(str(path), 'a')
    files.prepare(str(path), 'b')
    files.release_window('a')
    assert len(files.files) == 1 and next(iter(files.files.values()))['window_id'] == 'b'
    files.release_window('b')

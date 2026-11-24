from pathlib import Path
from unittest.mock import patch

import pytest

from mklink.mux import MuxTargetError
from mklink.remote.dashboards import SystemViewStreamManager
from mklink.symbol_sources import AmbiguousSymbolSource, match_upload, remember_source


def test_symbol_profile_matches_content_and_isolates_projects(tmp_path):
    from io import BytesIO
    from types import SimpleNamespace
    from mklink.remote.api import _store_uploaded_file_source
    def uploaded(data):
        return _store_uploaded_file_source(SimpleNamespace(filename='app.axf', file=BytesIO(data)),
                                           tmp_path, ('.axf',))
    def register(directory):
        directory.mkdir()
        elf = directory / 'app.axf'
        elf.write_bytes(b'build-1')
        remember_source(tmp_path, elf)
        return elf
    first = register(tmp_path/'one')
    assert match_upload(tmp_path, uploaded(b'build-1'))['path'] == str(first)
    assert match_upload(tmp_path, uploaded(b'build-2')) == uploaded(b'build-2')
    second = register(tmp_path/'two')
    with pytest.raises(AmbiguousSymbolSource, match='多个'):
        match_upload(tmp_path, uploaded(b'build-1'))
    first.write_bytes(b'build-2')
    assert match_upload(tmp_path, uploaded(b'build-1'))['path'] == str(second)
    assert match_upload(tmp_path, uploaded(b'build-2'))['path'] == str(first)


def test_trace_summary_can_retry_without_touching_jsonl(tmp_path):
    from types import SimpleNamespace
    mgr = SystemViewStreamManager()
    mgr._parser = mgr._create_parser()
    mgr._running = True
    mgr._recording_device = SimpleNamespace(_project_root=str(tmp_path))
    started = mgr.start_recording()
    trace = Path(started['recording_path'])
    assert not started['recording_summary_path']
    logger = mgr._recording
    with patch.object(logger, '_write_text_summary', side_effect=PermissionError(13, 'access denied', str(logger.summary_path))):
        failed = mgr.stop_recording()
    raw = trace.read_bytes()
    assert failed['summary_pending'] and 'JSONL 已保存' in failed['recording_error']
    assert not failed['recording_summary_path'] and not failed['recording']
    done = mgr.stop_recording()
    assert not done['summary_pending'] and not done['recording_error'] and mgr.running
    assert trace.read_bytes() == raw
    assert Path(done['recording_summary_path']).is_file()


def test_read_error_includes_operation_address_length_and_recovery():
    import struct
    error = MuxTargetError(5, 0x16, struct.pack('<IH', 0x010bd198, 24))
    for word in ['0x010BD198', '24', '供电', 'opcode 0x16', 'status 5']:
        assert word in str(error)


def test_desktop_trace_belongs_to_user_project(tmp_path):
    from mklink.systemview_logs import capture_project
    fallback = tmp_path / 'com.microkeen.mklink-ai-probe' / 'workspace'
    app = tmp_path / 'control'
    output = app / 'build' / 'output'
    output.mkdir(parents=True)
    (app / 'CMakeLists.txt').touch()
    elf = output / 'control.elf'
    elf.touch()
    assert capture_project(fallback, elf) == app
    assert capture_project(tmp_path, elf) == tmp_path
    assert capture_project(fallback, None, str(output)) == output
    with pytest.raises(ValueError, match='日志位置'):
        capture_project(fallback)


def test_competing_poll_allows_one_display_write_without_replaying_hardware():
    import asyncio
    from types import SimpleNamespace
    from fastapi import HTTPException
    from mklink.runtime_api import RuntimeControl

    async def exercise():
        control = RuntimeControl(SimpleNamespace(state=SimpleNamespace()), {})
        writes = []

        async def apply():
            writes.append('saved')

        await control.operation_lock.acquire()
        waiting = asyncio.create_task(control.run_operation('/api/dash/superwatch/workspace', apply))
        await asyncio.sleep(.01)
        assert not waiting.done() and not writes
        with pytest.raises(HTTPException) as busy:
            await control.run_operation('/api/device/write-memory', apply)
        assert busy.value.status_code == 409
        control.operation_lock.release()
        await waiting
        assert writes == ['saved']

    asyncio.run(exercise())


def test_trace_summary_counts_only_saved_events_and_handles_implicit_switches(tmp_path):
    import json
    from mklink.systemview_logger import SystemViewJsonlLogger
    logger = SystemViewJsonlLogger(str(tmp_path), {})
    logger.write_events([{'kind': 'task_start_exec', 'task_id': 1, 't_us': 10},
                         {'kind': 'isr_enter', 't_us': 11}])
    logger.write_events([{'kind': 'isr_exit', 't_us': 20},
                         {'kind': 'task_start_exec', 'task_id': 2, 't_us': 22},
                         {'kind': 'trace_stop', 't_us': 27}])
    logger.close({'stream_events': 513})
    footer = json.loads(logger.path.read_text(encoding='utf-8').splitlines()[-1])
    assert (footer['events'], footer['stream_events']) == (5, 513)
    assert {t['task_id']: t['run_time'] for t in footer['top_tasks']} == {1: 3, 2: 5}
    assert 'events: 5\n' in logger.summary_path.read_text(encoding='utf-8')

from array import array
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mklink.superwatch_recording import SuperWatchRecorder
from mklink.remote.dashboards import SuperWatchStreamManager


def rows(directory):
    return [json.loads(line) for path in sorted(directory.glob('*.jsonl'))
            for line in path.read_text(encoding='utf-8').splitlines()]


def manager():
    hub = SimpleNamespace(set_subscribe_callback=lambda callback: None, publish=lambda *a, **kw: None)
    sw = SuperWatchStreamManager(hub)
    sw._metadata_cache = (b'', '[{"name":"value"}]', 1)
    sw._running = True
    sw._collecting.set()
    return sw


def test_acquisition_does_not_record_until_explicit_start(tmp_path):
    sw = manager()
    for i in range(100):
        sw._publish_sample_values_locked([i], channel_count=1, sample_time=i)
    sw._flush_binary_batch()
    assert sw.recording_status() == {'state': 'idle', 'active': False}
    assert not list(tmp_path.iterdir())


def test_recording_keeps_ordered_boundaries_without_inventing_values(tmp_path):
    sw = manager()
    sw.start_recording(str(tmp_path))
    for i, boundary in enumerate((0, 0, 1, 0, 2)):
        sw._publish_sample_values_locked([i], channel_count=1, sample_time=i*10, break_before=boundary)
    result = sw.stop_recording()
    assert result['samples'] == 5
    data = rows(tmp_path)
    assert [r['value'] for r in data if 'value' in r] == list(range(5))
    assert data[2] == {'event': 'discontinuity', 'reason': 1}
    assert data[5] == {'event': 'discontinuity', 'reason': 2}


def test_recording_keeps_all_samples_beyond_display_buffer_and_drains_tail(tmp_path):
    sw = manager()
    sw._publish_sample_values_locked([-1], channel_count=1, sample_time=0)
    sw.start_recording(str(tmp_path))
    for i in range(60_001):
        sw._publish_sample_values_locked([i], channel_count=1, sample_time=i / 10)
    result = sw.stop_recording()
    sw._publish_sample_values_locked([999999], channel_count=1, sample_time=6001)
    sw._flush_binary_batch()
    data = rows(tmp_path)
    assert result['state'] == 'completed' and result['samples'] == len(data) == 60_001
    assert [r['value'] for r in data] == list(range(60_001))
    assert data[-1]['_t'] == 6
    assert result['bytes'] == sum(p.stat().st_size for p in tmp_path.glob('*.jsonl'))


def test_parts_retain_every_row_and_layout_without_overwriting(tmp_path):
    recorder = SuperWatchRecorder(tmp_path, max_values=3)
    recorder.append(array('f', range(8)), array('d', range(8)), [{'name': 'value'}])
    recorder.append(array('f', [42]), array('d', [8]), [{'name': 'new_name'}])
    result = recorder.stop()
    assert result['parts'] == 4
    assert [r.get('value', r.get('new_name')) for r in rows(tmp_path)] == [*range(8), 42]
    second = SuperWatchRecorder(tmp_path)
    assert second.status()['path'] != result['path']
    second.stop()


def test_recording_preserves_unicode_precision_and_valid_prefix_on_error(tmp_path):
    recorder = SuperWatchRecorder(tmp_path)
    recorder.append(array('f', [1.25, -2.5, 3.75]),
                    array('d', [0.125, 1234567.875, float('nan')]),
                    [{'name': '温度"\\'}], boundaries=((1, 2),))
    result = recorder.stop()
    assert result['state'] == 'failed' and 'invalid sample' in result['error']
    assert rows(tmp_path) == [
        {'温度"\\': 1.25, '_t': 0.000125},
        {'event': 'discontinuity', 'reason': 2},
        {'温度"\\': -2.5, '_t': 1234.567875},
    ]


@pytest.mark.parametrize('names', [('值"\\\n',), ('x', 'x', '_t', '温度')])
def test_numeric_recording_is_byte_identical_to_json_encoder(tmp_path, names):
    import math
    width = len(names)
    choices = [0.0, -0.0, 1.17549435e-38, 3.4028234e38, -1.0, float('nan')]
    values = array('f', [choices[i % len(choices)] for i in range(100 * width)])
    times = array('d', [i * 0.00123456789 for i in range(100)])
    # Preserve the existing rule that a partially invalid row omits that
    # channel, while a wholly invalid row fails explicitly.
    for row in range(100):
        if not any(math.isfinite(v) for v in values[row*width:(row+1)*width]):
            values[row*width] = 0.0
    expected = []
    for row, timestamp in enumerate(times):
        point = {name: float(values[row*width+i]) for i, name in enumerate(names)
                 if math.isfinite(values[row*width+i])}
        point['_t'] = timestamp / 1000
        expected.append(json.dumps(point, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
    recorder = SuperWatchRecorder(tmp_path)
    recorder.append(values, times, [{'name': n} for n in names])
    result = recorder.stop()
    assert result['state'] == 'completed'
    data = b''.join(p.read_bytes() for p in sorted(tmp_path.glob('*.jsonl')))
    assert data == ''.join(expected).encode('utf-8')
    assert result['bytes'] == len(data)


def test_overflow_and_disk_error_are_visible_not_success(tmp_path):
    recorder = SuperWatchRecorder(tmp_path, queue_bytes=1)
    recorder.append(array('f', [1]), array('d', [0]), [{'name': 'v'}])
    assert recorder.stop()['state'] == 'failed'
    recorder = SuperWatchRecorder(tmp_path, _local=True)
    recorder._file.close()
    recorder.append(array('f', [1]), array('d', [0]), [{'name': 'v'}])
    result = recorder.stop()
    assert result['state'] == 'failed' and result['error'] and not result['active']


def test_http_controls_share_manager_and_capture_stop_finalizes(tmp_path, monkeypatch):
    from mklink.remote import api, dashboards
    sw = manager()
    # Recording can be armed before acquisition, metadata or a device exists.
    sw._running = False
    sw._collecting.clear()
    sw._metadata_cache = (b'', '[]', 0)
    managers = {**dashboards.get_managers(), 'superwatch': sw}
    monkeypatch.setattr(dashboards, 'get_managers', lambda: managers)
    client = TestClient(api.create_app(auth_token=None, project_root=str(tmp_path)))
    base = '/api/dash/superwatch/recording/'
    assert client.post(base + 'start', json={'directory': 'relative'}).status_code == 400
    assert client.post(base + 'start', json={'directory': str(tmp_path)}).status_code == 200
    assert sw.recording_status()['samples'] == 0
    assert sw.recording_status()['active'] is True
    assert client.post(base + 'start', json={'directory': str(tmp_path)}).status_code == 409
    sw._metadata_cache = (b'', '[{"name":"value"}]', 1)
    sw._running = True
    sw._collecting.set()
    sw._publish_sample_values_locked([7], channel_count=1, sample_time=100)
    sw.stop()
    result = client.get(base + 'status').json()
    assert result['state'] == 'completed' and result['samples'] == 1
    assert client.post(base + 'stop').json() == result
    assert rows(tmp_path) == [{'value': 7, '_t': .1}]


def test_idle_recording_can_stop_and_restart_without_samples(tmp_path):
    sw = manager()
    sw._running = False
    sw._collecting.clear()
    first = sw.start_recording(str(tmp_path))
    result = sw.stop_recording()
    assert result['state'] == 'completed' and not result['active']
    assert result['samples'] == 0 and rows(tmp_path) == []
    second = sw.start_recording(str(tmp_path))
    assert first['path'] != second['path']
    sw.stop()
    assert sw.recording_status()['state'] == 'completed'


def test_cannot_arm_recording_while_old_acquisition_is_stopping(tmp_path):
    sw = manager()
    sw._running = False
    sw._thread = SimpleNamespace(is_alive=lambda: True)
    with pytest.raises(RuntimeError, match='still stopping'):
        sw.start_recording(str(tmp_path))
    assert not list(tmp_path.iterdir())


def test_worker_startup_does_not_block_acquisition(tmp_path, monkeypatch):
    import threading
    entered, release = threading.Event(), threading.Event()
    class DelayedRecorder:
        def __init__(self, directory):
            entered.set()
            assert release.wait(2)
        def status(self): return {'state': 'recording', 'active': True}
    monkeypatch.setattr('mklink.superwatch_recording.SuperWatchRecorder', DelayedRecorder)
    sw = manager()
    thread = threading.Thread(target=sw.start_recording, args=(str(tmp_path),))
    thread.start()
    try:
        assert entered.wait(2)
        assert sw._read_lock.acquire(timeout=.2)
        sw._read_lock.release()
        assert sw.recording_status() == {'state': 'idle', 'active': False}
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive() and sw.recording_status()['active']


def test_recording_worker_exit_is_failure_and_reaped(tmp_path):
    recorder = SuperWatchRecorder(tmp_path)
    process = recorder._worker.process
    process.terminate()
    process.wait(timeout=5)
    recorder.append(array('f', [1]), array('d', [0]), [{'name': 'v'}])
    result = recorder.stop()
    assert result['state'] == 'failed' and result['error'] and result['samples'] == 0
    assert process.poll() is not None
    assert not recorder._worker._inbox._thread.is_alive()
    assert not recorder._worker._writer.is_alive()


def test_stalled_worker_pipe_is_bounded_and_reaped(tmp_path, monkeypatch):
    import sys
    from mklink import _recording_worker as worker
    popen = worker.subprocess.Popen
    stalled = (
        "import json,sys,time; "
        "print(json.dumps(dict(state='recording',active=True,path='',parts=0,samples=0,bytes=0,error='')),flush=True); "
        "sys.stdin.buffer.read(1); time.sleep(60)"
    )
    monkeypatch.setattr(worker.subprocess, 'Popen',
                        lambda command, **kw: popen([sys.executable, '-u', '-c', stalled], **kw))
    recorder = SuperWatchRecorder(tmp_path)
    monkeypatch.setattr(worker, 'REPLY_TIMEOUT', .25)
    recorder.append(array('f', [1]) * 100_000, array('d', range(100_000)), [{'name': 'v'}])
    result = recorder.stop(timeout=5)
    assert result['state'] == 'failed' and 'timed out' in result['error']
    assert recorder._worker.process.poll() is not None
    assert not recorder._worker._writer.is_alive()
    assert not recorder._worker._inbox._thread.is_alive()


def test_mcp_recording_actions_use_shared_capabilities(monkeypatch):
    import asyncio
    from fastmcp import Client
    from mklink.runtime_mcp import build_server
    calls = []
    class Adapter:
        info = {}
        def __init__(self, **kwargs): pass
        def connect(self, **kwargs): return {'connected': True}
        def call(self, capability, arguments=None):
            calls.append((capability, arguments))
            return {'state': 'completed'}
        def close(self): pass
    # Use the real MCP tool validation and dispatch without opening hardware.
    import mklink.runtime_mcp as runtime_mcp
    monkeypatch.setattr(runtime_mcp, 'RuntimeClient', Adapter)
    async def scenario():
        async with Client(build_server()) as client:
            await client.call_tool('connect', {})
            for action in ('recording_start', 'recording_status', 'recording_stop'):
                result = await client.call_tool('superwatch', {'action': action, 'arguments': {}})
                assert not result.is_error
    asyncio.run(scenario())
    assert [name for name, _ in calls] == ['superwatch_recording_start', 'superwatch_recording_status', 'superwatch_recording_stop']

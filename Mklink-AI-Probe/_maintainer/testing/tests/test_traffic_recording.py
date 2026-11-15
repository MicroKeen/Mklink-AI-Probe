import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mklink.traffic_recording import TrafficRecorder
from mklink.remote.dashboards import RttStreamManager, SerialStreamManager
from test_serial_automation import ports, wait_for


def records(directory):
    return [json.loads(line) for p in sorted(directory.glob('*.jsonl'))
            for line in p.read_text(encoding='utf-8').splitlines()]


def test_lossless_raw_direction_session_rotation_and_no_overwrite(tmp_path):
    recorder = TrafficRecorder(tmp_path, 'rtt', part_events=2)
    for i in range(7):
        recorder.append(1, bytes(range(256)), 'TX' if i % 2 else 'RX', f'session-{i//3}', i + .125)
    status = recorder.stop()
    assert status['state'] == 'completed' and status['samples'] == 7 and status['parts'] == 4
    rows = records(tmp_path)
    assert all(r['complete'] for r in rows if r['type'] == 'end')
    frames = [r for r in rows if r['type'] == 'data']
    assert [r['time'] for r in frames] == [i + .125 for i in range(7)]
    assert all(bytes.fromhex(r['hex']) == bytes(range(256)) for r in frames)
    assert [r['direction'] for r in frames] == ['RX','TX','RX','TX','RX','TX','RX']
    assert frames[-1]['session'] == 'session-2'
    another = TrafficRecorder(tmp_path, 'rtt')
    assert another.status()['path'] != status['path']
    another.stop()


def test_overflow_or_disk_failure_is_reported_instead_of_success(tmp_path):
    recorder = TrafficRecorder(tmp_path, 'serial', queue_bytes=1)
    recorder.append('COM1', b'hello', 'RX', 's')
    status = recorder.stop()
    assert status['state'] == 'failed' and not status['active']
    assert records(tmp_path)[-1]['complete'] is False
    recorder = TrafficRecorder(tmp_path, 'serial')
    recorder._file.close()
    recorder.append('COM1', b'hello', 'RX', 's')
    assert recorder.stop()['state'] == 'failed'


def test_rtt_http_per_channel_records_without_viewer_and_stop_drains(tmp_path, monkeypatch):
    from mklink.remote import api, dashboards
    manager = RttStreamManager()
    managers = {**dashboards.get_managers(), 'rtt': manager}
    monkeypatch.setattr(dashboards, 'get_managers', lambda: managers)
    client = TestClient(api.create_app(auth_token=None, project_root=str(tmp_path)))
    base = '/api/dash/rtt/traffic-recording/'
    assert client.post(base + 'start', json={'directory':'relative'}).status_code == 400
    assert client.post(base + 'start', json={'directory':str(tmp_path), 'channel':8}).status_code == 422
    assert client.post(base + 'start', json={'directory':str(tmp_path), 'channel':2}).status_code == 200
    assert client.post(base + 'start', json={'directory':str(tmp_path), 'channel':2}).status_code == 409
    assert client.get(base + 'status?channel=0').json()['active'] is False
    manager._capture_session = 'test'
    manager._running = True
    manager._active_generation = manager._generation = object()
    manager._device = SimpleNamespace(rtt_write=lambda data, **kw: True, _rtt_session=SimpleNamespace(dropped_bytes={2:3}))
    manager._start_info = {'transport':'cdc-mux', 'down_buffers':[{'channel':2,'active':True}]}
    manager.feed_channel_bytes(0, b'unselected')
    for _ in range(100): manager.feed_channel_bytes(2, b'\xe4\xb8\xad\x00\xff')
    manager.write(b'tx\x00', 2)
    manager.stop()
    result = client.get(base + 'status?channel=2').json()
    assert result['state'] == 'completed' and result['samples'] == 101
    frames = [r for r in records(tmp_path) if r['type'] == 'data']
    assert b''.join(bytes.fromhex(r['hex']) for r in frames if r['direction'] == 'RX') == b'\xe4\xb8\xad\x00\xff' * 100
    assert frames[0]['lost_bytes'] == 3
    assert frames[-1]['direction'] == 'TX' and frames[-1]['hex'] == b'tx\x00'.hex()
    assert result['export_state'] == 'pending' and not list(tmp_path.glob('*.txt'))
    assert client.post(base + 'export', json={'path': result['path'], 'channel': 0}).status_code == 409
    assert client.post(base + 'export', json={'path': result['path'], 'channel': 2}).status_code == 200
    from test_recording_text import exported
    assert exported(manager.traffic_recordings._recorders[2]._export)['export_state'] == 'completed'
    client.post(base + 'start', json={'directory':str(tmp_path), 'channel':2})
    assert client.post(base + 'stop', json={'channel': 2}).json()['active'] is False


def test_serial_records_all_ports_raw_rx_tx_without_browser_and_closes_with_monitor(ports, tmp_path):
    manager = SerialStreamManager()
    manager.traffic_recordings.start(str(tmp_path))
    manager.start([{'port':'A'}, {'port':'B'}])
    for port in ports.instances:
        port.write = lambda data: len(data)
    try:
        ports.instances[-2].rx.put(b'a\x00\xff')
        ports.instances[-1].rx.put(b'b\xe4\xb8\xad')
        assert manager.send('A', b'tail')
        wait_for(lambda: manager.get_status()['stats']['rx_bytes'] == 7)
        manager.stop()
        rows = [r for r in records(tmp_path) if r['type'] == 'data']
        assert {(r['source'], r['direction'], r['hex']) for r in rows} == {
            ('A','RX',b'a\x00\xff'.hex()), ('B','RX',b'b\xe4\xb8\xad'.hex()), ('A','TX',b'tail'.hex())}
        assert manager.traffic_recordings.status()['state'] == 'completed'
    finally:
        manager.stop()

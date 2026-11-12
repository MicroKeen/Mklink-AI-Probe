"""TXT is a deferred readable companion; JSONL stays the authoritative capture."""
from array import array
import json
from pathlib import Path
import time

import pytest

from mklink.superwatch_recording import SuperWatchRecorder
from mklink.traffic_recording import TrafficRecorder


def exported(recorder):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        status = recorder.status()
        if status.get('text_state') in {'completed', 'failed'}:
            return status
        time.sleep(.01)
    pytest.fail(f'TXT did not finish: {recorder.status()}')


def test_superwatch_defers_text_and_keeps_samples_precision_and_boundaries(tmp_path):
    recorder = SuperWatchRecorder(tmp_path, max_values=2)
    try:
        recorder.append(array('f', [1.25, -2.5, 3.75]), array('d', [.001, .002, 1234.567]),
                        [{'name': '温度'}], boundaries=((2, 2),))
        assert recorder.status().get('text_state') == 'pending'
        assert not list(tmp_path.glob('*.txt'))
    finally:
        recorder.stop()
    status = exported(recorder)
    assert status['state'] == 'completed' and status['text_state'] == 'completed'
    text_parts = sorted(tmp_path.glob('*.txt'))
    assert len(text_parts) == status['parts'] == 2
    text = ''.join(p.read_text(encoding='utf-8') for p in text_parts)
    assert '[t=0.000001000 s] 温度=1.25' in text
    assert '[t=0.000002000 s] 温度=-2.5' in text
    assert '[t=1.234567000 s] 温度=3.75' in text
    assert 'DISCONTINUITY reason=2' in text
    assert 'acquisition-relative' in text and 'Recording started:' in text
    assert status['text_parts'] == 2 and Path(status['text_path']) == text_parts[-1]


def test_rtt_joins_unicode_lines_across_chunks_and_parts_with_rx_tx_and_loss(tmp_path):
    recorder = TrafficRecorder(tmp_path, 'rtt', part_events=2)
    try:
        recorder.append(2, b'first \xe4\xb8', 'RX', 's1', 1700000000.125)
        recorder.append(2, b'\xad\r', 'RX', 's1', 1700000000.25)
        recorder.append(2, b'\nnext\n\x00\xff', 'RX', 's1', 1700000000.5)
        recorder.append(2, b'command\n', 'TX', 's1', 1700000001)
        assert recorder.status().get('text_state') == 'pending'
        assert not list(tmp_path.glob('*.txt'))
    finally:
        recorder.stop()
    status = exported(recorder)
    assert status['text_state'] == 'completed' and status['parts'] == 2
    text = ''.join(p.read_text(encoding='utf-8') for p in sorted(tmp_path.glob('*.txt')))
    assert 'first 中' in text and '�' not in text
    assert 'channel=2 RX' in text and 'channel=2 TX' in text
    assert '\\x00\\xff' in text and 'command' in text
    assert 'session=s1' in text
    assert '.125000' in text
    assert all(p.with_suffix('.jsonl').is_file() for p in tmp_path.glob('*.txt'))


def test_text_failure_does_not_change_successful_json_recording_or_overwrite(tmp_path):
    recorder = TrafficRecorder(tmp_path, 'rtt')
    path = Path(recorder.status()['path']).with_suffix('.txt')
    path.write_text('user data', encoding='utf-8')
    recorder.append(0, b'hello\n', 'RX', 's', 1700000000)
    recorder.stop()
    status = exported(recorder)
    assert status['state'] == 'completed'
    assert status['text_state'] == 'failed' and status['text_error']
    assert path.read_text(encoding='utf-8') == 'user data'
    rows = [json.loads(line) for line in path.with_suffix('.jsonl').read_text().splitlines()]
    assert rows[-1]['complete'] is True
    assert bytes.fromhex(rows[1]['hex']) == b'hello\n'


def test_failed_recording_exports_valid_prefix_with_incomplete_warning(tmp_path):
    recorder = SuperWatchRecorder(tmp_path)
    recorder.append(array('f', [42, 43]), array('d', [1, float('nan')]), [{'name': 'v'}])
    assert recorder.stop()['state'] == 'failed'
    status = exported(recorder)
    assert status['text_state'] == 'completed'
    text = Path(status['text_path']).read_text(encoding='utf-8')
    assert 'INCOMPLETE' in text and 'v=42.0' in text
    assert 'v=43.0' not in text


def test_serial_recording_does_not_gain_unrequested_export(tmp_path):
    recorder = TrafficRecorder(tmp_path, 'serial')
    recorder.append('COM1', b'data', 'RX', 's')
    recorder.stop()
    assert 'text_state' not in recorder.status()
    assert not list(tmp_path.glob('*.txt'))


def test_rtt_loss_does_not_join_fragments_across_missing_bytes(tmp_path):
    recorder = TrafficRecorder(tmp_path, 'rtt')
    recorder.append(0, b'prefix\xe4', 'RX', 'session', 1700000000)
    recorder.append(0, b'after gap\n', 'RX', 'session', 1700000001, lost_bytes=3)
    recorder.stop()
    status = exported(recorder)
    text = Path(status['text_path']).read_text(encoding='utf-8')
    assert 'lost_bytes=3' in text
    lines = [line for line in text.splitlines() if not line.startswith('#')]
    assert len(lines) == 2
    assert 'prefix\\xe4' in lines[0] and '[partial line]' in lines[0]
    assert 'after gap' in lines[1] and 'prefix' not in lines[1]


def test_rtt_long_lines_and_session_restart_are_bounded(tmp_path):
    recorder = TrafficRecorder(tmp_path, 'rtt')
    recorder.append(0, b'a' * 100_000, 'RX', 's1', 1700000000)
    recorder.append(0, b'new session\n', 'RX', 's2', 1700000001)
    recorder.stop()
    status = exported(recorder)
    assert status['text_state'] == 'completed'
    lines = [line for line in Path(status['text_path']).read_text().splitlines() if not line.startswith('#')]
    assert max(map(len, lines)) < 17000
    assert 'new session' in lines[-1] and 'session=s2' in lines[-1]
    assert sum(line.split('session=s1 ', 1)[1].split(' [', 1)[0].count('a')
               for line in lines if 'session=s1 ' in line) == 100_000


def test_export_continues_after_owning_python_process_exits(tmp_path):
    import os
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[3]
    script = """from mklink.traffic_recording import TrafficRecorder
import sys
r = TrafficRecorder(sys.argv[1], 'rtt')
r.append(0, b'parent exit\\n', 'RX', 'session', 1700000000)
r.stop()
"""
    subprocess.run([sys.executable, '-c', script, str(tmp_path)], cwd=tmp_path,
                   env=dict(os.environ, PYTHONPATH=str(root)), timeout=10, check=True)
    manifest, = tmp_path.glob('*-text-export.json')
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = json.loads(manifest.read_text(encoding='utf-8'))
        if result['text_state'] != 'generating':
            break
        time.sleep(.01)
    assert result['text_state'] == 'completed'
    assert 'parent exit' in Path(result['text_path']).read_text(encoding='utf-8')


def test_worker_launch_failure_persists_failure_without_changing_source(tmp_path, monkeypatch):
    from mklink.recording_text import TextExport
    source = tmp_path / 'rtt-test-0001.jsonl'
    source.write_bytes(b'original')
    def fail(*args, **kwargs):
        raise OSError('worker launch denied')
    monkeypatch.setattr('mklink.recording_text.subprocess.Popen', fail)
    export = TextExport('rtt')
    export.start(dict(path=str(source), parts=1, started_at=1700000000, state='completed'))
    assert export.status()['text_state'] == 'failed'
    manifest, = tmp_path.glob('*-text-export.json')
    assert json.loads(manifest.read_text())['text_state'] == 'failed'
    assert source.read_bytes() == b'original'


def test_frozen_export_launch_owns_environment_and_does_not_inherit_pipes(tmp_path, monkeypatch):
    import os
    import sys
    from mklink import recording_text
    source = tmp_path / 'superwatch-test-0001.jsonl'
    source.write_text('{"v":1,"_t":0}\n')
    calls = []
    real_popen = recording_text.subprocess.Popen
    def source_launch(command, **kwargs):
        calls.append((command, kwargs.copy()))
        return real_popen([sys.executable, str(Path(recording_text.__file__)), command[-1]], **kwargs)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(recording_text.subprocess, 'Popen', source_launch)
    monkeypatch.setenv('MKLINK_PARENT_JOB_BREAKAWAY_OK', '1')
    export = recording_text.TextExport('superwatch')
    export.start(dict(path=str(source), parts=1, started_at=1700000000, state='completed'))
    assert exported(export)['text_state'] == 'completed'
    command, options = calls[0]
    assert command[1] == '--internal-recording-text'
    assert options['env']['PYINSTALLER_RESET_ENVIRONMENT'] == '1'
    assert options['env']['TEMP'] == str(tmp_path)
    assert options['cwd'] == str(tmp_path)
    if os.name == 'nt':
        assert options['creationflags'] & recording_text.subprocess.CREATE_BREAKAWAY_FROM_JOB

"""Both executable entries service the same Pack and guarded-child protocol."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from mklink.internal_process import dispatch_internal_process

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('entry', ['cli', 'remote'])
def test_pack_protocol_reaches_worker_in_both_entries(entry):
    command = ([sys.executable, '-m', 'mklink'] if entry == 'cli' else
               [sys.executable, str(ROOT/'packaging/site_agent/entry.py')])
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    result = subprocess.run(command+['--internal-pack-worker'], input='{}\n',
                            capture_output=True, text=True, env=env, cwd=ROOT, timeout=10)
    assert result.returncode == 1
    message = json.loads(result.stdout)
    assert message['type'] == 'error' and 'code' in message
    assert 'usage:' not in result.stderr


@pytest.mark.parametrize('entry', ['cli', 'remote'])
def test_guard_reaches_child_and_preserves_exit_code(entry):
    command = ([sys.executable, '-m', 'mklink'] if entry == 'cli' else
               [sys.executable, str(ROOT/'packaging/site_agent/entry.py')])
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    result = subprocess.run(command+['--internal-process-guard', str(os.getpid()),
                            sys.executable, '-c', 'raise SystemExit(7)'],
                            input='MKLINK-PROCESS-GUARD-GO\n', capture_output=True,
                            text=True, env=env, cwd=ROOT, timeout=10)
    assert result.returncode == 7
    assert result.stdout == 'MKLINK-PROCESS-GUARD-READY\n'


def test_normal_arguments_are_not_internal_and_guard_restores_argv():
    previous = sys.argv
    assert dispatch_internal_process(['start']) is None
    assert dispatch_internal_process(['--internal-pack-worker', 'unexpected']) is None
    assert dispatch_internal_process(['--internal-process-guard']) == 2
    assert sys.argv is previous


@pytest.mark.parametrize('entry', ['cli', 'remote'])
def test_serial_worker_internal_entry_preserves_control_protocol(entry):
    command = ([sys.executable, '-m', 'mklink'] if entry == 'cli' else
               [sys.executable, str(ROOT/'packaging/site_agent/entry.py')])
    result = subprocess.run(command+['--internal-serial-worker', 'loop://', '115200'],
                            input=b'{"op":"close"}\n', capture_output=True,
                            env=dict(os.environ, PYTHONPATH=str(ROOT)), cwd=ROOT, timeout=10)
    assert result.returncode == 0
    assert result.stdout == b''
    assert [json.loads(line) for line in result.stderr.splitlines()] == [
        {'ready': True}, {'result': None}]


def test_serial_worker_invalid_arguments_report_control_error(capsys):
    assert dispatch_internal_process(['--internal-serial-worker']) == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'requires port and baudrate' in json.loads(captured.err)['error']


@pytest.mark.parametrize('entry', ['cli', 'remote'])
def test_recording_worker_entries_finalize_empty_file(entry, tmp_path):
    command = ([sys.executable, '-m', 'mklink'] if entry == 'cli' else
               [sys.executable, str(ROOT/'packaging/site_agent/entry.py')])
    result = subprocess.run(command+['--internal-recording-worker', str(tmp_path), '1000'],
                            input=bytes(12), capture_output=True,
                            env=dict(os.environ, PYTHONPATH=str(ROOT)), cwd=ROOT, timeout=10)
    assert result.returncode == 0, result.stderr
    status = [json.loads(line) for line in result.stdout.splitlines()]
    assert [s['state'] for s in status] == ['recording', 'completed']
    assert status[-1]['samples'] == 0
    assert Path(status[-1]['path']).read_bytes() == b''


def test_recording_worker_filename_launch_without_pythonpath(tmp_path):
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    result = subprocess.run(
        [sys.executable, str(ROOT/'mklink/_recording_worker.py'), str(tmp_path), '1000'],
        input=bytes(12), capture_output=True, env=env, cwd=tmp_path, timeout=10)
    assert result.returncode == 0, result.stderr
    assert [json.loads(line)['state'] for line in result.stdout.splitlines()] == ['recording', 'completed']


@pytest.mark.parametrize('entry', ['cli', 'remote'])
@pytest.mark.parametrize('flag', ['--internal-recording-text', '--internal-recording-export'])
def test_text_export_internal_entry_writes_companion_without_hardware(entry, flag, tmp_path):
    base = tmp_path / 'superwatch-test'
    base.with_name(base.name + '-0001.jsonl').write_text('{"v":42,"_t":0.000001}\n', encoding='utf-8')
    manifest = tmp_path / 'text-export.json'
    manifest.write_text(json.dumps(dict(kind='superwatch', base=str(base), parts=1,
        started_at=1700000000, complete=True, source_error='', export_state='generating',
        export_format='txt', export_path='', export_parts=0, export_error='')), encoding='utf-8')
    command = ([sys.executable, '-m', 'mklink'] if entry == 'cli' else
               [sys.executable, str(ROOT/'packaging/site_agent/entry.py')])
    result = subprocess.run(command + [flag, str(manifest)],
                            capture_output=True, env=dict(os.environ, PYTHONPATH=str(ROOT)),
                            cwd=tmp_path, timeout=10)
    assert result.returncode == 0, result.stderr
    status = json.loads(manifest.read_text(encoding='utf-8'))
    assert status['export_state'] == 'completed'
    assert '[t=0.000001000 s] v=42' in Path(status['export_path']).read_text(encoding='utf-8')

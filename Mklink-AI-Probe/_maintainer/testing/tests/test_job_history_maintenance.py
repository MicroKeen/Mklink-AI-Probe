import json
from pathlib import Path

import pytest

from mklink import job_history
from mklink.runtime import runtime_dir, runtime_lock
from mklink.runtime_jobs import RuntimeJobs

A, B = 'usb-' + 'a' * 24, 'local-' + 'b' * 24


@pytest.fixture
def history(tmp_path, monkeypatch):
    monkeypatch.setenv('MKLINK_RUNTIME_DIR', str(tmp_path / 'runtime'))
    path = runtime_dir(A) / 'jobs.json'
    path.parent.mkdir(parents=True)
    return path


def row(state='unknown'):
    return {'job_id': 'original', 'request_id': 'keep-request', 'fingerprint': 'keep-fingerprint',
            'state': state, 'started': 1.0}


@pytest.mark.parametrize('data', [b'', b'\xff\x89old', b'{unfinished', b'{}', b'[null]',
                                b'[{"state":"running","job_id":"legacy"}]'])
def test_installer_archives_exact_invalid_bytes_and_never_runs_jobs(history, data):
    history.write_bytes(data)
    report = job_history.repair_for_install()
    assert not report['errors']
    entry, = report['archived']
    assert Path(entry['backup']).read_bytes() == data
    assert Path(entry['backup']).with_suffix('.manifest.json').is_file()
    assert json.loads(history.read_bytes()) == []
    assert not list(history.parent.glob('jobs-install-*.tmp'))
    assert job_history.repair_for_install()['archived'] == []


@pytest.mark.parametrize('state', ['running', 'unknown', 'failed', 'succeeded'])
@pytest.mark.parametrize('bom', ['', '\ufeff'])
def test_valid_history_is_preserved_byte_for_byte(history, state, bom):
    data = (bom + json.dumps([row(state)], indent=2)).encode('utf-8')
    history.write_bytes(data)
    report = job_history.repair_for_install()
    assert report == {'version': 1, 'archived': [], 'preserved': 1, 'errors': []}
    assert history.read_bytes() == data


def test_runtime_accepts_bom_and_preserves_duplicate_guard(history):
    from types import SimpleNamespace
    history.write_bytes(b'\xef\xbb\xbf' + json.dumps([row()]).encode())
    control = SimpleNamespace(info={})
    jobs = RuntimeJobs(control, path=history)
    assert not jobs.unread_paths
    assert jobs._previous('keep-request', 'keep-fingerprint')['state'] == 'unknown'


@pytest.mark.parametrize('lock_name', ['backend.lock', 'owner.lock'])
def test_any_live_backend_prevents_the_entire_maintenance(history, lock_name):
    history.write_bytes(b'invalid')
    with runtime_lock(lock_name, B):
        report = job_history.repair_for_install()
    assert report['errors'] and not report['archived']
    assert history.read_bytes() == b'invalid'


def test_archive_failure_preserves_original(history, monkeypatch):
    history.write_bytes(b'original')
    def fail(*args):
        raise OSError('disk full')
    monkeypatch.setattr(job_history, '_write_new', fail)
    report = job_history.repair_for_install()
    assert report['errors'] and not report['archived']
    assert history.read_bytes() == b'original'


def test_replace_failure_keeps_original_and_backup(history, monkeypatch):
    history.write_bytes(b'original')
    def fail(*args):
        raise PermissionError('locked file')
    monkeypatch.setattr(Path, 'replace', fail)
    report = job_history.repair_for_install()
    assert report['errors'] and not report['archived']
    assert history.read_bytes() == b'original'
    backups = list((runtime_dir() / 'history-backups').glob('*.jobs.json'))
    assert len(backups) == 1 and backups[0].read_bytes() == b'original'


def test_read_denial_is_not_permission_to_reset_history(history, monkeypatch):
    history.write_bytes(b'original')
    read = Path.read_bytes
    def guarded(path):
        if path == history:
            raise PermissionError('no read access')
        return read(path)
    monkeypatch.setattr(Path, 'read_bytes', guarded)
    assert job_history.repair_for_install()['errors']
    assert read(history) == b'original'


def test_linked_history_and_unrelated_project_files_are_untouched(history, tmp_path):
    outside = tmp_path / 'user-project.json'
    outside.write_bytes(b'project must survive')
    try:
        history.symlink_to(outside)
    except OSError:
        pytest.skip('Symlinks unavailable')
    report = job_history.repair_for_install()
    assert report['errors'] and not report['archived']
    assert outside.read_bytes() == b'project must survive'


def test_installer_dispatch_reports_backup_and_never_retries(history, capsys):
    from mklink.internal_process import dispatch_internal_process
    history.write_bytes(b'old-invalid-history')
    assert dispatch_internal_process(['--internal-install-history-maintenance']) == 0
    assert json.loads(capsys.readouterr().out)['archived'] == 1
    report = json.loads((runtime_dir() / 'installation-history-report.json').read_text())
    assert Path(report['archived'][0]['backup']).read_bytes() == b'old-invalid-history'
    assert json.loads(history.read_bytes()) == []

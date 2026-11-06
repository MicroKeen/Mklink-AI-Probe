from contextlib import contextmanager
import json
from pathlib import Path

import pytest

from mklink import runtime, runtime_registry as registry

LOCAL = 'local-' + 'a' * 24
PROBE = 'usb-' + 'b' * 24


@pytest.fixture
def record(monkeypatch, tmp_path):
    monkeypatch.setenv('MKLINK_RUNTIME_DIR', str(tmp_path / 'registry'))
    monkeypatch.setattr(registry, '_pid_exists', lambda pid: False)
    monkeypatch.setattr(runtime, 'request', lambda *a, **k: pytest.fail('cleanup must not contact endpoints'))
    def create(key=LOCAL, **changes):
        info = dict(runtime_id=LOCAL, probe_id='lobby', instance_id='fixture', pid=12345)
        info.update(changes)
        path = runtime.runtime_dir(key) / 'endpoint.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(info), encoding='utf-8')
        return path
    return create


def test_dead_records_are_reclaimed_but_jobs_logs_and_lock_files_survive(record):
    path = record(probe_id=PROBE)
    alias = record(PROBE, probe_id=PROBE)
    artifacts = [path.parent / name for name in ('jobs.json', 'runtime.log', 'startup.log')]
    for artifact in artifacts:
        artifact.write_text('retained evidence', encoding='utf-8')
    assert len(registry.prune_dead_endpoints(dry_run=True)['eligible']) == 2
    assert path.exists() and alias.exists()
    result = registry.prune_dead_endpoints()
    assert set(result['removed']) == {LOCAL, PROBE} and result['bytes_removed'] > 0
    assert not path.exists() and not alias.exists()
    assert all(p.read_text(encoding='utf-8') == 'retained evidence' for p in artifacts)
    assert (path.parent / 'backend.lock').exists()
    assert (alias.parent / 'owner.lock').exists()
    assert registry.prune_dead_endpoints()['removed'] == []


@pytest.mark.parametrize('pid', [None, 0, -1, True, '12345', 12345])
def test_live_and_unknown_pids_are_retained(record, monkeypatch, pid):
    path = record(pid=pid)
    monkeypatch.setattr(registry, '_pid_exists', lambda pid: True)
    assert registry.prune_dead_endpoints()['removed'] == []
    assert path.exists()


@pytest.mark.parametrize('current,removed', [('windows:old', False), (None, False), ('windows:new', True)])
def test_recycled_pid_is_distinguished_from_original_owner(record, monkeypatch, current, removed):
    path = record(process_identity='windows:old')
    monkeypatch.setattr(registry, '_pid_exists', lambda pid: True)
    monkeypatch.setattr(registry, 'get_process_identity', lambda pid: current)
    assert bool(registry.prune_dead_endpoints()['removed']) == removed
    assert path.exists() != removed


@pytest.mark.parametrize('lock_key,name', [(LOCAL, 'backend.lock'), (PROBE, 'owner.lock')])
def test_live_publishers_are_not_cleaned_even_when_pid_is_stale(record, lock_key, name):
    path = record(probe_id=PROBE)
    with runtime.runtime_lock(name, lock_key):
        result = registry.prune_dead_endpoints()
    assert not result['removed'] and path.exists()


def test_record_replaced_between_inspection_and_lock_is_retained(record, monkeypatch):
    path = record()
    @contextmanager
    def replacement(*args):
        record(instance_id='replacement')
        yield
    monkeypatch.setattr(runtime, 'runtime_lock', replacement)
    assert not registry.prune_dead_endpoints()['removed']
    assert json.loads(path.read_text())['instance_id'] == 'replacement'


@pytest.mark.parametrize('info', [[], {}, {'pid': 12345, 'instance_id': 'x', 'runtime_id': '../escape'}])
def test_malformed_identity_is_not_deleted(record, info):
    path = record()
    path.write_text(json.dumps(info))
    assert not registry.prune_dead_endpoints()['removed']
    assert path.exists()


def test_symlinked_record_is_not_followed(record, tmp_path):
    path = record()
    outside = tmp_path / 'evidence.json'
    outside.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(outside)
    except OSError:
        pytest.skip('File symlinks need Windows developer mode')
    assert not registry.prune_dead_endpoints()['removed']
    assert path.is_symlink() and outside.exists()


def test_symlinked_registry_root_is_not_cleaned(record, monkeypatch, tmp_path):
    path = record()
    link = tmp_path / 'linked-registry'
    try:
        link.symlink_to(runtime.runtime_dir(), target_is_directory=True)
    except OSError:
        pytest.skip('Directory symlinks need Windows developer mode')
    monkeypatch.setenv('MKLINK_RUNTIME_DIR', str(link))
    assert not registry.prune_dead_endpoints()['removed']
    assert path.exists()


def test_reparse_point_guard_does_not_depend_on_symlink_privileges(record, monkeypatch):
    path = record()
    real = Path.lstat
    def linked(item, *args, **kwargs):
        if item == path.parent:
            from types import SimpleNamespace
            return SimpleNamespace(st_mode=0, st_file_attributes=0x400)
        return real(item, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', linked)
    assert not registry.prune_dead_endpoints()['removed']
    assert path.exists()

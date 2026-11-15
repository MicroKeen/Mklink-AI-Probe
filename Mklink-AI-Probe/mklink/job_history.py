"""Job journal format and offline installer maintenance (never hardware I/O)."""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import stat
import tempfile


def parse_history(text):
    rows = json.loads(text.lstrip('\ufeff'))
    if not isinstance(rows, list):
        raise ValueError('Job history must be an array')
    for row in rows:
        if (not isinstance(row, dict)
                or any(not isinstance(row.get(key), str) or not row[key]
                       for key in ('job_id', 'request_id', 'fingerprint', 'state'))
                or type(row.get('started')) not in (int, float)
                or isinstance(row['started'], float) and not math.isfinite(row['started'])):
            raise ValueError('Invalid job history record')
    return rows


def _ordinary(path, *, directory=False):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise OSError(f'Linked history path is not eligible for maintenance: {path}')
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise OSError(f'Unexpected history path type: {path}')


def _write_new(path, content):
    with path.open('xb') as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())


def repair_for_install():
    """Archive invalid journals only, while all known runtimes are stopped.

    Valid history, including unknown outcomes, remains untouched. No task is
    submitted or retried. The installer invokes this after replacing its files.
    """
    from mklink.runtime import runtime_dir, runtime_lock
    root = runtime_dir()
    report = {'version': 1, 'archived': [], 'preserved': 0, 'errors': []}
    if not root.exists():
        return report
    try:
        _ordinary(root, directory=True)
        probes = root / 'probes'
        if not probes.exists():
            return report
        _ordinary(probes, directory=True)
        # Binding admission uses the same guard. A new backend cannot restore
        # a journal between our ownership check and its atomic replacement.
        guard = root / 'history-maintenance.lock'
        if guard.exists():
            _ordinary(guard)
        with runtime_lock('history-maintenance.lock'), ExitStack() as locks:
            directories = []
            for directory in sorted(probes.iterdir()):
                try:
                    expected = runtime_dir(directory.name)  # Validate identity syntax.
                except Exception:
                    continue
                _ordinary(directory, directory=True)
                assert expected == directory
                directories.append(directory)
                for name in ('backend.lock', 'owner.lock'):
                    lock = directory / name
                    if lock.exists():
                        _ordinary(lock)
                    locks.enter_context(runtime_lock(name, directory.name))
            # Acquire all locks before changing any journal. A running Skill or
            # another independent desktop blocks cleanup, even outside INSTDIR.
            for directory in directories:
                path = directory / 'jobs.json'
                if not path.exists():
                    continue
                try:
                    _ordinary(path)
                    if path.stat().st_size > 8 * 1024 * 1024:
                        raise OSError('History exceeds the 8 MiB maintenance limit')
                    original = path.read_bytes()
                    try:
                        parse_history(original.decode('utf-8-sig'))
                    except (UnicodeError, ValueError, TypeError):
                        pass
                    else:
                        report['preserved'] += 1
                        continue
                    backup_dir = root / 'history-backups'
                    backup_dir.mkdir(exist_ok=True, mode=0o700)
                    _ordinary(backup_dir, directory=True)
                    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                    backup = backup_dir / f'{stamp}-{directory.name}-{secrets.token_hex(4)}.jobs.json'
                    _write_new(backup, original)
                    digest = hashlib.sha256(original).hexdigest()
                    if hashlib.sha256(backup.read_bytes()).hexdigest() != digest:
                        raise OSError('History backup verification failed')
                    # Keep an audit record even if final replacement fails.
                    entry = {'source': str(path), 'backup': str(backup), 'sha256': digest,
                             'bytes': len(original), 'time': stamp, 'reason': 'invalid_history'}
                    _write_new(backup.with_suffix('.manifest.json'),
                               json.dumps(entry, ensure_ascii=False, indent=2).encode('utf-8'))
                    _ordinary(path)
                    if path.read_bytes() != original:
                        raise OSError('History changed during maintenance')
                    fd, name = tempfile.mkstemp(dir=directory, prefix='jobs-install-', suffix='.tmp')
                    temporary = Path(name)
                    try:
                        with os.fdopen(fd, 'wb') as output:
                            output.write(b'[]\n')
                            output.flush()
                            os.fsync(output.fileno())
                        temporary.replace(path)
                    finally:
                        temporary.unlink(missing_ok=True)
                    report['archived'].append(entry)
                except OSError as error:
                    report['errors'].append({'path': str(path), 'message': str(error)})
    except (OSError, RuntimeError) as error:
        report['errors'].append({'path': str(root), 'message': str(error)})
    return report


def installer_main():
    report = repair_for_install()
    from mklink.runtime import runtime_dir
    root = runtime_dir()
    if root.exists():
        try:
            destination = root / 'installation-history-report.json'
            if destination.exists():
                _ordinary(destination)
            destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as error:
            report['errors'].append({'message': str(error)})
    print(json.dumps({'archived': len(report['archived']), 'preserved': report['preserved'],
                      'errors': len(report['errors'])}))
    return 1 if report['errors'] else 0

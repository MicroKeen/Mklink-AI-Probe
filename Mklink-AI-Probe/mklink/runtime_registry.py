"""Reclaim dead discovery records without touching logs, jobs or live owners."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import stat

from mklink import runtime
from mklink.local_resources import _pid_exists
from mklink.web_entry import get_process_identity


def _plain_path(path, root):
    """Reject links/junctions in any ancestor, including the registry itself."""
    path, root = Path(path).absolute(), Path(root).absolute()
    if not path.is_relative_to(root) or not path.resolve().is_relative_to(root.resolve()):
        return False
    for item in (path, *path.parents):
        try:
            metadata = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
            return False
    return True


def endpoint_owner_dead(info):
    pid = info.get('pid')
    if type(pid) is not int or pid <= 0:
        return False
    if not _pid_exists(pid):
        return True
    saved = info.get('process_identity')
    current = get_process_identity(pid) if saved else None
    return bool(saved and current and saved != current)


def prune_dead_endpoints(*, dry_run=False):
    """Startup maintenance only; never expire a record by age or failed HTTP.

    Holding the publisher's OS locks and rereading the exact record protects a
    replacement backend. PID reuse/inspection failures retain records. Only
    endpoint.json is disposable: lock files, logs, jobs and scratch stay intact.
    """
    root = Path(os.environ['MKLINK_RUNTIME_DIR']).absolute() if os.environ.get('MKLINK_RUNTIME_DIR') else runtime.runtime_dir()
    result = {'removed': [], 'eligible': [], 'retained': [], 'bytes_removed': 0}
    try:
        safe = _plain_path(root / 'probes', root)
    except OSError:
        safe = False
    if not safe:
        result['retained'].append({'key': 'registry', 'reason': 'linked_or_unreadable_path'})
        return result
    for path in (root / 'probes').glob('*/endpoint.json'):
        key = path.parent.name
        reason = 'unknown'
        try:
            runtime.runtime_dir(key)  # Validate the directory identity.
            if not _plain_path(path, root):
                reason = 'linked_path'
                continue
            original = path.read_bytes()
            info = json.loads(original)
            if not isinstance(info, dict) or not info.get('instance_id'):
                reason = 'invalid_record'
                continue
            if not endpoint_owner_dead(info):
                reason = 'live_or_unknown_pid'
                continue
            identity = info.get('runtime_id') or key  # Older single-probe backends.
            owner = info.get('probe_id')
            if key not in (identity, owner):
                reason = 'identity_mismatch'
                continue
            locks = [(identity, 'backend.lock')]
            if owner and owner != 'lobby':
                locks.append((owner, 'owner.lock'))
            if not all(_plain_path(runtime.runtime_dir(lock_key) / name, root)
                       for lock_key, name in locks):
                reason = 'linked_path'
                continue
            with ExitStack() as stack:
                for lock_key, name in locks:
                    stack.enter_context(runtime.runtime_lock(name, lock_key))
                if not _plain_path(path, root) or path.read_bytes() != original or not endpoint_owner_dead(info):
                    reason = 'changed_during_cleanup'
                    continue
                result['eligible'].append(key)
                if not dry_run:
                    path.unlink()
                    result['removed'].append(key)
                    result['bytes_removed'] += len(original)
                reason = None
        except runtime.RuntimeErrorResponse:
            reason = 'invalid_identity_or_busy'
        except (OSError, ValueError, TypeError):
            reason = 'unreadable_or_invalid'
        finally:
            if reason:
                result['retained'].append({'key': key, 'reason': reason})
    return result

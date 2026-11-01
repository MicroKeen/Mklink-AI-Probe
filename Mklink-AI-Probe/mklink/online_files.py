"""Owned probe-volume copies for one successful online download, never a sweep."""
from __future__ import annotations

import hashlib
from pathlib import Path
import uuid

from mklink.file_content import sha256_file, source_fingerprint, sync_directory, sync_file


def stage_firmware(flash, source: Path, disk: str) -> str:
    root = Path(disk).resolve()
    suffix = source.suffix.lower()
    if suffix not in ('.bin', '.hex'):
        raise ValueError('Online staging requires BIN or HEX')
    before = source_fingerprint(source)
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != before['sha256']:
        raise OSError('Firmware changed while staging')
    destination = root / ('mklink-online-' + uuid.uuid4().hex + suffix)
    # Never replace an existing user or offline file, including the input file.
    with destination.open('xb') as output:
        if output.write(payload) != len(payload):
            raise OSError('Incomplete probe-volume copy')
        sync_file(output)
    sync_directory(root)
    if sha256_file(destination) != before['sha256']:
        raise OSError('Probe-volume copy differs from source')
    stat = destination.stat()
    flash._online_files[destination.name] = {
        'root': root, 'path': destination, 'sha256': before['sha256'],
        'stat': (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino),
    }
    return destination.name


def cleanup_firmware(flash, result: dict) -> dict:
    """Delete only this successful result's unchanged, identity-bound copies.

    A cleanup failure never turns successful programming into a reason to replay.
    Failed/unknown programming does not enter this function's deletion path.
    """
    outcome = {'deleted': [], 'retained': [], 'errors': []}
    owned = getattr(flash, '_online_files', None)
    if result.get('success') is not True or not isinstance(owned, dict):
        return outcome
    results = [result, *result.get('regions', [])]
    names = list(dict.fromkeys(row.get('filename') for row in results
                              if row.get('filename') in owned))
    if not names:
        return outcome
    try:
        # Verification may have entered idle MUX. V2 cannot process MSC writes
        # while MUX is active. Normal exit rejects active/unknown subscriptions.
        leave = getattr(flash._bridge, '_leave_multiplex', None)
        if callable(leave):
            leave()
        from mklink.discovery import find_microkeen_disk
        disk = find_microkeen_disk()
        if not disk:
            raise OSError('Bound probe volume is unavailable')
        root = Path(disk).resolve()
        for name in names:
            entry = owned[name]
            path = entry['path']
            try:
                if root != entry['root'] or path.parent != root or path.is_symlink():
                    raise OSError('Probe-volume identity or file path changed')
                stat = path.stat()
                if ((stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino) != entry['stat']
                        or sha256_file(path) != entry['sha256']):
                    raise OSError('Temporary file changed; retained')
                path.unlink()
                sync_directory(root)
                del owned[name]
                outcome['deleted'].append(name)
            except (OSError, ValueError) as error:
                outcome['retained'].append(name)
                outcome['errors'].append(str(error))
    except Exception as error:
        outcome['retained'] = names
        outcome['errors'].append(str(error))
    return outcome

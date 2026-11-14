"""Project workbench presentation only; loading never starts acquisition."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets

from .frontend_contract import bounded_json, identifier, integer, keys, require
from .watch_preferences import _LOCK, PreferencesConflict

MAX_BYTES = 256 * 1024
RESERVED_PANEL_IDS = frozenset({'dashboard', 'superwatch', 'workbench', 'SuperWatch', 'VOFA'})


def project_path(root, filename):
    path = Path(root).resolve() / '.mklink' / filename
    for part in (path.parent, path):
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            raise ValueError('Frontend preferences must not redirect outside the project')
    return path


def read_document(root, filename, default, limit=MAX_BYTES):
    path = project_path(root, filename)
    try:
        with path.open('rb') as source:
            raw = source.read(limit + 1)
    except FileNotFoundError:
        return default
    if len(raw) > limit:
        raise ValueError('Frontend preferences are too large')
    return json.loads(raw.decode('utf-8-sig'))


def atomic_document(root, filename, value):
    path = project_path(root, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f'.{path.name}.{secrets.token_hex(8)}.tmp'
    try:
        with temporary.open('x', encoding='utf-8') as output:
            json.dump(value, output, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            output.flush()
            os.fsync(output.fileno())
        project_path(root, filename)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def normalize_layout(value):
    keys(value, {'version', 'revision', 'panels'})
    require(type(value['version']) is int and value['version'] == 1, message='Unsupported layout version')
    require(integer(value['revision']), message='Invalid layout revision')
    require(isinstance(value['panels'], list) and len(value['panels']) <= 32, message='Expected at most 32 panels')
    ids = set()
    for panel in value['panels']:
        keys(panel, {'id', 'type', 'title', 'source', 'x', 'y', 'w', 'h', 'view'},
             {'id', 'type', 'title', 'source', 'x', 'y', 'w', 'h'})
        require(identifier(panel['id']) and panel['id'] not in ids and panel['id'] not in RESERVED_PANEL_IDS,
                message='Invalid, reserved or duplicate panel ID')
        ids.add(panel['id'])
        require(isinstance(panel['title'], str) and len(panel['title']) <= 200)
        require(panel['type'] in ('watch', 'variables', 'rtt', 'serial'), message='Unsupported panel type')
        require(integer(panel['x'], 0, 11) and integer(panel['y'], 0, 200)
                and integer(panel['w'], 1, 12) and integer(panel['h'], 1, 12)
                and panel['x'] + panel['w'] <= 12, message='Panel exceeds the 12-column grid')
        source = panel['source']
        if panel['type'] in ('watch', 'variables'):
            keys(source, {'signals'})
            require(isinstance(source['signals'], list) and len(source['signals']) <= 500)
            require(all(isinstance(signal, str) and 1 <= len(signal) <= 512 and not any(ord(c) < 32 for c in signal)
                        for signal in source['signals']), message='Invalid signal reference')
            require(len(set(source['signals'])) == len(source['signals']), message='Duplicate signal reference')
        elif panel['type'] == 'rtt':
            keys(source, {'channel'})
            require(integer(source['channel'], 0, 255), message='Invalid RTT channel')
        else:
            keys(source, {'port'})
            require(isinstance(source['port'], str) and len(source['port']) <= 256
                    and not any(ord(c) < 32 for c in source['port']), message='Invalid UART port')
        if 'view' in panel:
            require(isinstance(panel['view'], dict), message='Panel view must be an object')
            bounded_json(panel['view'], limit=16 * 1024, depth=8)
    bounded_json(value, limit=MAX_BYTES)
    return value


def load_layout(root):
    with _LOCK:
        return normalize_layout(read_document(root, 'frontend_layout.json', {'version': 1, 'revision': 0, 'panels': []}))


def save_layout(root, layout):
    layout = normalize_layout(layout)
    with _LOCK:
        current = load_layout(root)
        if current['revision'] != layout['revision']:
            raise PreferencesConflict('Layout changed in another window; reload and retry')
        require(integer(layout['revision'] + 1), message='Layout revision exhausted')
        result = {**layout, 'revision': layout['revision'] + 1}
        atomic_document(root, 'frontend_layout.json', result)
        return result

"""Project workbench presentation only; loading never starts acquisition."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets

from .frontend_contract import bounded_json, identifier, integer, keys, require
from .watch_preferences import _LOCK, PreferencesConflict

MAX_BYTES = 256 * 1024
RESERVED_PANEL_IDS = frozenset({'dashboard', 'superwatch', 'workbench', 'SuperWatch', 'VOFA'})
UNSAFE_PROPERTIES = frozenset({'__proto__', 'prototype', 'constructor'})
PANEL_MINIMUMS = {'watch': (4, 4), 'variables': (3, 4), 'rtt': (3, 3), 'serial': (3, 3), 'controls': (4, 3)}


def validate_component_manifest(manifest):
    keys(manifest, {'version', 'components'})
    require(type(manifest['version']) is int and manifest['version'] == 1, message='Unsupported component manifest')
    require(isinstance(manifest['components'], dict) and manifest['components'], message='Missing component definitions')
    for name, definition in manifest['components'].items():
        require(identifier(name) and name not in UNSAFE_PROPERTIES, message='Invalid component type ID')
        keys(definition, {'title', 'description', 'presentation', 'minW', 'minH', 'defaultW', 'defaultH'})
        require(isinstance(definition['title'], str) and 1 <= len(definition['title']) <= 200
                and isinstance(definition['description'], str) and len(definition['description']) <= 2000,
                message='Invalid component description')
        require(definition['presentation'] in ('button', 'form', 'value'), message='Unsupported component presentation')
        for axis in ('W', 'H'):
            require(integer(definition['min' + axis], 1, 12)
                    and integer(definition['default' + axis], definition['min' + axis], 12),
                    message='Invalid component dimensions')
    bounded_json(manifest, limit=64 * 1024, depth=4)
    return manifest['components']


# The renderer and backend load this same build-owned registry, never a project URL or script.
COMPONENT_TYPES = validate_component_manifest(json.loads(Path(__file__).with_name('frontend_components.json').read_text(encoding='utf-8')))


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


def validate_geometry(item, minimum_width=1, minimum_height=1):
    require(integer(item['x'], 0, 11) and integer(item['y'], 0, 200)
            and integer(item['w'], minimum_width, 12) and integer(item['h'], minimum_height, 12)
            and item['x'] + item['w'] <= 12, message='Component exceeds its grid or minimum size')


def reject_overlaps(items):
    for index, item in enumerate(items):
        for other in items[:index]:
            require(not (item['x'] < other['x'] + other['w'] and item['x'] + item['w'] > other['x']
                         and item['y'] < other['y'] + other['h'] and item['y'] + item['h'] > other['y']),
                    message='Components overlap in the layout')


def validate_widget(widget, ids):
    keys(widget, {'id', 'version', 'type', 'title', 'x', 'y', 'w', 'h', 'binding'})
    require(identifier(widget['id']) and widget['id'] not in ids and widget['id'] not in RESERVED_PANEL_IDS,
            message='Invalid, reserved or duplicate component ID')
    ids.add(widget['id'])
    require(type(widget['version']) is int and widget['version'] == 1, message='Unsupported component version')
    require(isinstance(widget['type'], str) and widget['type'] in COMPONENT_TYPES, message='Unsupported component type')
    definition = COMPONENT_TYPES[widget['type']]
    require(isinstance(widget['title'], str) and len(widget['title']) <= 200)
    validate_geometry(widget, definition['minW'], definition['minH'])
    binding = widget['binding']
    require(isinstance(binding, dict), message='Component binding must be an object')
    if not binding:
        return
    require(identifier(binding.get('panel_id')), message='Invalid binding panel ID')
    if definition['presentation'] == 'value':
        keys(binding, {'panel_id', 'state_path'})
        path = binding['state_path']
        require(isinstance(path, str) and 1 <= len(path) <= 512
                and all(part and part not in UNSAFE_PROPERTIES and not any(ord(c) < 32 for c in part)
                        for part in path.split('.')), message='Invalid public state path')
    else:
        keys(binding, {'panel_id', 'action', 'args', 'contract'})
        require(isinstance(binding['action'], str)
                and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', binding['action']) is not None,
                message='Invalid action name')
        require(isinstance(binding['args'], dict), message='Bound arguments must be an object')
        bounded_json(binding['args'], limit=8 * 1024, depth=8)
        require(isinstance(binding['contract'], str) and 1 <= len(binding['contract']) <= 16384,
                message='Invalid action contract')
    bounded_json(binding, limit=24 * 1024, depth=8)


def normalize_layout(value):
    keys(value, {'version', 'revision', 'panels', 'docks'}, {'version', 'revision', 'panels'})
    version = value['version']
    require(type(version) is int and version in (1, 2), message='Unsupported layout version')
    keys(value, {'version', 'revision', 'panels'} if version == 1 else {'version', 'revision', 'panels', 'docks'})
    require(integer(value['revision']), message='Invalid layout revision')
    require(isinstance(value['panels'], list) and len(value['panels']) <= 32, message='Expected at most 32 panels')
    ids = set()
    for panel in value['panels']:
        keys(panel, {'id', 'type', 'title', 'source', 'x', 'y', 'w', 'h', 'view', 'widgets'} if version == 2
             else {'id', 'type', 'title', 'source', 'x', 'y', 'w', 'h', 'view'},
             {'id', 'type', 'title', 'source', 'x', 'y', 'w', 'h'})
        require(identifier(panel['id']) and panel['id'] not in ids and panel['id'] not in RESERVED_PANEL_IDS,
                message='Invalid, reserved or duplicate panel ID')
        ids.add(panel['id'])
        require(isinstance(panel['title'], str) and len(panel['title']) <= 200)
        require(panel['type'] in (('watch', 'variables', 'rtt', 'serial', 'controls') if version == 2
                                 else ('watch', 'variables', 'rtt', 'serial')), message='Unsupported panel type')
        require(panel['type'] == 'controls' or 'widgets' not in panel,
                message='Only control panels may contain components')
        validate_geometry(panel)
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
        elif panel['type'] == 'serial':
            keys(source, {'port'})
            require(isinstance(source['port'], str) and len(source['port']) <= 256
                    and not any(ord(c) < 32 for c in source['port']), message='Invalid UART port')
        else:
            keys(source, set())
            require(isinstance(panel.get('widgets'), list) and len(panel['widgets']) <= 32,
                    message='Expected at most 32 components in a control panel')
        if 'view' in panel:
            require(isinstance(panel['view'], dict), message='Panel view must be an object')
            bounded_json(panel['view'], limit=16 * 1024, depth=8)
    if version == 2:
        require(isinstance(value['docks'], list) and len(value['docks']) <= 16, message='Expected at most 16 docks')
        panel_ids = set(ids)
        panels_by_id = {panel['id']: panel for panel in value['panels']}
        docked = set()
        hidden = set()
        minimums = {panel['id']: PANEL_MINIMUMS[panel['type']] for panel in value['panels']}
        for dock in value['docks']:
            keys(dock, {'id', 'panels', 'active'})
            require(identifier(dock['id']) and dock['id'] not in ids and dock['id'] not in RESERVED_PANEL_IDS,
                    message='Invalid, reserved or duplicate dock ID')
            ids.add(dock['id'])
            members = dock['panels']
            require(isinstance(members, list) and 2 <= len(members) <= 32
                    and all(identifier(member) and member in panel_ids and member not in docked for member in members),
                    message='Invalid or multiply docked panel')
            require(len(set(members)) == len(members), message='Duplicate dock member')
            require(identifier(dock['active']) and dock['active'] in members, message='Invalid active dock member')
            docked.update(members)
            hidden.update(members[1:])
            member_minimums = [PANEL_MINIMUMS[panels_by_id[member]['type']] for member in members]
            minimums[members[0]] = tuple(max(size[axis] for size in member_minimums) for axis in (0, 1))
        widget_count = 0
        for panel in value['panels']:
            if panel['type'] == 'controls':
                widget_count += len(panel['widgets'])
                require(widget_count <= 128, message='Expected at most 128 components in the layout')
                for widget in panel['widgets']:
                    validate_widget(widget, ids)
                reject_overlaps(panel['widgets'])
        visible = [panel for panel in value['panels'] if panel['id'] not in hidden]
        for panel in visible:
            validate_geometry(panel, *minimums[panel['id']])
        reject_overlaps(visible)
    bounded_json(value, limit=MAX_BYTES, depth=16 if version == 2 else 12)
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

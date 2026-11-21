"""Project workbench presentation only; loading never starts acquisition."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import time

from .frontend_contract import bounded_json, identifier, integer, finite_number, keys, require
from .watch_preferences import _LOCK, PreferencesConflict
from .hil_lock import _exclusive_guard

MAX_BYTES = 256 * 1024
RESERVED_PANEL_IDS = frozenset({'dashboard', 'superwatch', 'workbench', 'SuperWatch', 'VOFA'})
UNSAFE_PROPERTIES = frozenset({'__proto__', 'prototype', 'constructor'})
PANEL_MINIMUMS = {'watch': (4, 4), 'variables': (3, 4), 'rtt': (3, 3), 'serial': (3, 3), 'controls': (4, 3), 'capability': (4, 4),
                  'tool': (6, 5), 'log': (4, 3), 'information': (4, 3), 'chart': (4, 4)}
TOOL_TYPES = ('connection', 'superwatch', 'rtt', 'serial', 'memory', 'trace', 'hardfault', 'symbols', 'peripherals',
              'modbus', 'online-flash', 'offline-flash', 'files', 'firmware', 'runtime', 'remote-service')


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


def atomic_document(root, filename, value, before_commit=None):
    path = project_path(root, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f'.{path.name}.{secrets.token_hex(8)}.tmp'
    try:
        with temporary.open('x', encoding='utf-8') as output:
            json.dump(value, output, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            output.flush()
            os.fsync(output.fileno())
        project_path(root, filename)
        if before_commit is not None:
            before_commit()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_geometry(item, minimum_width=1, minimum_height=1, *, maximum_height=12):
    require(integer(item['x'], 0, 11) and integer(item['y'], 0, 200)
            and integer(item['w'], minimum_width, 12) and integer(item['h'], minimum_height, maximum_height)
            and item['x'] + item['w'] <= 12, message='Component exceeds its grid or minimum size')


def reject_overlaps(items):
    for index, item in enumerate(items):
        for other in items[:index]:
            require(not (item['x'] < other['x'] + other['w'] and item['x'] + item['w'] > other['x']
                         and item['y'] < other['y'] + other['h'] and item['y'] + item['h'] > other['y']),
                    message='Components overlap in the layout')


def validate_widget(widget, ids):
    keys(widget, {'id', 'version', 'type', 'title', 'x', 'y', 'w', 'h', 'binding', 'options'},
         {'id', 'version', 'type', 'title', 'x', 'y', 'w', 'h', 'binding'})
    if 'options' in widget:
        require(widget['type'] in ('numeric', 'gauge', 'bar-meter'), message='Only numeric components accept numeric options')
        options = widget['options']
        meter = widget['type'] in ('gauge', 'bar-meter')
        keys(options, {'unit', 'precision', 'stale_ms', 'valid_path', 'note'} | ({'min', 'max'} if meter else set()), set())
        if meter:
            low, high = options.get('min', 0), options.get('max', 100)
            require(finite_number(low) and finite_number(high) and -1e12 <= low < high <= 1e12, message='Invalid meter range')
        for name, limit in [('unit', 32), ('valid_path', 512), ('note', 200)]:
            if name in options:
                require(isinstance(options[name], str) and len(options[name]) <= limit, message='Invalid numeric option')
        if 'precision' in options:
            require(integer(options['precision'], 0, 6), message='Invalid numeric precision')
        if 'stale_ms' in options:
            require(integer(options['stale_ms'], 250, 60000), message='Invalid numeric freshness limit')
        path = options.get('valid_path')
        if path:
            require(path.startswith('signal:'), message='Choose an advertised validity signal')
            require(all(part and part not in UNSAFE_PROPERTIES and not any(ord(c) < 32 for c in part)
                        for part in path.split('.')), message='Invalid validity path')
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
        if widget['type'] in ('numeric', 'gauge', 'bar-meter'):
            require(isinstance(path, str) and path.startswith('signal:'), message='Choose an advertised timestamped signal')
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
    keys(value, {'version', 'revision', 'panels', 'docks', 'closed'}, {'version', 'revision', 'panels'})
    version = value['version']
    require(type(version) is int and version in (1, 2), message='Unsupported layout version')
    required = {'version', 'revision', 'panels'}
    if version == 2:
        required.add('docks')
    keys(value, required | ({'closed'} if version == 2 else set()), required)
    require(integer(value['revision']), message='Invalid layout revision')
    require(isinstance(value['panels'], list) and len(value['panels']) <= 32, message='Expected at most 32 panels')
    closed = value.get('closed', [])
    require(isinstance(closed, list) and len(closed) <= 32, message='Expected at most 32 recently closed panels')
    ids = set()
    for index, panel in enumerate(value['panels'] + closed):
        archived = index >= len(value['panels'])
        required_panel = {'id', 'type', 'title', 'source', 'x', 'y', 'w', 'h'}
        allowed = required_panel | {'view'}
        if version == 2:
            allowed.add('widgets')
        if archived:
            allowed.add('dockWith')
        keys(panel, allowed, required_panel)
        require(identifier(panel['id']) and panel['id'] not in ids and panel['id'] not in RESERVED_PANEL_IDS,
                message='Invalid, reserved or duplicate panel ID')
        if 'dockWith' in panel:
            require(identifier(panel['dockWith']) and panel['dockWith'] != panel['id'], message='Invalid archived dock target')
        ids.add(panel['id'])
        require(isinstance(panel['title'], str) and len(panel['title']) <= 200)
        require(panel['type'] in (tuple(PANEL_MINIMUMS) if version == 2
                                 else ('watch', 'variables', 'rtt', 'serial')), message='Unsupported panel type')
        require(panel['type'] == 'controls' or 'widgets' not in panel,
                message='Only control panels may contain components')
        validate_geometry(panel, maximum_height=200)
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
        elif panel['type'] == 'tool':
            keys(source, {'tool'})
            require(source['tool'] in TOOL_TYPES, message='Unsupported GUI tool')
        elif panel['type'] in ('capability', 'log', 'information', 'chart'):
            keys(source, set())
        else:
            keys(source, set())
            require(isinstance(panel.get('widgets'), list) and len(panel['widgets']) <= 32,
                    message='Expected at most 32 components in a control panel')
        if 'view' in panel:
            require(isinstance(panel['view'], dict), message='Panel view must be an object')
            bounded_json(panel['view'], limit=16 * 1024, depth=8)
    if version == 2:
        require(isinstance(value['docks'], list) and len(value['docks']) <= 16, message='Expected at most 16 docks')
        panel_ids = {panel['id'] for panel in value['panels']}
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
        for panel in value['panels'] + closed:
            if panel['type'] == 'controls':
                if panel['id'] in panel_ids:
                    widget_count += len(panel['widgets'])
                require(widget_count <= 128, message='Expected at most 128 components in the layout')
                for widget in panel['widgets']:
                    validate_widget(widget, ids)
                reject_overlaps(panel['widgets'])
        visible = [panel for panel in value['panels'] if panel['id'] not in hidden]
        for panel in visible:
            validate_geometry(panel, *minimums[panel['id']], maximum_height=200)
        for panel in closed:
            validate_geometry(panel, *PANEL_MINIMUMS[panel['type']], maximum_height=200)
        reject_overlaps(visible)
    bounded_json(value, limit=MAX_BYTES, depth=16 if version == 2 else 12)
    return value


def load_layout(root):
    with _LOCK:
        return normalize_layout(read_document(root, 'frontend_layout.json', {'version': 1, 'revision': 0, 'panels': []}))


def save_layout(root, layout, before_commit=None):
    layout = normalize_layout(layout)
    with _LOCK, _exclusive_guard(project_path(root, 'frontend_layout.lock'), timeout_s=4):
        current = load_layout(root)
        if current['revision'] != layout['revision']:
            raise PreferencesConflict('Layout changed in another window; reload and retry')
        require(integer(layout['revision'] + 1), message='Layout revision exhausted')
        result = {**layout, 'revision': layout['revision'] + 1}
        atomic_document(root, 'frontend_layout.json', result, before_commit)
        return result


def layout_name(value):
    require(isinstance(value, str) and 1 <= len(value.strip()) <= 80
            and all(ord(char) >= 32 for char in value), message='Expected a layout name of 1–80 characters')
    return value.strip()


def layout_library(root, filename):
    data = read_document(root, filename, {'version': 1, 'layouts': []}, limit=64 * (MAX_BYTES + 1024))
    keys(data, {'version', 'layouts'})
    require(data['version'] == 1 and isinstance(data['layouts'], list) and len(data['layouts']) <= 64)
    names = set()
    for entry in data['layouts']:
        keys(entry, {'name', 'revision', 'updated_at', 'layout'})
        name = layout_name(entry['name']).casefold()
        require(name not in names and integer(entry['revision'], 1) and finite_number(entry['updated_at']))
        names.add(name)
        normalize_layout(entry['layout'])
    return data


def layout_summary(entry):
    return {key: entry[key] for key in ('name', 'revision', 'updated_at')} | {'panel_count': len(entry['layout']['panels']), 'builtin': entry.get('builtin', False)}


def library_location(root, scope):
    require(scope in ('project', 'global'), message='Expected project or global layout scope')
    home = Path.home()
    if scope == 'project' and Path(root).resolve() == home.resolve():
        return root, 'frontend_project_layouts.json'
    return (home if scope == 'global' else root), 'frontend_layouts.json'


def builtin_layouts():
    presets = (
        ('RTT 与变量波形', (('tool', 'RTT', {'tool': 'rtt'}), ('watch', 'SuperWatch', {'signals': []}), ('variables', '变量', {'signals': []}), ('log', '操作日志', {}))),
        ('串口调试', (('tool', '串口助手', {'tool': 'serial'}), ('log', '操作日志', {}), ('information', '信息', {}))),
        ('内存与 RTOS Trace', (('tool', 'Memory', {'tool': 'memory'}), ('tool', 'RTOS Trace', {'tool': 'trace'}), ('log', '操作日志', {}), ('information', '信息', {}))),
    )
    return [{'name': name, 'revision': 0, 'updated_at': 0, 'builtin': True, 'layout': normalize_layout({
        'version': 2, 'revision': 0, 'docks': [], 'panels': [
            {'id': f'preset_{index}', 'type': kind, 'title': title, 'source': source,
             'x': (index % 2) * 6, 'y': (index // 2) * 6, 'w': 6, 'h': 6}
            for index, (kind, title, source) in enumerate(panels)]})} for name, panels in presets]


def search_layouts(root, query='', scope='project'):
    require(isinstance(query, str) and len(query) <= 80, message='Layout search is limited to 80 characters')
    root, filename = library_location(root, scope)
    with _LOCK:
        entries = layout_library(root, filename)['layouts'] + (builtin_layouts() if scope == 'global' else [])
        return {'scope': scope, 'location': str(project_path(root, filename)),
                'layouts': [layout_summary(entry) for entry in sorted(entries, key=lambda item: item['updated_at'], reverse=True)
                            if query.strip().casefold() in entry['name'].casefold()]}


def load_named_layout(root, name, scope='project'):
    name = layout_name(name)
    root, filename = library_location(root, scope)
    with _LOCK:
        entries = layout_library(root, filename)['layouts'] + (builtin_layouts() if scope == 'global' else [])
        entry = next((entry for entry in entries if entry['name'].casefold() == name.casefold()), None)
        require(entry is not None, code='NOT_FOUND', message='Saved layout not found', status=404)
        return entry


def save_named_layout(root, value, before_commit=None):
    keys(value, {'name', 'revision', 'layout', 'scope'}, {'name', 'revision', 'layout'})
    name = layout_name(value['name'])
    scope = value.get('scope', 'project')
    root, filename = library_location(root, scope)
    require(scope != 'global' or all(entry['name'].casefold() != name.casefold() for entry in builtin_layouts()),
            message='Built-in templates are read-only; save with a new name')
    require(integer(value['revision']), message='Expected the saved layout revision; use 0 for a new name')
    layout = normalize_layout(value['layout'])
    with _LOCK, _exclusive_guard(project_path(root, 'frontend_layouts.lock'), timeout_s=4):
        data = layout_library(root, filename)
        existing = next((entry for entry in data['layouts'] if entry['name'].casefold() == name.casefold()), None)
        if value['revision'] != (existing['revision'] if existing else 0):
            raise PreferencesConflict('Saved layout changed or name already exists; search again before replacing it')
        require(integer(value['revision'] + 1), message='Layout revision exhausted')
        require(existing is not None or len(data['layouts']) < 64, message='Layout library is full (64 layouts); update an existing layout')
        result = {'name': existing['name'] if existing else name, 'revision': value['revision'] + 1,
                  'updated_at': time.time(), 'layout': layout}
        if existing:
            data['layouts'][data['layouts'].index(existing)] = result
        else:
            data['layouts'].append(result)
        atomic_document(root, filename, data, before_commit)
        return layout_summary(result)

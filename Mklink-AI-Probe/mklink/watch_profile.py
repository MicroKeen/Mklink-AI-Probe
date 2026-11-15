"""AXF/ELF-adjacent SuperWatch preferences. No saved addresses or acquisition I/O."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import threading

from .watch_preferences import normalize_pins, PreferencesConflict
from .watch_workspace import normalize_workspace

MAX_BYTES = 1024 * 1024


def names(value):
    if not isinstance(value, list) or len(value) > 256:
        raise ValueError('Expected at most 256 variable names')
    result = []
    for name in value:
        if (not isinstance(name, str) or not name or len(name) > 512
                or any(ord(c) < 32 for c in name)):
            raise ValueError('Invalid variable name')
        if name not in result:
            result.append(name)
    return result


def number(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Expected a finite number in {low}..{high}')
    return value


def display_object(value, keys):
    if not isinstance(value, dict):
        raise ValueError('Expected display settings object')
    return {key: deepcopy(value[key]) for key in keys if key in value}


def viewer(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid viewer settings')
    result = dict(bufferPoints=50000, interval=.001, channels=[])
    result['bufferPoints'] = number(value.get('bufferPoints', 50000), 50000, 1000000)
    if int(result['bufferPoints']) != result['bufferPoints']:
        raise ValueError('Buffer size must be an integer')
    result['interval'] = number(value.get('interval', .001), .000001, 60)
    channels = value.get('channels', [])
    if not isinstance(channels, list) or len(channels) > 256:
        raise ValueError('Too many channel settings')
    for item in channels:
        if not isinstance(item, dict):
            raise ValueError('Invalid channel')
        names([item.get('name')])
        channel = display_object(item, ('name', 'color', 'format', 'precision',
                                       'yOffset', 'yZoom', 'yAutoRange', 'yMin', 'yMax'))
        if 'thresholds' in item:
            channel['thresholds'] = (None if item['thresholds'] is None else
                display_object(item['thresholds'], ('warnLow', 'warnHigh', 'alarmLow', 'alarmHigh')))
        result['channels'].append(channel)
    for key, allowed in (
        ('globalYView', ('zoom', 'offset', 'autoRange', 'manualMin', 'manualMax')),
        ('triggerSettings', ('source', 'edge', 'level', 'mode', 'preTrigger')),
    ):
        if key in value:
            result[key] = display_object(value[key], allowed)
    if 'timeSpan' in value:
        result['timeSpan'] = (None if value['timeSpan'] is None else
                              number(value['timeSpan'], .000000001, 1e12))
    if 'watchColumns' in value:
        columns = value['watchColumns']
        if not isinstance(columns, dict) or len(columns) > 32:
            raise ValueError('Invalid columns')
        result['watchColumns'] = {
            key: display_object(item, ('width', 'visible'))
            for key, item in columns.items() if key not in ('__proto__', 'constructor', 'prototype')
        }
    # Reject nested payloads masquerading as scalar display values.
    def scalar_tree(node, depth=0):
        if depth > 4:
            raise ValueError('Display settings are too deeply nested')
        if isinstance(node, dict):
            for k, v in node.items():
                if len(k) > 512:
                    raise ValueError('Display key is too long')
                scalar_tree(v, depth + 1)
        elif isinstance(node, list):
            for v in node:
                scalar_tree(v, depth + 1)
        elif isinstance(node, str):
            if len(node) > 512 or any(ord(c) < 32 for c in node):
                raise ValueError('Invalid display text')
        elif node is not None and not isinstance(node, bool):
            number(node, -1e300, 1e300)
    scalar_tree(result)
    def numeric_fields(item, fields, nullable=False):
        for key in fields:
            if key in item and not (nullable and item[key] is None):
                number(item[key], -1e300, 1e300)
    def boolean_fields(item, fields):
        if any(key in item and type(item[key]) is not bool for key in fields):
            raise ValueError('Invalid boolean display setting')
    for channel in result['channels']:
        if 'color' in channel and (not isinstance(channel['color'], str)
                                  or not re.fullmatch(r'#[0-9a-fA-F]{6}', channel['color'])):
            raise ValueError('Invalid channel color')
        if 'format' in channel and not isinstance(channel['format'], str):
            raise ValueError('Invalid value format')
        numeric_fields(channel, ('precision', 'yOffset', 'yZoom'))
        numeric_fields(channel, ('yMin', 'yMax'), True)
        boolean_fields(channel, ('yAutoRange',))
        if channel.get('thresholds') is not None:
            numeric_fields(channel['thresholds'], ('warnLow', 'warnHigh', 'alarmLow', 'alarmHigh'), True)
    if 'globalYView' in result:
        numeric_fields(result['globalYView'], ('zoom', 'offset'))
        numeric_fields(result['globalYView'], ('manualMin', 'manualMax'), True)
        boolean_fields(result['globalYView'], ('autoRange',))
    if 'triggerSettings' in result:
        trigger = result['triggerSettings']
        if not isinstance(trigger.get('source', ''), str):
            raise ValueError('Invalid trigger source')
        if trigger.get('edge', 'rising') not in ('rising', 'falling', 'both'):
            raise ValueError('Invalid trigger edge')
        if trigger.get('mode', 'auto') not in ('auto', 'normal', 'single'):
            raise ValueError('Invalid trigger mode')
        numeric_fields(trigger, ('level',))
        if 'preTrigger' in trigger:
            number(trigger['preTrigger'], 10, 50000)
            if int(trigger['preTrigger']) != trigger['preTrigger']:
                raise ValueError('Invalid pre-trigger count')
    for column in result.get('watchColumns', {}).values():
        numeric_fields(column, ('width',))
        boolean_fields(column, ('visible',))
    return result


def layout(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid layout')
    return dict(panelWidth=number(value.get('panelWidth', 340), 280, 10000),
                source='peripherals' if value.get('source') == 'peripherals' else 'variables',
                hidden=names(value.get('hidden', [])))


def snapshot(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('Invalid array snapshot')
    names([value.get('name')])
    start = number(value.get('start_index'), 0, 2**31 - 1)
    count = number(value.get('count'), 1, 4096)
    if int(start) != start or int(count) != count:
        raise ValueError('Array range must use integers')
    return dict(name=value['name'], start_index=int(start), count=int(count))


NORMALIZE = {'selected': names, 'pins': normalize_pins, 'snapshot': snapshot,
             'workspace': normalize_workspace, 'viewer': viewer, 'layout': layout}


def defaults():
    return dict(version=1, selected=[], pins=[], snapshot=None, workspace=normalize_workspace({'version': 2}),
                viewer=viewer({}), layout=layout({}))


class WatchProfile:
    def __init__(self):
        self.lock = threading.RLock()
        self.path = None
        self.data = defaults()
        self.raw = None
        self.error = ''
        self.missing = []

    def _check_path(self):
        if self.path.is_symlink() or getattr(self.path, 'is_junction', lambda: False)():
            raise ValueError('SuperWatch configuration must not be a link')

    def _read(self):
        self._check_path()
        try:
            with self.path.open('rb') as source:
                raw = source.read(MAX_BYTES + 1)
        except FileNotFoundError:
            return None
        if len(raw) > MAX_BYTES:
            raise ValueError('SuperWatch configuration exceeds 1 MiB')
        return raw

    def _write(self, data):
        if self._read() != self.raw:
            raise PreferencesConflict('SuperWatch configuration changed on disk; reload AXF/ELF before saving')
        raw = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
        if len(raw) > MAX_BYTES:
            raise ValueError('SuperWatch configuration exceeds 1 MiB')
        temporary = self.path.with_name('.' + self.path.name + '.' + secrets.token_hex(8) + '.tmp')
        try:
            with temporary.open('xb') as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            self._check_path()
            if self._read() != self.raw:
                raise PreferencesConflict('SuperWatch configuration changed while saving')
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.raw, self.data, self.error = raw, data, ''

    def section(self, name):
        with self.lock:
            value = deepcopy(self.data[name])
            identity = str(self.path or '')
            # Interval has its own live-control endpoint. A successful interval
            # edit must not conflict with the same window's pending display save.
            versioned = {k: v for k, v in value.items() if k != 'interval'} if name == 'viewer' else value
            revision = hashlib.sha256((identity + '\0' + json.dumps(versioned, sort_keys=True)).encode()).hexdigest()
            return {name: value, 'revision': revision}

    def status(self):
        with self.lock:
            return dict(path=str(self.path or ''), available=self.raw is not None,
                        error=self.error, missing=list(self.missing),
                        viewer=self.section('viewer'), layout=self.section('layout'))

    def save(self, name, value, revision=None):
        with self.lock:
            try:
                if not self.path or self.raw is None:
                    raise ValueError('SuperWatch configuration is unavailable; reload AXF/ELF')
                if revision is not None and revision != self.section(name)['revision']:
                    raise PreferencesConflict('SuperWatch configuration changed; reload settings and retry')
                updated = {**self.data, name: NORMALIZE[name](value)}
                if updated != self.data:
                    self._write(updated)
                else:
                    self.error = ''
                return self.section(name)
            except (OSError, ValueError) as exc:
                self.error = str(exc)
                raise

    def save_display(self, name, value, revision):
        # Read and preserve the live interval under the same lock as the write.
        # A queued display edit must never undo a newer interval command.
        with self.lock:
            if name == 'viewer':
                value = {**value, 'interval': self.data['viewer']['interval']}
            return self.save(name, value, revision)

    def save_interval(self, interval):
        with self.lock:
            return self.save('viewer', {**self.data['viewer'], 'interval': interval})

    def activate(self, axf, manager):
        """Called after explicit symbol load/connection, outside sample callbacks."""
        if not isinstance(axf, str) or not axf or not Path(axf).is_file():
            return
        with self.lock:
            path = Path(axf).resolve()
            self.path = path.with_name(path.name + '.superwatch.json')
            self.data, self.raw, self.error, self.missing = defaults(), None, '', []
            try:
                self.raw = self._read()
                if self.raw is None:
                    self._write(self.data)
                else:
                    data = json.loads(self.raw.decode('utf-8-sig'))
                    if not isinstance(data, dict) or data.get('version') != 1:
                        raise ValueError('Unsupported SuperWatch configuration version')
                    self.data = dict(version=1, **{
                        key: normalize(data.get(key, defaults()[key])) for key, normalize in NORMALIZE.items()
                    })
            except (OSError, ValueError, TypeError, RecursionError) as exc:
                self.raw = None  # Never overwrite a damaged or unreadable file.
                self.error = str(exc)
                return
            if manager.running:
                return  # Loading display preferences never mutates a live acquisition.
            manager.clear_array_snapshot()
            for item in manager.list_watches():
                if item.get('source', 'ram') == 'ram':
                    manager.remove_watch(item['name'])
            catalog = getattr(manager._device, 'symbol_catalog', None)
            for name in self.data['selected']:
                descriptor = catalog.by_path(name, writable_only=False) if catalog else None
                if descriptor is None:
                    self.missing.append(name)
                    continue
                result = manager.add_watch(name)
                if result.get('error') or result.get('item', {}).get('error'):
                    self.missing.append(name)
            if self.data['snapshot']:
                from mklink.symbol_catalog import SymbolCatalogError
                try:
                    result = manager.select_array_snapshot(**self.data['snapshot'])
                    if result.get('error'):
                        self.missing.append(self.data['snapshot']['name'])
                except (SymbolCatalogError, ValueError):
                    self.missing.append(self.data['snapshot']['name'])
            manager.set_interval(self.data['viewer']['interval'])

    def remember_selection(self, name, selected, manager):
        if not self.path:
            return
        catalog = getattr(manager._device, 'symbol_catalog', None)
        if selected and (catalog is None or catalog.by_path(name, writable_only=False) is None):
            return  # Peripheral selection is target-specific, not an ELF variable.
        desired = list(self.data['selected'])
        if selected and name not in desired:
            desired.append(name)
        elif not selected and name in desired:
            desired.remove(name)
        self.save('selected', desired)

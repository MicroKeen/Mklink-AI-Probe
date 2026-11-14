"""Strict, bounded agent-frontend/1 messages; no executable or device actions."""
from __future__ import annotations

import json
import re
import sys

from fastapi import HTTPException

PROTOCOL = 'agent-frontend/1'
MAX_INTEGER = 9007199254740991


def require(condition, code='INVALID_INPUT', message='Unexpected or missing fields', status=422):
    if not condition:
        raise HTTPException(status, {'code': code, 'message': message})


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value) is not None


def integer(value, minimum=0, maximum=MAX_INTEGER):
    return type(value) is int and minimum <= value <= maximum


def finite_number(value):
    return type(value) in (int, float) and abs(value) <= sys.float_info.max


def keys(value, allowed, required=None):
    require(isinstance(value, dict) and not value.keys() - set(allowed)
            and set(allowed if required is None else required) <= value.keys())


def bounded_json(value, *, limit=256 * 1024, depth=12):
    def check(item, level):
        require(level <= depth, message='JSON nesting exceeds the limit')
        if isinstance(item, dict):
            require(len(item) <= 4096 and all(isinstance(key, str) and len(key) <= 512 for key in item))
            for child in item.values():
                check(child, level + 1)
        elif isinstance(item, list):
            require(len(item) <= 2048, message='JSON array exceeds the limit')
            for child in item:
                check(child, level + 1)
        else:
            require(item is None or type(item) in (str, bool, int, float))
            if type(item) in (int, float):
                require(finite_number(item), message='JSON numbers must be finite')
    check(value, 0)
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))
    require(len(raw.encode('utf-8')) <= limit, message='JSON document exceeds the limit', status=413)
    return raw


def validate_schema(rule, depth=0):
    require(depth <= 8 and isinstance(rule, dict), 'SCHEMA_UNSUPPORTED', 'Invalid or deeply nested schema')
    kind = rule.get('type')
    common = {'type', 'description'}
    allowed = common
    valid = True
    if kind == 'object':
        allowed |= {'properties', 'required', 'additionalProperties'}
        valid = (rule.get('additionalProperties') is False and isinstance(rule.get('properties'), dict)
                 and isinstance(rule.get('required'), list)
                 and all(isinstance(key, str) and key in rule['properties'] for key in rule.get('required', [])))
        require(valid, 'SCHEMA_UNSUPPORTED', 'Object schemas must reject additional properties')
        for child in rule['properties'].values():
            validate_schema(child, depth + 1)
    elif kind == 'array':
        allowed |= {'items', 'minItems', 'maxItems'}
        valid = integer(rule.get('maxItems'), 0, 500) and integer(rule.get('minItems', 0), 0, rule['maxItems'])
        require(valid, 'SCHEMA_UNSUPPORTED', 'Array schemas require bounded lengths')
        validate_schema(rule.get('items'), depth + 1)
    else:
        allowed |= {'enum', 'minimum', 'maximum', 'maxLength'}
        valid = kind in ('string', 'number', 'integer', 'boolean')
        if 'enum' in rule:
            valid = valid and isinstance(rule['enum'], list) and bool(rule['enum'])
        for bound in ('minimum', 'maximum'):
            if bound in rule:
                valid = valid and kind in ('number', 'integer') and finite_number(rule[bound])
        if 'maxLength' in rule:
            valid = valid and kind == 'string' and integer(rule['maxLength'])
    require(valid and not rule.keys() - allowed, 'SCHEMA_UNSUPPORTED', 'Unsupported schema constraint')
    require('description' not in rule or isinstance(rule['description'], str), 'SCHEMA_UNSUPPORTED', 'Invalid schema description')


def validate_args(value, rule):
    kind = rule['type']
    if kind == 'object':
        keys(value, rule['properties'], rule['required'])
        for key, child in value.items():
            validate_args(child, rule['properties'][key])
    elif kind == 'array':
        require(isinstance(value, list) and rule.get('minItems', 0) <= len(value) <= rule['maxItems'], message='Invalid array length')
        for child in value:
            validate_args(child, rule['items'])
    else:
        valid = (integer(value, -MAX_INTEGER) if kind == 'integer' else
                 finite_number(value) if kind == 'number' else
                 isinstance(value, str) if kind == 'string' else type(value) is bool)
        require(valid, message='Invalid field type')
        require('enum' not in rule or any(type(value) is type(item) and value == item for item in rule['enum']), message='Invalid enum value')
        require('minimum' not in rule or value >= rule['minimum'], message='Value is below minimum')
        require('maximum' not in rule or value <= rule['maximum'], message='Value exceeds maximum')
        require('maxLength' not in rule or len(value) <= rule['maxLength'], message='Text exceeds maximum length')


def validate_state(state):
    keys(state, {'revision', 'value'})
    require(integer(state['revision']), message='Invalid state revision')


def validate_report(report):
    keys(report, {'protocol', 'session_id', 'page_id', 'title', 'catalog', 'actions', 'state'})
    require(report['protocol'] == PROTOCOL, 'PROTOCOL_MISMATCH', 'Unsupported interaction protocol')
    require(identifier(report['session_id']) and identifier(report['page_id']), message='Invalid page identity')
    require(isinstance(report['title'], str) and len(report['title']) <= 200)
    require(isinstance(report['catalog'], dict) and isinstance(report['actions'], dict) and len(report['actions']) <= 4096)
    validate_state(report['state'])
    for action, descriptor in report['actions'].items():
        require(identifier(action), message='Invalid action name')
        keys(descriptor, {'inputSchema', 'description', 'title', 'effect', 'panel_id', 'name'}, {'inputSchema'})
        for key in ('title', 'description'):
            require(key not in descriptor or isinstance(descriptor[key], str))
        require('effect' not in descriptor or descriptor['effect'] in ('view', 'device', 'file'))
        require('panel_id' not in descriptor or identifier(descriptor['panel_id']))
        require('name' not in descriptor or isinstance(descriptor['name'], str) and 1 <= len(descriptor['name']) <= 160)
        validate_schema(descriptor['inputSchema'])
    bounded_json(report, limit=1024 * 1024, depth=24)


def validate_command(command):
    keys(command, {'protocol', 'session_id', 'page_id', 'command_id', 'expect_revision', 'deadline', 'action', 'args'})
    require(command['protocol'] == PROTOCOL, 'PROTOCOL_MISMATCH', 'Unsupported interaction protocol')
    require(all(identifier(command[key]) for key in ('session_id', 'page_id', 'command_id', 'action')))
    require(integer(command['expect_revision']) and integer(command['deadline']) and isinstance(command['args'], dict))
    bounded_json(command, limit=64 * 1024)

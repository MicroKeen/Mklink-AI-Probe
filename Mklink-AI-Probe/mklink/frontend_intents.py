"""Durable, bounded user requests and agent replies; never execute an intent."""
from __future__ import annotations

from .frontend_contract import bounded_json, identifier, integer, keys, require
from .frontend_layout import atomic_document, read_document
from .watch_preferences import _LOCK

FILENAME = 'frontend_intents.json'
LIMIT = 2 * 1024 * 1024


def validate_request(value):
    keys(value, {'request_id', 'session_id', 'page_id', 'revision', 'intent', 'object_id', 'message'})
    require(all(identifier(value[key]) for key in ('request_id', 'session_id', 'page_id')))
    require(integer(value['revision']) and value['intent'] in ('explain', 'inspect', 'plan'))
    require(isinstance(value['object_id'], str) and 1 <= len(value['object_id']) <= 512)
    require(isinstance(value['message'], str) and bool(value['message'].strip()) and len(value['message']) <= 4000)
    bounded_json(value, limit=20 * 1024)


def load_intents(root):
    value = read_document(root, FILENAME, {'version': 1, 'requests': []}, LIMIT)
    keys(value, {'version', 'requests'})
    require(type(value['version']) is int and value['version'] == 1, message='Unsupported inbox version')
    require(isinstance(value['requests'], list) and len(value['requests']) <= 200)
    ids = set()
    for entry in value['requests']:
        fields = {'request', 'target', 'created_at', 'revision', 'status', 'reply', 'replied_at'}
        keys(entry, fields | {'context'}, fields)
        validate_request(entry['request'])
        require(entry['request']['request_id'] not in ids, message='Duplicate persisted request ID')
        ids.add(entry['request']['request_id'])
        require(isinstance(entry['target'], dict) and integer(entry['revision']) and integer(entry['created_at'])
                and entry['status'] in ('pending', 'replied') and isinstance(entry['reply'], str)
                and len(entry['reply']) <= 16000 and (entry['replied_at'] is None or integer(entry['replied_at'])))
        if 'context' in entry:
            keys(entry['context'], {'object', 'state', 'page_revision'})
            require(integer(entry['context']['page_revision']))
            bounded_json(entry['context'], limit=64 * 1024)
    bounded_json(value, limit=LIMIT)
    return value


def find_intent(root, request_id):
    require(identifier(request_id), message='Invalid request ID')
    with _LOCK:
        entry = next((entry for entry in load_intents(root)['requests'] if entry['request']['request_id'] == request_id), None)
        require(entry is not None, 'NOT_FOUND', 'Unknown user request', 404)
        return entry


def save_intent(root, request, target, now, context=None):
    validate_request(request)
    with _LOCK:
        data = load_intents(root)
        old = next((entry for entry in data['requests'] if entry['request']['request_id'] == request['request_id']), None)
        if old:
            require(old['request'] == request and old['target'] == target, 'ID_CONFLICT', 'Request ID already has different content', 409)
            return {**old, 'duplicate': True}
        require(len(data['requests']) < 200, 'SESSION_LIMIT', 'Project inbox is full; archive its file before submitting more requests', 429)
        entry = {'request': request, 'target': target, 'created_at': now, 'revision': 0,
                 'status': 'pending', 'reply': '', 'replied_at': None}
        if context is not None:
            bounded_json(context, limit=64 * 1024)
            entry['context'] = context
        data['requests'].append(entry)
        bounded_json(data, limit=LIMIT)
        atomic_document(root, FILENAME, data)
        return entry


def reply_intent(root, body, session_id, now):
    keys(body, {'request_id', 'revision', 'reply'})
    require(identifier(body['request_id']) and integer(body['revision']))
    require(isinstance(body['reply'], str) and bool(body['reply'].strip()) and len(body['reply']) <= 16000)
    with _LOCK:
        data = load_intents(root)
        entry = next((entry for entry in data['requests'] if entry['request']['request_id'] == body['request_id']), None)
        require(entry is not None, 'NOT_FOUND', 'Unknown user request', 404)
        require(entry['request']['session_id'] == session_id, 'WRONG_TARGET', 'Request belongs to an earlier target session', 409)
        # A lost HTTP reply can be checked or retried without changing the result.
        if entry['status'] == 'replied' and entry['revision'] == body['revision'] + 1 and entry['reply'] == body['reply']:
            return {**entry, 'duplicate': True}
        require(entry['revision'] == body['revision'], 'STALE_REVISION', 'Read the current request before replying', 409)
        require(integer(body['revision'] + 1), message='Reply revision exhausted')
        entry.update(reply=body['reply'], revision=body['revision'] + 1, status='replied', replied_at=now)
        bounded_json(data, limit=LIMIT)
        atomic_document(root, FILENAME, data)
        return entry

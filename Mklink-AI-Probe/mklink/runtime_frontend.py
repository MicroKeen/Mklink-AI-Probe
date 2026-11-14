"""Authenticated GUI semantic mailbox, scoped to the actual runtime target.

The mailbox only delivers declared page actions. Existing GUI business handlers
remain responsible for execution and the runtime gate retains device admission.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time

from fastapi import FastAPI, HTTPException, Request
from starlette.routing import Mount

from .frontend_contract import (PROTOCOL, bounded_json, identifier, keys, require,
                                validate_args, validate_command, validate_report, validate_state)
from .frontend_layout import load_layout, save_layout
from .watch_preferences import PreferencesConflict

TERMINAL = frozenset({'applied', 'completed', 'rejected', 'failed'})


class FrontendBroker:
    def __init__(self, control, clock=None):
        self.control = control
        self.clock = clock or (lambda: int(time.time() * 1000))
        self.pages = {}
        self.commands = {}

    @property
    def target(self):
        state = self.control.app.state.mklink_state
        return {'instance_id': self.control.info['instance_id'], 'probe_id': self.control.info.get('probe_id'),
                'device_generation': state.get('device_generation', 0), 'project_root': state['project_root']}

    @property
    def session_id(self):
        raw = json.dumps(self.target, sort_keys=True, ensure_ascii=False).encode('utf-8')
        return 'frontend_' + hashlib.sha256(raw).hexdigest()[:48]

    def check_target(self, session_id):
        require(session_id == self.session_id, 'WRONG_TARGET', 'Runtime target changed; rediscover the page', 409)

    def online(self, page):
        return bool(page and page['report']['session_id'] == self.session_id and self.clock() - page['seen'] < 15000)

    def receipt(self, record):
        result = record['receipt']
        if result['status'] not in TERMINAL:
            target_changed = record['command']['session_id'] != self.session_id
            if (target_changed or not self.online(self.pages.get(record['command']['page_id']))
                    or (result['status'] == 'queued' and self.clock() > record['command']['deadline'])):
                # This is a persisted transition: an offline command must never
                # become queued again merely because the page comes back.
                result = {**result, 'status': 'unknown',
                          'code': 'TARGET_CHANGED' if target_changed else 'DELIVERY_UNCONFIRMED'}
                record['receipt'] = result
        return copy.deepcopy(result)

    def discover(self):
        return {'protocol': PROTOCOL, 'session_id': self.session_id, 'target': self.target,
                'pages': [{'page_id': key, 'title': page['report']['title'], 'online': self.online(page), 'last_seen': page['seen']}
                          for key, page in self.pages.items() if page['report']['session_id'] == self.session_id]}

    def read(self, page_id):
        require(identifier(page_id), message='Invalid page ID')
        page = self.pages.get(page_id)
        require(page is not None, 'NOT_FOUND', 'Unknown page', 404)
        return {**copy.deepcopy(page['report']), 'online': self.online(page), 'last_seen': page['seen']}

    def read_receipt(self, command_id):
        require(identifier(command_id), message='Invalid command ID')
        record = self.commands.get(command_id)
        require(record is not None, 'NOT_FOUND', 'Unknown command; absence does not prove non-execution', 404)
        return self.receipt(record)

    def call(self, command):
        validate_command(command)
        self.check_target(command['session_id'])
        old = self.commands.get(command['command_id'])
        if old:
            require(bounded_json(old['command'], limit=64 * 1024) == bounded_json(command, limit=64 * 1024),
                    'ID_CONFLICT', 'Command ID already has different content', 409)
            return {**self.receipt(old), 'duplicate': True}
        page = self.pages.get(command['page_id'])
        require(self.online(page), 'PAGE_OFFLINE', 'Select a live page', 409)
        require(self.clock() < command['deadline'] <= self.clock() + 30000, 'EXPIRED', 'Deadline must be within the next 30 seconds', 409)
        require(page['report']['state']['revision'] == command['expect_revision'], 'STALE_REVISION', 'Read the current page state', 409)
        require(command['action'] in page['report']['actions'], 'UNKNOWN_ACTION', 'Action is not advertised')
        validate_args(command['args'], page['report']['actions'][command['action']]['inputSchema'])
        require(not any(record['command']['page_id'] == command['page_id'] and self.receipt(record)['status'] not in TERMINAL
                        for record in self.commands.values()), 'BUSY', 'Previous action is still running or its result is unknown', 409)
        require(len(self.commands) < 500, 'SESSION_LIMIT', 'Command history is full; restart the runtime before sending more commands', 429)
        record = {'command': copy.deepcopy(command),
                  'receipt': {'command_id': command['command_id'], 'action': command['action'], 'status': 'queued'}}
        self.commands[command['command_id']] = record
        return copy.deepcopy(record['receipt'])

    def exchange(self, body):
        keys(body, {'report', 'receipts'})
        report = body['report']
        validate_report(report)
        self.check_target(report['session_id'])
        require(isinstance(body['receipts'], list) and len(body['receipts']) <= 500)
        bounded_json(body, limit=2 * 1024 * 1024, depth=26)
        page = self.pages.get(report['page_id'])
        require(page is not None or len(self.pages) < 32, 'SESSION_LIMIT', 'Too many page sessions', 429)
        if page:
            require(page['report']['session_id'] == report['session_id'], 'WRONG_TARGET', 'Use a fresh page ID after a target change', 409)
            previous = page['report']['state']
            require(report['state']['revision'] >= previous['revision'], 'STALE_REVISION', 'Page revision went backwards', 409)
            require(report['state']['revision'] != previous['revision'] or report['state'] == previous,
                    'STALE_REVISION', 'Changed public state requires a new revision', 409)
        receipt_ids = set()
        for receipt in body['receipts']:
            keys(receipt, {'command_id', 'action', 'status', 'code', 'state', 'result', 'message'}, {'command_id', 'action', 'status'})
            require(identifier(receipt['command_id']) and identifier(receipt['action']))
            require(receipt['command_id'] not in receipt_ids, 'INVALID_RECEIPT', 'Duplicate receipt in exchange')
            receipt_ids.add(receipt['command_id'])
            record = self.commands.get(receipt['command_id'])
            require(record is not None and record['command']['page_id'] == report['page_id']
                    and record['command']['session_id'] == report['session_id'] and record['command']['action'] == receipt['action']
                    and isinstance(receipt['status'], str) and receipt['status'] in TERMINAL | {'accepted', 'unknown'},
                    'INVALID_RECEIPT', 'Receipt does not match a submitted command')
            require('code' not in receipt or identifier(receipt['code']), 'INVALID_RECEIPT', 'Invalid receipt code')
            require('message' not in receipt or isinstance(receipt['message'], str) and len(receipt['message']) <= 2000,
                    'INVALID_RECEIPT', 'Invalid receipt message')
            if 'result' in receipt:
                bounded_json(receipt['result'], limit=512 * 1024)
            if 'state' in receipt:
                validate_state(receipt['state'])
                require(receipt['state']['revision'] <= report['state']['revision'], 'INVALID_RECEIPT', 'Receipt is newer than page report')
        # Freeze undelivered commands before making an offline page online again.
        for record in self.commands.values():
            if record['command']['page_id'] == report['page_id']:
                self.receipt(record)
        self.pages[report['page_id']] = {'report': copy.deepcopy(report), 'seen': self.clock()}
        for receipt in body['receipts']:
            record = self.commands[receipt['command_id']]
            if record['receipt']['status'] not in TERMINAL:
                # accepted cannot turn an unknown outcome back into executable work.
                if record['receipt']['status'] != 'unknown' or receipt['status'] in TERMINAL:
                    record['receipt'] = copy.deepcopy(receipt)
        pending = next((record['command'] for record in self.commands.values()
                        if record['command']['page_id'] == report['page_id'] and self.receipt(record)['status'] == 'queued'), None)
        return {'command': copy.deepcopy(pending)}

    def submit_intent(self, body):
        from .frontend_intents import find_intent, save_intent, validate_request
        validate_request(body)
        self.check_target(body['session_id'])
        # Accept an exact retry even after page state advanced.
        try:
            old = find_intent(self.target['project_root'], body['request_id'])
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
        else:
            require(old['request'] == body and old['target'] == self.target, 'ID_CONFLICT', 'Request ID already has different content', 409)
            return {**old, 'duplicate': True}
        page = self.pages.get(body['page_id'])
        require(self.online(page), 'PAGE_OFFLINE', 'Submit from a live page', 409)
        require(body['revision'] == page['report']['state']['revision'], 'STALE_REVISION', 'Read the current page before submitting', 409)
        panels = page['report']['catalog'].get('panels', [])
        selected = next((panel for panel in panels if isinstance(panel, dict) and panel.get('id') == body['object_id']), None) if isinstance(panels, list) else None
        require(selected is not None,
                'NOT_FOUND', 'Intent object is not present in the page catalog', 404)
        value = page['report']['state']['value']
        states = value.get('panels', []) if isinstance(value, dict) else []
        selected_state = next((panel for panel in states if isinstance(panel, dict) and panel.get('id') == body['object_id']), None) if isinstance(states, list) else None
        require(selected_state is not None, 'STALE_REVISION', 'Read the selected panel state before submitting', 409)
        context = copy.deepcopy({'object': selected, 'state': selected_state.get('state', selected_state),
                                 'page_revision': body['revision']})
        bounded_json(context, limit=64 * 1024)
        return save_intent(self.target['project_root'], body, self.target, self.clock(), context)


def install_frontend(app, control):
    broker = FrontendBroker(control)
    control.frontend = broker
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @api.middleware('http')
    async def no_cache(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    async def body(request, limit=2 * 1024 * 1024):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            require(len(raw) <= limit, message='Frontend request exceeds the limit', status=413)
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(422, {'code': 'INVALID_INPUT', 'message': 'Invalid JSON request'}) from exc
        require(isinstance(value, dict))
        return value

    def storage(operation, *args):
        try:
            return operation(*args)
        except PreferencesConflict as exc:
            raise HTTPException(409, {'code': 'STALE_REVISION', 'message': str(exc)}) from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(422, {'code': 'STORAGE_UNAVAILABLE', 'message': str(exc)}) from exc

    def public_intent(entry):
        return {**entry, 'request_id': entry['request']['request_id']}

    @api.get('/pages')
    async def pages():
        return broker.discover()

    @api.get('/read')
    async def read(page_id: str):
        return broker.read(page_id)

    @api.post('/call')
    async def call(request: Request):
        return broker.call(await body(request, 64 * 1024))

    @api.get('/receipt')
    async def receipt(command_id: str):
        return broker.read_receipt(command_id)

    @api.post('/exchange')
    async def exchange(request: Request):
        return broker.exchange(await body(request))

    @api.get('/layout')
    async def layout():
        return storage(load_layout, broker.target['project_root'])

    @api.put('/layout')
    async def put_layout(request: Request):
        return storage(save_layout, broker.target['project_root'], await body(request, 256 * 1024))

    @api.post('/replay-file')
    async def replay_file(request: Request):
        from fastapi.responses import FileResponse
        from starlette.concurrency import run_in_threadpool
        from .frontend_replay import recording_file
        session_id = request.headers.get('X-MKLink-Frontend-Session')
        require(identifier(session_id), message='A frontend target session header is required')
        broker.check_target(session_id)
        path, info = await run_in_threadpool(recording_file, await body(request, 20 * 1024))
        broker.check_target(session_id)
        return FileResponse(path, filename=path.name, media_type='application/octet-stream', stat_result=info,
                            headers={'Cache-Control': 'no-store'})

    @api.post('/intent')
    async def intent(request: Request):
        return public_intent(storage(broker.submit_intent, await body(request, 20 * 1024)))

    @api.get('/intents')
    async def intents():
        from .frontend_intents import load_intents
        data = storage(load_intents, broker.target['project_root'])
        return {'requests': [{**public_intent(entry), 'current_target': entry['request']['session_id'] == broker.session_id}
                             for entry in data['requests']]}

    @api.get('/intent')
    async def read_intent(request_id: str):
        from .frontend_intents import find_intent
        return public_intent(storage(find_intent, broker.target['project_root'], request_id))

    @api.post('/reply')
    async def reply(request: Request):
        from .frontend_intents import reply_intent
        return public_intent(storage(reply_intent, broker.target['project_root'], await body(request, 64 * 1024), broker.session_id, broker.clock()))

    app.router.routes.insert(0, Mount('/api/runtime/frontend', app=api))
    return broker

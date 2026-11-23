"""Authenticated GUI semantic mailbox, scoped to the actual runtime target.

The mailbox only delivers declared page actions. Existing GUI business handlers
remain responsible for execution and the runtime gate retains device admission.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import time

from fastapi import FastAPI, HTTPException, Request
from starlette.routing import Mount
from starlette.concurrency import run_in_threadpool

from .frontend_contract import (PROTOCOL, bounded_json, identifier, integer, keys, require,
                                validate_args, validate_command, validate_report, validate_state)
from .frontend_layout import load_layout, save_layout, search_layouts, load_named_layout, save_named_layout
from .watch_preferences import PreferencesConflict

TERMINAL = frozenset({'applied', 'completed', 'rejected', 'failed'})


def _prepare_exchange(body):
    keys(body, {'report', 'receipts', 'feedback_ack'}, {'report', 'receipts'})
    require(integer(body.get('feedback_ack', 0)))
    report = body['report']
    validate_report(report)
    require(isinstance(body['receipts'], list) and len(body['receipts']) <= 500)
    bounded_json(body, limit=2 * 1024 * 1024, depth=26)
    receipt_ids = set()
    for receipt in body['receipts']:
        keys(receipt, {'command_id', 'action', 'status', 'code', 'state', 'result', 'message'}, {'command_id', 'action', 'status'})
        require(identifier(receipt['command_id']) and identifier(receipt['action']))
        require(receipt['command_id'] not in receipt_ids, 'INVALID_RECEIPT', 'Duplicate receipt in exchange')
        receipt_ids.add(receipt['command_id'])
        require('code' not in receipt or identifier(receipt['code']), 'INVALID_RECEIPT', 'Invalid receipt code')
        require('message' not in receipt or isinstance(receipt['message'], str) and len(receipt['message']) <= 2000,
                'INVALID_RECEIPT', 'Invalid receipt message')
        if 'result' in receipt:
            bounded_json(receipt['result'], limit=512 * 1024)
        if 'state' in receipt:
            validate_state(receipt['state'])
            require(receipt['state']['revision'] <= report['state']['revision'], 'INVALID_RECEIPT', 'Receipt is newer than page report')
    return body


class FrontendBroker:
    def __init__(self, control, clock=None):
        self.control = control
        self.clock = clock or (lambda: int(time.time() * 1000))
        self.pages = {}
        self.commands = {}
        self.feedback_sequence = 0

    def reclaim_pages(self):
        expired = {key for key, page in self.pages.items() if not self.online(page)}
        # Receipts outlive reports: returning pages must never resurrect queued work.
        for record in self.commands.values():
            if record['command']['page_id'] in expired:
                self._current_receipt(record)
        for key in expired:
            del self.pages[key]

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

    def _current_receipt(self, record):
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
        return result

    def receipt(self, record):
        return copy.deepcopy(self._current_receipt(record))

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
        try:
            self._check_admission(page, command)
        except HTTPException as exc:
            # Only this authenticated, online page may see its refused attempt.
            # Keep presentation data separate from executable commands and receipts.
            notices = page.setdefault('notices', [])
            command_id = command['command_id']
            if not any(item['command_id'] == command_id for item in notices):
                # A resumed tab may still acknowledge notices from a reclaimed page.
                self.feedback_sequence += 1
                notice = {'seq': self.feedback_sequence, 'command_id': command_id, 'action': command['action'],
                          'status': 'rejected', 'code': exc.detail['code']}
                args = command['args']
                if identifier(args.get('panel_id')):
                    notice['target_panel'] = args['panel_id']
                if type(args.get('open')) is bool:
                    notice['open'] = args['open']
                notices.append(notice)
                del notices[:-32]
            raise
        record = {'command': copy.deepcopy(command),
                  'receipt': {'command_id': command['command_id'], 'action': command['action'], 'status': 'queued'}}
        self.commands[command['command_id']] = record
        return copy.deepcopy(record['receipt'])

    def _check_admission(self, page, command):
        require(self.clock() < command['deadline'] <= self.clock() + 30000, 'EXPIRED', 'Deadline must be within the next 30 seconds', 409)
        require(page['report']['state']['revision'] == command['expect_revision'], 'STALE_REVISION', 'Read the current page state', 409)
        require(command['action'] in page['report']['actions'], 'UNKNOWN_ACTION', 'Action is not advertised')
        validate_args(command['args'], page['report']['actions'][command['action']]['inputSchema'])
        require(not any(record['command']['page_id'] == command['page_id'] and self._current_receipt(record)['status'] not in TERMINAL
                        for record in self.commands.values()), 'BUSY', 'Previous action is still running or its result is unknown', 409)
        require(len(self.commands) < 500, 'SESSION_LIMIT', 'Command history is full; restart the runtime before sending more commands', 429)

    def exchange(self, body):
        # In-process callers retain ownership of their input.
        return self._commit_exchange(_prepare_exchange(copy.deepcopy(body)))

    def _commit_exchange(self, body):
        report = body['report']
        self.check_target(report['session_id'])
        page = self.pages.get(report['page_id'])
        require(page is not None or sum(self.online(item) for item in self.pages.values()) < 32,
                'SESSION_LIMIT', 'Too many active page sessions', 429)
        require(not any(record['command']['page_id'] == report['page_id']
                        and record['command']['session_id'] != report['session_id'] for record in self.commands.values()),
                'WRONG_TARGET', 'Use a fresh page ID after a target change', 409)
        if page:
            require(page['report']['session_id'] == report['session_id'], 'WRONG_TARGET', 'Use a fresh page ID after a target change', 409)
            previous = page['report']['state']
            require(report['state']['revision'] >= previous['revision'], 'STALE_REVISION', 'Page revision went backwards', 409)
            require(report['state']['revision'] != previous['revision'] or report['state'] == previous,
                    'STALE_REVISION', 'Changed public state requires a new revision', 409)
        for receipt in body['receipts']:
            record = self.commands.get(receipt['command_id'])
            require(record is not None and record['command']['page_id'] == report['page_id']
                    and record['command']['session_id'] == report['session_id'] and record['command']['action'] == receipt['action']
                    and isinstance(receipt['status'], str) and receipt['status'] in TERMINAL | {'accepted', 'unknown'},
                    'INVALID_RECEIPT', 'Receipt does not match a submitted command')
        # Freeze undelivered commands before making an offline page online again.
        for record in self.commands.values():
            if record['command']['page_id'] == report['page_id']:
                self._current_receipt(record)
        self.reclaim_pages()
        page = self.pages.setdefault(report['page_id'], {})
        page.update(report=report, seen=self.clock())
        for receipt in body['receipts']:
            record = self.commands[receipt['command_id']]
            if record['receipt']['status'] not in TERMINAL:
                # accepted cannot turn an unknown outcome back into executable work.
                if record['receipt']['status'] != 'unknown' or receipt['status'] in TERMINAL:
                    record['receipt'] = receipt
        pending = next((record['command'] for record in self.commands.values()
                        if record['command']['page_id'] == report['page_id'] and self._current_receipt(record)['status'] == 'queued'), None)
        response = {'command': copy.deepcopy(pending)}
        if page.get('notices'):
            ack = body.get('feedback_ack', 0)
            page['notices'] = [notice for notice in page['notices'] if notice['seq'] > ack]
            if page['notices']:
                response['feedback'] = copy.deepcopy(page['notices'])
        return response

    def submit_intent(self, body, on_loop=lambda fn: fn()):
        from .frontend_intents import find_intent, save_intent, validate_request
        validate_request(body)
        on_loop(lambda: self.check_target(body['session_id']))
        target = on_loop(lambda: self.target)
        # Accept an exact retry even after page state advanced.
        try:
            old = find_intent(target['project_root'], body['request_id'])
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
        else:
            require(old['request'] == body and old['target'] == target, 'ID_CONFLICT', 'Request ID already has different content', 409)
            return {**old, 'duplicate': True}
        context = on_loop(lambda: self.intent_context(body))
        return save_intent(target['project_root'], body, target, self.clock(), context,
                           before_commit=lambda: on_loop(lambda: self.intent_context(body)))

    def intent_context(self, body):
        self.check_target(body['session_id'])
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
        return context


def install_frontend(app, control):
    broker = FrontendBroker(control)
    control.frontend = broker
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @api.middleware('http')
    async def no_cache(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    async def raw_body(request, limit=2 * 1024 * 1024):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            require(len(raw) <= limit, message='Frontend request exceeds the limit', status=413)
        return raw

    def decode(raw):
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(422, {'code': 'INVALID_INPUT', 'message': 'Invalid JSON request'}) from exc
        require(isinstance(value, dict))
        return value

    async def body(request, limit=2 * 1024 * 1024):
        return decode(await raw_body(request, limit))

    def loop_caller():
        loop = asyncio.get_running_loop()

        async def invoke(fn):
            return fn()

        # Worker-side commit checks run on the event loop; never inspect mutable
        # page/target state from a filesystem worker holding the storage lock.
        return lambda fn: asyncio.run_coroutine_threadsafe(invoke(fn), loop).result()

    async def storage(session_id, operation, *args, **kwargs):
        broker.check_target(session_id)
        try:
            result = await run_in_threadpool(operation, *args, **kwargs)
        except PreferencesConflict as exc:
            raise HTTPException(409, {'code': 'STALE_REVISION', 'message': str(exc)}) from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(422, {'code': 'STORAGE_UNAVAILABLE', 'message': str(exc)}) from exc
        broker.check_target(session_id)
        return result

    def storage_target(request):
        session_id = broker.session_id
        broker.check_target(request.headers.get('X-MKLink-Frontend-Session', session_id))
        return session_id, broker.target['project_root']

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
        raw = await raw_body(request)
        # Only request-owned data leaves the loop. Commit against the current target and revision.
        prepared = await run_in_threadpool(lambda: _prepare_exchange(decode(raw)))
        return broker._commit_exchange(prepared)

    @api.get('/layout')
    async def layout(request: Request):
        session_id, root = storage_target(request)
        return await storage(session_id, load_layout, root)

    @api.put('/layout')
    async def put_layout(request: Request):
        session_id, root = storage_target(request)
        on_loop = loop_caller()
        return await storage(session_id, save_layout, root, await body(request, 256 * 1024),
                             before_commit=lambda: on_loop(lambda: broker.check_target(session_id)))

    @api.get('/layouts')
    async def layouts(request: Request, query: str = '', scope: str = 'project'):
        session_id, root = storage_target(request)
        return await storage(session_id, search_layouts, root, query, scope)

    @api.get('/layouts/item')
    async def named_layout(request: Request, name: str, scope: str = 'project'):
        session_id, root = storage_target(request)
        return await storage(session_id, load_named_layout, root, name, scope)

    @api.post('/layouts')
    async def put_named_layout(request: Request):
        session_id, root = storage_target(request)
        on_loop = loop_caller()
        return await storage(session_id, save_named_layout, root, await body(request, 257 * 1024),
                             before_commit=lambda: on_loop(lambda: broker.check_target(session_id)))

    @api.post('/replay-file')
    async def replay_file(request: Request):
        from fastapi.responses import FileResponse
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
        session_id, _ = storage_target(request)
        return public_intent(await storage(session_id, broker.submit_intent, await body(request, 20 * 1024), loop_caller()))

    @api.get('/intents')
    async def intents(request: Request):
        from .frontend_intents import load_intents
        session_id, root = storage_target(request)
        data = await storage(session_id, load_intents, root)
        return {'requests': [{**public_intent(entry), 'current_target': entry['request']['session_id'] == broker.session_id}
                             for entry in data['requests']]}

    @api.get('/intent')
    async def read_intent(request: Request, request_id: str):
        from .frontend_intents import find_intent
        session_id, root = storage_target(request)
        return public_intent(await storage(session_id, find_intent, root, request_id))

    @api.post('/reply')
    async def reply(request: Request):
        from .frontend_intents import reply_intent
        session_id, root = storage_target(request)
        on_loop = loop_caller()
        return public_intent(await storage(session_id, reply_intent, root, await body(request, 64 * 1024), session_id, broker.clock(),
                                           before_commit=lambda: on_loop(lambda: broker.check_target(session_id))))

    app.router.routes.insert(0, Mount('/api/runtime/frontend', app=api))
    from .frontend_capabilities import install_capability_panel
    install_capability_panel(app, control, broker, body)
    return broker

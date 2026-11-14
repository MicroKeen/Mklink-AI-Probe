"""Optional, acknowledged presentation on an existing GUI presence socket."""
import asyncio
import secrets
import time
from fastapi import HTTPException

TABS = frozenset({'superwatch', 'rtt', 'memory', 'symbols', 'hardfault', 'systemview'})
PAGES = frozenset({'config', 'dashboard', 'online-flash', 'offline-flash', 'remote-service'})
ALL_TABS = TABS | {'serial', 'modbus'}
SECTIONS = frozenset({'local', 'files', 'firmware', 'runtime'})
ACTIONS = frozenset({'snapshot', 'navigate', 'focus', 'controls', 'control.click', 'control.set', 'file.select', 'directory.select', 'systemview.window',
                     'systemview.pause', 'systemview.resume', 'systemview.zoom-in',
                     'systemview.zoom-out', 'systemview.fit', 'superwatch.pause', 'superwatch.resume'})


def windows(control):
    control.prune()
    return {'windows': [{'window_id': key, 'name': v['name'],
                         **({'gui_protocol': 2, 'kind': v.get('kind', 'web')} if v.get('gui_protocol') == 2 else {})}
                        for key, v in control.views.items()
                        if v.get('presentation') and v.get('live')]}


def validate_action(body):
    action = body.get('action', 'snapshot')
    if not isinstance(action, str) or action not in ACTIONS:
        raise HTTPException(422, 'Unsupported GUI action')
    fields = {'window_id', 'action'}
    if action == 'controls':
        fields.add('offset')
        if type(body.get('offset', 0)) is not int or not 0 <= body.get('offset', 0) <= 10000:
            raise HTTPException(422, 'Invalid controls offset')
    if action in {'control.click', 'control.set', 'file.select', 'directory.select'}:
        fields |= {'control_id', 'expected_context'}
        for field in ('control_id', 'expected_context'):
            if not isinstance(body.get(field), str) or not 1 <= len(body[field]) <= 1024:
                raise HTTPException(422, f'{field} is required from a fresh GUI snapshot')
        if action == 'control.set':
            fields.add('value')
            if type(body.get('value')) not in (str, bool, int, float):
                raise HTTPException(422, 'Set a scalar control value')
        if action in {'file.select', 'directory.select'}:
            fields.add('path')
            if not isinstance(body.get('path'), str) or len(body['path']) > 4096:
                raise HTTPException(422, 'Select a file on the backend computer')
    if action == 'navigate':
        fields |= {'page', 'tab', 'section'}
        page = body.get('page', 'dashboard')
        if not isinstance(page, str) or page not in PAGES:
            raise HTTPException(422, 'Choose a supported GUI page')
        if 'tab' in body and (page != 'dashboard' or not isinstance(body['tab'], str) or body['tab'] not in ALL_TABS):
            raise HTTPException(422, 'Choose a supported dashboard tab')
        if 'section' in body and (page != 'config' or not isinstance(body['section'], str) or body['section'] not in SECTIONS):
            raise HTTPException(422, 'Choose a supported configuration section')
    if action == 'systemview.window':
        fields.add('seconds')
        if type(body.get('seconds')) not in (float, int) or body['seconds'] not in (0.5, 1, 2, 5, 10, 30, 60):
            raise HTTPException(422, 'Choose a supported Timeline window in seconds')
    if body.keys() - fields:
        raise HTTPException(422, 'Unsupported GUI action arguments')
    return action


async def action(control, body):
    command = validate_action(body)
    key = body.get('window_id')
    if key is not None and (not isinstance(key, str) or not 1 <= len(key) <= 128):
        raise HTTPException(422, 'Invalid window_id')
    candidates = windows(control)['windows']
    if key is None:
        if len(candidates) != 1:
            raise HTTPException(409, {'reason': 'select_gui_window', **windows(control)})
        key = candidates[0]['window_id']
    view = control.views.get(key)
    if not view or not view.get('live'):
        raise HTTPException(404, 'GUI window unavailable')
    if view.get('gui_protocol') != 2:
        raise HTTPException(409, 'Update/reload this GUI window to use GUI actions; no action was sent')
    if view.get('pending'):
        raise HTTPException(409, 'GUI request already pending')
    payload = {**body, 'action': command}
    if command == 'directory.select':
        from pathlib import Path
        directory = Path(payload['path'])
        if not directory.is_absolute() or not directory.is_dir():
            raise HTTPException(422, 'Choose an existing absolute directory on the backend computer')
    if command == 'file.select':
        from mklink.runtime_gui_files import GuiFiles
        files = getattr(control, 'gui_files', None)
        if files is None:
            files = control.gui_files = GuiFiles()
        payload['file'] = files.prepare(payload.pop('path'), key)
        from urllib.parse import quote
        payload['file']['url'] += '?window_id=' + quote(key, safe='')
    request_id = secrets.token_hex(12)
    future = asyncio.get_running_loop().create_future()
    view['pending'] = (request_id, future)
    view['pending_kind'] = 'gui_result'
    try:
        await asyncio.wait_for(view['socket'].send_json({'type': 'gui_request', 'request_id': request_id,
            'command': payload, 'expires_at': time.time() + 3}), timeout=1)
        result = await asyncio.wait_for(future, timeout=3)
        return {'window_id': key, 'request_id': request_id,
                **(result if isinstance(result, dict) else {'status': result})}
    except (TimeoutError, RuntimeError, OSError):
        return {'window_id': key, 'status': 'unconfirmed', 'request_id': request_id}
    finally:
        view.pop('pending', None)
        view.pop('pending_kind', None)


async def present(control, body):
    if (set(body) - {'window_id', 'tab'} or not isinstance(body.get('tab', 'superwatch'), str)
            or body.get('tab', 'superwatch') not in TABS):
        raise HTTPException(422, 'Choose a supported dashboard tab')
    key = body.get('window_id')
    if key is not None and (not isinstance(key, str) or not key or len(key) > 128):
        raise HTTPException(422, 'Invalid window_id')
    candidates = windows(control)['windows']
    if key is None:
        if len(candidates) != 1:
            raise HTTPException(409, {'reason': 'select_gui_window', **windows(control)})
        key = candidates[0]['window_id']
    view = control.views.get(key)
    if not view or not view.get('presentation'):
        raise HTTPException(404, 'GUI window unavailable or requires an update')
    if view.get('pending'):
        raise HTTPException(409, 'GUI presentation already pending')
    request_id = secrets.token_hex(12)
    future = asyncio.get_running_loop().create_future()
    view['pending'] = (request_id, future)
    view['pending_kind'] = 'present_result'
    try:
        await asyncio.wait_for(view['socket'].send_json({'type': 'present', 'request_id': request_id,
            'tab': body.get('tab', 'superwatch'), 'expires_at': time.time() + 3}), timeout=1)
        result = await asyncio.wait_for(future, timeout=3)
        return {'window_id': key, 'tab': body.get('tab', 'superwatch'), 'status': result}
    except (TimeoutError, RuntimeError, OSError):
        return {'window_id': key, 'status': 'unconfirmed', 'request_id': request_id}
    finally:
        view.pop('pending', None)
        view.pop('pending_kind', None)


def acknowledge(view, message):
    if message.get('type') == 'gui_hello' and message.get('protocol') == 2:
        view['gui_protocol'] = 2
        view['kind'] = 'desktop' if message.get('kind') == 'desktop' else 'web'
        return
    pending = view.get('pending')
    if message.get('type') != view.get('pending_kind'):
        return
    if pending and message.get('type') == 'gui_result' and message.get('request_id') == pending[0]:
        if not pending[1].done():
            state = message.get('state')
            pending[1].set_result({'status': 'applied' if message.get('ok') is True else 'rejected',
                                  'state': state if isinstance(state, dict) else {},
                                  'error': str(message.get('error', ''))[:512]})
        return
    if pending and message.get('type') == 'present_result' and message.get('request_id') == pending[0]:
        if not pending[1].done():
            pending[1].set_result('displayed' if message.get('ok') is True else 'rejected')

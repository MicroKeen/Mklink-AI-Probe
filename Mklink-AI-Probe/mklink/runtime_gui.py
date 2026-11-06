"""Explicit GUI launch/observation; never connects hardware or changes acquisition."""
from __future__ import annotations

from pathlib import Path
import time
import webbrowser

from mklink import runtime


def public_runtime(info):
    return {key: info.get(key) for key in ('runtime_id', 'instance_id', 'probe_id', 'project_root')}


def select_gui_runtime(*, current=None, probe=None, runtime_id=None, project_root=None):
    """Resolve one existing backend before considering a new unbound window."""
    selected = None
    if probe is not None:
        from mklink.probes import select_probe
        selected = select_probe(probe)['probe_id']
    candidates = runtime.running_runtimes() if current is None else [current]
    described = []
    for item in candidates:
        if 'project_root' not in item:
            health = runtime.request(item, 'GET', '/_runtime/status', timeout=2)
            if health.get('instance_id') != item.get('instance_id'):
                raise runtime.RuntimeErrorResponse('GUI backend instance changed; rediscover explicitly')
            item = {**item, 'project_root': health['project_root'], 'probe_id': health['probe_id']}
        described.append(item)
    candidates = described
    if runtime_id is not None:
        matches = [item for item in candidates if item.get('runtime_id') == runtime_id]
        if not matches:
            raise runtime.RuntimeErrorResponse('Selected runtime is unavailable or differs from this MCP session; detach before selecting another backend')
        candidates = matches
    elif selected is not None:
        bound = [item for item in candidates if item.get('probe_id') == selected]
        candidates = bound or [item for item in candidates if item.get('probe_id') == 'lobby']
        if current is not None and not candidates:
            raise runtime.RuntimeErrorResponse('MCP is attached to another probe; connect explicitly or detach before opening another backend')
    if len(candidates) > 1:
        return None, {'status': 'select_runtime', 'runtimes': [public_runtime(item) for item in candidates]}
    if candidates:
        info = candidates[0]
        if selected and info.get('probe_id') not in (selected, 'lobby'):
            raise runtime.RuntimeErrorResponse('Selected runtime belongs to another probe')
        if project_root is not None and Path(project_root).resolve() != Path(info['project_root']).resolve():
            raise runtime.RuntimeErrorResponse('GUI project differs; keep the existing project or explicitly stop/reconfigure its backend')
    else:
        if not project_root:
            raise ValueError('project_root is required when opening a new GUI backend')
        root = Path(project_root).resolve()
        if not root.is_dir():
            raise ValueError('project_root must be an existing directory on the MCP computer')
        # No probe selection here: GUI startup must not claim hardware.
        info = runtime.ensure_runtime(project_root=str(root), allow_lobby=True, new_window=True)
    return info, {'requested_probe': selected} if selected else {}


class GuiLaunch:
    """Remember an outstanding browser launch so status/repeated calls do not reopen it."""
    def __init__(self):
        self.pending = None

    def inspect(self, client):
        info = client.info
        health = runtime.request(info, 'GET', '/_runtime/status', timeout=2)
        if health.get('instance_id') != info.get('instance_id'):
            raise runtime.RuntimeErrorResponse('GUI backend instance changed; reconnect explicitly')
        windows = runtime.request(info, 'GET', '/api/runtime/control/windows')['windows']
        if windows:
            self.pending = None
        return {**public_runtime({**info, 'probe_id': health.get('probe_id'),
                                 'project_root': health.get('project_root')}),
                'status': 'ready' if windows else 'awaiting_window', 'windows': windows,
                'url': f"http://127.0.0.1:{info['port']}/",
                'gui_launch_supported': health.get('gui_launch') == 1}

    def open(self, client, *, window_id=None, open_browser=True):
        result = self.inspect(client)
        windows = result['windows']
        if window_id is not None and not any(item['window_id'] == window_id for item in windows):
            raise runtime.RuntimeErrorResponse('Selected GUI window is unavailable; inspect windows again')
        if windows:
            if len(windows) > 1 and window_id is None:
                result['status'] = 'select_window'
            else:
                result['window_id'] = window_id or windows[0]['window_id']
            return result
        if not result['gui_launch_supported']:
            raise runtime.RuntimeErrorResponse('This backend lacks GUI launch links; update and explicitly restart it, or open its installed GUI. No second backend was started')
        if self.pending is None or self.pending['expires'] <= time.monotonic():
            link = runtime.request(client.info, 'POST', '/_runtime/gui-link', {'session_id': client.session_id})
            self.pending = {'url': f"{result['url']}_runtime/open#{link['ticket']}",
                            'expires': time.monotonic() + link['expires_in'], 'attempted': False}
        pending = self.pending
        if open_browser and not pending['attempted']:
            pending['attempted'] = True
            try:
                pending['browser_requested'] = bool(webbrowser.open(pending['url']))
            except Exception:
                # Browser handlers can include the URL in their exception text.
                pending['browser_requested'] = False
        return {**result, 'open_url': pending['url'],
                'url_expires_in': max(0, int(pending['expires'] - time.monotonic())),
                'browser_requested': pending.get('browser_requested', False),
                'guidance': 'Open open_url on this computer, then check gui_open(action="status"). The MCP attachment keeps the backend alive until detach; this one-use login link expires separately. Do not publish the link.'}

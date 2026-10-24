"""Bounded connection evidence; no target data, credentials or hardware access."""
from contextlib import contextmanager
from datetime import datetime
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import re
import threading
import time
import zipfile

_sink = None
MAX_BYTES = 512 * 1024
BACKUPS = 3


def clean(value):
    if isinstance(value, dict):
        return {str(k): '[redacted]' if re.search(r'token|password|secret|authorization|nonce|api[_-]?key|private[_-]?key|cookie', str(k), re.I)
                else clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value[:32]]
    if isinstance(value, str):
        value = re.sub(r'(?i)(bearer\s+)[^\s,;\"\x27]+', r'\1[redacted]', value)
        value = re.sub(r'(?i)((?:token|password|secret|authorization|nonce|api[_-]?key|private[_-]?key|cookie)[\"\x27]?\s*[:=]\s*[\"\x27]?)[^\s,;&\"\x27]+',
                       r'\1[redacted]', value)
        return value[:2048]
    return value if value is None or isinstance(value, (bool, int, float)) else type(value).__name__


def error_detail(error):
    chain, seen = [], set()
    while error is not None and id(error) not in seen and len(chain) < 4:
        seen.add(id(error))
        chain.append(clean({'type': type(error).__name__, 'message': str(error),
                            'errno': getattr(error, 'errno', None), 'winerror': getattr(error, 'winerror', None)}))
        error = error.__cause__ or error.__context__
    return chain


def event(name, **fields):
    """Logging failure must never change transport/recovery behavior."""
    handler = _sink
    if handler is None:
        return
    try:
        entry = {'time': datetime.now().astimezone().isoformat(timespec='milliseconds'),
                 'monotonic_ms': round(time.monotonic() * 1000), 'pid': os.getpid(),
                 'thread': threading.current_thread().name, 'event': name, **clean(fields)}
        record = logging.LogRecord('mklink.connection', logging.INFO, '', 0,
                                   json.dumps(entry, ensure_ascii=False), (), None)
        handler.handle(record)
    except Exception:
        pass


@contextmanager
def connection_log(directory):
    global _sink
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(Path(directory) / 'connection.jsonl', maxBytes=MAX_BYTES,
                                      backupCount=BACKUPS, encoding='utf-8')
    except OSError:
        # Additional diagnostics must not prevent an otherwise usable backend.
        yield
        return
    previous, _sink = _sink, handler
    event('runtime.started')
    try:
        yield
    finally:
        event('runtime.stopped')
        _sink = previous
        handler.close()


def export_bundle():
    """Only allowlisted structured event files; never endpoint/config/RTT logs."""
    from mklink.runtime import runtime_dir, VERSION
    root = runtime_dir()
    directories = [root]
    def regular_directory(path):
        return path.is_dir() and not path.is_symlink() and not getattr(path, 'is_junction', lambda: False)()
    for parent in (root / 'probes', root / 'desktops'):
        if regular_directory(parent):
            directories += sorted((p for p in parent.iterdir() if regular_directory(p)),
                                  key=lambda p: p.stat().st_mtime, reverse=True)[:8]
    output, files = io.BytesIO(), []
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for index, directory in enumerate(directories):
            for suffix in ('', '.1', '.2', '.3'):
                path = directory / ('connection.jsonl' + suffix)
                if not path.is_file() or path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
                    continue
                try:
                    with path.open('rb') as stream:
                        stream.seek(0, 2)
                        length = stream.tell()
                        stream.seek(max(0, length - MAX_BYTES))
                        data = stream.read(MAX_BYTES)
                    rows = []
                    for line in data.decode('utf-8', 'replace').splitlines():
                        try:
                            row = json.loads(line)
                        except ValueError:
                            continue  # Concurrent last write or truncated oldest line.
                        if isinstance(row, dict):
                            rows.append(json.dumps(clean(row), ensure_ascii=False))
                    name = f'connection-{index}{suffix}.jsonl'
                    archive.writestr(name, '\n'.join(rows) + ('\n' if rows else ''))
                    files.append({'name': name, 'records': len(rows), 'tail_only': length > MAX_BYTES})
                except OSError:
                    files.append({'name': f'connection-{index}{suffix}.jsonl', 'unavailable': True})
        archive.writestr('manifest.json', json.dumps({
            'format': 1, 'created_at': datetime.now().astimezone().isoformat(),
            'version': VERSION, 'os': platform.system(), 'os_release': platform.release(),
            'architecture': platform.machine(), 'files': files,
            'scope': 'Connection events only; no firmware, target output, credentials or project files.',
            'retention': 'Newest 8 probe and 8 desktop log directories, up to four 512-KiB event files each.',
            'note': 'Events before this feature was installed are unavailable. Client timestamps use the client clock.',
        }, ensure_ascii=False, indent=2))
    return output.getvalue()


def install_export(app):
    from fastapi.responses import Response
    from starlette.concurrency import run_in_threadpool
    from typing import Literal
    from pydantic import BaseModel, Field

    class ClientEvent(BaseModel):
        event: Literal['status_failed', 'status_restored']
        time: str = Field(max_length=40)
        message: str = Field(default='', max_length=512)

    class ClientEvents(BaseModel):
        events: list[ClientEvent] = Field(max_length=25)

    @app.post('/api/runtime/diagnostics/events')
    async def record_client_events(body: ClientEvents):
        for row in body.events:
            event('gui.' + row.event, client_time=row.time, message=row.message)
        return {'recorded': len(body.events)}

    @app.get('/api/diagnostics/export')
    async def export_diagnostics():
        data = await run_in_threadpool(export_bundle)
        return Response(data, media_type='application/zip', headers={
            'Content-Disposition': 'attachment; filename="mklink-diagnostics.zip"',
            'Cache-Control': 'no-store',
        })

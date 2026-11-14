"""Bounded, short-lived file delivery to one authenticated local GUI window."""
import asyncio
import os
from pathlib import Path
import secrets
import stat
import time

from fastapi import HTTPException
from fastapi.responses import StreamingResponse


class GuiFiles:
    def __init__(self):
        self.files = {}

    def prune(self):
        for token, entry in list(self.files.items()):
            if entry['expires'] <= time.monotonic():
                self.expire(token)

    def expire(self, token):
        entry = self.files.pop(token, None)
        if entry:
            entry['file'].close()

    def release_window(self, window_id):
        for token, entry in list(self.files.items()):
            if entry['window_id'] == window_id:
                self.expire(token)

    def prepare(self, path, window_id):
        self.prune()
        if len(self.files) >= 8:
            raise HTTPException(429, 'GUI file delivery limit reached; wait for pending imports')
        if not isinstance(path, str) or not Path(path).is_absolute():
            raise HTTPException(422, 'Use an absolute local file path')
        source = Path(path)
        if source.is_symlink() or (hasattr(source, 'is_junction') and source.is_junction()):
            raise HTTPException(422, 'Choose a regular file, not a link')
        try:
            if not source.is_file():
                raise HTTPException(422, 'Choose an existing regular file')
            flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
            handle = os.fdopen(os.open(source, flags), 'rb')
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 256 * 1024 * 1024:
                handle.close()
                raise HTTPException(422, 'GUI imports require a regular file of at most 256 MiB')
        except OSError as error:
            raise HTTPException(422, f'Cannot read selected GUI file: {error.strerror}') from error
        token = secrets.token_urlsafe(24)
        self.files[token] = {'file': handle, 'expires': time.monotonic() + 60, 'window_id': window_id}
        try:
            asyncio.get_running_loop().call_later(60, self.expire, token)
        except RuntimeError:
            pass  # Synchronous callers explicitly prune; HTTP handlers have a loop.
        return {'url': f'/api/runtime/control/gui-files/{token}', 'name': source.name,
                'size': info.st_size, 'path': str(source)}

    def response(self, token, window_id):
        self.prune()
        entry = self.files.get(token)
        if not entry or entry['window_id'] != window_id:
            raise HTTPException(404, 'GUI file delivery expired or belongs to another window')
        self.files.pop(token)
        handle = entry['file']
        def chunks():
            try:
                while data := handle.read(256 * 1024):
                    yield data
            finally:
                handle.close()
        return StreamingResponse(chunks(), media_type='application/octet-stream', headers={'Cache-Control': 'no-store'})

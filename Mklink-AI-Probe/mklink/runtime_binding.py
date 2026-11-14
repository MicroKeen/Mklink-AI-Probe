"""A window owns a backend; a backend temporarily owns one physical probe.

Endpoint aliases are discovery only. OS locks remain the authority, including
while a switch is draining the old transport. Never transfer a live transport.
"""
from contextlib import contextmanager
import json
import os

from mklink.runtime import _private_dir, runtime_lock, RuntimeErrorResponse


def write_endpoint(key, info):
    path = _private_dir(key) / 'endpoint.json'
    temporary = path.with_suffix('.tmp')
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
                   'w', encoding='utf-8') as output:
        json.dump(info, output)
    temporary.replace(path)


class RuntimeBinding:
    def __init__(self, info):
        self.info = info
        self.lock = None

    def _remove_alias(self, key):
        path = _private_dir(key) / 'endpoint.json'
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            if saved.get('instance_id') == self.info['instance_id']:
                path.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass

    @contextmanager
    def reserve(self, probe_id):
        lock = None
        committed = False
        if probe_id != 'lobby':
            lock = runtime_lock('owner.lock', probe_id)
            try:
                with runtime_lock('history-maintenance.lock'):
                    lock.__enter__()
            except RuntimeErrorResponse as error:
                message = 'This probe is in use by another backend; select a different probe or disconnect it there before switching'
                raise RuntimeErrorResponse(message, status_code=409,
                                           detail={'reason': 'probe_in_use', 'message': message}) from error
        def commit():
            nonlocal committed
            from mklink.probes import rebind_runtime
            old_id, old_lock = self.info['probe_id'], self.lock
            transport = 'cdc'
            if probe_id.startswith('s3-'):
                # Registration cannot change while this owner lock is held.
                from mklink.s3_registry import load_nodes
                node = load_nodes().get(probe_id)
                transport = 's3-' + node['transport'] if node else 's3'
            updated = {**self.info, 'probe_id': probe_id, 'transport': transport}
            # Publish while both ownership locks are held. Readers additionally
            # verify the live identity, so a partial publication cannot attach.
            write_endpoint(self.info['runtime_id'], updated)
            if probe_id != 'lobby':
                write_endpoint(probe_id, updated)
            rebind_runtime(old_id, probe_id)
            self.info.update(updated)
            self.lock, committed = lock, True
            if old_id != probe_id and old_id != 'lobby':
                self._remove_alias(old_id)
            if old_lock:
                old_lock.__exit__(None, None, None)
        try:
            yield commit
        finally:
            if lock and not committed:
                lock.__exit__(None, None, None)

    def close(self):
        self._remove_alias(self.info['runtime_id'])
        if self.info['probe_id'] != 'lobby':
            self._remove_alias(self.info['probe_id'])
        if self.lock:
            self.lock.__exit__(None, None, None)
            self.lock = None

"""Deferred cloud advice from the existing handshake cache, never probe I/O.

This is not capability negotiation or upgrade authorization. Status reads only
schedule a delayed network task and compare immutable metadata; they never wait
for it, enumerate USB, reserve the target, or interrupt a capture.
"""
from __future__ import annotations

import asyncio
import time

from mklink.capture_clock import firmware_lines
from mklink.firmware_check import cached_probe_version, _remote_firmwares


def cached_identity(device):
    if device is None or not device.connected:
        return None
    lines = firmware_lines(getattr(device, '_bridge', None))
    version = cached_probe_version(getattr(device, '_bridge', None))
    if version is None or version.major not in (2, 3, 4):
        return None
    products = {line.partition('=')[2].upper() for line in lines if line.startswith('PROBE_PRODUCT=')}
    if products == {'HPMLINK'} and version.major == 4:
        family = 'hpmlink'
    elif products == {'MKLINK'} or not products:
        family = 'microlink'
    else:
        # Missing product declarations use the legacy MicroLink identity.
        # Explicit unknown/conflicting declarations are not a missing identity.
        return None
    return family, f'V{version.major}', version


class FirmwareNotice:
    DELAY = 3.0
    SUCCESS_TTL = 6 * 3600
    FAILURE_TTL = 15 * 60

    def __init__(self):
        self._cache = {}
        self._tasks = {}
        self._closed = False

    def snapshot(self, state):
        device = state.get('device')
        if device is None or not device.connected:
            return None
        connection = dict(probe_id=state.get('shared_probe_id') or device.port,
                          device_generation=state.get('device_generation', 0))
        identity = cached_identity(device)
        if identity is None:
            return dict(connection, status='unrecognized', action='upgrade_probe_firmware')
        family, model, current = identity
        result = dict(status='checking', family=family, model=model,
                      current_version=str(current), latest_version=None,
                      **connection)
        v2 = model == 'V2'
        cached = self._cache.get(v2)
        if cached is None or time.monotonic() >= cached[0]:
            if not self._closed and v2 not in self._tasks:
                self._tasks[v2] = asyncio.create_task(self._check(v2))
            return result
        entries = cached[1]
        if entries is None:
            return {**result, 'status': 'unavailable'}
        latest = next((item for item in entries if item.family == family and item.model == model), None)
        if latest is None:
            return {**result, 'status': 'no_firmware'}
        result.update(status='available' if current < latest.version else 'current',
                      latest_version=str(latest.version))
        if result['status'] == 'available':
            result['action'] = 'upgrade_probe_firmware'
        return result

    async def _check(self, v2):
        try:
            await asyncio.sleep(self.DELAY)
            # Cloud-only advice: an offline bundled catalog must not be called
            # a successful cloud check. The manual updater retains its fallback.
            try:
                entries = await asyncio.to_thread(_remote_firmwares, timeout=3.0,
                                                   v2=v2, include_bundled=False)
            except Exception:
                entries = None
            ttl = self.FAILURE_TTL if entries is None else self.SUCCESS_TTL
            self._cache[v2] = (time.monotonic() + ttl, entries)
        finally:
            self._tasks.pop(v2, None)

    async def close(self):
        self._closed = True
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

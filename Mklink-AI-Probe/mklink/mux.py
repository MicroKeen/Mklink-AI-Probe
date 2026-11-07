"""Bounded V4 CDC multiplex transport, fed by the bridge's sole reader.

No serial handle or reader thread here. Writes share one request slot; a timeout
poisons the session and is never retried or silently converted into Pika source.
"""
from __future__ import annotations

from collections import deque
import binascii
import secrets
import struct
import threading
import time
from mklink.connection_diagnostics import event, error_detail


class MuxError(ConnectionError):
    pass


class MuxTargetError(RuntimeError):
    def __init__(self, status, op=None):
        self.status = status
        if status == 6:
            message = ('Multiplex target busy (status 6); debugger access is currently reserved. '
                       'Retry explicitly when available; the request was not replayed')
        elif status == 5:
            message = ('Multiplex target status 5; target access failed. Check target power and debug access. '
                       'For a periodically sleeping Cortex-M, enable sleep access before reading or starting RTT.')
            if op not in (0x11, 0x13, 0x16):
                message += ' A submitted write or reset may have an unknown outcome.'
        else:
            message = f'Multiplex target status {status}; failed writes may have an unknown outcome'
        super().__init__(message)


class MuxWatchEvent(bytes):
    """Local reset generation accompanies queued wire bytes, without loss."""
    def __new__(cls, payload, reset_generation):
        value = super().__new__(cls, payload)
        value.reset_generation = reset_generation
        # 1: confirmed discarded/read-failed records; 2: wire continuity unknown.
        value.break_before = 0
        return value


def packet(op, epoch, request, payload=b''):
    limit = {0x12: 492, 0x24: 489}.get(op, 256)
    if len(payload) > limit:
        raise ValueError(f'Multiplex payload exceeds {limit} bytes')
    raw = struct.pack('<4sBBHII', b'MLX1', 1, op, len(payload), epoch, request) + payload
    return raw + struct.pack('<I', binascii.crc32(raw) & 0xffffffff)


class MuxTransport:
    RTT_UPDATE_CAPABILITY = 1 << 7
    FAST_TRANSFER_CAPABILITY = 1 << 8
    FAST_TRANSFER_BYTES = 480
    BLOCK_READ_CAPABILITY = 1 << 6
    BLOCK_READ_COMMAND = 0x16
    BULK_WATCH_CAPABILITY = 1 << 11
    SOFTWARE_RESET_CAPABILITY = 1 << 5
    SOFTWARE_RESET_COMMAND = 0x15
    MAX_QUEUE_BYTES = 65536
    # ~160 ms at 200k 4-byte samples/s (timestamp + value). RTT queues keep
    # their original limit; replies bypass event queues. Still drop oldest on
    # sustained overload, never block the sole USB reader or command replies.
    WATCH_QUEUE_BYTES = 262144

    def __init__(self, write, command_lock=None, *, diagnostic_context=None):
        self._diagnostic_context = diagnostic_context or {}
        self._write = write
        self._condition = threading.Condition()
        self._commands = command_lock or threading.RLock()
        self._rx = bytearray()
        self._pending = None
        self._request_waiting = False
        self._reply = None
        self._error = None
        self._next_id = 0
        self.epoch = 0
        self.nonce = secrets.token_bytes(8)
        self.ready = False
        self.capabilities = 0
        self.transfer_quantum = 128
        self.sleep_access = False
        self._pending_quantum = None
        self._reset_generation = 0
        self.rtt_mask = 0
        self._rtt_manager = None
        self.watch_running = False
        self.bulk_running = False
        self._last_command = time.monotonic()
        self._queues = {}
        self._sizes = {}
        self.dropped_bytes = {}
        self.event_gaps = 0
        self._event_id = None
        self._watch_wire_gap = False
        self._bulk_wire_gap = False
        self._last_receive = None
        self._last_reply = None
        self._last_timeout = None

    @property
    def sampling(self):
        return bool(self.rtt_mask or self.watch_running or self.bulk_running)

    def fail(self, error):
        with self._condition:
            if self._error is None:
                self._error = MuxError(str(error))
                now = time.monotonic()
                event('mux.failed', **self._diagnostic_context,
                      error=error_detail(error if isinstance(error, BaseException) else self._error),
                      epoch=self.epoch,
                      pending=None if self._pending is None else {
                          'opcode': f'0x{self._pending[0]:02X}', 'request': self._pending[1],
                          'heartbeat': self._pending[3]},
                      last_receive_age_ms=None if self._last_receive is None else round((now-self._last_receive)*1000),
                      last_reply_age_ms=None if self._last_reply is None else round((now-self._last_reply)*1000),
                      timeout=self._last_timeout, rtt_mask=self.rtt_mask, watch_running=self.watch_running)
            self.ready = False
            self._condition.notify_all()

    def _check(self):
        if self._error:
            raise self._error

    def _send(self, op, payload, heartbeat=False):
        if op == 0x12 and len(payload) > 4 + self.transfer_quantum:
            raise ValueError('Memory write exceeds negotiated transfer size')
        if op == 0x24 and (self.transfer_quantum != self.FAST_TRANSFER_BYTES
                          or not 2 <= len(payload) <= 1 + self.FAST_TRANSFER_BYTES):
            raise ValueError('Fast RTT write requires negotiated 480-byte capability')
        self._next_id += 1
        if self._next_id > 0xffffffff:
            raise MuxError('Request IDs exhausted; close and create a new session')
        req = self._next_id
        wire = packet(op, 0 if op == 1 else self.epoch, req,
                      (self.nonce if 0x10 <= op < 0x40 else b'') + payload)
        # At 10 Hz WFI, a 128-byte RTT poll plus its cursor update can span
        # over three seconds. Keep the deadline inside the probe's 5 s lease.
        self._pending = (op, req, time.monotonic() + (4.8 if self.sleep_access else 3), heartbeat)
        self._reply = None
        self._last_command = time.monotonic()
        try:
            count = self._write(wire)
            if count is not None and count != len(wire):
                raise MuxError('Partial serial write; outcome unknown')
        except Exception as exc:
            self.fail(exc)
            raise

    def request(self, op, payload=b'', *, deadline=None):
        with self._commands, self._condition:
            self._check()
            self._request_waiting = True
            try:
                while self._pending:
                    self._wait(deadline)
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError('Memory capture deadline expired before command delivery')
                self._send(op, payload)
            finally:
                self._request_waiting = False
            while self._pending:
                self._wait(deadline)
            self._check()
            answer = self._reply
            self._reply = None
            if not answer:
                raise MuxError('Empty command response')
            if answer[0] in (3, 4):
                self.fail('Claim expired or request duplicated; reconnect explicitly')
                self._check()
            if answer[0]:
                raise MuxTargetError(answer[0], op)
            return answer[1:]

    def _wait(self, deadline=None):
        self._check()
        limit = self._pending[2] if deadline is None else min(self._pending[2], deadline)
        remaining = limit-time.monotonic()
        if remaining <= 0:
            if limit < self._pending[2]:
                op, req, _, heartbeat = self._pending
                self._pending = (op, req, limit, heartbeat)
            self._expire_pending('command')
            self._check()
        self._condition.wait(min(remaining, .1))
        self._check()

    def handshake(self):
        caps = self.request(1)
        if len(caps) != 8 or struct.unpack_from('<I', caps)[0] & 3 != 3:
            raise MuxError('Firmware does not support multiplex target operations')
        self.capabilities = struct.unpack_from('<I', caps)[0]
        if self.request(4, self.nonce) != self.nonce:
            raise MuxError('Session claim mismatch')
        if self.capabilities & self.FAST_TRANSFER_CAPABILITY and not self.sleep_access:
            self.set_transfer_quantum(self.FAST_TRANSFER_BYTES)
        self.ready = True

    def set_transfer_quantum(self, quantum):
        """Negotiate bounded short frames; never expand limits on HELLO alone."""
        if type(quantum) is not int or quantum not in (128, self.FAST_TRANSFER_BYTES):
            raise ValueError('Transfer quantum must be 128 or 480')
        if not self.capabilities & self.FAST_TRANSFER_CAPABILITY:
            raise RuntimeError('Probe firmware lacks bounded fast-transfer support')
        with self._commands:
            self._pending_quantum = quantum
            try:
                self.request(0x25, struct.pack('<H', quantum))
            finally:
                self._pending_quantum = None

    def tick(self):
        """Called by the serial reader even when no bytes arrive."""
        with self._condition:
            if self._error:
                return
            if self._pending and time.monotonic() >= self._pending[2]:
                self._expire_pending('response')
            elif (self.ready and not self._pending and self._reply is None
                  and not self._request_waiting and time.monotonic()-self._last_command >= 1):
                # A delayed heartbeat reply must release the request slot to
                # an already waiting command, not immediately start another
                # heartbeat before the notified command thread can run.
                self._send(2, b'', heartbeat=True)

    def _expire_pending(self, source):
        """Keep the failed request identity; never replay uncertain operations."""
        op, request, deadline, heartbeat = self._pending
        now = time.monotonic()
        self._last_timeout = {
            'opcode': f'0x{op:02X}', 'request': request, 'epoch': self.epoch,
            'heartbeat': heartbeat, 'overdue_ms': round(max(0, now-deadline)*1000, 1),
            'last_receive_age_ms': None if self._last_receive is None else round((now-self._last_receive)*1000, 1),
            'last_reply_age_ms': None if self._last_reply is None else round((now-self._last_reply)*1000, 1),
            'buffered_bytes': len(self._rx),
        }
        self.fail(
            f'Multiplex {source} timed out; outcome unknown, no replay '
            f'(opcode=0x{op:02X}, request={request}, epoch={self.epoch}, '
            f'heartbeat={heartbeat}, overdue_ms={self._last_timeout["overdue_ms"]}, '
            f'last_receive_age_ms={self._last_timeout["last_receive_age_ms"]}, '
            f'buffered_bytes={len(self._rx)})'
        )

    def feed(self, data):
        with self._condition:
            if self._error:
                return
            if data:
                self._last_receive = time.monotonic()
            self._rx.extend(data)
            while True:
                at = self._rx.find(b'MLX1')
                if at < 0:
                    del self._rx[:-3]
                    return
                if at:
                    del self._rx[:at]
                if len(self._rx) < 16:
                    return
                _, version, op, n, epoch, req = struct.unpack_from('<4sBBHII', self._rx)
                limit = 1024 if op == 0x41 and self.capabilities & 8 else 256
                if op == 0x42:
                    if not self.capabilities & self.BULK_WATCH_CAPABILITY:
                        self.fail('Unnegotiated bulk sampling event')
                        self._rx.clear()
                        return
                    limit = 492  # 40-byte header plus 452 bytes, CRC-v1 frame <=512.
                if op == 0x96 and self.capabilities & self.BLOCK_READ_CAPABILITY:
                    limit = 4097  # Status plus one bounded block; CRC v1 only.
                if (self.capabilities & self.FAST_TRANSFER_CAPABILITY
                        and self.transfer_quantum == self.FAST_TRANSFER_BYTES):
                    if op == 0x40:
                        limit = 6 + self.FAST_TRANSFER_BYTES
                    elif op == 0x91:
                        limit = 1 + self.FAST_TRANSFER_BYTES
                # Version 2 is restricted to advertised Watch events. Commands,
                # replies and RTT retain their CRC-protected version 1 framing.
                watch_raw = version == 2 and op == 0x41 and bool(self.capabilities & 16)
                if (version != 1 and not watch_raw) or n > limit:
                    self.fail('Malformed multiplex frame')
                    self._rx.clear()
                    return
                frame_size = n + (16 if watch_raw else 20)
                if len(self._rx) < frame_size:
                    return
                raw = bytes(self._rx[:frame_size]); del self._rx[:frame_size]
                if not watch_raw and binascii.crc32(raw[:-4]) & 0xffffffff != struct.unpack_from('<I', raw, n+16)[0]:
                    self.fail('Multiplex CRC error; session requires explicit reconnect')
                    return
                payload = raw[16:16+n]
                if op & 0x80:
                    if not self._pending or (op & 0x7f, req) != self._pending[:2]:
                        self.fail('Unexpected multiplex response')
                        return
                    hello = self._pending[0] == 1
                    if not hello and epoch != self.epoch:
                        self.fail('Multiplex session expired; no automatic reconfiguration')
                        return
                    if hello:
                        self.epoch = epoch
                    if self._pending[0] == 4 and payload[:1] == b'\0':
                        self.transfer_quantum = 128  # Each claim starts compatible.
                    if self._pending[0] == 0x25 and payload[:1] == b'\0':
                        if payload != b'\0' or self._pending_quantum is None:
                            self.fail('Invalid transfer quantum ACK; outcome unknown, do not replay')
                            return
                        # ACK and first large event can share one USB read. Set
                        # the limit here before parsing the next frame, not in
                        # the requesting thread after request() returns.
                        self.transfer_quantum = self._pending_quantum
                    heartbeat = self._pending[3]
                    self._last_reply = time.monotonic()
                    self._reply = payload
                    if self._pending[0] == self.SOFTWARE_RESET_COMMAND and payload[:1] in (b'\0', b'\x05'):
                        # Mark the boundary before subsequent events arrive.
                        # Queued pre-reset samples keep their own generation.
                        self._reset_generation += 1
                    self._pending = None
                    if heartbeat and payload != b'\0':
                        self.fail('Heartbeat rejected')
                    if heartbeat:
                        self._reply = None
                    self._condition.notify_all()
                elif op in (0x40, 0x41, 0x42):
                    if epoch != self.epoch or len(payload) < (40 if op == 0x42 else 6):
                        self.fail('Invalid stream event')
                        return
                    if op != 0x42 and payload[0] >= (8 if op == 0x40 else 15):
                        self.fail('Invalid event channel')
                        return
                    if self._event_id is not None:
                        missing = (req-self._event_id-1) & 0xffffffff
                        self.event_gaps += missing
                        self._watch_wire_gap |= bool(missing)
                        self._bulk_wire_gap |= bool(missing)
                    self._event_id = req
                    if op == 0x40 and self._rtt_manager is not None:
                        self._rtt_manager.publish(payload)
                        self._condition.notify_all()
                        continue
                    key = (op, payload[0] if op == 0x40 else 255)
                    if op == 0x41:
                        payload = MuxWatchEvent(payload, self._reset_generation)
                        if self._watch_wire_gap:
                            payload.break_before = 2
                            self._watch_wire_gap = False
                    elif op == 0x42:
                        payload = MuxWatchEvent(payload, self._reset_generation)
                        if self._bulk_wire_gap:
                            payload.break_before = 2
                            self._bulk_wire_gap = False
                    queue = self._queues.setdefault(key, deque())
                    size = self._sizes.get(key, 0)
                    budget = self.WATCH_QUEUE_BYTES if op in (0x41, 0x42) else self.MAX_QUEUE_BYTES
                    lost = 0
                    while queue and size+len(payload) > budget:
                        removed = queue.popleft()
                        size -= len(removed)
                        self.dropped_bytes[key] = self.dropped_bytes.get(key, 0)+len(removed)-(40 if op == 0x42 else 6)
                        if op == 0x41:
                            # Carry the boundary with the first retained event,
                            # including when a previously marked event is evicted.
                            lost |= removed.break_before | (1 if removed[1] in (0, 5, 9) else 2)
                        elif op == 0x42:
                            lost |= removed.break_before | 1
                    if lost:
                        (queue[0] if queue else payload).break_before |= lost
                    queue.append(payload)
                    self._sizes[key] = size+len(payload)
                    self._condition.notify_all()

    def stats(self):
        with self._condition:
            return {'event_gaps': self.event_gaps,
                    'transfer_quantum': self.transfer_quantum,
                    'last_timeout': dict(self._last_timeout) if self._last_timeout else None,
                    'rtt_dropped_bytes': {ch: self.dropped_bytes.get((0x40, ch), 0) for ch in range(8)},
                    'watch_dropped_bytes': self.dropped_bytes.get((0x41, 255), 0),
                    'bulk_dropped_bytes': self.dropped_bytes.get((0x42, 255), 0)}

    def drain(self, op, channel, *, max_bytes=None):
        with self._condition:
            self._check()
            key = (op, channel)
            if max_bytes is None:
                frames = list(self._queues.pop(key, ()))
                self._sizes.pop(key, None)
                return frames
            if max_bytes <= 0:
                raise ValueError('Drain budget must be positive')
            queue = self._queues.get(key)
            frames = []
            used = 0
            while queue and (not frames or used+len(queue[0]) <= max_bytes):
                frame = queue.popleft()
                frames.append(frame)
                used += len(frame)
            if queue:
                self._sizes[key] -= used
            else:
                self._queues.pop(key, None)
                self._sizes.pop(key, None)
            return frames

    def read_memory(self, address, size, *, deadline=None):
        if not 0 <= address <= 0xffffffff or size < 0 or address+size > 0x100000000:
            raise ValueError('Invalid memory range')
        result = bytearray()
        block_read = bool(self.capabilities & self.BLOCK_READ_CAPABILITY)
        chunk_size = 32 if self.sleep_access else (4096 if block_read else self.transfer_quantum)
        command = self.BLOCK_READ_COMMAND if block_read else 0x11
        for offset in range(0, size, chunk_size):
            n = min(chunk_size, size-offset)
            payload = struct.pack('<IH', address+offset, n)
            data = (self.request(command, payload) if deadline is None
                    else self.request(command, payload, deadline=deadline))
            if len(data) != n:
                self.fail('Incomplete memory response')
                raise self._error
            result.extend(data)
        return bytes(result)

    def write_memory(self, address, data):
        if not 0 <= address <= 0xffffffff or address+len(data) > 0x100000000:
            raise ValueError('Invalid memory range')
        chunk_size = 32 if self.sleep_access else self.transfer_quantum
        for offset in range(0, len(data), chunk_size):
            self.request(0x12, struct.pack('<I', address+offset)+data[offset:offset+chunk_size])

    @property
    def supports_software_reset(self):
        return bool(self.capabilities & self.SOFTWARE_RESET_CAPABILITY)

    def software_reset(self):
        """Reset once in the existing session; event queues remain readable."""
        if not self.supports_software_reset:
            raise RuntimeError('Probe firmware does not support in-stream software reset; update the probe firmware')
        answer = self.request(self.SOFTWARE_RESET_COMMAND)
        if answer:
            self.fail('Invalid software reset response; outcome unknown, do not replay')
            self._check()

    def close(self):
        with self._commands:
            if self._error is None:
                self.request(3)
            self.ready = False

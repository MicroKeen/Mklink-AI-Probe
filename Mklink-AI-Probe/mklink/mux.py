"""Bounded V4 CDC multiplex transport, fed by the bridge's sole reader.

No serial handle or reader thread here. Target commands share one request slot;
an opted-in duplex transport can track bounded PINGs while a reply is delayed.
A timeout poisons the session and is never retried or converted into Pika source.
"""
from __future__ import annotations

from collections import deque
import binascii
import math
import secrets
import struct
import threading
import time
from mklink.connection_diagnostics import event, error_detail
from mklink.firmware_compatibility import FirmwareUpgradeRequired, upgrade_message


class MuxError(ConnectionError):
    pass


SLEEP_ACCESS_COMMAND = 0x17
SLEEP_COMMAND_TIMEOUT = 12.0
SLEEP_READ_MAX = 480
# Keep a write in a single 512-byte wire frame (20 header/CRC + 8 nonce + 7 parameters).
SLEEP_WRITE_MAX = 477
PROFILE_ATTACH_COMMAND = 0x18
PROFILE_ATTACH_CAPABILITY = 1 << 13
HARDWARE_ID_CAPABILITY = 1 << 14
SWD_IDENTITY_COMMAND = 0x19
PROFILE_MAX_STEPS = 16
PROFILE_STEP = struct.Struct('<BBHIII')
PROFILE_DIAGNOSTIC = struct.Struct('<BBBBI')
PROFILE_REASONS = ('success', 'format', 'DP initialization', 'AP read', 'AP value',
                   'AP write', 'AP write verification', 'memory read', 'memory value',
                   'AP binding', 'target or binding lost', 'TARGETID read', 'TARGETID mismatch')


def encode_attach_profile(profile):
    """Validate the complete recipe before sending any target operation."""
    if type(profile.mem_ap) is not int or not 0 <= profile.mem_ap <= 255:
        raise ValueError('Invalid profile memory AP')
    steps = profile.steps
    if not 1 <= len(steps) <= PROFILE_MAX_STEPS or steps[-1].kind not in (3, 4):
        raise ValueError('Profile requires 1–16 steps ending with MEM32_CHECK or MEM32_CAPTURE')
    encoded = bytearray(struct.pack('<BBBB', 1, profile.mem_ap, len(steps), 0))
    identified_aps = set()
    checking_memory = False
    for index, step in enumerate(steps):
        kind, ap, addr, mask, value = step.kind, step.ap, step.address, step.mask, step.value
        if (any(type(v) is not int for v in (kind, ap, addr, mask, value))
                or kind not in (1, 2, 3, 4, 5) or not 0 <= ap <= 255
                or not 0 <= addr <= 0xffffffff or addr % 4
                or not 0 < mask <= 0xffffffff or value < 0 or value & ~mask):
            raise ValueError(f'Invalid profile fields at step {index}')
        if kind == 5:
            if index != 0 or ap or addr:
                raise ValueError('DP_TARGETID_CHECK must be first with zero AP and address')
        elif kind in (3, 4):
            if ap != profile.mem_ap:
                raise ValueError(f'MEM32_CHECK must use the selected memory AP at step {index}')
            if kind == 4 and (index != len(steps) - 1 or value):
                raise ValueError('MEM32_CAPTURE must be last with zero value')
            checking_memory = True
        elif checking_memory:
            raise ValueError(f'AP operations must precede memory checks at step {index}')
        elif addr > 0xfc:
            raise ValueError(f'Invalid AP register offset at step {index}')
        elif kind == 1 and addr == 0xfc and mask == 0xffffffff:
            identified_aps.add(ap)
        elif kind == 2:
            if addr == 0xfc:
                raise ValueError(f'AP_UPDATE cannot modify the read-only AP IDR at step {index}')
            if ap not in identified_aps:
                raise ValueError(f'AP_UPDATE requires a preceding full AP IDR check at step {index}')
        encoded.extend(PROFILE_STEP.pack(kind, ap, 0, addr, mask, value))
    return bytes(encoded)


def sleep_rpc_timeout(size, *, write=False, verify=False):
    """Bound a bulk RPC by the number of acknowledged firmware commands it needs."""
    if type(size) is not int or not 1 <= size <= 4096:
        return 35
    chunk = SLEEP_WRITE_MAX if write else SLEEP_READ_MAX
    commands = (size + chunk - 1) // chunk
    if write and verify:
        commands += (size + SLEEP_READ_MAX - 1) // SLEEP_READ_MAX
    return max(35, commands * SLEEP_COMMAND_TIMEOUT + 5)


class MuxTargetError(RuntimeError):
    def __init__(self, status, op=None, payload=b"", *, response=b""):
        self.status = status
        self.op = op
        self.response = response
        if status == 1 and op in (0x10, 0x11, 0x12, 0x13, 0x15, 0x16, 0x17,
                                  0x20, 0x21, 0x22, 0x23, 0x24, 0x25,
                                  0x31, 0x32, 0x33, 0x34):
            message = upgrade_message('Requested host operation', f'MUX command 0x{op:02X} (status 1: unsupported)')
        elif status == 2:
            message = '探针未接受命令参数。请核对通道、地址和长度，以及上位机与探针固件的兼容性。Multiplex target status 2'
        elif status == 6:
            message = ('Multiplex target busy or access preparation incomplete (status 6); '
                       'debugger ownership is one possible cause, not confirmed by this status. '
                       'Retry explicitly when available; the request was not replayed')
        elif status == 5 and op in (0x11, 0x16):
            location = ''
            if len(payload) == 6:
                address, size = struct.unpack('<IH', payload)
                location = f' 0x{address:08X}（{size} 字节）'
            message = (f'读取目标内存{location}失败。请核对目标板供电、调试接口和对应 ELF 的地址，'
                       '再读取一个已知可读的 Flash 或 RAM 地址作对照。'
                       ' Multiplex target status 5; target access failed.')
        elif status == 5 and op == SLEEP_ACCESS_COMMAND:
            message = 'Sleep access or restoration of the original core state was not confirmed; submitted writes must not be replayed'
        elif status == 5:
            message = 'Multiplex target status 5; target access failed. Check target power and the debug connection.'
            if op not in (0x11, 0x13, 0x16):
                message += ' A submitted write or reset may have an unknown outcome.'
        else:
            message = f'Multiplex target status {status}; failed writes may have an unknown outcome'
        if op is not None:
            message += f' (opcode 0x{op:02X})'
        super().__init__(message)


def _profile_error_diagnostic(profile, status, response):
    if len(response) != PROFILE_DIAGNOSTIC.size:
        return None
    version, ap, step, reason, actual = PROFILE_DIAGNOSTIC.unpack(response)
    if version != 1 or (step != 0xff and step >= len(profile.steps)):
        return None
    if status == 2 and reason == 1 and actual == 0:
        if ap == profile.mem_ap or (ap == 0xff and step == 0xff):
            return step, reason, actual
    if status != 5 or ap != profile.mem_ap:
        return None
    if step == 0xff:
        return (step, reason, actual) if reason in (2, 9, 10) and actual == 0 else None
    # A step-specific reason must identify an operation that could produce it.
    step_kinds = {3: (1, 2), 4: (1,), 5: (2,), 6: (2,), 7: (3, 4), 8: (3,), 11: (5,), 12: (5,)}
    if profile.steps[step].kind not in step_kinds.get(reason, ()):
        return None
    if reason in (3, 7, 11) and actual != 0:
        return None
    return step, reason, actual


class MuxProfileError(MuxTargetError):
    def __init__(self, profile, status, response):
        super().__init__(status, PROFILE_ATTACH_COMMAND, response=response)
        step = reason = actual = None
        mismatch = None
        message = f'{profile.name} PROFILE_ATTACH failed (status {status})'
        diagnostic = _profile_error_diagnostic(profile, status, response)
        if diagnostic is not None:
            step, reason, actual = diagnostic
            message += f': step={step}, reason={reason} ({PROFILE_REASONS[reason]}), actual=0x{actual:08X}'
            if reason == 8:
                from mklink.s32k3 import midr1_model_mismatch
                mismatch = midr1_model_mismatch(profile, profile.steps[step], actual)
                if mismatch:
                    message = mismatch['message'] + ' ' + message
        elif response or status in (2, 5):
            message += f': missing or invalid diagnostic ({response.hex()})'
        if status == 1:
            message += ' ' + upgrade_message('Profile-based SWD attach', 'MUX command 0x18 (status 1: unsupported)')
        elif status in (3, 4):
            message += (': epoch/nonce or claim invalid' if status == 3 else ': request ID duplicated or out of order')
            message += '; reconnect explicitly, do not replay the profile'
        elif status == 6:
            message += ': target busy; check for active capture or external debugger ownership before reconnecting explicitly'
        elif status == 5:
            through_failure = profile.steps if step in (None, 0xff) else profile.steps[:step + 1]
            if reason == 5:
                message += '; submitted AP write outcome unknown, do not replay the profile'
            elif reason not in (2, 10) and any(s.kind == 2 for s in through_failure):
                message += '; previously submitted AP writes may have taken effect, do not replay the profile'
        self.args = (message,)
        self.detail = dict(code='mux_profile_attach_failed', message=message, profile=profile.name,
                           status=status, mem_ap=profile.mem_ap, step=step, reason=reason,
                           actual=actual, response_hex=response.hex())
        if mismatch:
            self.detail['model_mismatch'] = mismatch
        if status == 1:
            self.detail.update(code='firmware_upgrade_required', action='upgrade_probe_firmware',
                               feature='Profile-based SWD attach', required='MUX command 0x18')

    def record_selection_sources(self, sources):
        if sources and 'model_mismatch' in self.detail:
            self.detail['model_mismatch']['selection_sources'] = sources
            message = self.detail['message'] + ' 本次配置来源为 ' + '、'.join(sources) + '。'
            self.args = (message,)
            self.detail['message'] = message


class MuxWatchEvent(bytes):
    """Local reset generation accompanies queued wire bytes, without loss."""
    def __new__(cls, payload, reset_generation):
        value = super().__new__(cls, payload)
        value.reset_generation = reset_generation
        # 1: confirmed discarded/read-failed records; 2: wire continuity unknown.
        value.break_before = 0
        return value


def packet(op, epoch, request, payload=b''):
    limit = {0x12: 492, 0x24: 489, SLEEP_ACCESS_COMMAND: 15 + SLEEP_WRITE_MAX,
             PROFILE_ATTACH_COMMAND: 8 + 4 + PROFILE_MAX_STEPS * PROFILE_STEP.size,
             SLEEP_ACCESS_COMMAND | 0x80: 1 + SLEEP_READ_MAX}.get(op, 256)
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
    ATOMIC_SLEEP_CAPABILITY = 1 << 12
    SOFTWARE_RESET_CAPABILITY = 1 << 5
    SOFTWARE_RESET_COMMAND = 0x15
    MAX_QUEUE_BYTES = 65536
    # ~160 ms at 200k 4-byte samples/s (timestamp + value). RTT queues keep
    # their original limit; replies bypass event queues. Still drop oldest on
    # sustained overload, never block the sole USB reader or command replies.
    WATCH_QUEUE_BYTES = 262144

    def __init__(self, write, command_lock=None, *, diagnostic_context=None, command_timeout=3.0,
                 background_heartbeats=False):
        if (isinstance(command_timeout, bool) or not isinstance(command_timeout, (int, float))
                or not math.isfinite(command_timeout) or command_timeout <= 0):
            raise ValueError('MUX command timeout must be finite and positive')
        self._diagnostic_context = diagnostic_context or {}
        self.command_timeout = command_timeout
        self.background_heartbeats = background_heartbeats
        self._heartbeats = {}
        self._closing = False
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
        self.attach_profile = None
        self._profile_failed = False
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
            self.attach_profile = None
            self._condition.notify_all()

    def _check(self):
        if self._error:
            raise self._error

    def _send(self, op, payload, heartbeat=False, *, background=False):
        if op == SLEEP_ACCESS_COMMAND and not self.supports_atomic_sleep:
            raise ValueError(upgrade_message('Atomic Cortex-M sleep access', 'MUX HELLO 0x1000'))
        if self.sleep_access and self.supports_atomic_sleep and op in (0x20, 0x23, 0x32, 0x33, 0x34):
            raise RuntimeError('Asynchronous sampling is unavailable in atomic sleep access mode; disable sleep access to start a stream')
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
        timeout = self.command_timeout
        if op in (SLEEP_ACCESS_COMMAND, self.SOFTWARE_RESET_COMMAND) and self.supports_atomic_sleep:
            timeout = max(timeout, SLEEP_COMMAND_TIMEOUT)
        elif self.sleep_access:
            # A slow legacy WFI poll needs up to 4.8 s of the local 5 s lease.
            timeout = max(timeout, 4.8)
        deadline = time.monotonic() + timeout
        if background:
            self._heartbeats[req] = deadline
        else:
            self._pending = (op, req, deadline, heartbeat)
            self._reply = None
        self._last_command = time.monotonic()
        try:
            count = self._write(wire)
            if count is not None and count != len(wire):
                raise MuxError('Partial serial write; outcome unknown')
        except Exception as exc:
            self.fail(exc)
            raise

    def invalidate_target_binding(self):
        """Retire the target data while keeping the claimed USB transport usable for STOP/EXIT."""
        with self._condition:
            self.attach_profile = None
            self._profile_failed = True
            self._queues.clear()
            self._sizes.clear()
            self._condition.notify_all()

    def check_capture_binding(self):
        if self._profile_failed:
            raise MuxError('Target binding lost; stop capture and start again to verify the target')

    def request(self, op, payload=b'', *, deadline=None):
        with self._commands, self._condition:
            self._check()
            if self._profile_failed and op >= 0x10 and op not in (0x22, 0x31, 0x35):
                raise MuxError('Profile AP binding is unavailable; reconnect explicitly')
            if self.attach_profile is not None and op in (1, 4, 0x13, PROFILE_ATTACH_COMMAND):
                raise MuxError('Changing a profile AP binding requires an explicit reconnect')
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
                if op == PROFILE_ATTACH_COMMAND:
                    raise MuxTargetError(answer[0], op, payload, response=answer[1:])
                self._check()
            if answer[0]:
                error = MuxTargetError(answer[0], op, payload, response=answer[1:])
                if self._profile_failed and answer[0] == 5:
                    error.args = (str(error) + ' Profile AP binding is unconfirmed; reconnect explicitly.',)
                raise error
            return answer[1:]

    def bind_attach_profile(self, profile):
        """Bind the AP only after the firmware confirms every profile step."""
        with self._commands:
            self._check()
            if not self.ready or self._profile_failed or self.attach_profile is not None:
                raise MuxError('Profile attach requires a fresh HELLO/CLAIM')
            if not self.capabilities & PROFILE_ATTACH_CAPABILITY:
                self._profile_failed = True
                raise FirmwareUpgradeRequired('Profile-based SWD attach', 'MUX HELLO 0x2000')
            payload = encode_attach_profile(profile)
            capture = profile.steps[-1].kind == 4
            if (capture or profile.steps[0].kind == 5) and not self.capabilities & HARDWARE_ID_CAPABILITY:
                raise FirmwareUpgradeRequired('SWD hardware identification', 'MUX HELLO 0x4000')
            try:
                answer = self.request(PROFILE_ATTACH_COMMAND, payload)
                actual = int.from_bytes(answer[4:], 'little') if capture else 0
                if len(answer) != 8 or answer != PROFILE_DIAGNOSTIC.pack(1, profile.mem_ap, 0xff, 0, actual):
                    raise MuxError(f'Invalid PROFILE_ATTACH success response {answer.hex()}; '
                                   'binding unconfirmed, do not replay the profile')
            except MuxTargetError as error:
                self._profile_failed = True
                raise MuxProfileError(profile, error.status, error.response) from error
            except Exception:
                self._profile_failed = True
                raise
            with self._condition:
                self._check()
                self.attach_profile = profile
            return actual if capture else None

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
        if len(caps) != 8:
            raise MuxError('Invalid MUX HELLO response; firmware capabilities are unconfirmed')
        if struct.unpack_from('<I', caps)[0] & 3 != 3:
            raise MuxError(upgrade_message('Multiplex target operations', 'MUX HELLO 0x3'))
        self.capabilities = struct.unpack_from('<I', caps)[0]
        if self.request(4, self.nonce) != self.nonce:
            raise MuxError('Session claim mismatch')
        if self.capabilities & self.FAST_TRANSFER_CAPABILITY and (not self.sleep_access or self.supports_atomic_sleep):
            self.set_transfer_quantum(self.FAST_TRANSFER_BYTES)
        self.ready = True

    def set_transfer_quantum(self, quantum):
        """Negotiate bounded short frames; never expand limits on HELLO alone."""
        if type(quantum) is not int or quantum not in (128, self.FAST_TRANSFER_BYTES):
            raise ValueError('Transfer quantum must be 128 or 480')
        if not self.capabilities & self.FAST_TRANSFER_CAPABILITY:
            raise RuntimeError(upgrade_message('Bounded fast transfers', 'MUX HELLO 0x100'))
        with self._commands:
            self._pending_quantum = quantum
            try:
                self.request(0x25, struct.pack('<H', quantum))
            finally:
                self._pending_quantum = None

    def tick(self):
        """Service deadlines from the reader or a duplex transport's timer."""
        with self._condition:
            if self._error:
                return
            if self._heartbeats and time.monotonic() >= next(iter(self._heartbeats.values())):
                self.fail('Multiplex heartbeat timed out; outcome unknown, no replay')
                return
            if self._pending and time.monotonic() >= self._pending[2]:
                self._expire_pending('response')
            elif self.ready and not self._closing and time.monotonic() - self._last_command >= 1:
                if self.background_heartbeats:
                    if len(self._heartbeats) >= 64:
                        self.fail('Multiplex heartbeat window full; outcome unknown, no replay')
                        return
                    self._send(2, b'', heartbeat=True, background=True)
                elif not self._pending and self._reply is None and not self._request_waiting:
                    # A queued target command gets the shared slot before a new PING.
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
                if op == (SLEEP_ACCESS_COMMAND | 0x80) and self.supports_atomic_sleep:
                    limit = 1 + SLEEP_READ_MAX
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
                    if req in self._heartbeats:
                        if op != 0x82 or epoch != self.epoch or payload != b'\0':
                            self.fail('Invalid multiplex heartbeat response; no replay')
                            return
                        del self._heartbeats[req]
                        self._last_reply = time.monotonic()
                        self._condition.notify_all()
                        continue
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
                    if self.attach_profile is not None and payload[:1] == b'\x05':
                        self.invalidate_target_binding()
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
                    status = payload[38] if op == 0x42 else payload[1]
                    if self.attach_profile is not None and status in (5, 7, 8):
                        self.invalidate_target_binding()
                    if self._profile_failed:
                        continue
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
            self.check_capture_binding()
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
        if self.sleep_access and self.supports_atomic_sleep:
            return self.read_atomic_memory(address, size, deadline=deadline)
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
        if self.sleep_access and self.supports_atomic_sleep:
            raise ValueError('Atomic sleep writes require a validated target RAM range')
        if not 0 <= address <= 0xffffffff or address+len(data) > 0x100000000:
            raise ValueError('Invalid memory range')
        chunk_size = 32 if self.sleep_access else self.transfer_quantum
        for offset in range(0, len(data), chunk_size):
            self.request(0x12, struct.pack('<I', address+offset)+data[offset:offset+chunk_size])

    @property
    def supports_atomic_sleep(self):
        return bool(self.capabilities & self.ATOMIC_SLEEP_CAPABILITY)

    def _sleep_transfer(self, kind, address, size, expected, data=b'', *, deadline=None):
        if not self.supports_atomic_sleep:
            raise ValueError(upgrade_message('Atomic Cortex-M sleep access', 'MUX HELLO 0x1000'))
        answer = self.request(SLEEP_ACCESS_COMMAND, struct.pack('<BIH', kind, address, size) + data,
                              deadline=deadline)
        if len(answer) != expected:
            self.fail('Invalid sleep access response; operation or core state is unconfirmed, do not replay')
            self._check()
        return answer

    def probe_sleep_core(self):
        return int.from_bytes(self._sleep_transfer(2, 0, 0, 4), 'little')

    def read_atomic_memory(self, address, size, *, deadline=None):
        if not 0 <= address <= 0xffffffff or size < 0 or address + size > 0x100000000:
            raise ValueError('Invalid sleep read range')
        result = bytearray()
        for offset in range(0, size, SLEEP_READ_MAX):
            n = min(SLEEP_READ_MAX, size - offset)
            result.extend(self._sleep_transfer(0, address + offset, n, n, deadline=deadline))
        return bytes(result)

    def write_atomic_ram(self, address, data):
        # The device layer has validated the whole range before the first write.
        if not 0 <= address <= 0xffffffff or address + len(data) > 0x100000000:
            raise ValueError('Invalid sleep write range')
        for offset in range(0, len(data), SLEEP_WRITE_MAX):
            part = data[offset:offset + SLEEP_WRITE_MAX]
            self._sleep_transfer(1, address + offset, len(part), 0, part)

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
            with self._condition:
                self._closing = True
                if self.attach_profile is not None:
                    self._profile_failed = True
                    self.attach_profile = None
                while self._heartbeats and self._error is None:
                    self.tick()
                    if self._error is None:
                        self._condition.wait(.1)
            if self._error is None:
                self.request(3)
            self.ready = False

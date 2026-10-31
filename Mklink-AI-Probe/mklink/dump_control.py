"""Separate legacy dump control replies from CRC-protected OLD/B1 samples."""
from __future__ import annotations

import binascii
import struct
import time

from ._types import DeviceState, MKLINK_IDENTITY_COMMAND, MKLINK_IDENTITY_TOKEN
from .dump_memory import MAGIC, OLD_HEADER_LEN, MIN_OLD_FRAME_LEN, MAX_FRAME_LEN

STOP_TIMEOUT = 2.0  # Firmware: 500 ms producer stop + up to 250 ms ACK queueing.
QUIET_PERIOD = 0.05


class DumpControlDecoder:
    """Emit ordered text/frame events, never recognizing tokens inside samples."""
    def __init__(self):
        self.pending = bytearray()

    def feed(self, data):
        self.pending.extend(data)
        while self.pending:
            if self.pending.startswith(MAGIC):
                if len(self.pending) < OLD_HEADER_LEN:
                    return
                length = struct.unpack_from('<H', self.pending, 16)[0]
                if not MIN_OLD_FRAME_LEN <= length <= MAX_FRAME_LEN:
                    raise RuntimeError('Invalid dump frame length during stop')
                if len(self.pending) < length:
                    return
                frame = bytes(self.pending[:length])
                if binascii.crc32(frame[:-4]) & 0xffffffff != struct.unpack_from('<I', frame, length - 4)[0]:
                    raise RuntimeError('Invalid dump frame CRC during stop')
                del self.pending[:length]
                yield 'frame', b''
                continue
            index = self.pending.find(MAGIC)
            if index < 0:
                keep = next((n for n in range(min(len(self.pending), len(MAGIC)-1), 0, -1)
                             if self.pending.endswith(MAGIC[:n])), 0)
                index = len(self.pending) - keep
            if not index:
                return
            text = bytes(self.pending[:index])
            del self.pending[:index]
            yield 'text', text


def stop_dump_and_sync(bridge, command: bytes, prefix: bytes = b'') -> bool:
    """One stop, a clean stop reply, then one identity reply and a quiet tail.

    New firmware must ACK DUMP_STOPPED. Legacy firmware must return an error-free
    prompt and stop producing frames; identity alone is never a stop receipt.
    Keep the sole reader in raw mode until this whole exchange is complete.
    """
    bridge.last_stream_stop_error = None
    decoder = DumpControlDecoder()
    text = bytearray()
    require_ack = 'DUMP_STOP=1' in (getattr(bridge, '_firmware_capabilities', None) or ())
    ack = stop_seen = identity_sent = identity_seen = False
    quiet_since = None

    def consume(raw):
        nonlocal ack, stop_seen, identity_seen
        for kind, payload in decoder.feed(raw):
            if kind == 'frame':
                if stop_seen or ack:
                    raise RuntimeError('dump-memory still produced frames after its stop response')
                continue
            text.extend(payload)
            if len(text) > 16384:
                raise RuntimeError('Oversized dump stop control response')
            # Only raw control text is checked; frame payloads never reach here.
            from .memory_access import read_response_error
            complete_lines = bytes(text).rsplit(b'\n', 1)[0] if b'\n' in text else b''
            error = read_response_error(complete_lines.decode('utf-8', errors='replace'))
            if error:
                raise RuntimeError(error)
            if b'DUMP_STOPPED' in [line.strip() for line in text.split(b'\n')[:-1]]:
                ack = True
            while b'>>>' in text:
                index = text.index(b'>>>')
                reply = bytes(text[:index])
                del text[:index+3]
                error = read_response_error(reply.decode('utf-8', errors='replace'))
                if error:
                    raise RuntimeError(error)
                lines = [line.strip() for line in reply.splitlines()]
                ack = ack or b'DUMP_STOPPED' in lines
                if not stop_seen:
                    if require_ack and not ack:
                        # A delayed start prompt is not a stop acknowledgement.
                        continue
                    stop_seen = True
                elif identity_sent and MKLINK_IDENTITY_TOKEN.encode('ascii') in lines:
                    identity_seen = True

    try:
        if bridge._transport_error is not None:
            raise ConnectionError('Serial transport failed before dump stop')
        bridge._cancel_stream_arm()
        bridge._utf8_decoder.reset()
        bridge._ctx.state = DeviceState.DUMP_STREAM
        # Preserve a partial frame already consumed by the sample parser.
        consume(prefix)
        bridge._serial.write(command)
        deadline = time.monotonic() + STOP_TIMEOUT
        while time.monotonic() < deadline:
            if bridge._transport_error is not None:
                raise ConnectionError('Serial transport failed during dump stop')
            raw = bridge.drain_stream_bytes(max_bytes=262144)
            if raw:
                consume(raw)
                quiet_since = None
            if stop_seen and not identity_sent:
                identity_sent = True
                bridge._serial.write((MKLINK_IDENTITY_COMMAND + '\n').encode('ascii'))
            if identity_seen and not decoder.pending and not text.strip():
                now = time.monotonic()
                if quiet_since is None:
                    quiet_since = now
                elif now - quiet_since >= QUIET_PERIOD:
                    # Do not discard bytes arriving between the final drain and
                    # the mode switch. A nonempty tail needs another iteration.
                    with bridge._buffer_lock:
                        if bridge._response_buffer:
                            continue
                        bridge._prompt_event.clear()
                        bridge._ctx.state = DeviceState.READY
                    bridge._utf8_decoder.reset()
                    return True
            time.sleep(.001)
        needed = 'DUMP_STOPPED, prompt and identity' if require_ack else 'clean stop, identity and quiet stream'
        raise TimeoutError('dump-memory stop unconfirmed; expected ' + needed)
    except Exception as error:
        bridge.last_stream_stop_error = str(error)
        bridge._ctx.state = DeviceState.ERROR
        return False

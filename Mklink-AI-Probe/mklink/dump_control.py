"""Separate legacy dump control replies from CRC-protected OLD/B1 samples."""
from __future__ import annotations

import binascii
import struct

from .dump_memory import MAGIC, OLD_HEADER_LEN, MIN_OLD_FRAME_LEN, MAX_FRAME_LEN



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

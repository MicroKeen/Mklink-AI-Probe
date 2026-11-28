"""One append-only capture with independently readable blocks and a seek index."""
import json
import struct
import time
import zlib


MAGIC = b'MKLOG1 '
TRAILER = b'MKIDX1\r\n'
BLOCK = struct.Struct('<II')
TAIL = struct.Struct('<Q8s')
MAX_BLOCK = 1024 * 1024


def encoded(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


class RecordingFile:
    def __init__(self, path, kind, *, block_bytes=256 * 1024, block_rows=2048):
        self.path = path
        self.stream = path.open('xb')
        self.kind = kind
        self.block_bytes = min(block_bytes, MAX_BLOCK)
        self.block_rows = block_rows
        self.index = []
        self.payload = bytearray()
        self.count = 0
        self.tracks = {}
        self.gap = 0
        self.loss = False
        self.start = self.end = None
        self.flushed = time.monotonic()
        try:
            self.stream.write(MAGIC + kind.encode('ascii') + b'\n')
            self.stream.flush()
        except BaseException:
            self.stream.close()
            raise

    def append(self, line, stamp, *, values=None, source=None, gap=0, lost=False, new_layout=False):
        if values is not None and self.end is not None and stamp < self.end:
            raise ValueError('SuperWatch sample timestamps moved backwards')
        if len(line) > MAX_BLOCK:
            raise ValueError('Recording row exceeds 1 MiB')
        if self.count and (gap or new_layout or self.count >= self.block_rows
                           or len(self.payload) + len(line) > self.block_bytes
                           or time.monotonic() - self.flushed >= 2):
            self.flush_block()
        if not self.count:
            self.start = stamp
            self.gap = gap
        self.end = stamp
        self.loss |= lost
        self.payload.extend(line)
        self.count += 1
        if values is None:
            track = self.tracks.setdefault(source, [0, stamp, stamp])
            track[0] += 1
            track[2] = max(track[2], stamp)
        else:
            for name, value in values.items():
                if name == '_t':
                    continue
                track = self.tracks.get(name)
                if track is None:
                    self.tracks[name] = [1, stamp, value, stamp, value, stamp, value, stamp, value]
                else:
                    track[0] += 1
                    if value < track[4]:
                        track[3], track[4] = stamp, value
                    if value > track[6]:
                        track[5], track[6] = stamp, value
                    track[7], track[8] = stamp, value

    def flush_block(self):
        if not self.count:
            return
        description = dict(start=self.start, end=self.end, rows=self.count, tracks=self.tracks,
                           gap=self.gap, loss=self.loss)
        payload = self.payload
        if len(payload) >= 1024:
            compressed = zlib.compress(payload, level=1)
            if len(compressed) < len(payload):
                description['deflate_bytes'] = len(payload)
                payload = compressed
        meta = encoded(description)
        if len(meta) > MAX_BLOCK:
            raise ValueError('Recording block metadata exceeds 1 MiB')
        offset = self.stream.tell()
        length = len(payload)
        try:
            self.stream.write(BLOCK.pack(len(meta), length))
            self.stream.write(meta)
            self.stream.write(payload)
            self.stream.flush()
        except OSError:
            # A partially written block has no trustworthy end offset.
            self.stream.close()
            raise
        self.index.append((offset, len(meta), length, meta))
        self.payload.clear()
        self.count, self.gap, self.loss = 0, 0, False
        self.tracks = {}
        self.flushed = time.monotonic()

    def finish(self, error=''):
        try:
            self.flush_block()
            self.stream.write(BLOCK.pack(0, 0))
            index_at = self.stream.tell()
            self.stream.write(encoded({'complete': not error, 'blocks': len(self.index)}) + b'\n')
            for offset, size, length, metadata in self.index:
                self.stream.write(b'[%d,%d,%d,' % (offset, size, length) + metadata + b']\n')
            self.stream.write(TAIL.pack(index_at, TRAILER))
        finally:
            self.stream.close()
            self.index.clear()


def capture_blocks(path):
    """Iterate acquisition records for text and Excel export, one block at a time."""
    from mklink.work_files import open_log_file
    with open_log_file(path, 'rb') as stream:
        if stream.readline(32) not in (b'MKLOG1 superwatch\n', b'MKLOG1 serial\n', b'MKLOG1 rtt\n'):
            raise ValueError('Invalid recording header')
        while True:
            prefix = stream.read(BLOCK.size)
            if len(prefix) != BLOCK.size:
                raise ValueError('Incomplete recording block')
            size, length = BLOCK.unpack(prefix)
            if size == length == 0:
                break
            if not (0 < size <= MAX_BLOCK and 0 < length <= MAX_BLOCK):
                raise ValueError('Invalid recording block length')
            description = json.loads(stream.read(size))
            data = stream.read(length)
            if len(data) != length:
                raise ValueError('Truncated recording block')
            if 'deflate_bytes' in description:
                expected = description['deflate_bytes']
                if type(expected) is not int or not 0 < expected <= MAX_BLOCK:
                    raise ValueError('Invalid uncompressed block size')
                codec = zlib.decompressobj()
                data = codec.decompress(data, expected + 1)
                if len(data) != expected or not codec.eof or codec.unused_data:
                    raise ValueError('Incomplete compressed recording block')
            yield data


def capture_rows(path):
    for data in capture_blocks(path):
        for line in data.splitlines():
            yield json.loads(line)

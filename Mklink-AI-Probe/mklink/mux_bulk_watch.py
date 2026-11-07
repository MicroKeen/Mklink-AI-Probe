"""CRC-protected, bounded continuous bulk reads; never an atomic snapshot."""
import struct

from mklink.mux_watch import MuxWatchSession, MuxWatchCapacityError


HEADER = struct.Struct('<IIQQIIHHHBB')


class MuxBulkWatchSession:
    START, STOP, EVENT = 0x34, 0x35, 0x42
    CAPABILITY = 1 << 11

    def __init__(self, transport, regions, period, *, fastest=False):
        from mklink.dump_memory import validate_dump_regions
        validate_dump_regions(regions)
        self.total = sum(size for _, size in regions)
        if self.total > 4096:
            raise MuxWatchCapacityError('MUX bulk sampling supports at most 4096 bytes per complete sample')
        # Reuse the existing finite/fastest period validation without changing
        # its small-variable path or widening any requested address range.
        timing = MuxWatchSession(None, [(regions[0][0], 1)], period, fastest=fastest)
        self.period, self.fastest = timing.period, timing.fastest
        self.transport, self.regions = transport, regions
        self.stream_id = None
        self.timing = None
        self.samples = self.gaps = self.read_errors = 0
        self._pending = bytearray()
        self._metadata = None
        self._last_sample = 0
        self._last_end = None
        self._generation = None
        self._break_before = 0
        self._started = False

    def start(self):
        transport = self.transport
        if not transport.capabilities & self.CAPABILITY:
            raise RuntimeError('4096-byte continuous sampling requires MUX bulk capability 0x800; update probe firmware')
        with transport._commands:
            if transport.bulk_running:
                raise RuntimeError('Another bulk sampling subscription is active')
            stream_id = getattr(transport, '_next_bulk_id', 0) + 1
            if stream_id > 0xffffffff:
                raise RuntimeError('Bulk stream IDs exhausted; reconnect explicitly')
            transport._next_bulk_id = self.stream_id = stream_id
            transport.drain(self.EVENT, 255)
            body = struct.pack('<IIB', stream_id, self.period, len(self.regions))
            body += b''.join(struct.pack('<IH', address, size) for address, size in self.regions)
            answer = transport.request(self.START, body)
            transport.bulk_running = self._started = True
            try:
                if len(answer) != 16:
                    raise RuntimeError('Invalid MUX bulk START acknowledgement length')
                returned_id, accepted, total, chunk, hz = struct.unpack('<IIHHI', answer)
                if (returned_id != stream_id or accepted != self.period or total != self.total
                        or chunk != 452 or hz == 0):
                    raise RuntimeError('MUX bulk START acknowledgement does not match request')
            except RuntimeError:
                try:
                    self.stop()
                except Exception as error:
                    transport.fail(error)
                raise
            self.timing = {'protocol': 'mux', 'mode': 'bulk-fastest' if self.fastest else 'bulk-periodic',
                           'requested_period_us': self.period, 'accepted_period_us': accepted,
                           'timebase_hz': hz, 'stream_id': stream_id, 'max_chunk_bytes': chunk,
                           'atomic_snapshot': False}

    def read_frames(self, *, packed=False):
        result = []
        for event in self.transport.drain(self.EVENT, 255, max_bytes=16384):
            if len(event) < HEADER.size:
                raise RuntimeError('Truncated MUX bulk header')
            stream, sample, start, end, first_epoch, last_epoch, total, offset, length, status, flags = HEADER.unpack_from(event)
            if stream != self.stream_id:
                raise RuntimeError('Unexpected MUX bulk stream identity')
            if status:
                self._pending.clear()
                self.read_errors += 1
                raise RuntimeError(f'MUX bulk acquisition failed (status {status}); no partial sample returned')
            if (flags & ~7 or not 1 <= sample < 0xffffffff or total != self.total or not 1 <= length <= 452
                    or len(event) != HEADER.size + length or offset + length > total
                    or start > end or bool(flags & 1) != (offset == 0)
                    or bool(flags & 2) != (offset + length == total)
                    or bool(flags & 4) != (first_epoch != last_epoch)):
                raise RuntimeError('Invalid MUX bulk fragment metadata')
            generation = getattr(event, 'reset_generation', None)
            if self._pending and generation != self._generation:
                self._pending.clear()
                raise RuntimeError('Target reset interrupted MUX bulk sample')
            self._generation = generation
            boundary = getattr(event, 'break_before', 0)
            if boundary & 1:
                self.gaps += 1
                self._pending.clear()
                raise RuntimeError('MUX bulk receive queue discarded sample fragments')
            self._break_before |= boundary
            metadata = (sample, start, end, first_epoch, last_epoch, total)
            if offset == 0:
                if self._pending or sample != self._last_sample + 1:
                    self.gaps += 1
                    raise RuntimeError('MUX bulk sample sequence is incomplete')
                if self._last_end is not None and start < self._last_end:
                    raise RuntimeError('MUX bulk sample timestamps regressed')
                self._metadata = metadata
            if metadata != self._metadata or offset != len(self._pending):
                self.gaps += 1
                raise RuntimeError('MUX bulk fragment sequence/metadata mismatch')
            self._pending.extend(event[HEADER.size:])
            if not flags & 2:
                continue
            data = bytes(self._pending)
            self._pending.clear()
            regions, cursor = [], 0
            for index, (_, size) in enumerate(self.regions):
                regions.append((index, data[cursor:cursor + size]))
                cursor += size
            self._last_sample, self._last_end = sample, end
            self.samples += 1
            result.append({'format': 'mux', 'timestamp_us': start, 'flags': 0, 'regions': regions,
                           'break_before': self._break_before,
                           'acquisition': {'stream_id': stream, 'sample_id': sample, 'start_us': start,
                                           'end_us': end, 'dap_epoch_first': first_epoch,
                                           'dap_epoch_last': last_epoch, 'dap_intervened': bool(flags & 4),
                                           'atomic_snapshot': False}})
            self._break_before = 0
        return result

    def write(self, address, data, future):
        # Existing acknowledged MUX writes, never legacy SW01 or readback.
        return MuxWatchSession.write(self, address, data, future)

    def stop(self):
        if not self._started:
            return
        with self.transport._commands:
            answer = self.transport.request(self.STOP, struct.pack('<I', self.stream_id))
            if answer != struct.pack('<I', self.stream_id):
                self.transport.fail('Invalid MUX bulk STOP acknowledgement; outcome unknown')
                self.transport._check()
            self.transport.bulk_running = self._started = False

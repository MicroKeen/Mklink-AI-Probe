"""Adapt bounded multiplex watch events to the existing SuperWatch decoder."""
import math
import struct
import time
from typing import NamedTuple


class PackedWatchSample(NamedTuple):
    timestamp_us: int
    payload: bytes
    offset: int
    break_before: int = 0


class MuxWatchCapacityError(ValueError):
    """Configuration cannot fit the bounded multiplex sampler."""


class MuxWatchSession:
    REQUIRED_CAPABILITIES = (1 << 3) | (1 << 4) | (1 << 9) | (1 << 10)
    TIMING_V2_CAPABILITY = 1 << 9
    NARROW_BATCH_CAPABILITY = 1 << 10
    NARROW_BATCH_START = 0x33

    def __init__(self, transport, regions, period, *, fastest=False):
        from mklink.dump_memory import validate_dump_regions
        validate_dump_regions(regions)
        self.transport = transport
        self.regions = regions
        self.parts = [(index, address+offset, min(128, size-offset))
                      for index, (address, size) in enumerate(regions)
                      for offset in range(0, size, 128)]
        if not self.parts or len(self.parts) > 15:
            raise MuxWatchCapacityError('Multiplex watch allows 15 regions of at most 128 bytes; select fewer/smaller variables')
        self._batch_size = sum(n for _, _, n in self.parts)
        self._word_batch = 4 <= self._batch_size <= 64 and self._batch_size % 4 == 0
        if not math.isfinite(period) or period < 0:
            raise MuxWatchCapacityError('Multiplex watch period must be finite and nonnegative')
        if type(fastest) is not bool or (fastest and period != 0):
            raise MuxWatchCapacityError('Fastest sampling requires fastest=True and period=0')
        self.fastest = fastest
        self.timing = None
        self._narrow_batch = False
        self.period = max(1, math.ceil(period*1000000))
        if period == 0:
            # Keep the existing period=0 adapter for finite single reads.
            # Only the explicit, capability-gated mode sends zero on the wire.
            self.period = 0 if fastest else 2000
        if self.period > 60000000:
            raise MuxWatchCapacityError('Multiplex watch period exceeds 60 seconds')
        self._pending = []
        self._break_before = 0
        self._reset_generation = None
        self._last_clock = None
        self._clock_high = 0
        self.samples = 0
        self.gaps = 0
        self.read_errors = 0
        self._read_failure_since = None
        # A read error is not a transport disconnect. Allow subsequent scheduled
        # samples to recover, including slow configurations and batched delivery.
        self._read_failure_timeout = max(3.0, self.period / 1000000 * 3 + 0.5)

    def start(self):
        # DumpMemoryStreamSession validates capacity before opening transport.
        # Negotiate units only after the real firmware capabilities are known.
        capabilities = getattr(self.transport, 'capabilities', 0)
        if capabilities & self.REQUIRED_CAPABILITIES != self.REQUIRED_CAPABILITIES:
            raise RuntimeError('SuperWatch requires MUX sampling capabilities 0x618; update the probe firmware and host together')
        self.timing = None
        self._narrow_batch = False
        # Select before any target command. HELLO support alone must never
        # enable new event widths for an old/ordinary START subscription.
        narrow = bool(self.transport.capabilities & self.NARROW_BATCH_CAPABILITY
                      and len(self.parts) == 1 and self.parts[0][2] in (1, 2)
                      and self.parts[0][1] % self.parts[0][2] == 0)
        command = self.NARROW_BATCH_START if narrow else 0x32
        self.transport.drain(0x41, 255)
        body = struct.pack('<IB', self.period, len(self.parts))
        body += b''.join(struct.pack('<IB', address, size) for _, address, size in self.parts)
        with self.transport._commands:
            answer = self.transport.request(command, body)
            self.transport.watch_running = True
            contract = 'WATCH_NARROW_BATCH' if narrow else 'WATCH_TIMING=2'
            try:
                if not isinstance(answer, (bytes, bytearray)) or len(answer) != 8:
                    raise RuntimeError(f'Invalid {contract} START acknowledgement length')
                accepted, timebase_hz = struct.unpack('<II', answer)
                if accepted != self.period or timebase_hz == 0:
                    raise RuntimeError(f'{contract} START acknowledgement does not match requested period/timebase')
            except RuntimeError as error:
                # The command succeeded but its timing contract is invalid.
                # Stop this subscription once; never replay START or use REPL.
                try:
                    self.stop()
                except Exception as stop_error:
                    self.transport.fail(stop_error)
                    raise RuntimeError(f'{error}; stopping the unconfirmed capture failed: {stop_error}') from error
                raise
            self.timing = {
                'mode': 'fastest' if self.fastest else 'periodic',
                'requested_period_us': self.period,
                'accepted_period_us': accepted,
                'timebase_hz': timebase_hz,
            }
            self._narrow_batch = narrow

    def read_frames(self, *, packed=False):
        result = []
        now = time.monotonic()
        # Keep decoding/publication bursts below the bounded RX queue's time
        # budget. Draining 64 KiB expands into thousands of Python sample
        # objects and can stall the next drain long enough to overflow it.
        for event in self.transport.drain(0x41, 255, max_bytes=16384):
            boundary = getattr(event, 'break_before', 0)
            if boundary:
                self._pending = []
                self._break_before |= boundary
            generation = getattr(event, 'reset_generation', None)
            if generation != self._reset_generation:
                self._pending = []
                self._read_failure_since = None
                self._reset_generation = generation
            if len(event) < 6:
                raise RuntimeError('Invalid multiplex watch event')
            index, status = event[:2]
            if status == 7:
                self._pending = []
                self._narrow_batch = False
                raise RuntimeError('DAP changed the target; SuperWatch capture was invalidated. Restart capture after debugging.')
            if status == 8:
                self._pending = []
                self._narrow_batch = False
                self.gaps += 1
                raise RuntimeError('MCU reset recovery timed out; SuperWatch could not read the target within 5 seconds. The reset was not repeated.')
            if status == 5:
                if len(event) != 6 or index >= len(self.parts):
                    raise RuntimeError('Invalid multiplex watch read-error event')
                self._pending = []
                self.gaps += 1
                self.read_errors += 1
                self._break_before |= 1
                if self._read_failure_since is None:
                    self._read_failure_since = now
                # Firmware retains the subscription. Do not replay commands,
                # reset the target, lower its clock or publish stale/zero values.
                continue
            if status and status != 9:
                self._pending = []
                self.gaps += 1
                raise RuntimeError(f'SuperWatch target read failed (status {status}); capture stopped. Check the target connection and sampling debug speed before restarting.')
            if status == 9:
                size = self._batch_size
                stride = 4+size
                if (len(event) < 4 or event[0] or not (self._word_batch or self._narrow_batch)
                        or event[3] != size or not 1 <= event[2] <= min(127, 1020//stride)
                        or len(event) != 4+stride*event[2]):
                    raise RuntimeError('Invalid multiplex watch batch')
                self._pending = []
                self._read_failure_since = None
                for offset in range(4, len(event), stride):
                    timestamp = struct.unpack_from('<I', event, offset)[0]
                    if packed:
                        result.append(PackedWatchSample(self._timestamp(timestamp), event, offset+4, self._take_break()))
                        continue
                    cursor = offset+4
                    regions = []
                    for index, (_, length) in enumerate(self.regions):
                        regions.append((index, event[cursor:cursor+length]))
                        cursor += length
                    result.append(self._frame(timestamp, regions))
                continue
            timestamp = struct.unpack_from('<I', event, 2)[0]
            if index == 0:
                if self._pending:
                    self.gaps += 1
                    self._break_before |= 1
                self._pending = []
            if index >= len(self.parts) or index != len(self._pending) or status or len(event)-6 != self.parts[index][2]:
                self._pending = []
                self.gaps += 1
                self._break_before |= 1
                continue
            self._pending.append(event[6:])
            if len(self._pending) != len(self.parts):
                continue
            regions = [bytearray() for _ in self.regions]
            for (logical, _, _), data in zip(self.parts, self._pending):
                regions[logical].extend(data)
            self._pending = []
            self._read_failure_since = None
            result.append(self._frame(timestamp, [(i, bytes(data)) for i, data in enumerate(regions)]))
        if (self._read_failure_since is not None
                and now - self._read_failure_since >= self._read_failure_timeout
                and not result):
            raise RuntimeError(
                f'SuperWatch target read failed continuously (status 5); '
                f'no valid sample for {self._read_failure_timeout:g}s. Capture stopped; '
                'check the target connection, selected addresses and sampling debug speed.'
            )
        return result

    def _frame(self, timestamp, regions):
        return {'format': 'mux', 'timestamp_us': self._timestamp(timestamp),
                'flags': 0, 'regions': regions, 'break_before': self._take_break()}

    def _take_break(self):
        boundary = self._break_before
        self._break_before = 0
        return boundary

    def _timestamp(self, timestamp):
        if self._last_clock is not None and timestamp < self._last_clock:
            self._clock_high += 1 << 32
        self._last_clock = timestamp
        self.samples += 1
        return timestamp+self._clock_high

    def write(self, address, data, future):
        try:
            self.transport.write_memory(address, data)
            # A running target may immediately change the value. The write ACK
            # completes this operation; do not add a read or replay the write.
            future.set_result({'data': data, 'acknowledged': True, 'verified': False,
                               'mode': 'cdc-mux', 'timestamp_us': None})
        except Exception as exc:
            future.set_exception(exc)
            raise

    def stop(self):
        with self.transport._commands:
            self.transport.request(0x31)
            self.transport.watch_running = False
            self._narrow_batch = False

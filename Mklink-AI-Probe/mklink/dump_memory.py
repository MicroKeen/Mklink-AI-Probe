"""Default MUX capture with explicitly selected legacy Dump Memory support.

Implements the streaming binary frame parser for both OLD and B1 (chunked)
frame formats defined in the dump_memory protocol specification.

Frame formats (per firmware spec, 2026-06-06):

  OLD (total_size <= 2048):
    +0x00  8B magic           "MPMDMPMD"
    +0x08  8B timestamp_us
    +0x10  2B frame_length
    +0x12  1B region_count
    +0x13  ... region[i] = idx(1) + size(2) + data(size)
    +EOF-6 2B flags
    +EOF-4 4B crc32

  B1 (total_size > 2048, chunked):
    +0x00  8B magic           "MPMDMPMD"
    +0x08  8B timestamp_us
    +0x10  2B frame_length
    +0x12  1B region_count
    +0x13  2B flags
    +0x15  4B total_size
    +0x19  2B block_size      (firmware: fixed 2048)
    +0x1B  2B block_index
    +0x1D  2B block_count
    +0x1F  4B block_crc32     (crc32 of region data payload)
    +0x23  ... region[i] = idx(1) + size(2) + data(size)
    +EOF-4 4B crc32            (crc32 of magic..last region data byte)

These formats serve offline records and explicit ``protocol='dmpm'`` capture.
Live helpers default to MUX, accepting an existing shared bridge; they never
fall back to the legacy protocol after a failed or unsupported MUX operation.
"""

from __future__ import annotations

import secrets

import binascii
import struct
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

# Protocol envelope; the manager additionally intersects HPM ranges with the
# target's writable ELF/profile RAM. Never infer an exact chip from JTAG ID.
ARM_WRITE_RANGES = ((0x20000000, 0x40000000),)
HPM_WRITE_RANGES = (
    (0x00000000, 0x00040000), (0x00200000, 0x00240000),
    (0x01200000, 0x012C0000), (0x012FC000, 0x01300000),
    (0xF0200000, 0xF0208000),
)

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------
MAGIC = b'\x4D\x50\x4D\x44\x4D\x50\x4D\x44'   # "MPMDMPMD"
MAGIC_LEN = 8

# OLD frame header: magic(8) + ts(8) + frame_length(2) + region_count(1) = 19
OLD_HEADER_LEN = 19
OLD_TRAILER_LEN = 6  # flags(2) + crc32(4)
MIN_OLD_FRAME_LEN = OLD_HEADER_LEN + 3 + OLD_TRAILER_LEN  # 1 region(3) + 6 = 28

# B1 frame header: OLD_HEADER + flags(2) + total_size(4) + block_size(2) +
#                  block_index(2) + block_count(2) + block_crc32(4) = 35
B1_HEADER_LEN = 35
B1_TRAILER_LEN = 4  # crc32(4)
MIN_B1_FRAME_LEN = B1_HEADER_LEN + 3 + B1_TRAILER_LEN  # 1 region(3) + 4 = 42

MAX_FRAME_LEN = 65535
MAX_REGIONS = 16
# Current MUX sampling has 15 physical region slots (each at most 128 bytes).
MAX_SAMPLING_REGIONS = 15
EXPECTED_BLOCK_SIZE = 2048  # firmware-fixed per spec

# Bounded finite-capture result size, independent of MUX sampling capacity.
MAX_TOTAL_DATA_SIZE = 512 * 1024  # 524288

_DUMP_MEMORY_CAPTURE_LOCK = threading.RLock()


# FLAGS bit masks
FLAG_TICK_OVERFLOW    = 0x0001
FLAG_TIMING_VIOLATION = 0x0002
FLAG_REGION_ERROR     = 0x0004
FLAG_SAMPLE_DROPPED   = 0x0008


class DumpMemoryReadError(RuntimeError):
    """The dump stream returned a malformed or explicitly failed sample."""

    def __init__(
        self,
        message: str,
        *,
        gap_fact: str = "invalid_block_count",
        gap_count: int = 1,
    ) -> None:
        super().__init__(message)
        self.gap_fact = gap_fact
        self.gap_count = max(1, int(gap_count))


class DumpMemoryUnsupported(DumpMemoryReadError):
    """The connected firmware cannot supply current MUX capture operations."""


class DumpMemoryBusyError(RuntimeError):
    """Another bridge stream currently owns the connected probe."""


@contextmanager
def exclusive_dump_memory_capture() -> Iterator[None]:
    """Serialize dump captures in this process, including multi-sample calls."""
    with _DUMP_MEMORY_CAPTURE_LOCK:
        yield


def _require_memory_mux(bridge):
    """Select the current transport; never leave MUX or send a legacy dump."""
    from mklink._types import DeviceState
    state = getattr(bridge, 'state', DeviceState.READY)
    if state is not DeviceState.READY:
        raise DumpMemoryBusyError(f'memory capture requires an idle READY bridge; current state is {state.value}')
    supported = getattr(bridge, 'supports_multiplex', None)
    if not callable(supported) or supported() is not True:
        raise DumpMemoryUnsupported('Memory capture requires MUX firmware; update the probe firmware and host together')
    transport = bridge.enable_multiplex()
    if transport is None:
        raise DumpMemoryUnsupported('Memory capture requires MUX firmware; update the probe firmware and host together')
    return transport


# Sentinel return values for _try_parse
_NEED_MORE = object()
_RETRY = object()


class DumpStartupEcho:
    """Remove one exact generated command echo, only at stream startup.

    Keep arbitrary preambles, later echoes and all damaged bytes observable.
    Candidate buffering is bounded by the generated REPL command length.
    """
    def __init__(self, command: str):
        echo = command.encode('ascii')
        self.candidates = tuple(sorted({
            echo + ending + separator + prompt
            for ending in (b'\n', b'\r\n')
            for separator in (b'', b'\n', b'\r\n')
            for prompt in (b'', b'>>>', b'>>> ')
        }, key=len, reverse=True))
        self.pending = bytearray()
        self.control_bytes = 0
        self.done = False

    def feed(self, data: bytes) -> bytes:
        if self.done:
            return data
        self.pending.extend(data)
        raw = bytes(self.pending)
        if any(candidate.startswith(raw) for candidate in self.candidates):
            return b''
        prefix = next((candidate for candidate in self.candidates if raw.startswith(candidate)), b'')
        self.control_bytes = len(prefix)
        self.pending.clear()
        self.done = True
        return raw[len(prefix):]


class DumpMemoryParser:
    """Streaming binary parser for dump_memory frames (OLD + B1).

    Follows the same feed() -> list[dict] pattern as JustFloatParser
    and JScopeBinaryParser.

    Each returned frame dict has:
        "timestamp_us": int
        "format":       "OLD" or "B1"
        "regions":      list[(region_index, bytes)]
        "flags":        int
        # B1-only fields (absent for OLD):
        "total_size":   int
        "block_size":   int
        "block_index":  int
        "block_count":  int
        "block_crc32":  int   (crc32 of region data payload)
        "block_crc_ok": bool  (B1 region data payload CRC result)
    """

    def __init__(self, region_sizes: list[int] | None = None, *, startup_command: str | None = None):
        self._buf = bytearray()
        self._startup = DumpStartupEcho(startup_command) if startup_command else None
        self._region_sizes = region_sizes or []
        self._expected_count = len(self._region_sizes)
        self._dropped_bytes: int = 0
        self._dropped_frames: int = 0
        self._crc_errors: int = 0

    @property
    def dropped_bytes(self) -> int:
        return self._dropped_bytes

    @property
    def dropped_frames(self) -> int:
        return self._dropped_frames

    @property
    def crc_errors(self) -> int:
        return self._crc_errors

    @property
    def startup_control_bytes(self) -> int:
        return self._startup.control_bytes if self._startup else 0

    @property
    def pending_bytes(self) -> bytes:
        return bytes(self._startup.pending if self._startup else b'') + bytes(self._buf)

    def feed(self, data: bytes) -> list[dict]:
        """Feed raw bytes, return list of parsed frame dicts."""
        if self._startup:
            data = self._startup.feed(data)
        self._buf.extend(data)
        frames: list[dict] = []
        while True:
            result = self._try_parse()
            if result is _NEED_MORE:
                break
            if result is not _RETRY:
                frames.append(result)
        return frames

    # ---- internal ---------------------------------------------------------

    def _try_parse(self):
        # Step 1: Find MAGIC
        idx = self._buf.find(MAGIC)
        if idx < 0:
            drop = len(self._buf) - MAGIC_LEN + 1
            if drop > 0:
                self._dropped_bytes += drop
                del self._buf[:drop]
            return _NEED_MORE

        if idx > 0:
            self._dropped_bytes += idx
            del self._buf[:idx]

        # Step 2: Need at least header bytes to read frame_length
        if len(self._buf) < OLD_HEADER_LEN:
            return _NEED_MORE

        frame_length = struct.unpack_from('<H', self._buf, 16)[0]
        if frame_length < MIN_OLD_FRAME_LEN or frame_length > MAX_FRAME_LEN:
            self._dropped_bytes += MAGIC_LEN
            self._dropped_frames += 1
            del self._buf[:MAGIC_LEN]
            return _RETRY

        if len(self._buf) < frame_length:
            return _NEED_MORE

        frame_bytes = bytes(self._buf[:frame_length])
        del self._buf[:frame_length]

        # Step 3: CRC32 check (trailing 4 bytes)
        payload = frame_bytes[:-4]
        expected_crc = struct.unpack('<I', frame_bytes[-4:])[0]
        actual_crc = binascii.crc32(payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            self._crc_errors += 1
            self._dropped_frames += 1
            return _RETRY

        # Step 4: Detect B1 vs OLD
        region_count = frame_bytes[18]

        if region_count == 0 and frame_length == 42 and frame_bytes[19] == 0x57:
            request_id, address, size, status = struct.unpack_from('<IIBB', frame_bytes, 20)
            return {"format": "WRITE_ACK", "timestamp_us": struct.unpack_from('<Q', frame_bytes, 8)[0],
                    "request_id": request_id, "address": address, "size": size,
                    "status": status, "data": frame_bytes[30:38][:size]}
        if self._looks_like_b1(frame_bytes, frame_length, region_count):
            return self._parse_b1(frame_bytes, frame_length)
        return self._parse_old(frame_bytes, frame_length, region_count)

    @staticmethod
    def _looks_like_b1(frame_bytes: bytes, frame_length: int, region_count: int) -> bool:
        """Heuristic: B1 frames have a recognisable B1 header before the regions.

        In a B1 frame:
          - frame_length >= MIN_B1_FRAME_LEN (42)
          - offset 0x13..0x14 = flags (2B, expected 0 unless error)
          - offset 0x15..0x18 = total_size (4B, 0 < x <= MAX)
          - offset 0x19..0x1A = block_size (2B, expect 2048)
          - offset 0x1B..0x1C = block_index (2B)
          - offset 0x1D..0x1E = block_count (2B)
        """
        if frame_length < MIN_B1_FRAME_LEN:
            return False
        if frame_length < B1_HEADER_LEN + 4:
            return False
        # B1 only triggers when total_size > 2048. Reading total_size at 0x15:
        total_size = struct.unpack_from('<I', frame_bytes, 0x15)[0]
        if total_size == 0 or total_size > MAX_TOTAL_DATA_SIZE:
            return False
        block_size = struct.unpack_from('<H', frame_bytes, 0x19)[0]
        if block_size != EXPECTED_BLOCK_SIZE:
            return False
        block_index = struct.unpack_from('<H', frame_bytes, 0x1B)[0]
        block_count = struct.unpack_from('<H', frame_bytes, 0x1D)[0]
        if block_count == 0 or block_index >= block_count:
            return False
        return True

    @staticmethod
    def _parse_b1(frame_bytes: bytes, frame_length: int) -> dict:
        timestamp_us = struct.unpack_from('<Q', frame_bytes, 8)[0]
        region_count = frame_bytes[18]
        flags = struct.unpack_from('<H', frame_bytes, 0x13)[0]
        total_size = struct.unpack_from('<I', frame_bytes, 0x15)[0]
        block_size = struct.unpack_from('<H', frame_bytes, 0x19)[0]
        block_index = struct.unpack_from('<H', frame_bytes, 0x1B)[0]
        block_count = struct.unpack_from('<H', frame_bytes, 0x1D)[0]
        block_crc32 = struct.unpack_from('<I', frame_bytes, 0x1F)[0]

        regions: list[tuple[int, bytes]] = []
        region_payload = bytearray()
        offset = B1_HEADER_LEN
        for _ in range(region_count):
            if offset + 3 > frame_length - 4:
                break
            region_index = frame_bytes[offset]
            region_size = struct.unpack_from('<H', frame_bytes, offset + 1)[0]
            offset += 3
            if offset + region_size > frame_length - 4:
                break
            region_data = frame_bytes[offset:offset + region_size]
            regions.append((region_index, region_data))
            region_payload.extend(region_data)
            offset += region_size

        actual_block_crc32 = binascii.crc32(bytes(region_payload)) & 0xFFFFFFFF

        return {
            "timestamp_us": timestamp_us,
            "format": "B1",
            "regions": regions,
            "flags": flags,
            "total_size": total_size,
            "block_size": block_size,
            "block_index": block_index,
            "block_count": block_count,
            "block_crc32": block_crc32,
            "block_crc_ok": actual_block_crc32 == block_crc32,
        }

    @staticmethod
    def _parse_old(frame_bytes: bytes, frame_length: int, region_count: int) -> dict:
        timestamp_us = struct.unpack_from('<Q', frame_bytes, 8)[0]
        # OLD frame: regions, then flags(2), then crc32(4)
        flags = struct.unpack_from('<H', frame_bytes, frame_length - 6)[0]

        regions: list[tuple[int, bytes]] = []
        offset = OLD_HEADER_LEN
        for _ in range(region_count):
            if offset + 3 > frame_length - 6:
                break
            region_index = frame_bytes[offset]
            region_size = struct.unpack_from('<H', frame_bytes, offset + 1)[0]
            offset += 3
            if offset + region_size > frame_length - 6:
                break
            regions.append((region_index, frame_bytes[offset:offset + region_size]))
            offset += region_size

        return {
            "timestamp_us": timestamp_us,
            "format": "OLD",
            "regions": regions,
            "flags": flags,
        }


# ---------------------------------------------------------------------------
# Configurable max total data size per dump_memory batch.
# Default = MAX_TOTAL_DATA_SIZE (32 KiB). Override with set_max_total_data_size
# only if the connected firmware has been confirmed to support a larger value.
# ---------------------------------------------------------------------------


def get_max_total_data_size() -> int:
    """Return current max total data size for dump_memory batches (bytes)."""
    return MAX_TOTAL_DATA_SIZE


def set_max_total_data_size(size: int) -> None:
    """Override the max total data size for dump_memory batches.

    Args:
        size: New max in bytes. Default is 512 KiB (firmware V4.3.3 validated).
              Must not exceed 512 KiB — that is the largest total validated to
              date (see docs/Mklink/2026-06-26-gd32f303-dump-flush-boundary-retest-report.md).
              Use this to *lower* the cap (e.g. on older firmware carrying BUG-5).
    """
    global MAX_TOTAL_DATA_SIZE
    if size > 512 * 1024:
        raise ValueError(
            f"size {size} exceeds the 512 KiB validated ceiling. "
            f"See docs/Mklink/2026-06-26-gd32f303-dump-flush-boundary-retest-report.md."
        )
    MAX_TOTAL_DATA_SIZE = size


def validate_dump_regions(region_pairs):
    """Validate finite memory ranges without generating a REPL command."""
    if not isinstance(region_pairs, (list, tuple)) or not 1 <= len(region_pairs) <= MAX_SAMPLING_REGIONS:
        raise ValueError(f'dump-memory supports at most {MAX_SAMPLING_REGIONS} regions and requires at least one')
    for index, pair in enumerate(region_pairs):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError(f'region_pairs[{index}] must be an (address, size) pair')
        address, size = pair
        if type(address) is not int or not 0 <= address <= 0xffffffff:
            raise ValueError(f'region_pairs[{index}] address is outside 32-bit range')
        if type(size) is not int or size <= 0:
            raise ValueError(f'region_pairs[{index}] size must be a positive integer')
        if address + size > 0x100000000:
            raise ValueError(f'region_pairs[{index}] exceeds the 32-bit address space')
    if sum(size for _, size in region_pairs) > MAX_TOTAL_DATA_SIZE:
        raise ValueError(f'Total region size exceeds maximum {MAX_TOTAL_DATA_SIZE} bytes')


def read_dump_memory_range_once(bridge, address, size, *, timeout=10.0, poll_interval=0.0005):
    """Read exact bytes using MUX memory commands; the API name is retained.

    poll_interval is retained for callers but MUX waits on response notification.
    Large requests are sequential reads, not an atomic target snapshot.
    """
    return read_dump_memory_regions_once(bridge, [(address, size)], timeout=timeout,
                                         poll_interval=poll_interval)[0]


def read_dump_memory_regions_once(
    bridge,
    region_pairs: list[tuple[int, int]],
    *,
    timeout: float = 10.0,
    poll_interval: float = 0.0005,
    cancelled=None,
) -> tuple[bytes, ...]:
    """Read one sample while holding the process-wide dump capture lock."""
    with exclusive_dump_memory_capture():
        return _read_dump_memory_regions_once_locked(
            bridge,
            region_pairs,
            timeout=timeout,
            poll_interval=poll_interval,
            cancelled=cancelled,
        )


class DumpSampleAssembler:
    """Validate and assemble exactly one OLD/B1 sample; never return partial bytes."""

    def __init__(self, region_sizes, *, ordered=False):
        self.ordered = ordered
        self.timestamp_us = None
        self._last_timestamp_us = None
        self.region_sizes = list(region_sizes)
        self.total_size = sum(region_sizes)
        self.blocks = {}
        self.expected_blocks = None
        self.expected_block_size = None
        self.incomplete_region_count = 0

    def feed(self, frame):
        # A terminal target-change frame may interrupt a partial B1 sample.
        # Report it before sequence/coverage checks; never join epochs.
        if int(frame.get("flags", 0)) & 0x10:
            raise DumpMemoryReadError(
                "Dump invalidated by DAP target change; start a new capture",
                gap_fact="firmware_error_count",
            )
        if self.ordered:
            timestamp = frame.get('timestamp_us')
            if type(timestamp) is not int or timestamp < 0:
                raise DumpMemoryReadError('Invalid sample timestamp', gap_fact='invalid_block_count')
            if self._last_timestamp_us is not None and timestamp < self._last_timestamp_us:
                raise DumpMemoryReadError('Dump block timestamp regressed', gap_fact='invalid_block_count')
            if frame.get('format') == 'B1' and frame.get('block_index') != len(self.blocks):
                raise DumpMemoryReadError('Periodic dump lost block sequence', gap_fact='missing_block_count')
            if self.blocks and frame.get('format') != 'B1':
                raise DumpMemoryReadError('Dump format changed within a sample', gap_fact='missing_block_count')
            if self.timestamp_us is None:
                self.timestamp_us = timestamp
            self._last_timestamp_us = timestamp
        flags = int(frame.get("flags", 0))
        if flags:
            raise DumpMemoryReadError(
                "dump_memory returned firmware error flags",
                gap_fact="firmware_error_count",
            )
        regions = frame.get("regions", ())
        by_region: dict[int, bytes] = {}
        valid_regions = True
        for region_index, payload in regions:
            if (
                type(region_index) is not int
                or not 0 <= region_index < len(self.region_sizes)
                or region_index in by_region
                or not isinstance(payload, (bytes, bytearray, memoryview))
            ):
                valid_regions = False
                break
            by_region[region_index] = bytes(payload)
        if not valid_regions:
            raise DumpMemoryReadError(
                "dump_memory region coverage is invalid",
                gap_fact="region_gap_count",
            )

        if frame.get("format") in ("OLD", "mux"):
            if len(by_region) != len(self.region_sizes):
                if self.ordered:
                    raise DumpMemoryReadError('Dump region coverage mismatch', gap_fact='region_gap_count')
                self.incomplete_region_count = max(
                    self.incomplete_region_count,
                    len(self.region_sizes) - len(by_region),
                )
                return None
            mismatched_regions = sum(
                len(by_region.get(index, b"")) != size
                for index, size in enumerate(self.region_sizes)
            )
            if mismatched_regions:
                if self.ordered:
                    raise DumpMemoryReadError('Dump region size mismatch', gap_fact='region_gap_count')
                self.incomplete_region_count = max(
                    self.incomplete_region_count,
                    mismatched_regions,
                )
                return None
            return tuple(by_region[index] for index in range(len(self.region_sizes)))

        if int(frame.get("total_size", 0)) != self.total_size:
            if self.ordered:
                raise DumpMemoryReadError('Dump sample size mismatch', gap_fact='region_gap_count')
            # The bridge may still contain a complete sample left by a
            # prior request; total size is the protocol's discriminator.
            return None
        block_size = int(frame.get("block_size", 0))
        block_index = int(frame.get("block_index", -1))
        block_count = int(frame.get("block_count", 0))
        calculated_count = (
            (self.total_size + block_size - 1) // block_size
            if block_size > 0
            else 0
        )
        if (
            block_size <= 0
            or block_count != calculated_count
            or block_index < 0
            or block_index >= block_count
        ):
            raise DumpMemoryReadError(
                "dump_memory block metadata is invalid",
                gap_fact="invalid_block_count",
            )
        if not bool(frame.get("block_crc_ok", False)):
            raise DumpMemoryReadError(
                "dump_memory block CRC validation failed",
                gap_fact="crc_error_count",
            )
        if self.expected_blocks is None:
            self.expected_blocks = block_count
            self.expected_block_size = block_size
        elif (
            self.expected_blocks != block_count
            or self.expected_block_size != block_size
        ):
            raise DumpMemoryReadError(
                "dump_memory block layout changed",
                gap_fact="invalid_block_count",
            )
        expected_payload = min(
            block_size,
            self.total_size - block_index * block_size,
        )
        if sum(len(data) for data in by_region.values()) != expected_payload:
            raise DumpMemoryReadError(
                "dump_memory block coverage is incomplete",
                gap_fact="region_gap_count",
            )
        if block_index in self.blocks:
            raise DumpMemoryReadError(
                "dump_memory repeated a block index",
                gap_fact="invalid_block_count",
            )
        self.blocks[block_index] = by_region
        if len(self.blocks) == self.expected_blocks:
            if set(self.blocks) != set(range(self.expected_blocks)):
                raise DumpMemoryReadError(
                    "dump_memory block sequence is incomplete",
                    gap_fact="missing_block_count",
                )
            assembled = [bytearray() for _ in self.region_sizes]
            for current_index in range(self.expected_blocks):
                for region_index, data in self.blocks[current_index].items():
                    assembled[region_index].extend(data)
                    if len(assembled[region_index]) > self.region_sizes[region_index]:
                        raise DumpMemoryReadError(
                            "dump_memory region coverage overflowed",
                            gap_fact="region_gap_count",
                        )
            incomplete_regions = sum(
                len(data) != self.region_sizes[index]
                for index, data in enumerate(assembled)
            )
            if incomplete_regions:
                raise DumpMemoryReadError(
                    "dump_memory region coverage is incomplete",
                    gap_fact="region_gap_count",
                    gap_count=incomplete_regions,
                )
            return tuple(bytes(data) for data in assembled)


def _read_dump_memory_regions_once_locked(bridge, region_pairs, *, timeout=10.0,
                                          poll_interval=0.0005, cancelled=None):
    """Read exact ranges, rejecting active streams and never publishing partial data."""
    import math
    from contextlib import nullcontext
    validate_dump_regions(region_pairs)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be positive and finite')
    deadline = time.monotonic() + timeout

    def check():
        check_capture_cancelled(cancelled)
        if time.monotonic() >= deadline:
            raise TimeoutError('timed out waiting for complete memory capture')

    check()
    # The real bridge shares this lock with MUX command/start/stop admission.
    # Capture remains exclusive; it must not consume another sampler's events.
    with getattr(bridge, '_cmd_lock', nullcontext()):
        transport = _require_memory_mux(bridge)
        with transport._commands:
            if transport.sampling:
                raise DumpMemoryBusyError('Memory capture requires idle RTT and SuperWatch')
            result = []
            chunk_size = 4096 if transport.capabilities & transport.BLOCK_READ_CAPABILITY else transport.transfer_quantum
            for address, size in region_pairs:
                data = bytearray()
                for offset in range(0, size, chunk_size):
                    check()
                    length = min(chunk_size, size - offset)
                    block = transport.read_memory(address + offset, length, deadline=deadline)
                    check()
                    if not isinstance(block, bytes) or len(block) != length:
                        raise DumpMemoryReadError('Incomplete memory response', gap_fact='region_gap_count')
                    data.extend(block)
                result.append(bytes(data))
            check()
            return tuple(result)


def validate_dump_capture(regions, sample_count=1, timeout=10.0, speed_profile=None):
    """The bounded MCP/API contract, independent of transport and publication."""
    import math
    from mklink.remote.stream_protocol import MAX_MEMORY_REGIONS, MAX_MEMORY_SAMPLES
    if not isinstance(regions, list) or not 1 <= len(regions) <= MAX_MEMORY_REGIONS:
        raise ValueError(f"regions must contain 1..{MAX_MEMORY_REGIONS} entries")
    if type(sample_count) is not int or not 1 <= sample_count <= MAX_MEMORY_SAMPLES:
        raise ValueError("sample_count must be between 1 and 64")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not .001 <= timeout <= 60:
        raise ValueError("timeout must be between 0.001 and 60 seconds")
    if speed_profile is not None and speed_profile not in ('low', 'medium', 'high', 'ultra'):
        raise ValueError("speed_profile must be low/medium/high/ultra")
    pairs = []
    for index, region in enumerate(regions):
        if not isinstance(region, dict) or set(region) != {'address', 'size'}:
            raise ValueError(f"regions[{index}] must contain only address and size")
        address, size = region['address'], region['size']
        if (type(address) is not int or type(size) is not int or size <= 0
                or not 0 <= address <= 0x10000000000000000 - size):
            raise ValueError(f"regions[{index}] has an invalid address/size range")
        pairs.append((address, size))
    total = sum(size for _, size in pairs)
    if total > MAX_TOTAL_DATA_SIZE:
        raise ValueError(f"one sample exceeds the {MAX_TOTAL_DATA_SIZE}-byte device limit")
    if total * sample_count > 512 * 1024:
        raise ValueError("capture exceeds the 524288-byte result limit")
    # Validate wire addresses before changing the debug clock.
    validate_dump_regions(pairs)
    return pairs


def capture_memory(device, regions, *, sample_count=1, timeout=10.0, speed_profile=None,
                   publish_sample=None, publish_gap=None, cancelled=None):
    """Capture complete samples on an already-owned bridge, with no replay.

    Optional publishers keep legacy sidecar wiring outside the acquisition
    service. Shared callers use the ordinary operation/observation records.
    """
    from mklink.observe_bridge import observe_operation, memory_dump_facts
    from mklink.remote.stream_protocol import canonical_memory_address
    pairs = validate_dump_capture(regions, sample_count, timeout, speed_profile)
    def gap(fact, count):
        if publish_gap:
            try:
                publish_gap(fact, count)
            except Exception:
                pass
    with observe_operation('memory.dump', capability='target.memory', action_class='observe') as observation:
        operation_id = f"op-{secrets.token_hex(8)}"
        samples = []
        with exclusive_dump_memory_capture():
            check_capture_cancelled(cancelled)
            if speed_profile is not None:
                device.set_debug_speed(speed_profile)
            for index in range(sample_count):
                check_capture_cancelled(cancelled)
                try:
                    payloads = read_dump_memory_regions_once(device._bridge, pairs, timeout=float(timeout), cancelled=cancelled)
                    if (len(payloads) != len(pairs) or any(not isinstance(data, bytes) or len(data) != size
                            for (_, size), data in zip(pairs, payloads))):
                        raise DumpMemoryReadError('dump_memory returned incomplete region coverage', gap_fact='region_gap_count')
                except DumpMemoryReadError as error:
                    gap(error.gap_fact, error.gap_count)
                    raise
                if publish_sample:
                    try:
                        published = publish_sample(pairs, payloads, index, sample_count, operation_id)
                    except Exception:
                        published = False
                    if not published:
                        gap('publish_drop_count', 1)
                samples.append({'sample_index': index, 'regions': [
                    {'address': canonical_memory_address(address), 'size': len(data), 'data_hex': data.hex().upper()}
                    for (address, _), data in zip(pairs, payloads)]})
            check_capture_cancelled(cancelled)
        response = {'sample_count': sample_count, 'region_count': len(pairs),
                    'total_bytes': sum(size for _, size in pairs) * sample_count, 'samples': samples}
        observation.complete(facts=memory_dump_facts(canonical_memory_address(pairs[0][0]),
            total_bytes=response['total_bytes'], region_count=len(pairs), sample_count=sample_count))
        return response


MAX_DUMP_RESULT_JSON_BYTES = 16 * 1024 * 1024


def validate_sampling_protocol(protocol):
    if protocol not in ('mux', 'dmpm'):
        raise ValueError('protocol must be mux (default) or explicit dmpm')


def validate_dump_stream(regions, period=0.0, frames=1, duration=2.0, speed_profile=None, *, fastest=False, protocol='mux'):
    """Validate the finite CLI capture contract before a bridge or clock is touched."""
    import math
    if not isinstance(regions, list) or not 1 <= len(regions) <= MAX_SAMPLING_REGIONS:
        raise ValueError('dump capture requires 1..15 regions (MUX sampling capacity)')
    if type(frames) is not int or not 0 <= frames <= 100000:
        raise ValueError('frames must be between 0 and 100000')
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in (period, duration)):
        raise ValueError('period and duration must be finite numbers')
    if period < 0 or not 0 <= duration <= 300 or (not frames and not duration):
        raise ValueError('Use period >= 0, duration 0..300, and at least one capture bound')
    if type(fastest) is not bool or (fastest and period != 0):
        raise ValueError('Fastest sampling requires fastest=True and period=0')
    if not fastest and period == 0 and frames not in (0, 1):
        raise ValueError('period=0 produces one sample; choose a positive period for multiple samples')
    if speed_profile is not None and speed_profile not in ('low', 'medium', 'high', 'ultra'):
        raise ValueError('speed_profile must be low/medium/high/ultra')
    pairs = []
    for region in regions:
        if not isinstance(region, dict) or set(region) != {'address', 'size'}:
            raise ValueError('Each region requires exactly address and size')
        pairs.append((region['address'], region['size']))
    validate_sampling_protocol(protocol)
    if protocol == 'mux':
        from mklink.mux_watch import create_mux_capture_session
        create_mux_capture_session(None, pairs, period, fastest=fastest)
    else:
        from mklink.legacy_dump import command_for
        if fastest:
            raise ValueError('DMPM has no acknowledged fastest mode; use a positive period')
        command_for(pairs, period)
    return pairs


def check_capture_cancelled(cancelled):
    if cancelled is not None and cancelled():
        raise InterruptedError('Dump capture cancelled: owning session ended or request disconnected')


def capture_dump_stream(device, regions, *, period=0.0, frames=1, duration=2.0, speed_profile=None,
                        fastest=False, protocol='mux', cancelled=None):
    """Collect complete samples using the existing session and shared assembler.

    First sample has a 2s startup allowance; duration starts at that sample.
    A count-only capture still ends within 300s. Serialized samples are bounded
    by 16 MiB; overflow fails instead of returning or saving an incomplete result.
    Explicit fastest=True requires period=0 and negotiated timing-v2 firmware.
    Without the flag, period=0 retains its single-sample meaning. Returned timing
    is the accepted START configuration, not a measured sampling-rate guarantee.
    """
    import json
    from mklink.mux_watch import PackedWatchSample
    pairs = validate_dump_stream(regions, period, frames, duration, speed_profile, fastest=fastest, protocol=protocol)
    check_capture_cancelled(cancelled)
    if speed_profile is not None:
        device.set_debug_speed(speed_profile)
    session = DumpMemoryStreamSession(device._bridge, pairs, period, fastest=fastest, protocol=protocol)
    session.packed_frames = True
    assembler = DumpSampleAssembler([size for _, size in pairs], ordered=True)
    region_metadata = [{'address': f'0x{address:08X}', 'size': size} for address, size in pairs]
    # Every field has a fixed ASCII representation except the two integers and
    # hex payloads. Bound the same JSON without serializing it while sampling.
    template = {'sample_index': 0, 'timestamp_us': 0,
                'regions': [{**region, 'data_hex': ''} for region in region_metadata]}
    sample_fixed_bytes = (len(json.dumps(template, separators=(',', ':'))) - 2
                          + 2 * sum(size for _, size in pairs) + 1)
    samples, result_bytes = [], 0
    deadline = time.monotonic() + 2.0
    stopped_by = 'duration'
    try:
        session.start()
        timing = session.timing
        while time.monotonic() < deadline:
            check_capture_cancelled(cancelled)
            batch = session.read_frames(max_bytes=1024 * 1024)
            for frame in batch:
                check_capture_cancelled(cancelled)
                if isinstance(frame, PackedWatchSample):
                    timestamp = frame.timestamp_us
                    sample = frame
                else:
                    payloads = assembler.feed(frame)
                    if payloads is None:
                        continue
                    timestamp = assembler.timestamp_us
                    sample = (timestamp, payloads, frame.get('acquisition'))
                    assembler = DumpSampleAssembler([size for _, size in pairs], ordered=True)
                if not samples:
                    deadline = time.monotonic() + (duration or 300)
                result_bytes += sample_fixed_bytes + len(str(len(samples))) + len(str(timestamp))
                if not isinstance(sample, PackedWatchSample) and sample[2] is not None:
                    result_bytes += len(json.dumps({'acquisition': sample[2]}, separators=(',', ':'))) - 1
                if result_bytes > MAX_DUMP_RESULT_JSON_BYTES:
                    raise ValueError('Dump result exceeds 16 MiB JSON limit; reduce frames, duration or regions')
                samples.append(sample)
                if (period == 0 and not fastest) or (frames and len(samples) >= frames):
                    stopped_by = 'frames'
                    break
            if stopped_by == 'frames':
                break
            if not batch:
                time.sleep(.001)
    finally:
        session.stop()
    if not samples:
        raise TimeoutError('No complete dump sample received')
    stats = session.stats
    if any(stats.get(k, 0) for k in ('parser_crc_errors', 'parser_dropped_frames',
                                   'parser_dropped_bytes', 'firmware_flagged_frames')):
        raise DumpMemoryReadError(f'mem_dump integrity failure: {stats}')
    # Construct API objects after the confirmed stop, so JSON/hex allocation
    # cannot hold up the live bounded RX queue.
    for index, sample in enumerate(samples):
        check_capture_cancelled(cancelled)
        if isinstance(sample, PackedWatchSample):
            acquisition = None
            timestamp = sample.timestamp_us
            cursor = sample.offset
            payloads = []
            for _, size in pairs:
                payloads.append(sample.payload[cursor:cursor+size])
                cursor += size
        else:
            timestamp, payloads, acquisition = sample
        samples[index] = {'sample_index': index, 'timestamp_us': timestamp,
                          'regions': [{**region, 'data_hex': data.hex()}
                                      for region, data in zip(region_metadata, payloads)]}
        if acquisition is not None:
            samples[index]['acquisition'] = acquisition
    return {'sample_count': len(samples), 'region_count': len(pairs),
            'total_bytes': sum(size for _, size in pairs) * len(samples), 'samples': samples,
            'stopped_by': stopped_by, 'incomplete_tail': bool(assembler.blocks or assembler.incomplete_region_count
                                                            or stats.get('incomplete_samples', 0)),
            'stats': stats, 'timing': timing, 'protocol': protocol}


class DumpMemoryStreamSession:
    """Default to MUX; DMPM requires explicit selection before any I/O."""

    packed_frames = False

    def __init__(self, bridge, region_pairs, period, *, write_ranges=ARM_WRITE_RANGES, fastest=False, protocol='mux',
                 wait_after_sample=False):
        import math
        if not math.isfinite(period) or period < 0:
            raise ValueError('dump period must be nonnegative and finite')
        self.bridge = bridge
        self.region_pairs = list(region_pairs)
        self.period = float(period)
        self.write_ranges = tuple(write_ranges)
        self._wait_after_sample = wait_after_sample
        self.fastest = fastest
        validate_sampling_protocol(protocol)
        self.protocol = protocol
        self._legacy = None
        validate_dump_regions(self.region_pairs)
        if type(fastest) is not bool or (fastest and period != 0):
            raise ValueError('Fastest sampling requires fastest=True and period=0')
        if protocol == 'dmpm':
            from mklink.legacy_dump import LegacyDumpSession
            if fastest:
                raise ValueError('DMPM has no acknowledged fastest mode; use a positive period')
            self._legacy = LegacyDumpSession(bridge, self.region_pairs, self.period)
        # Capacity validation is repeated at start before any connection I/O.
        self.started = False
        self._mux_watch = None
        self._mux_dropped_bytes_start = 0

    def start(self):
        if self.started:
            return
        if self._legacy is not None:
            try:
                self._legacy.start()
            finally:
                self.started = self._legacy.started
            return
        from mklink.mux_watch import create_mux_capture_session
        watch = create_mux_capture_session(None, self.region_pairs, self.period, fastest=self.fastest,
                                           wait_after_sample=self._wait_after_sample)
        supported = getattr(self.bridge, 'supports_multiplex', None)
        if not callable(supported) or supported() is not True:
            raise DumpMemoryUnsupported('SuperWatch requires MUX sampling firmware; update the probe firmware and host together')
        watch.transport = self.bridge.enable_multiplex()
        if watch.transport is None:
            raise DumpMemoryUnsupported('SuperWatch requires MUX sampling firmware; update the probe firmware and host together')
        self._mux_watch = watch
        self._mux_drop_key = 'bulk_dropped_bytes' if getattr(watch, 'EVENT', None) == 0x42 else 'watch_dropped_bytes'
        self._mux_dropped_bytes_start = watch.transport.stats()[self._mux_drop_key]
        watch.start()
        self.started = True

    @property
    def timing(self):
        """Accepted wire timing, not a measured sampling-rate guarantee."""
        if self._legacy is not None:
            return self._legacy.timing
        value = self._mux_watch.timing if self._mux_watch is not None else None
        return dict(value) if value is not None else None

    def request_write(self, address, data, future):
        if not self.started:
            raise RuntimeError('Sampling stream is not started')
        if self._legacy is not None:
            raise RuntimeError('Live variable writes require MUX; DMPM compatibility capture is read-only')
        if len(data) not in (1, 2, 4, 8) or not any(
            start <= address and address + len(data) <= end for start, end in self.write_ranges
        ):
            raise ValueError('Live writes require supported target RAM scalars of 1/2/4/8 bytes')
        self._mux_watch.write(address, data, future)

    def read_frames(self, max_bytes=None):
        if not self.started:
            raise RuntimeError('dump-memory stream is not started')
        if self._legacy is not None:
            return self._legacy.read_frames(max_bytes)
        return self._mux_watch.read_frames(packed=self.packed_frames)

    def stop(self):
        if not self.started:
            return
        try:
            (self._legacy if self._legacy is not None else self._mux_watch).stop()
        finally:
            self.started = False

    @property
    def stats(self):
        if self._legacy is not None:
            return self._legacy.stats
        watch = self._mux_watch
        return {'protocol_frames': watch.samples if watch else 0,
                'complete_samples': watch.samples if watch else 0,
                'parser_dropped_bytes': (watch.transport.stats()[self._mux_drop_key]
                                         - self._mux_dropped_bytes_start) if watch else 0,
                'parser_dropped_frames': watch.gaps if watch else 0,
                'firmware_read_errors': watch.read_errors if watch else 0,
                'incomplete_samples': int(bool(watch and watch._pending)),
                'parser_crc_errors': 0, 'firmware_flagged_frames': 0, 'firmware_sample_drop_flags': 0}


def decode_frame_to_points(
    frame: dict,
    block_addresses: list[tuple[int, int, list[tuple]]],
    origin_us: int | None,
) -> tuple[list[dict], int | None]:
    """Decode a parsed frame's region data into per-variable point dicts.

    This bridges binary region data back to the variable name/type system
    used by the SuperWatch visualizer.

    Args:
        frame: Parsed frame from DumpMemoryParser.feed().
        block_addresses: Per-region info list with item name, type, offset,
            byte size, scalar kind, and enum values.
        origin_us: Baseline timestamp in microseconds (from first sample).

    Returns:
        (points, origin_us) where points is a list of dicts suitable for
        server.push_data_point().
    """
    from mklink.watch import decode_value

    if int(frame.get("flags", 0)) & ~FLAG_SAMPLE_DROPPED:
        raise ValueError("dump_memory firmware reported region/read error")
    regions = frame["regions"]
    seen = set()
    for index, payload in regions:
        if index < 0 or index >= len(block_addresses) or index in seen:
            raise ValueError("dump_memory region configuration mismatch")
        seen.add(index)
        if len(payload) != block_addresses[index][1]:
            raise ValueError("dump_memory region payload length mismatch")
    if seen != set(range(len(block_addresses))):
        raise ValueError("dump_memory frame is missing configured regions")

    current_origin = origin_us
    if current_origin is None:
        current_origin = frame["timestamp_us"]

    ts = frame["timestamp_us"]
    relative_t = (ts - current_origin) / 1_000_000.0

    points: list[dict] = []
    for region_index, region_data in frame["regions"]:
        if region_index >= len(block_addresses):
            continue
        block_addr, _block_size, items = block_addresses[region_index]
        point: dict = {"_t": relative_t, "timestamp_us": ts}
        for item in items:
            if len(item) == 4:
                name, type_name, item_offset, enum_values = item
                item_size = _item_size(type_name)
                scalar_kind = None
            else:
                name, type_name, item_offset, item_size, scalar_kind, enum_values = item
            data = region_data[item_offset:item_offset + item_size]
            if len(data) != item_size:
                raise ValueError("dump_memory variable payload is incomplete: " + name)
            if data:
                # Store raw numeric value for charting; enum display is handled by frontend
                point[name] = decode_value(
                    data,
                    type_name,
                    known_size=item_size,
                    scalar_kind=scalar_kind,
                )
        if len(point) > 2:
            points.append(point)

    return points, current_origin


def _item_size(type_name: str) -> int:
    """Return byte size for a C type name."""
    _SIZES = {
        "uint8_t": 1, "int8_t": 1, "bool": 1,
        "uint16_t": 2, "int16_t": 2,
        "uint32_t": 4, "int32_t": 4, "float": 4,
        "uint64_t": 8, "int64_t": 8, "double": 8,
    }
    return _SIZES.get(type_name, 4)

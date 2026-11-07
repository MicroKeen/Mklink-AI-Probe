import binascii
import codecs
import struct
import sys
import threading

import pytest

from mklink._types import DeviceContext, DeviceState
from mklink.bridge import MKLinkSerialBridge
from mklink.dump_memory import (
    DumpMemoryParser,
    DumpSampleAssembler,
    DumpMemoryBusyError,
    DumpMemoryReadError,
    DumpMemoryStreamSession,
    FLAG_SAMPLE_DROPPED,
    MAGIC,
    read_dump_memory_range_once,
    read_dump_memory_regions_once,
)


@pytest.mark.parametrize("partial", [False, True])
def test_dap_terminal_frame_rejects_capture_before_block_coverage(partial):
    assembler = DumpSampleAssembler([4096], ordered=True)
    parser = DumpMemoryParser()
    if partial:
        block = _b1_frame(1, bytes(2048), block_index=0, block_count=2, total_size=4096)
        assert assembler.feed(parser.feed(block)[0]) is None
    terminal = parser.feed(_old_frame(2, b"", flags=0x10))[0]
    with pytest.raises(DumpMemoryReadError, match="invalidated by DAP"):
        assembler.feed(terminal)


def _old_frame(timestamp_us, payload, *, flags=0):
    region = b"\x00" + struct.pack("<H", len(payload)) + payload
    length = 19 + len(region) + 6
    body = MAGIC + struct.pack("<QHB", timestamp_us, length, 1) + region + struct.pack("<H", flags)
    return body + struct.pack("<I", binascii.crc32(body) & 0xFFFFFFFF)


def _b1_frame(timestamp_us, payload, *, block_index, block_count, total_size, flags=0):
    block_crc = binascii.crc32(payload) & 0xFFFFFFFF
    body = bytearray()
    body.extend(MAGIC)
    body.extend(struct.pack("<QH", timestamp_us, 0))
    body.extend(struct.pack("<B", 1))
    body.extend(struct.pack("<H", flags))
    body.extend(struct.pack("<IHHHI", total_size, 2048, block_index, block_count, block_crc))
    body.extend(struct.pack("<BH", 0, len(payload)))
    body.extend(payload)
    frame_length = len(body) + 4
    struct.pack_into("<H", body, 16, frame_length)
    return bytes(body) + struct.pack("<I", binascii.crc32(body) & 0xFFFFFFFF)


def _old_regions_frame(timestamp_us, regions, *, flags=0):
    encoded_regions = b"".join(
        bytes([index]) + struct.pack("<H", len(payload)) + payload
        for index, payload in regions
    )
    length = 19 + len(encoded_regions) + 6
    body = (
        MAGIC
        + struct.pack("<QHB", timestamp_us, length, len(regions))
        + encoded_regions
        + struct.pack("<H", flags)
    )
    return body + struct.pack("<I", binascii.crc32(body) & 0xFFFFFFFF)


def _b1_regions_frame(
    timestamp_us,
    regions,
    *,
    block_index,
    block_count,
    total_size,
    flags=0,
    corrupt_block_crc=False,
):
    payload = b"".join(data for _index, data in regions)
    block_crc = binascii.crc32(payload) & 0xFFFFFFFF
    if corrupt_block_crc:
        block_crc ^= 0xFFFFFFFF
    body = bytearray()
    body.extend(MAGIC)
    body.extend(struct.pack("<QH", timestamp_us, 0))
    body.extend(struct.pack("<B", len(regions)))
    body.extend(struct.pack("<H", flags))
    body.extend(struct.pack(
        "<IHHHI", total_size, 2048, block_index, block_count, block_crc,
    ))
    for region_index, data in regions:
        body.extend(struct.pack("<BH", region_index, len(data)))
        body.extend(data)
    struct.pack_into("<H", body, 16, len(body) + 4)
    return bytes(body) + struct.pack("<I", binascii.crc32(body) & 0xFFFFFFFF)


class FakeBridge:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.calls = []

    def _enter_stream(self, state):
        self.calls.append(("enter", state))

    def _write_raw(self, data):
        self.calls.append(("write", data))

    def drain_stream_bytes(self, max_bytes=None):
        self.calls.append(("drain", max_bytes))
        return self.chunks.pop(0) if self.chunks else b""

    def _exit_stream(self):
        self.calls.append(("exit",))
        return ""

    def _stop_stream_and_sync(self, command, **options):
        self._write_raw(command)
        self.drain_stream_bytes()
        self._exit_stream()
        return True


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            ["dump-memory"]
            + [f"0x{0x20000000 + index * 4:08X}:4" for index in range(16)],
            "MUX sampling capacity",
        ),
        (
            ["vofa", "--period", "0.001"]
            + [
                value
                for index in range(16)
                for value in (f"0x{0x20000000 + index * 4096:08X}", "float")
            ],
            "at most 15",
        ),
    ],
)
def test_cli_main_reports_unsafe_stream_request_as_failure(
    monkeypatch, capsys, arguments, message,
):
    from mklink import cli

    monkeypatch.setattr(sys, "argv", ["mklink", *arguments])
    from mklink import runtime_cli
    monkeypatch.setattr(runtime_cli, 'RuntimeClient', lambda **kw: pytest.fail('invalid stream input connected'))
    with pytest.raises(SystemExit, match=message):
        cli.main()


def test_superwatch_poll_reuses_one_connection_and_accounts_for_read_time(monkeypatch):
    from unittest.mock import Mock
    from mklink import superwatch

    bridge = Mock()
    bridge.connect.return_value = True
    now = [0.0]
    def send(*args, **kwargs):
        now[0] += 0.04
        return "timestamp=100\n20000000 00 00 80 3f"
    bridge.send_command.side_effect = send
    factory = Mock(return_value=bridge)
    init = Mock()
    monkeypatch.setattr('mklink.bridge.MKLinkSerialBridge', factory)
    monkeypatch.setattr('mklink.device.initialize_target', init)
    sleeps = []
    def sleep(delay):
        sleeps.append(delay)
        now[0] += delay
    blocks = superwatch.build_read_blocks([superwatch.WatchItem('a', 0x20000000, 'float', 4)])
    points = superwatch.poll_blocks(blocks, port='test', duration=.13, period=.05,
                                   clock=lambda: now[0], sleep_func=sleep)
    assert len(points) == 3
    assert factory.call_count == init.call_count == 1
    assert sleeps == pytest.approx([.01, .01])
    bridge.close.assert_called_once()


def test_superwatch_poll_closes_on_read_error_and_keeps_custom_reader(monkeypatch):
    from unittest.mock import Mock
    from mklink import superwatch

    bridge = Mock()
    bridge.send_command.side_effect = RuntimeError('read failed')
    factory = Mock(return_value=bridge)
    monkeypatch.setattr(superwatch, '_open_sampling_bridge', factory)
    blocks = superwatch.build_read_blocks([superwatch.WatchItem('a', 0x20000000, 'float', 4)])
    with pytest.raises(RuntimeError, match='read failed'):
        superwatch.poll_blocks(blocks, duration=.1)
    bridge.close.assert_called_once()
    factory.reset_mock()
    reader = Mock(return_value=(struct.pack('<f', 3.0), 'timestamp=1000\n20000000 00 00 40 40'))
    now = iter([0, 0, 1])
    assert superwatch.poll_blocks(blocks, duration=.1, read_func=reader, clock=lambda: next(now))[0]['a'] == 3.0
    factory.assert_not_called()


def test_real_bridge_failed_dump_claim_preserves_active_rtt_buffer_and_state():
    bridge = MKLinkSerialBridge("TEST-LEGACY")
    bridge._ctx = DeviceContext(state=DeviceState.RTT_STREAM)
    bridge._buffer_lock = threading.Lock()
    bridge._response_buffer = [b"live-rtt-bytes"]
    bridge._utf8_decoder = codecs.getincrementaldecoder("utf-8")()

    assert bridge._try_enter_stream(DeviceState.DUMP_STREAM) is False
    with pytest.raises(RuntimeError, match="bridge state is rtt_stream"):
        bridge._enter_stream(DeviceState.DUMP_STREAM)
    assert bridge.state is DeviceState.RTT_STREAM
    assert bridge._response_buffer == [b"live-rtt-bytes"]


def test_multi_region_old_incomplete_region_reports_region_gap():
    bridge = FakeBridge([_old_regions_frame(1, [
        (0, b"abcd"),
        (1, b"e"),
    ])])

    with pytest.raises(DumpMemoryReadError) as raised:
        read_recorded_regions(
            bridge,
            [(0x20000000, 4), (0x20001000, 2)],
            timeout=0.01,
            poll_interval=0,
        )

    assert raised.value.gap_fact == "region_gap_count"
    assert raised.value.gap_count == 1


def test_multi_region_b1_tracks_blocks_and_exact_region_coverage():
    first = b"A" * 1500
    second = b"B" * 1000
    bridge = FakeBridge([
        _b1_regions_frame(
            1,
            [(0, first), (1, second[:548])],
            block_index=0,
            block_count=2,
            total_size=2500,
        ),
        _b1_regions_frame(
            2,
            [(1, second[548:])],
            block_index=1,
            block_count=2,
            total_size=2500,
        ),
    ])

    assert read_recorded_regions(
        bridge,
        [(0x20000000, 1500), (0x20001000, 1000)],
        timeout=0.1,
        poll_interval=0,
    ) == (first, second)


def test_multi_region_b1_reassembles_out_of_order_complete_blocks():
    first = b"A" * 2048
    bridge = FakeBridge([
        _b1_regions_frame(
            2,
            [(0, b"B")],
            block_index=1,
            block_count=2,
            total_size=2049,
        ),
        _b1_regions_frame(
            1,
            [(0, first)],
            block_index=0,
            block_count=2,
            total_size=2049,
        ),
    ])

    assert read_recorded_regions(
        bridge,
        [(0x20000000, 2049)],
        timeout=0.1,
        poll_interval=0,
    ) == (first + b"B",)


def test_multi_region_b1_rejects_bad_block_crc_with_stable_gap_fact():
    bridge = FakeBridge([_b1_regions_frame(
        1,
        [(0, b"A" * 2048)],
        block_index=0,
        block_count=2,
        total_size=2049,
        corrupt_block_crc=True,
    )])

    with pytest.raises(DumpMemoryReadError) as raised:
        read_recorded_regions(
            bridge,
            [(0x20000000, 2049)],
            timeout=0.1,
            poll_interval=0,
        )

    assert raised.value.gap_fact == "crc_error_count"
    assert raised.value.gap_count == 1


def test_multi_region_b1_missing_tail_never_returns_partial_sample():
    bridge = FakeBridge([_b1_regions_frame(
        1,
        [(0, b"A" * 2048)],
        block_index=0,
        block_count=2,
        total_size=2049,
    )])

    with pytest.raises(DumpMemoryReadError) as raised:
        read_recorded_regions(
            bridge,
            [(0x20000000, 2049)],
            timeout=0.01,
            poll_interval=0,
        )

    assert raised.value.gap_fact == "missing_block_count"
    assert raised.value.gap_count == 1


def test_multi_region_b1_rejects_incomplete_per_region_coverage():
    bridge = FakeBridge([
        _b1_regions_frame(
            1,
            [(0, b"A" * 1499), (1, b"B" * 549)],
            block_index=0,
            block_count=2,
            total_size=2500,
        ),
        _b1_regions_frame(
            2,
            [(1, b"B" * 452)],
            block_index=1,
            block_count=2,
            total_size=2500,
        ),
    ])

    with pytest.raises(DumpMemoryReadError) as raised:
        read_recorded_regions(
            bridge,
            [(0x20000000, 1500), (0x20001000, 1000)],
            timeout=0.1,
            poll_interval=0,
        )

    assert raised.value.gap_fact == "region_gap_count"


def test_multi_region_b1_rejects_duplicate_block_even_when_bytes_match():
    first = _b1_regions_frame(
        1,
        [(0, b"A" * 2048)],
        block_index=0,
        block_count=2,
        total_size=2049,
    )
    bridge = FakeBridge([first, first])

    with pytest.raises(DumpMemoryReadError) as raised:
        read_recorded_regions(
            bridge,
            [(0x20000000, 2049)],
            timeout=0.1,
            poll_interval=0,
        )

    assert raised.value.gap_fact == "invalid_block_count"


def test_multi_region_b1_rejects_block_count_change():
    bridge = FakeBridge([
        _b1_regions_frame(
            1,
            [(0, b"A" * 2048)],
            block_index=0,
            block_count=2,
            total_size=2049,
        ),
        _b1_regions_frame(
            2,
            [(0, b"B")],
            block_index=1,
            block_count=3,
            total_size=2049,
        ),
    ])

    with pytest.raises(DumpMemoryReadError) as raised:
        read_recorded_regions(
            bridge,
            [(0x20000000, 2049)],
            timeout=0.1,
            poll_interval=0,
        )

    assert raised.value.gap_fact == "invalid_block_count"


def test_multi_region_outer_crc_error_is_counted_and_never_published():
    corrupt = bytearray(_b1_regions_frame(
        1,
        [(0, b"A" * 2048)],
        block_index=0,
        block_count=2,
        total_size=2049,
    ))
    corrupt[-1] ^= 0xFF
    bridge = FakeBridge([bytes(corrupt)])

    with pytest.raises(DumpMemoryReadError) as raised:
        read_recorded_regions(
            bridge,
            [(0x20000000, 2049)],
            timeout=0.01,
            poll_interval=0,
        )

    assert raised.value.gap_fact == "crc_error_count"
    assert raised.value.gap_count == 1


def test_multi_region_outer_crc_error_poisoning_prevents_later_good_frame():
    corrupt = bytearray(_old_regions_frame(1, [(0, b"bad!")]))
    corrupt[-1] ^= 0xFF
    good = _old_regions_frame(2, [(0, b"good")])
    bridge = FakeBridge([bytes(corrupt) + good])

    with pytest.raises(DumpMemoryReadError) as raised:
        read_recorded_regions(
            bridge,
            [(0x20000000, 4)],
            timeout=0.1,
            poll_interval=0,
        )

    assert raised.value.gap_fact == "crc_error_count"
    assert raised.value.gap_count == 1


def read_recorded_regions(record, regions, **unused):
    """Offline test fixture: no transport or target operation is possible."""
    sizes = [size for _, size in regions]
    parser, assembler = DumpMemoryParser(sizes), DumpSampleAssembler(sizes)
    for raw in record.chunks:
        frames = parser.feed(raw)
        if parser.crc_errors:
            raise DumpMemoryReadError('record CRC error', gap_fact='crc_error_count', gap_count=parser.crc_errors)
        for frame in frames:
            result = assembler.feed(frame)
            if result is not None:
                return result
    if assembler.incomplete_region_count:
        raise DumpMemoryReadError('record incomplete region', gap_fact='region_gap_count', gap_count=assembler.incomplete_region_count)
    raise DumpMemoryReadError('record missing tail', gap_fact='missing_block_count')

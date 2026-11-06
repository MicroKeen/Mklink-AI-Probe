"""Bulk wire assembly and lifecycle isolation through the real transport parser."""
import binascii
import struct
from types import SimpleNamespace

import pytest

from mklink.dump_memory import DumpMemoryStreamSession, capture_dump_stream
from mklink.mux import MuxTransport, MuxError, packet
from mklink.mux_bulk_watch import HEADER, MuxBulkWatchSession
from test_watch_timing_v2 import bridge_for


def peer(*, capable=True, bad_ack=False, stop_ack=None, first_data=None):
    calls = []
    def write(wire):
        _, _, op, n, epoch, request = struct.unpack_from('<4sBBHII', wire)
        payload = wire[16:16+n]
        body = payload[8:] if 0x10 <= op < 0x40 else payload
        calls.append((op, body))
        answer = b''
        if op == 1: answer = struct.pack('<IHH', 0x61f | (0x800 if capable else 0), 256, 1)
        elif op == 4: answer = payload
        elif op == 0x34:
            stream, period, count = struct.unpack_from('<IIB', body)
            total = sum(struct.unpack_from('<IH', body, 9+6*i)[1] for i in range(count))
            answer = struct.pack('<IIHHI', stream, period, total, 452, 360000000)
            if bad_ack: answer = answer[:-1]
        elif op == 0x35: answer = body if stop_ack is None else stop_ack
        elif op in (0x32, 0x33): answer = struct.pack('<II', struct.unpack_from('<I', body)[0], 360000000)
        transport.feed(packet(op | 0x80, 17, request, b'\0'+answer))
        if op == 0x34 and first_data is not None and not bad_ack:
            for index, fragment in enumerate(fragments(first_data, stream=stream, last_epoch=12), 1):
                raw = struct.pack('<4sBBHII', b'MLX1', 1, 0x42, len(fragment), 17, index) + fragment
                transport.feed(raw + struct.pack('<I', binascii.crc32(raw) & 0xffffffff))
        return len(wire)
    transport = MuxTransport(write)
    transport.handshake()
    return transport, calls


def wire(seq, payload, *, version=1, epoch=17):
    raw = struct.pack('<4sBBHII', b'MLX1', version, 0x42, len(payload), epoch, seq) + payload
    return raw + struct.pack('<I', binascii.crc32(raw) & 0xffffffff)


def fragments(data, *, stream=1, sample=1, start=100, end=500, first_epoch=10, last_epoch=10):
    return [HEADER.pack(stream, sample, start, end, first_epoch, last_epoch, len(data), off,
                        len(data[off:off+452]), 0,
                        (1 if off == 0 else 0) | (2 if off+452 >= len(data) else 0) |
                        (4 if first_epoch != last_epoch else 0)) + data[off:off+452]
            for off in range(0, len(data), 452)]


@pytest.mark.parametrize('split', [1, 19, 127, 512, 4096])
def test_complete_4096_group_keeps_all_bytes_metadata_and_rtt_ownership(split):
    transport, calls = peer()
    transport.rtt_mask = 2
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x24040001, 4096)], 0, fastest=True)
    session.start()
    assert isinstance(session._mux_watch, MuxBulkWatchSession)
    assert session.timing['accepted_period_us'] == 0 and transport.bulk_running
    expected = bytes(range(256))*16
    data = b''.join(wire(i+1, p) for i, p in enumerate(fragments(expected, last_epoch=12)))
    for off in range(0, len(data), split): transport.feed(data[off:off+split])
    result, = session.read_frames()
    assert result['regions'] == [(0, expected)]
    assert result['timestamp_us'] == 100
    assert result['acquisition'] == dict(stream_id=1, sample_id=1, start_us=100, end_us=500,
        dap_epoch_first=10, dap_epoch_last=12, dap_intervened=True, atomic_snapshot=False)
    session.stop()
    assert not transport.bulk_running and transport.rtt_mask == 2 and transport.sampling
    assert calls[-1] == (0x35, struct.pack('<I', 1))


def test_partial_tail_never_becomes_sample_and_successive_streams_do_not_reuse_id():
    transport, calls = peer()
    for identity in (1, 2):
        session = DumpMemoryStreamSession(bridge_for(transport), [(0x24040000, 4096)], .001)
        session.start()
        transport.feed(wire(identity, fragments(bytes(4096), stream=identity)[0]))
        assert session.read_frames() == [] and session.stats['incomplete_samples'] == 1
        session.stop()
    assert [struct.unpack_from('<I', b)[0] for op, b in calls if op == 0x34] == [1, 2]


@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'reorder', 'timestamp', 'stream', 'total', 'flags', 'epoch', 'exhausted'])
def test_damaged_group_is_never_published(damage):
    transport, calls = peer()
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 4096)], .001)
    session.start()
    parts = fragments(bytes(4096))
    if damage == 'missing': del parts[1]
    elif damage == 'duplicate': parts.insert(1, parts[0])
    elif damage == 'reorder': parts[1], parts[2] = parts[2], parts[1]
    elif damage == 'exhausted': parts = fragments(bytes(4096), sample=0xffffffff)
    else:
        fields = list(HEADER.unpack_from(parts[1]))
        fields[{'timestamp':2, 'stream':0, 'total':6, 'flags':10, 'epoch':5}[damage]] += 8
        parts[1] = HEADER.pack(*fields) + parts[1][40:]
    for i, part in enumerate(parts): transport.feed(wire(i+1, part))
    with pytest.raises(RuntimeError): session.read_frames()
    session.stop()
    assert sum(op == 0x34 for op, _ in calls) == 1


@pytest.mark.parametrize('damage', ['crc', 'version', 'epoch', 'unadvertised', 'oversized'])
def test_transport_rejects_bulk_frame_before_publication(damage):
    transport, _ = peer(capable=damage != 'unadvertised')
    payload = fragments(bytes(4096))[0]
    if damage == 'oversized': payload += b'x'
    raw = wire(1, payload, version=2 if damage == 'version' else 1, epoch=18 if damage == 'epoch' else 17)
    if damage == 'crc': raw = raw[:-1] + bytes([raw[-1] ^ 1])
    transport.feed(raw)
    with pytest.raises(MuxError): transport.drain(0x42, 255)


@pytest.mark.parametrize('status', [5, 7, 99])
def test_read_or_lifecycle_failure_discards_entire_group(status):
    transport, _ = peer()
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 4096)], .001)
    session.start()
    transport.feed(wire(1, fragments(bytes(4096))[0]))
    assert session.read_frames() == []
    transport.feed(wire(2, HEADER.pack(1, 1, 100, 600, 10, 11, 4096, 0, 0, status, 7)))
    with pytest.raises(RuntimeError, match='failed'): session.read_frames()
    assert not session._mux_watch._pending
    session.stop()


def test_capability_failure_has_no_start_stop_or_legacy_fallback():
    transport, calls = peer(capable=False)
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 4096)], .001)
    before = list(calls)
    with pytest.raises(RuntimeError, match='0x800'): session.start()
    session.stop()
    assert calls == before


def test_bad_start_ack_is_stopped_once_and_bad_stop_poisons_session():
    transport, calls = peer(bad_ack=True)
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 4096)], .001)
    with pytest.raises(RuntimeError, match='acknowledgement'): session.start()
    session.stop()
    assert [op for op, _ in calls][-2:] == [0x34, 0x35]
    transport, calls = peer(stop_ack=b'bad')
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 4096)], .001)
    session.start()
    with pytest.raises(MuxError): session.stop()
    assert transport.bulk_running


def test_receive_queue_loss_never_publishes_a_successful_partial_group():
    transport, _ = peer()
    session = DumpMemoryStreamSession(bridge_for(transport), [(0x20000000, 4096)], .001)
    session.start()
    transport.WATCH_QUEUE_BYTES = 600
    for i, part in enumerate(fragments(bytes(4096))): transport.feed(wire(i+1, part))
    with pytest.raises(RuntimeError, match='discarded'): session.read_frames()
    assert session.stats['parser_dropped_bytes'] > 0
    session.stop()


def test_public_capture_returns_complete_bytes_and_acquisition_metadata():
    expected = bytes(range(256))*16
    transport, calls = peer(first_data=expected)
    result = capture_dump_stream(SimpleNamespace(_bridge=bridge_for(transport)),
        [{'address': 0x24040000, 'size': 4096}], fastest=True, frames=1)
    sample, = result['samples']
    assert result['protocol'] == 'mux' and result['sample_count'] == 1
    assert bytes.fromhex(sample['regions'][0]['data_hex']) == expected
    assert sample['acquisition']['end_us'] == 500
    assert sample['acquisition']['dap_intervened']
    assert not sample['acquisition']['atomic_snapshot']
    assert calls[-1][0] == 0x35


def test_bulk_stop_does_not_stop_small_watch_or_rtt():
    from mklink.mux_watch import MuxWatchSession
    transport, calls = peer()
    transport.rtt_mask = 2
    small = MuxWatchSession(transport, [(0x24040000, 4)], .001)
    small.start()
    bulk = MuxBulkWatchSession(transport, [(0x24041000, 4096)], .001)
    bulk.start()
    bulk.stop()
    assert transport.watch_running and transport.rtt_mask == 2
    assert calls[-1][0] == 0x35
    transport.feed(packet(0x41, 17, 1, struct.pack('<BBI', 0, 0, 1000) + b'abcd'))
    assert small.read_frames()[0]['regions'] == [(0, b'abcd')]
    small.stop()
    assert transport.rtt_mask == 2 and not transport.watch_running

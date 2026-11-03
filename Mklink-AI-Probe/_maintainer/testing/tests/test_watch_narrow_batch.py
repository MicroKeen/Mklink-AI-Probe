"""Negotiated byte/halfword Watch batches through the real wire parser."""
import binascii
import json
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from mklink.dump_memory import DumpMemoryStreamSession, capture_dump_stream
from mklink.mux import MuxError, MuxTargetError, MuxTransport
from mklink.mux_watch import MuxWatchSession, PackedWatchSample
from mklink.superwatch import WatchItem, build_read_blocks, compile_frame_decoder
from test_watch_timing_v2 import bridge_for
from test_runtime_memory import batch
from test_runtime_watch_timing import shared_client


CAPS = 15 | (1 << 9) | (1 << 10)
ADDRESS = 0x58021010


def wire(op, payload, *, request=1, version=1, epoch=17):
    header = struct.pack('<4sBBHII', b'MLX1', version, op, len(payload), epoch, request)
    raw = header + payload
    return raw if version == 2 else raw + struct.pack('<I', binascii.crc32(raw) & 0xffffffff)


def batch_payload(width, values, timestamps=None):
    timestamps = timestamps if timestamps is not None else range(len(values))
    return bytes([0, 9, len(values), width]) + b''.join(
        struct.pack('<I', t) + v.to_bytes(width, 'little') for t, v in zip(timestamps, values))


def peer(*, caps=CAPS, ack=None, status=0, stop_status=0, first_event=b'', partial=False, epoch=17):
    calls = []

    def write(request):
        _, _, op, size, _epoch, seq = struct.unpack_from('<4sBBHII', request)
        payload = request[16:16 + size]
        body = payload[8:] if 0x10 <= op < 0x40 else payload
        calls.append((op, body))
        if op == 1:
            answer = struct.pack('<IHH', caps, 256, 1)
        elif op == 4:
            answer = payload
        elif op in (0x32, 0x33):
            assert payload[:8] == transport.nonce
            if partial:
                return len(request) - 1
            period, = struct.unpack_from('<I', body)
            answer = (ack if ack is not None else struct.pack('<II', period, 360_000_000)
                      if op == 0x33 or caps & (1 << 9) else b'')
        else:
            answer = b''
        result = status if op in (0x32, 0x33) else stop_status if op == 0x31 else 0
        reply = wire(op | 0x80, bytes([result]) + answer, request=seq, epoch=epoch)
        if op in (0x32, 0x33) and not result:
            reply += first_event
        transport.feed(reply[:11])
        transport.feed(reply[11:])
        return len(request)

    transport = MuxTransport(write)
    transport.handshake()
    return transport, calls


@pytest.mark.parametrize('row', json.loads(
    Path(__file__).with_name('watch_narrow_batch_golden.json').read_text(encoding='utf-8'))['frames'],
    ids=lambda row: f"{row['width']}byte-{row['count']}samples")
@pytest.mark.parametrize('packed', [False, True])
def test_firmware_production_golden_frames(row, packed):
    # These bytes come from the firmware production packer, independently of
    # this test's encoder. Keep raw-v2 framing, exact widths and clock wrap.
    raw = bytes.fromhex(row['frame_hex'])
    epoch, = struct.unpack_from('<I', raw, 8)
    transport, calls = peer(caps=CAPS | 16, epoch=epoch)
    watch = MuxWatchSession(transport, [(ADDRESS, row['width'])], 4e-6)
    watch.start()
    assert calls[-1] == (0x33, struct.pack('<IBIB', 4, 1, ADDRESS, row['width']))
    for offset in range(0, len(raw), 7):
        transport.feed(raw[offset:offset + 7])
    frames = watch.read_frames(packed=packed)
    assert len(frames) == watch.samples == row['count']
    for i, frame in enumerate(frames):
        timestamp = frame.timestamp_us if packed else frame['timestamp_us']
        data = (frame.payload[frame.offset:frame.offset + row['width']]
                if packed else frame['regions'][0][1])
        assert timestamp == row['first_timestamp'] + i * row['step_us']
        assert data.hex() == row['value_hex']
    assert watch.gaps == watch.read_errors == 0
    assert transport.stats()['event_gaps'] == transport.stats()['watch_dropped_bytes'] == 0


@pytest.mark.parametrize('width', [1, 2])
@pytest.mark.parametrize('period,fastest,accepted', [(0, False, 2000), (0, True, 0), (4e-6, False, 4)])
def test_start_negotiates_exact_width_and_preserves_first_ack_adjacent_sample(width, period, fastest, accepted):
    maximum = (1 << (width * 8)) - 1
    transport, calls = peer(first_event=wire(0x41, batch_payload(width, [maximum])))
    session = DumpMemoryStreamSession(bridge_for(transport), [(ADDRESS, width)], period, fastest=fastest)
    session.packed_frames = True
    session.start()
    assert calls[-1] == (0x33, struct.pack('<IBIB', accepted, 1, ADDRESS, width))
    assert session.timing['accepted_period_us'] == accepted
    frame, = session.read_frames()
    assert isinstance(frame, PackedWatchSample)
    assert frame.payload[frame.offset:frame.offset + width] == maximum.to_bytes(width, 'little')
    assert session.stats['complete_samples'] == 1
    session.stop()
    assert not transport.watch_running and not session._mux_watch._narrow_batch


@pytest.mark.parametrize('caps', [15, 15 | (1 << 9)])
@pytest.mark.parametrize('width', [1, 2])
def test_new_host_old_firmware_uses_original_start_and_single_sample_events(caps, width):
    transport, calls = peer(caps=caps)
    watch = MuxWatchSession(transport, [(ADDRESS, width)], 4e-6)
    watch.start()
    assert calls[-1] == (0x32, struct.pack('<IBIB', 4, 1, ADDRESS, width))
    transport.feed(wire(0x41, struct.pack('<BBI', 0, 0, 12) + bytes([0xa5]) * width))
    assert watch.read_frames()[0]['regions'] == [(0, bytes([0xa5]) * width)]
    assert not watch._narrow_batch


@pytest.mark.parametrize('width', [1, 2])
@pytest.mark.parametrize('caps', [CAPS, CAPS & ~(1 << 9)])
def test_new_start_also_accepts_legacy_sample_path_used_by_jtag(width, caps):
    transport, calls = peer(caps=caps)
    watch = MuxWatchSession(transport, [(ADDRESS, width)], 4e-6)
    watch.start()
    assert calls[-1][0] == 0x33 and watch.timing['accepted_period_us'] == 4
    transport.feed(wire(0x41, struct.pack('<BBI', 0, 0, 12) + bytes([0xa5]) * width))
    assert watch.read_frames()[0]['regions'] == [(0, bytes([0xa5]) * width)]
    watch.stop()


@pytest.mark.parametrize('regions', [[(ADDRESS, 4)], [(ADDRESS, 16)], [(ADDRESS, 64)],
                                    [(ADDRESS + 1, 2)], [(ADDRESS, 3)],
                                    [(ADDRESS, 1), (ADDRESS + 4, 1)]])
def test_ineligible_layouts_keep_original_start_without_widening(regions):
    transport, calls = peer()
    watch = MuxWatchSession(transport, regions, 4e-6)
    watch.start()
    assert calls[-1] == (0x32, struct.pack('<IB', 4, len(regions)) + b''.join(
        struct.pack('<IB', address, width) for address, width in regions))
    assert not watch._narrow_batch


@pytest.mark.parametrize('width', [1, 2])
@pytest.mark.parametrize('version', [1, 2])
@pytest.mark.parametrize('packed', [False, True])
def test_full_batch_fragmentation_wrap_packed_offsets_and_signed_decode(width, version, packed):
    transport, calls = peer(caps=CAPS | 16)
    watch = MuxWatchSession(transport, [(ADDRESS, width)], 0, fastest=True)
    watch.start()
    maximum = (1 << (width * 8)) - 1
    values = [((i * 997) ^ maximum) & maximum for i in range(127)]
    timestamps = [(0xfffffff0 + i * 4) & 0xffffffff for i in range(127)]
    payload = batch_payload(width, values, timestamps)
    raw = wire(0x41, payload, version=version)
    for chunk in raw:
        transport.feed(bytes([chunk]))
    frames = watch.read_frames(packed=packed)
    assert len(frames) == 127
    item = WatchItem('narrow', ADDRESS, 'int8_t' if width == 1 else 'int16_t', width, source='svd')
    blocks = build_read_blocks([item])
    assert [(b.address, b.size) for b in blocks] == [(ADDRESS, width)]
    decoder = compile_frame_decoder([item], blocks)
    for i, frame in enumerate(frames):
        assert (frame.timestamp_us if packed else frame['timestamp_us']) == 0xfffffff0 + i * 4
        expected = values[i] - (1 << (width * 8)) if values[i] & (1 << (width * 8 - 1)) else values[i]
        assert decoder.decode(frame) == [float(expected)]
        if packed:
            assert frame.payload is frames[0].payload and frame.offset == 8 + i * (4 + width)
    assert watch.samples == 127 and watch.gaps == watch.read_errors == 0
    assert transport.stats()['event_gaps'] == transport.stats()['watch_dropped_bytes'] == 0
    assert transport.request(2) == b''  # Raw/CRC boundaries did not consume the following reply.


@pytest.mark.parametrize('width', [1, 2])
@pytest.mark.parametrize('enabled', [False, True])
def test_narrow_batches_require_acknowledged_current_subscription(width, enabled):
    transport, _ = peer()
    watch = MuxWatchSession(transport, [(ADDRESS, width)], 4e-6)
    if enabled:
        watch.start()
        watch.stop()
    transport.feed(wire(0x41, batch_payload(width, [1])))
    with pytest.raises(RuntimeError, match='Invalid multiplex watch batch'):
        watch.read_frames()
    assert watch.samples == 0


@pytest.mark.parametrize('ack', [b'', bytes(7), bytes(9), struct.pack('<II', 5, 360_000_000),
                                struct.pack('<II', 4, 0)])
def test_invalid_narrow_ack_stops_once_without_fallback_or_affecting_rtt(ack):
    transport, calls = peer(ack=ack)
    transport.rtt_mask = 2
    watch = MuxWatchSession(transport, [(ADDRESS, 1)], 4e-6)
    with pytest.raises(RuntimeError, match='WATCH_NARROW_BATCH START acknowledgement'):
        watch.start()
    assert [op for op, _ in calls if op >= 0x10] == [0x33, 0x31]
    assert not watch._narrow_batch and watch.timing is None
    assert transport.ready and not transport.watch_running and transport.rtt_mask == 2


def test_narrow_cleanup_failure_poisoned_without_replay():
    transport, calls = peer(ack=b'', stop_status=5)
    watch = MuxWatchSession(transport, [(ADDRESS, 2)], 4e-6)
    with pytest.raises(RuntimeError, match='stopping the unconfirmed capture failed'):
        watch.start()
    assert not transport.ready and transport.watch_running and not watch._narrow_batch
    assert [op for op, _ in calls if op >= 0x10] == [0x33, 0x31]


@pytest.mark.parametrize('partial', [False, True])
def test_failed_start_is_not_retried_as_legacy(partial):
    transport, calls = peer(status=1, partial=partial)
    watch = MuxWatchSession(transport, [(ADDRESS, 2)], 4e-6)
    with pytest.raises(MuxError if partial else MuxTargetError):
        watch.start()
    assert [op for op, _ in calls if op >= 0x10] == [0x33]
    assert not watch._narrow_batch and watch.timing is None


@pytest.mark.parametrize('width', [1, 2])
@pytest.mark.parametrize('malformed', ['index', 'width', 'zero', 'too_many', 'short', 'extra'])
def test_bad_narrow_batches_never_publish_partial_samples(width, malformed):
    transport, _ = peer()
    watch = MuxWatchSession(transport, [(ADDRESS, width)], 4e-6)
    watch.start()
    payload = bytearray(batch_payload(width, [1, 2]))
    if malformed == 'index': payload[0] = 1
    elif malformed == 'width': payload[3] = 3 - width
    elif malformed == 'zero': payload[2] = 0
    elif malformed == 'too_many': payload = bytearray(batch_payload(width, [1] * 128))
    elif malformed == 'short': payload.pop()
    elif malformed == 'extra': payload.append(0)
    transport.feed(wire(0x41, payload))
    with pytest.raises(RuntimeError, match='Invalid multiplex watch batch'):
        watch.read_frames()
    assert watch.samples == 0


@pytest.mark.parametrize('width', [1, 2])
def test_legacy_events_and_errors_can_mix_with_narrow_batches(width):
    transport, calls = peer()
    session = DumpMemoryStreamSession(bridge_for(transport), [(ADDRESS, width)], 4e-6)
    session.start()
    events = [batch_payload(width, [1], [10]), struct.pack('<BBI', 0, 5, 11),
              struct.pack('<BBI', 0, 0, 12) + (2).to_bytes(width, 'little'),
              batch_payload(width, [3], [14])]
    transport.feed(b''.join(wire(0x41, p, request=i + 1) for i, p in enumerate(events)))
    assert [f['regions'][0][1] for f in session.read_frames()] == [i.to_bytes(width, 'little') for i in (1, 2, 3)]
    assert session.stats['complete_samples'] == 3 and session.stats['firmware_read_errors'] == 1
    assert session.stats['parser_dropped_frames'] == 1
    assert [op for op, _ in calls if op >= 0x10] == [0x33]
    transport.feed(wire(0x41, struct.pack('<BBI', 0, 8, 15), request=5))
    with pytest.raises(RuntimeError, match='reset recovery timed out'):
        session.read_frames()
    assert not session._mux_watch._narrow_batch


@pytest.mark.parametrize('width', [1, 2])
def test_public_capture_returns_exact_narrow_bytes_and_counts(width):
    values = [0, (1 << (8 * width)) - 1, 0x55]
    transport, calls = peer(first_event=wire(0x41, batch_payload(width, values, [100, 104, 108])))
    device = SimpleNamespace(_bridge=bridge_for(transport))
    result = capture_dump_stream(device, [{'address': ADDRESS, 'size': width}],
                                 period=0, fastest=True, frames=3, duration=0)
    assert result['sample_count'] == 3 and result['total_bytes'] == 3 * width
    assert result['stats']['complete_samples'] == 3
    assert [s['timestamp_us'] for s in result['samples']] == [100, 104, 108]
    assert [s['regions'][0]['data_hex'] for s in result['samples']] == [v.to_bytes(width, 'little').hex() for v in values]
    assert [op for op, _ in calls if op >= 0x10] == [0x33, 0x31]


@pytest.mark.parametrize('width', [1, 2])
def test_shared_capture_ten_thousand_narrow_samples_with_clock_wrap(batch, monkeypatch, width):
    transport, calls = peer()
    batch[2]._bridge = bridge_for(transport)
    drain = transport.drain
    emitted = 0
    sequence = 0
    maximum = (1 << (width * 8)) - 1

    def produce(*args, **kwargs):
        nonlocal emitted, sequence
        if transport.watch_running and emitted < 10000:
            end = min(10000, emitted + 127)
            values = [(i * 997) & maximum for i in range(emitted, end)]
            timestamps = [(0xfffffff0 + i * 4) & 0xffffffff for i in range(emitted, end)]
            sequence += 1
            transport.feed(wire(0x41, batch_payload(width, values, timestamps), request=sequence))
            emitted = end
        return drain(*args, **kwargs)

    monkeypatch.setattr(transport, 'drain', produce)
    result = shared_client(batch, monkeypatch).call('capture_dump', {
        'regions': [{'address': ADDRESS, 'size': width}], 'period': 0,
        'fastest': True, 'frames': 10000, 'duration': 0})
    assert result['sample_count'] == 10000 and result['total_bytes'] == 10000 * width
    assert result['stopped_by'] == 'frames' and not result['incomplete_tail']
    for i, sample in enumerate(result['samples']):
        assert sample == {'sample_index': i, 'timestamp_us': 0xfffffff0 + i * 4,
                          'regions': [{'address': f'0x{ADDRESS:08X}', 'size': width,
                                       'data_hex': ((i * 997) & maximum).to_bytes(width, 'little').hex()}]}
    assert result['stats']['complete_samples'] == 10000
    assert not any(result['stats'].get(k, 0) for k in (
        'parser_crc_errors', 'parser_dropped_bytes', 'parser_dropped_frames', 'firmware_read_errors'))
    assert [op for op, _ in calls if op >= 0x10] == [0x33, 0x31]
    assert not transport.watch_running
    assert not batch[3].operation_lock.locked() and not batch[1]['resource_manager'].get_status()


@pytest.mark.parametrize('width', [1, 2])
def test_known_ram_gui_padding_retains_original_word_fast_path(width):
    transport, calls = peer()
    address = 0x20010000
    item = WatchItem('value', address, 'uint8_t' if width == 1 else 'uint16_t', width)
    blocks = build_read_blocks([item], ram_ranges=((address, address + 256),))
    assert [(b.address, b.size) for b in blocks] == [(address, 4)]
    watch = MuxWatchSession(transport, [(b.address, b.size) for b in blocks], 4e-6)
    watch.start()
    assert calls[-1] == (0x32, struct.pack('<IBIB', 4, 1, address, 4))
    transport.feed(wire(0x41, batch_payload(4, [0xa5bc43e7])))
    frame, = watch.read_frames(packed=True)
    assert compile_frame_decoder([item], blocks).decode(frame) == [float(0xe7 if width == 1 else 0x43e7)]

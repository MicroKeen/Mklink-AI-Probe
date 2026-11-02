import hashlib
import json
import uuid

import pytest

from mklink.rtt_subscription import RttByteSubscription
from mklink.remote.stream_protocol import (
    Frame, StreamType, encode_frame, RTT_CHANNEL_BYTES, RTT_BYTES_HEADER,
)
from test_remote_rtt_subscription import source


def frame(sequence, capture, offset, data, *, lost=0):
    return encode_frame(Frame(StreamType.RTT_RAW, RTT_CHANNEL_BYTES, 3, sequence,
                              0, len(data), RTT_BYTES_HEADER.pack(capture.bytes, offset, lost)+data))


def test_ten_mib_all_byte_values_one_persistent_socket(source):
    info, publish = source
    capture = uuid.uuid4()
    data = bytes(range(256))*64
    actual, expected = hashlib.sha256(), hashlib.sha256()
    with RttByteSubscription(info, 1, session=capture.hex) as reader:
        for i in range(640):
            publish(frame(i+1, capture, i*len(data), data))
            page = reader.read(2)
            actual.update(page['data'])
            expected.update(data)
            assert not any(page[k] for k in ('missing_batches', 'lost_bytes', 'mux_dropped_bytes'))
        assert reader.cursor == 10*1024*1024
        assert actual.digest() == expected.digest()
        assert reader.read(.001)['data'] == b''


def test_drops_and_capture_replacement_are_explicit(source):
    info, publish = source
    capture = uuid.uuid4()
    with RttByteSubscription(info) as reader:
        publish(frame(1, capture, 100, b'ab'))
        assert reader.read(2)['data'] == b'ab'
        publish(frame(3, capture, 107, b'c', lost=128))
        page = reader.read(2)
        assert (page['missing_batches'], page['lost_bytes'], page['mux_dropped_bytes']) == (1, 5, 128)
        publish(frame(4, uuid.uuid4(), 0, b'new'))
        with pytest.raises(RuntimeError, match='capture changed'):
            reader.read(2)


def test_heartbeat_does_not_hide_missing_data_sequence(source):
    info, publish = source
    with RttByteSubscription(info) as reader:
        publish(encode_frame(Frame(StreamType.CONTROL, 0, 3, 20, 0, 0, json.dumps({'last_sequence': 20}).encode())))
        assert reader.read(2)['data'] == b''
        publish(frame(21, uuid.uuid4(), 0, b'next'))
        assert reader.read(2)['missing_batches'] == 20


def test_dashboard_publishes_unchanged_bytes_before_text_decoding():
    from types import SimpleNamespace
    from mklink.remote.dashboards import RttStreamManager
    calls = []
    manager = RttStreamManager()
    manager._capture_session = uuid.uuid4().hex
    manager._byte_hubs = {1: SimpleNamespace(has_subscribers=True, publish=lambda data, **kw: calls.append((data, kw)))}
    manager._device = SimpleNamespace(_rtt_session=SimpleNamespace(dropped_bytes={1: 7}))
    payload = bytes(range(256))*129
    manager.feed_channel_bytes(1, payload)
    assert b''.join(data[32:] for data, _ in calls) == payload
    assert [RTT_BYTES_HEADER.unpack_from(data)[1] for data, _ in calls] == [0, 16384, 32768]
    assert all(RTT_BYTES_HEADER.unpack_from(data)[2] == 7 for data, _ in calls)
    assert all(kw['flags'] == RTT_CHANNEL_BYTES for _, kw in calls)

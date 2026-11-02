"""Shared capture keeps runtime admission and negotiated timing through real MUX frames."""
import struct
from unittest.mock import Mock

import pytest

from mklink.mux import packet
from mklink.runtime import RuntimeClient, RuntimeErrorResponse
from mklink.runtime_api import Session
from test_runtime_memory import batch
from test_watch_timing_v2 import bridge_for, peer


REGIONS = [{'address': 0x20000000, 'size': 4}]


def feed_samples(monkeypatch, transport, count):
    """Produce bounded batches only after START, through the real CRC parser."""
    drain = transport.drain
    emitted = 0

    def produce(*args, **kwargs):
        nonlocal emitted
        if transport.watch_running and emitted < count:
            # This peer negotiated a 256-byte payload: 4-byte batch header
            # plus at most 31 eight-byte timestamp/value pairs.
            end = min(count, emitted + 31)
            body = bytes([0, 9, end - emitted, 4])
            body += b''.join(struct.pack('<II', (2**32 - 64 + i) & 0xffffffff, i)
                             for i in range(emitted, end))
            transport.feed(packet(0x41, 17, emitted + 1, body))
            emitted = end
        return drain(*args, **kwargs)

    monkeypatch.setattr(transport, 'drain', produce)


def shared_client(batch, monkeypatch):
    http, state, device, control, _ = batch
    control.sessions['timing-test'] = Session(state['project_root'], None)

    def request(info, method, path, body, **kwargs):
        response = http.request(method, path, json=body)
        if response.status_code >= 400:
            raise RuntimeErrorResponse(response.text)
        return response.json()

    monkeypatch.setattr('mklink.runtime.request', request)
    client = RuntimeClient(info=control.info)
    client.session_id = 'timing-test'
    return client


@pytest.mark.parametrize('timing_v2,period,fastest', [
    (False, 1e-6, False), (True, 1e-6, False), (True, 0, True),
])
def test_shared_capture_10000_samples_roundtrips_ack_and_microsecond_wrap(batch, monkeypatch,
                                                                       timing_v2, period, fastest):
    _, state, device, control, _ = batch
    transport, calls = peer(timing_v2=timing_v2)
    device._bridge = bridge_for(transport)
    feed_samples(monkeypatch, transport, 10000)
    result = shared_client(batch, monkeypatch).call('capture_dump', {
        'regions': REGIONS, 'period': period, 'fastest': fastest, 'frames': 10000, 'duration': 0})
    assert result['sample_count'] == 10000 and result['total_bytes'] == 40000
    assert result['stopped_by'] == 'frames' and not result['incomplete_tail']
    assert [s['timestamp_us'] for s in result['samples']] == list(range(2**32 - 64, 2**32 - 64 + 10000))
    assert [s['regions'][0]['data_hex'] for s in result['samples']] == [struct.pack('<I', i).hex() for i in range(10000)]
    assert result['stats']['complete_samples'] == 10000
    assert not any(result['stats'].get(k, 0) for k in (
        'parser_crc_errors', 'parser_dropped_bytes', 'parser_dropped_frames', 'firmware_flagged_frames'))
    expected_period = 0 if fastest else 1
    assert result['timing'] == ({'mode': 'fastest' if fastest else 'periodic',
        'requested_period_us': expected_period, 'accepted_period_us': expected_period,
        'timebase_hz': 360_000_000} if timing_v2 else None)
    assert [op for op, _ in calls if op >= 0x10] == [0x32, 0x31]
    assert not transport.watch_running
    assert not control.operation_lock.locked() and not state['resource_manager'].get_status()


@pytest.mark.parametrize('timing_v2', [False, True])
def test_default_zero_still_returns_one_sample_with_no_fastest_wire_request(batch, monkeypatch, timing_v2):
    transport, calls = peer(timing_v2=timing_v2)
    batch[2]._bridge = bridge_for(transport)
    feed_samples(monkeypatch, transport, 3)
    result = shared_client(batch, monkeypatch).call('capture_dump', {'regions': REGIONS})
    assert result['sample_count'] == 1
    assert struct.unpack_from('<I', next(body for op, body in calls if op == 0x32))[0] == 2000
    assert (result['timing']['accepted_period_us'] if timing_v2 else result['timing']) == (2000 if timing_v2 else None)


@pytest.mark.parametrize('options', [
    {'fastest': 1}, {'fastest': 'true'}, {'fastest': None}, {'fastest': True, 'period': .001},
    {'fastest': False, 'frames': 2}, {'fastest': True, 'frames': 0, 'duration': 0},
])
def test_invalid_mode_rejected_by_client_and_backend_before_clock_or_stream(batch, monkeypatch, options):
    http, state, device, _, _ = batch
    device._bridge = Mock()
    device.set_debug_speed = Mock()
    request = Mock()
    monkeypatch.setattr('mklink.runtime.request', request)
    client = RuntimeClient(info={})
    client.session_id = 'one'
    body = {'regions': REGIONS, 'speed_profile': 'low', **options}
    with pytest.raises(ValueError):
        client.call('capture_dump', body)
    request.assert_not_called()
    response = http.post('/api/device/dump-memory/capture', json=body)
    assert response.status_code == 422, response.text
    device.set_debug_speed.assert_not_called()
    device._bridge.enable_multiplex.assert_not_called()
    assert not state['resource_manager'].get_status()


@pytest.mark.parametrize('failure', ['old_firmware', 'bad_ack', 'stop_failed', 'busy'])
def test_shared_fastest_failure_never_returns_partial_success_or_replays(batch, monkeypatch, failure):
    _, state, device, control, managers = batch
    transport, calls = peer(timing_v2=failure != 'old_firmware',
                            ack=b'' if failure == 'bad_ack' else None,
                            stop_status=5 if failure == 'stop_failed' else 0)
    device._bridge = bridge_for(transport)
    feed_samples(monkeypatch, transport, 2)
    if failure == 'busy':
        managers['rtt'].running = True
    with pytest.raises(RuntimeErrorResponse):
        shared_client(batch, monkeypatch).call('capture_dump', {
            'regions': REGIONS, 'period': 0, 'fastest': True, 'frames': 2})
    assert [op for op, _ in calls if op >= 0x10] == ([] if failure in ('old_firmware', 'busy') else [0x32, 0x31])
    if failure == 'busy':
        assert managers['rtt'].running
    assert not control.operation_lock.locked() and not state['resource_manager'].get_status()


def test_fastest_count_only_transport_budget_and_no_retry(monkeypatch):
    request = Mock(side_effect=RuntimeErrorResponse('response lost'))
    monkeypatch.setattr('mklink.runtime.request', request)
    client = RuntimeClient(info={})
    client.session_id = 'one'
    with pytest.raises(RuntimeErrorResponse, match='response lost'):
        client.call('capture_dump', {'regions': REGIONS, 'period': 0, 'fastest': True,
                                    'frames': 10000, 'duration': 0})
    assert request.call_count == 1 and request.call_args.kwargs['timeout'] == 320

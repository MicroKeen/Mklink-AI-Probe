"""One idle shared diagnostic; no stream stops, reconnects, clears or raw fallback."""
import struct
from unittest.mock import Mock

import pytest

from mklink.mux import packet
from mklink.runtime import RuntimeErrorResponse
from test_runtime_memory import batch
from test_runtime_watch_timing import REGIONS, feed_samples, shared_client
from test_watch_timing_v2 import bridge_for, peer


PATH = '/api/device/dump-memory/runtime-stats'
COUNTERS = (123, 10000, 0xffffffff, 0x80000000)


def stats_peer(batch, monkeypatch, *, body=struct.pack('<IIII', *COUNTERS), status=0,
               timing_v2=True, stop_status=0, write_error=False):
    transport, calls = peer(timing_v2=timing_v2, stop_status=stop_status)
    write = transport._write

    def reply(wire):
        _, _, op, size, _epoch, request = struct.unpack_from('<4sBBHII', wire)
        if op != 0x14:
            return write(wire)
        assert wire[16:16 + size] == transport.nonce
        calls.append((op, b''))
        if write_error:
            raise OSError('fixture transport failure')
        answer = packet(op | 0x80, 17, request, bytes([status]) + body)
        transport.feed(answer[:11])
        transport.feed(answer[11:])
        return len(wire)

    monkeypatch.setattr(transport, '_write', reply)
    bridge = bridge_for(transport)
    bridge._mux = transport
    batch[2]._bridge = bridge
    return transport, calls


@pytest.mark.parametrize('timing_v2', [False, True])
def test_stats_follow_confirmed_capture_stop_without_reset_or_unit_conversion(batch, monkeypatch, timing_v2):
    transport, calls = stats_peer(batch, monkeypatch, timing_v2=timing_v2)
    feed_samples(monkeypatch, transport, 10000)
    client = shared_client(batch, monkeypatch)
    capture = client.call('capture_dump', {'regions': REGIONS, 'period': 1e-6,
                                         'frames': 10000, 'duration': 0})
    assert capture['sample_count'] == 10000
    batch[2]._bridge.enable_multiplex = Mock(side_effect=AssertionError('must not reopen'))
    result = client.call('watch_runtime_stats')
    assert result == dict(zip(('batches', 'collected', 'collect_cycles', 'pack_cycles'), COUNTERS))
    assert [op for op, _ in calls if op >= 0x10] == [0x32, 0x31, 0x14]
    assert transport.ready and not transport.sampling
    batch[2]._bridge.enable_multiplex.assert_not_called()
    assert not batch[1]['resource_manager'].get_status() and not batch[3].operation_lock.locked()


@pytest.mark.parametrize('blocker', ['no_mux', 'unready', 'watch', 'rtt', 'operation',
                                     'dashboard_rtt', 'dashboard_superwatch', 'dashboard_systemview', 'dashboard_vofa',
                                     'nonshared', 'stale_session'])
def test_unavailable_or_busy_diagnostic_does_not_take_or_stop_resources(batch, monkeypatch, blocker):
    transport, calls = stats_peer(batch, monkeypatch)
    http, state, device, control, managers = batch
    client = shared_client(batch, monkeypatch)
    for manager in managers.values():
        manager.stop = Mock()
    if blocker == 'no_mux':
        device._bridge._mux = None
    elif blocker == 'unready':
        transport.ready = False
    elif blocker == 'watch':
        transport.watch_running = True
    elif blocker == 'rtt':
        transport.rtt_mask = 1
    elif blocker.startswith('dashboard_'):
        managers[blocker.removeprefix('dashboard_')].running = True
    elif blocker == 'nonshared':
        state['shared_runtime'] = False
    elif blocker == 'stale_session':
        control.sessions.clear()
    elif blocker == 'operation':
        monkeypatch.setattr(control.operation_lock, 'locked', lambda: True)
    with pytest.raises(RuntimeErrorResponse):
        client.call('watch_runtime_stats')
    assert [op for op, _ in calls if op >= 0x10] == []
    for manager in managers.values():
        manager.stop.assert_not_called()
    assert transport.watch_running == (blocker == 'watch')
    assert transport.rtt_mask == (1 if blocker == 'rtt' else 0)
    assert not state['resource_manager'].get_status()


@pytest.mark.parametrize('body', [b'', bytes(15), bytes(17)])
def test_malformed_stats_are_rejected_not_zero_filled_or_retried(batch, monkeypatch, body):
    transport, calls = stats_peer(batch, monkeypatch, body=body)
    response = batch[0].post(PATH, json={})
    assert response.status_code == 502 and '16 bytes' in response.text
    assert [op for op, _ in calls if op >= 0x10] == [0x14]
    assert transport.ready


@pytest.mark.parametrize('status,http_status', [(1, 501), (5, 502), (6, 409)])
def test_firmware_rejection_is_reported_without_fallback(batch, monkeypatch, status, http_status):
    _, calls = stats_peer(batch, monkeypatch, status=status)
    response = batch[0].post(PATH, json={})
    assert response.status_code == http_status and f'firmware status {status}' in response.text
    assert [op for op, _ in calls if op >= 0x10] == [0x14]


def test_unknown_arguments_rejected_at_shared_and_direct_entry(batch, monkeypatch):
    _, calls = stats_peer(batch, monkeypatch)
    with pytest.raises(RuntimeErrorResponse, match='no arguments'):
        shared_client(batch, monkeypatch).call('watch_runtime_stats', {'reset': True})
    assert batch[0].post(PATH, json={'reset': True}).status_code == 422
    assert [op for op, _ in calls if op >= 0x10] == []


def test_failed_capture_stop_cannot_be_followed_by_stats_query(batch, monkeypatch):
    transport, calls = stats_peer(batch, monkeypatch, stop_status=5)
    feed_samples(monkeypatch, transport, 2)
    client = shared_client(batch, monkeypatch)
    with pytest.raises(RuntimeErrorResponse):
        client.call('capture_dump', {'regions': REGIONS})
    with pytest.raises(RuntimeErrorResponse, match='confirmed stopped'):
        client.call('watch_runtime_stats')
    assert [op for op, _ in calls if op >= 0x10] == [0x32, 0x31]


def test_stats_transport_failure_invalidates_without_retry_or_reopen(batch, monkeypatch):
    transport, calls = stats_peer(batch, monkeypatch, write_error=True)
    client = shared_client(batch, monkeypatch)
    for _ in range(2):
        with pytest.raises(RuntimeErrorResponse):
            client.call('watch_runtime_stats')
    assert not transport.ready
    assert [op for op, _ in calls if op >= 0x10] == [0x14]

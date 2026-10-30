"""Software reset shares the framed acquisition session without replay."""
import struct
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from mklink.device import Device
from mklink.mux import MuxTransport, packet
from mklink.remote.api import create_app
from mklink.remote.resource_manager import ResourceGroup
from mklink.runtime_api import install_runtime
from test_runtime_jobs import terminal


@pytest.fixture
def capturing(monkeypatch, tmp_path):
    managers = {name: SimpleNamespace(running=name in ('rtt', 'superwatch'), stop=Mock())
                for name in ('rtt', 'superwatch', 'systemview', 'vofa', 'serial', 'modbus')}
    monkeypatch.setattr('mklink.remote.dashboards.get_managers', lambda: managers)
    monkeypatch.setattr('mklink.probes.inventory', lambda: [])
    app = create_app(project_root=str(tmp_path))
    state = app.state.mklink_state
    transport = MuxTransport(lambda data: len(data))
    transport.ready = True
    transport.capabilities = 0xffffffff
    transport.epoch = 17
    transport.rtt_mask = 1
    transport.watch_running = True
    transport.software_reset = Mock()
    device = Device(project_root=str(tmp_path))
    device._connected = True
    device._bridge = SimpleNamespace(_mux=transport, _mux_supported=True, state=None,
                                     send_command=Mock(side_effect=AssertionError('No raw commands')))
    device.close = Mock()
    state['device'] = device
    resource = state['resource_manager']
    resource.acquire(ResourceGroup.MUX_RTT, 'user:dashboard:rtt')
    resource.acquire(ResourceGroup.MUX_WATCH, 'user:dashboard:superwatch')
    control = install_runtime(app, {'port':8765, 'token':'fixture', 'instance_id':'fixture',
                                   'jobs_path':str(tmp_path/'jobs.json')})
    with TestClient(app, base_url='http://127.0.0.1:8765', headers={'X-Auth-Token':'fixture'}) as client:
        yield client, state, control, transport, managers
        state['device'] = None


def request_reset(client, request_id='reset-once'):
    return client.post('/api/runtime/jobs/', json={
        'action':'reset', 'request_id':request_id, 'confirm':True,
    })


def assert_captures_kept(state, transport, managers):
    assert transport.epoch == 17 and transport.rtt_mask == 1 and transport.watch_running
    assert managers['rtt'].running and managers['superwatch'].running
    for manager in managers.values():
        manager.stop.assert_not_called()
    status = state['resource_manager'].get_status()
    assert set(status) == {'mux_rtt', 'mux_watch'}
    assert status['mux_rtt']['owner'] == 'user:dashboard:rtt'
    assert status['mux_watch']['owner'] == 'user:dashboard:superwatch'


def test_reset_job_keeps_both_captures_and_deduplicates(capturing):
    client, state, _, transport, managers = capturing
    event = struct.pack('<BBI', 0, 0, 100) + b'before reset\n'
    transport.feed(packet(0x40, 17, 1, event))
    accepted = request_reset(client)
    assert accepted.status_code == 202, accepted.text
    result = terminal(client, accepted.json()['job_id'])
    assert result['state'] == 'succeeded', result
    assert result['result'] == {'status':'ok', 'stopped':[]}
    assert request_reset(client).json()['job_id'] == result['job_id']
    transport.software_reset.assert_called_once_with()
    assert transport.drain(0x40, 0) == [event]
    assert_captures_kept(state, transport, managers)


@pytest.mark.parametrize('failure', [RuntimeError('reset not observed'), TimeoutError('reply lost')])
def test_reset_failure_does_not_stop_or_replay_capture(capturing, failure):
    client, state, _, transport, managers = capturing
    transport.software_reset.side_effect = failure
    accepted = request_reset(client)
    assert accepted.status_code == 202, accepted.text
    result = terminal(client, accepted.json()['job_id'])
    assert result['state'] == 'unknown'
    assert request_reset(client).json()['job_id'] == result['job_id']
    transport.software_reset.assert_called_once_with()
    assert_captures_kept(state, transport, managers)


def test_unadvertised_reset_cannot_interrupt_or_stop_capture(capturing):
    client, state, _, transport, managers = capturing
    transport.capabilities = 31
    assert request_reset(client).status_code == 409
    transport.software_reset.assert_not_called()
    assert_captures_kept(state, transport, managers)


def test_reset_still_excludes_flash_and_other_control_jobs(capturing):
    client, state, control, transport, managers = capturing
    control.jobs.jobs['existing'] = {'job_id':'existing', 'state':'running', 'request_id':'other'}
    assert request_reset(client).status_code == 409
    transport.software_reset.assert_not_called()
    control.jobs.jobs.clear()
    assert_captures_kept(state, transport, managers)


@pytest.mark.parametrize('status', [0, 5, 6])
def test_reset_wire_keeps_events_and_never_falls_back(status):
    from mklink.mux import MuxTargetError
    calls = []
    def write(wire):
        _, _, op, size, epoch, request = struct.unpack_from('<4sBBHII', wire)
        calls.append((op, wire[16:16+size]))
        transport.feed(packet(0x40, 17, 1, struct.pack('<BBI', 0, 0, 1)+b'boot\n'))
        transport.feed(packet(op|0x80, epoch, request, bytes([status])))
        return len(wire)
    transport = MuxTransport(write)
    transport.epoch, transport.ready = 17, True
    transport.capabilities = transport.SOFTWARE_RESET_CAPABILITY
    transport.rtt_mask, transport.watch_running = 1, True
    if status:
        with pytest.raises(MuxTargetError):
            transport.software_reset()
    else:
        transport.software_reset()
    assert calls == [(transport.SOFTWARE_RESET_COMMAND, transport.nonce)]
    assert transport.drain(0x40, 0)[0][6:] == b'boot\n'
    assert transport.epoch == 17 and transport.ready and transport._error is None
    assert transport.rtt_mask == 1 and transport.watch_running


def test_reset_capability_is_checked_before_any_wire_write():
    write = Mock()
    transport = MuxTransport(write)
    transport.capabilities = 31
    with pytest.raises(RuntimeError, match='firmware'):
        transport.software_reset()
    write.assert_not_called()


def test_malformed_reset_reply_is_unknown_without_retry():
    transport = MuxTransport(Mock())
    transport.capabilities = transport.SOFTWARE_RESET_CAPABILITY
    transport.request = Mock(return_value=b'not-empty')
    with pytest.raises(ConnectionError, match='outcome unknown'):
        transport.software_reset()
    transport.request.assert_called_once_with(transport.SOFTWARE_RESET_COMMAND)


@pytest.mark.parametrize('status', [0, 5])
@pytest.mark.parametrize('consume_old_before_reset', [True, False])
def test_watch_parts_never_join_across_reset_even_when_new_first_part_is_lost(status, consume_old_before_reset):
    from mklink.mux import MuxTargetError
    from mklink.mux_watch import MuxWatchSession
    def write(wire):
        _, _, op, _, epoch, request = struct.unpack_from('<4sBBHII', wire)
        transport.feed(packet(op|0x80, epoch, request, bytes([status])))
        return len(wire)
    transport = MuxTransport(write)
    transport.epoch, transport.ready = 17, True
    transport.capabilities = transport.SOFTWARE_RESET_CAPABILITY
    watch = MuxWatchSession(transport, [(0x20000000, 130)], .001)
    def part(seq, index, data):
        transport.feed(packet(0x41, 17, seq, struct.pack('<BBI', index, 0, seq)+data))
    part(1, 0, b'A'*128)
    part(2, 1, b'aa')  # A complete old sample must be retained.
    part(3, 0, b'B'*128)  # An incomplete old sample must never be completed by new data.
    old = watch.read_frames() if consume_old_before_reset else []
    if status:
        with pytest.raises(MuxTargetError): transport.software_reset()
    else:
        transport.software_reset()
    part(5, 1, b'cc')  # Simulate a lost post-reset index 0.
    part(6, 0, b'D'*128)
    part(7, 1, b'dd')
    values = [frame['regions'][0][1] for frame in old + watch.read_frames()]
    assert values == [b'A'*128+b'aa', b'D'*128+b'dd']


def test_busy_reset_does_not_change_watch_generation():
    from mklink.mux import MuxTargetError
    def write(wire):
        _, _, op, _, epoch, request = struct.unpack_from('<4sBBHII', wire)
        transport.feed(packet(op|0x80, epoch, request, b'\x06'))
        return len(wire)
    transport = MuxTransport(write)
    transport.epoch = 17
    transport.capabilities = transport.SOFTWARE_RESET_CAPABILITY
    with pytest.raises(MuxTargetError): transport.software_reset()
    assert transport._reset_generation == 0


@pytest.mark.parametrize('stream', ['rtt', 'superwatch'])
def test_recovery_timeout_reports_reset_context_without_poisoning_other_stream(stream):
    from mklink.mux_watch import MuxWatchSession
    from mklink.mux_rtt import MuxRTTSession
    transport = MuxTransport(Mock())
    transport.epoch = 17
    if stream == 'rtt':
        session = MuxRTTSession(transport, {'down_buffers': []}, channels=[0])
        transport.request = Mock(return_value=b'')
        session.start('0x20000000')
        opcode, read = 0x40, lambda: session.read_channels(0)
    else:
        session = MuxWatchSession(transport, [(0x20000000, 4)], .001)
        opcode, read = 0x41, session.read_frames
    transport.feed(packet(opcode, 17, 1, struct.pack('<BBI', 0, 8, 100)))
    with pytest.raises(RuntimeError, match='reset recovery timed out'):
        read()
    assert transport._error is None
    transport._write.assert_not_called()

"""Ordinary shared memory operations negotiate binary transport without capture."""
import struct
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from mklink._types import DeviceState
from mklink.bridge import MKLinkSerialBridge
from mklink.device import Device, DeviceNotConnectedError
from mklink.mux import MuxError, MuxTargetError, packet
from mklink.remote.api import create_app
from mklink.runtime_api import install_runtime


@pytest.fixture
def target(tmp_path):
    bridge = MKLinkSerialBridge('TEST_MEMORY_MUX')
    bridge._ctx.state = DeviceState.READY
    bridge._mux_marker = tmp_path / 'mux'
    bridge.send_command = Mock(return_value='V4\nMUX_TARGET=1\n')
    memory = bytearray(range(256)) * 16
    frames = []
    failures = {}

    def write(wire):
        if wire == b'~MKLINK-MUX1\n':
            frames.append(('enter', b''))
            return len(wire)
        _, _, op, size, epoch, request = struct.unpack_from('<4sBBHII', wire)
        payload = wire[16:16 + size]
        if 0x10 <= op < 0x40:
            assert payload[:8] == bridge._mux.nonce
            payload = payload[8:]
        frames.append((op, payload))
        failure = failures.get(op)
        if failure == 'timeout':
            # Use the production deadline path without a three-second sleep.
            pending = bridge._mux._pending
            bridge._mux._pending = (*pending[:2], 0, pending[3])
            return len(wire)
        answer = {1: struct.pack('<IHH', 15, 256, 1), 4: payload,
                  0x10: bytes(15) + b'\x02'}.get(op, b'')
        if op == 0x11:
            address, count = struct.unpack('<IH', payload)
            answer = memory[address - 0x20000000:address - 0x20000000 + count]
        elif op == 0x12:
            address = struct.unpack_from('<I', payload)[0]
            memory[address - 0x20000000:address - 0x20000000 + len(payload) - 4] = payload[4:]
        bridge._mux.feed(packet(op | 0x80, 17, request, bytes([failure or 0]) + answer))
        return len(wire)

    bridge._serial = SimpleNamespace(write=write)
    device = Device(project_root=str(tmp_path))
    device._connected, device._bridge = True, bridge
    yield device, bridge, memory, frames, failures
    if bridge._mux is not None:
        bridge._mux.close()


@pytest.mark.parametrize('first', ['read', 'write'])
def test_first_operation_claims_once_and_reuses_native_frames(target, first):
    device, bridge, memory, frames, _ = target
    data = bytes(reversed(range(256))) + b'last'
    if first == 'read':
        assert device.read_memory(0x20000000, len(data)) == bytes(memory[:len(data)])
    device.write_memory(0x20000000, data)
    assert device.read_memory(0x20000000, len(data)) == data
    assert [op for op, _ in frames[:4]] == ['enter', 1, 4, 0x10]
    assert sum(op == 1 for op, _ in frames) == 1
    assert [len(payload) - 4 for op, payload in frames if op == 0x12] == [128, 128, 4]
    assert all(op in ('enter', 1, 4, 0x10, 0x11, 0x12) for op, _ in frames)
    assert not bridge._mux.sampling
    bridge.send_command.assert_called_once_with('cmd.get_version()', timeout=3.0)


def test_explicitly_unsupported_uses_legacy_and_caches_capabilities(target):
    device, bridge, _, frames, _ = target
    bridge.send_command.side_effect = ['V4\nDUMP_WRITE=1\n', '20000000 01 02 03 04\n', '']
    assert device.read_memory(0x20000000, 4) == bytes([1, 2, 3, 4])
    device.write_memory(0x20000000, b'1234')
    commands = [call.args[0] for call in bridge.send_command.call_args_list]
    assert commands[0] == 'cmd.get_version()'
    assert commands[1].startswith('cmd.read_ram(')
    assert commands[2].startswith('cmd.flush_memory(')
    assert not frames


@pytest.mark.parametrize('operation', ['read', 'write'])
def test_capability_query_failure_is_not_unsupported(target, operation):
    device, bridge, _, frames, _ = target
    bridge.send_command.side_effect = TimeoutError('version response lost')
    with pytest.raises(TimeoutError):
        if operation == 'read':
            device.read_memory(0x20000000, 4)
        else:
            device.write_memory(0x20000000, b'1234')
    assert bridge.send_command.call_count == 1 and not frames
    assert bridge._mux_supported is None


@pytest.mark.parametrize('op', [1, 0x11, 0x12])
def test_transition_or_memory_timeout_never_falls_back_or_replays(target, op):
    device, bridge, _, frames, failures = target
    failures[op] = 'timeout'
    with pytest.raises(MuxError):
        if op == 0x11:
            device.read_memory(0x20000000, 256)
        else:
            device.write_memory(0x20000000, bytes(256))
    before = list(frames)
    with pytest.raises(DeviceNotConnectedError):
        device.read_memory(0x20000000, 4)
    assert frames == before and sum(code == op for code, _ in frames) == 1
    bridge.send_command.assert_called_once_with('cmd.get_version()', timeout=3.0)


def test_unknown_target_write_stops_before_next_chunk(target):
    device, bridge, _, frames, failures = target
    failures[0x12] = 5
    with pytest.raises(MuxTargetError, match='unknown outcome'):
        device.write_memory(0x20000000, bytes(256))
    assert sum(op == 0x12 for op, _ in frames) == 1
    bridge.send_command.assert_called_once()


@pytest.mark.parametrize('state', [DeviceState.RTT_STREAM, DeviceState.DUMP_STREAM, DeviceState.SYSTEMVIEW_STREAM])
def test_cached_support_does_not_enter_mux_from_legacy_capture(target, state):
    device, bridge, _, frames, _ = target
    bridge._mux_supported = True
    bridge._ctx.state = state
    with pytest.raises(ConnectionError, match='not ready'):
        device.read_memory(0x20000000, 4)
    assert not frames
    bridge.send_command.assert_not_called()


def test_public_write_verify_then_batch_read_uses_same_mux(target, monkeypatch, tmp_path):
    device, bridge, _, frames, _ = target
    managers = {name: SimpleNamespace(running=False) for name in ('rtt', 'superwatch', 'systemview', 'vofa', 'serial', 'modbus')}
    monkeypatch.setattr('mklink.remote.dashboards.get_managers', lambda: managers)
    app = create_app(project_root=str(tmp_path))
    state = app.state.mklink_state
    state['device'] = device
    install_runtime(app, {'port': 8765, 'token': 'fixture', 'instance_id': 'fixture'})
    with TestClient(app, base_url='http://127.0.0.1:8765', headers={'X-Auth-Token': 'fixture'}) as client:
        response = client.post('/api/device/write-memory', json={'address': '0x20000000', 'data_hex': '01020304', 'verify': True})
        assert response.status_code == 200, response.text
        assert response.json() == {'status': 'ok', 'address': '0x20000000', 'bytes_written': 4, 'verified': True}
        response = client.post('/api/device/read-memory-regions', json={'regions': [{'address': 0x20000000, 'size': 4}]})
        assert response.status_code == 200, response.text
        assert response.json()['regions'][0]['hex'] == '01020304'
        assert [op for op, _ in frames] == ['enter', 1, 4, 0x10, 0x12, 0x11, 0x11]
        assert not state['resource_manager'].get_status()
        state['device'] = None


@pytest.mark.parametrize('data,verify', [(bytes(range(256)) * 16, False), (bytes(4096), True)])
def test_client_write_deadline_covers_legacy_and_native_without_replay(monkeypatch, data, verify):
    from mklink.memory_write import plan_flush_batches
    from mklink.runtime import RuntimeClient, RuntimeErrorResponse
    request = Mock(side_effect=RuntimeErrorResponse('response lost'))
    monkeypatch.setattr('mklink.runtime.request', request)
    client = RuntimeClient()
    client.session_id, client.info = 'test', {}
    with pytest.raises(RuntimeErrorResponse, match='response lost'):
        client.call('write_memory', {'address': '0x20000000', 'data_hex': data.hex(), 'verify': verify})
    request.assert_called_once()
    budget = request.call_args.kwargs['timeout']
    assert budget >= 10 * len(plan_flush_batches([(0x20000000, data)])) + 15
    assert budget >= 96 * (2 if verify else 1) + 15

"""Profile reset and target-power recovery on the shared USB connection."""
import struct
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from mklink._types import DeviceState
from mklink.device import Device
from mklink.mux import MuxTargetError, packet
from mklink.remote.api import create_app
from test_mux_profile_attach import profile_bridge


MIDR = 0x2D580000
TARGET = 0x0995C01D


@pytest.fixture
def attached(tmp_path, monkeypatch):
    monkeypatch.setattr('mklink.remote.dashboards._managers', {})
    bridge, _ = profile_bridge(tmp_path, profile=None)
    model = dict(midr=MIDR, target=TARGET)
    ops = []

    def wire(frame):
        if frame == b'~MKLINK-MUX1\n':
            return len(frame)
        _, _, op, size, _, request = struct.unpack_from('<4sBBHII', frame)
        data = frame[16:16 + size]
        ops.append(op)
        answer = b'\0'
        if op == 1:
            answer += struct.pack('<IHH', 0x6023, 256, 1)
        elif op == 4:
            answer += data
        elif op == 0x19:
            answer += struct.pack('<II', 0x6BA02477, model['target'])
        elif op == 0x18:
            kind, ap, _, addr, mask, expected = struct.unpack_from('<BBHIII', data, len(data) - 16)
            assert (ap, addr, mask) == (4, 0x40290004, 0xffff0000)
            if kind == 3 and expected != model['midr'] & mask:
                answer = b'\x05' + struct.pack('<BBBBI', 1, 4, 8, 8, model['midr'])
            else:
                answer += struct.pack('<BBBBI', 1, 4, 255, 0, model['midr'] if kind == 4 else 0)
        elif op == 0x11:
            answer += struct.pack('<I', model['midr'])
        elif op == 0x15:
            answer = b'\x05'
        else:
            assert op in {2, 3, 0x31}
        bridge._mux.feed(packet(op | 0x80, 17, request, answer))
        return len(frame)

    bridge._serial.write = wire
    device = Device(port='TEST_PROFILE', project_root=str(tmp_path))
    device._bridge = bridge
    device._hardware_target = bridge.identify_swd_target()
    device._attach_profile = bridge.attach_profile
    device._connected = True
    assert device.connected
    app = create_app(project_root=str(tmp_path))
    app.state.mklink_state['device'] = device
    return device, model, ops, TestClient(app)


@pytest.mark.parametrize('swap', ['same', 'different-part', 'different-dp'])
def test_start_reidentifies_only_original_target_after_status5(attached, swap):
    device, model, ops, client = attached
    mux = device._bridge._mux
    mux.watch_running = True
    sample = b'\0\0' + bytes(8)
    mux.feed(packet(0x41, 17, 1, sample))
    assert mux._queues
    with pytest.raises(MuxTargetError):
        mux.software_reset()
    mux.feed(packet(0x41, 17, 2, sample))
    assert not mux._queues
    status = client.get('/api/device/status').json()
    assert status['connected'] and status['target_binding_lost'] and status['target_attach'] is None
    mux.request(0x31)
    mux.watch_running = False
    port = device._bridge._serial
    if swap == 'different-part':
        model['midr'] = 0x2D380000
    if swap == 'different-dp':
        model['target'] = 0
    response = client.post('/api/dash/superwatch/start', json={})
    if swap == 'same':
        # No symbols/watch configured in this fixture. The start preflight already rebound AP4.
        assert device.connected, response.text
        assert device._bridge._mux.read_memory(0x40290004, 4) == struct.pack('<I', MIDR)
        assert client.get('/api/device/status').json()['target_attach']['profile'] == 'S32K344'
    else:
        assert response.status_code == 409 and response.json()['detail']['code'] == 'target_binding_unavailable'
        assert not device.connected and device.probe_connected
    assert device._bridge._serial is port and device.state is DeviceState.READY
    assert ops.count(0x15) == 1 and 0x13 not in ops
    assert ops.count(0x18) == (1 if swap == 'different-dp' else 2)


@pytest.mark.parametrize('result', ['ok', 'unknown', 'mismatch'])
def test_gui_reset_uses_confirmed_model_once_then_rebinds(attached, monkeypatch, result):
    device, model, ops, client = attached
    backend = Mock()
    backend.read_memory.return_value = struct.pack('<I', (MIDR if result != 'mismatch' else 0x2d380000))
    if result == 'unknown':
        backend.reset_run.side_effect = OSError('lost AP reset acknowledgement')
    monkeypatch.setattr('mklink.cmsis_dap.backend.PyOcdBackend', lambda: backend)
    monkeypatch.setattr('mklink.probes.select_probe', lambda port: dict(port=port, serial_number='ONLY_TEST'))
    response = client.post('/api/device/reset')
    backend.connect.assert_called_once_with(probe='ONLY_TEST', target='S32K344', frequency=1000000, connect_mode='attach')
    backend.disconnect.assert_called_once_with()
    if result == 'mismatch':
        backend.reset_run.assert_not_called()
    else:
        backend.reset_run.assert_called_once_with('software')
    if result == 'ok':
        assert response.status_code == 200, response.text
        assert response.json()['method'] == 'FunctionalReset' and device.connected
    else:
        assert response.status_code == 409 and not device.connected and device.probe_connected
        device.verify_capture_target()
        assert device.connected and backend.reset_run.call_count == int(result == 'unknown')
    assert 0x15 not in ops and 0x13 not in ops

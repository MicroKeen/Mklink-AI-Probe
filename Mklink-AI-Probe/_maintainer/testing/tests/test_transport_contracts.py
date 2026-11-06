"""Shared transport policy works without S3 names or implementation details."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink.bridge import MKLinkSerialBridge
from mklink.mux import MuxTransport


@pytest.mark.parametrize('floor,respond_after', [(0.0, 1.0), (60.0, 30.0)])
def test_command_budget_is_per_transport_and_does_not_replay(monkeypatch, floor, respond_after):
    from mklink._types import DeviceState
    bridge = MKLinkSerialBridge('test-deadline')
    bridge.command_timeout_floor = floor
    bridge._ctx.state = DeviceState.READY
    bridge._serial = Mock()
    clock = [0.0]
    monkeypatch.setattr('mklink.bridge.time.monotonic', lambda: clock[0])
    def wait(timeout):
        clock[0] += 1.0
        if clock[0] >= respond_after:
            bridge._response_buffer.append('OK\n>>> ')
            return True
        return False
    bridge._prompt_event = Mock(wait=wait)
    assert 'OK' in bridge.send_command('query', timeout=5.0)
    bridge._serial.write.assert_called_once_with(b'query\n')
    assert MKLinkSerialBridge('other').command_timeout_floor == 0.0


@pytest.mark.parametrize('value', [True, 0, -1, float('nan'), float('inf'), '60'])
def test_mux_rejects_invalid_deadline_before_writing(value):
    write = Mock()
    with pytest.raises(ValueError, match='timeout'):
        MuxTransport(write, command_timeout=value)
    write.assert_not_called()


@pytest.mark.parametrize('auto_recovery', [True, False])
def test_reader_retains_ownership_independently_of_reconnect_policy(auto_recovery):
    bridge = MKLinkSerialBridge('test-transport')
    bridge.auto_recovery = auto_recovery
    bridge.require_reader_exit = True
    bridge.reader_close_timeout = .01
    bridge._reader_thread = Mock(is_alive=Mock(return_value=True))
    bridge._serial = Mock(is_open=True)
    bridge._port_lock = Mock()
    with pytest.raises(ConnectionError, match='Reader still owns IO'):
        bridge.close()
    bridge._reader_thread.join.assert_called_once_with(timeout=.01)
    bridge._serial.close.assert_not_called()
    bridge._port_lock.release.assert_not_called()


@pytest.mark.parametrize('transport', ['s3-http', 'another-relay'])
def test_remote_transport_never_enumerates_local_usb(transport, monkeypatch, tmp_path):
    from mklink.probe_volumes import resolve_volume
    from mklink.runtime_probe import upgrade_firmware
    probe = dict(port='remote', transport=transport, local_usb=False, identity_stable=False)
    monkeypatch.setattr('mklink.probes.select_probe', lambda _: probe)
    scan = Mock(side_effect=AssertionError('Must not scan unrelated local devices'))
    monkeypatch.setattr('mklink.probe_volumes.volume_inventory', scan)
    with pytest.raises(RuntimeError, match='no local USB'):
        resolve_volume('remote')
    assert upgrade_firmware({'shared_probe_id': 'remote'}, tmp_path)['status'] == 'manual_required'
    scan.assert_not_called()


def test_algorithm_and_firmware_use_transport_providers(monkeypatch, tmp_path):
    from mklink.device import Device
    from mklink.flash import MKLinkFlash
    bridge = SimpleNamespace(upload_algorithm=Mock(return_value='/FLM/verified.flm'),
                             upload_firmware=Mock(return_value='/verified.bin'))
    device = Device.__new__(Device)
    device._bridge = bridge
    deploy = Mock(side_effect=AssertionError('No local USB fallback'))
    monkeypatch.setattr('mklink.cmsis_dap.algorithm_catalog.deploy_algorithm_to_probe', deploy)
    monkeypatch.setattr('mklink.flash.find_microkeen_disk', deploy)
    algorithm = object()
    assert device._deploy_flash_algorithm(algorithm) == '/FLM/verified.flm'
    assert MKLinkFlash(bridge)._copy_to_microkeen(str(tmp_path / 'firmware.bin')) == '/verified.bin'
    bridge.upload_algorithm.assert_called_once_with(algorithm)
    deploy.assert_not_called()

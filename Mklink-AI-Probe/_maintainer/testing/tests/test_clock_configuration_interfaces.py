"""Independent interface configuration is not permission to switch target mode."""
from unittest.mock import MagicMock, patch

import pytest

from mklink._types import DeviceContext, DeviceState
from mklink.capture_clock import V3_CLOCKS, clock_options, clock_snapshot, requested_clock, save_interface_clock
from mklink.device import Device
from mklink.project_config import load_config, save_config
from _maintainer.testing.tests.test_capture_clock import api_clock, v3_device


def test_first_split_preserves_legacy_shared_request_then_keeps_both_values():
    config = {'swd_clock': '30000000', 'debug_speed': 'ultra'}
    save_interface_clock(config, 'JTAG', 20000000)
    assert requested_clock(config, 'SWD') == 30000000
    assert requested_clock(config, 'JTAG') == 20000000
    save_interface_clock(config, 'SWD', 2000000)
    assert requested_clock(config, 'JTAG') == 20000000
    assert 'debug_speed' not in config
    save_interface_clock(config, 'JTAG')
    assert requested_clock(config, 'SWD') == 2000000


def test_new_interface_settings_default_to_ten_megahertz():
    config = {}
    save_interface_clock(config, 'SWD', 5000000)
    assert requested_clock(config, 'JTAG') == 10000000


@pytest.mark.parametrize('mode', ['SWD', 'JTAG'])
@pytest.mark.parametrize('hz', V3_CLOCKS)
def test_disconnected_full_catalog_is_saved_without_claiming_hardware_support(api_clock, tmp_path, mode, hz):
    client, dev, _ = api_clock
    # A retained bridge from a former connection must not restrict offline choices.
    dev._connected = False
    dev._bridge._firmware_capabilities = frozenset({'V4.7.1'})
    result = client.put('/api/config', json={'clock_interface': mode, 'clock_hz': hz})
    assert result.status_code == 200, result.text
    status = client.get('/api/device/debug-speed').json()
    assert status['interfaces'][mode]['requested_hz'] == hz
    for interface in ('SWD', 'JTAG'):
        assert status['interfaces'][interface]['clocks_hz'] == list(V3_CLOCKS)
        assert status['interfaces'][interface]['clock_source'] == 'configuration'
    assert status['active_interface'] == 'unknown' and status['applied_hz'] is None
    assert not status['connected']
    assert 1000 not in clock_options(None)['clocks_hz']
    dev._bridge.send_command.assert_not_called()


def test_saved_offline_clock_cannot_unlock_legacy_jtag_on_connection(api_clock, tmp_path):
    client, dev, _ = api_clock
    dev._connected = False
    result = client.put('/api/config', json={'clock_interface': 'JTAG', 'clock_hz': 5000})
    assert result.status_code == 200
    dev._connected = True
    dev._bridge._ctx.clock_interface = 'JTAG'
    dev._bridge._firmware_capabilities = frozenset({'V4.7.1'})
    status = client.get('/api/device/debug-speed').json()
    assert status['interfaces']['JTAG']['clocks_hz'] == [4000000,10000000,20000000,30000000]
    assert status['interfaces']['JTAG']['requested_hz'] == 5000
    result = client.post('/api/device/debug-speed', json={'interface':'JTAG', 'clock_hz':5000})
    assert result.status_code == 400
    dev._bridge.send_command.assert_not_called()
    assert load_config(str(tmp_path))['jtag_clock'] == '5000'


def test_preference_does_not_change_cached_interface_or_apply_frequency(api_clock, tmp_path):
    client, dev, _ = api_clock
    dev._bridge._ctx.clock_interface = 'SWD'
    dev._bridge._ctx.swd_clock_hz = 10000000
    response = client.put('/api/config', json={'clock_interface': 'JTAG', 'clock_hz': 20000000})
    assert response.status_code == 200, response.text
    for _ in range(3):
        status = client.get('/api/device/debug-speed').json()
        assert status['active_interface'] == status['interface'] == 'SWD'
        assert status['selected_interface'] == 'JTAG'
        assert status['interfaces']['SWD']['requested_hz'] == 10000000
        assert status['interfaces']['JTAG']['requested_hz'] == 20000000
        assert status['configured_hz'] == 10000000
        assert status['interfaces']['JTAG']['clocks_hz'] == [4000000,10000000,20000000,30000000]
    dev._bridge.send_command.assert_not_called()


@pytest.mark.parametrize('active', ['SWD', 'unknown'])
def test_wrong_or_unknown_interface_rejects_application_without_commands_or_saving(api_clock, tmp_path, active):
    client, dev, _ = api_clock
    dev._bridge._ctx.clock_interface = active
    result = client.post('/api/device/debug-speed', json={'interface': 'JTAG', 'clock_hz': 20000000})
    assert result.status_code == 400, result.text
    dev._bridge.send_command.assert_not_called()
    assert not load_config(str(tmp_path))


def test_apply_matching_interface_does_not_overwrite_other_saved_clock(api_clock, tmp_path):
    client, dev, _ = api_clock
    dev._bridge._ctx.clock_interface = 'SWD'
    save_config(str(tmp_path), {'clock_interface': 'JTAG', 'swd_clock': '10000000', 'jtag_clock': '30000000'})
    result = client.post('/api/device/debug-speed', json={'interface': 'SWD', 'clock_hz': 2000000})
    assert result.status_code == 200, result.text
    config = load_config(str(tmp_path))
    assert config['swd_clock'] == '2000000' and config['jtag_clock'] == '30000000'
    assert config['clock_interface'] == 'SWD'
    dev._bridge.send_command.assert_called_once()


@pytest.mark.parametrize('body', [
    {'clock_interface': 'JTAG', 'clock_hz': 2000000},
    {'clock_interface': 'jtag', 'clock_hz': 10000000},
    {'clock_hz': 10000000}, {'clock_interface': 'SWD', 'clock_hz': True},
    {'clock_interface': 'SWD', 'swd_clock': '10000000'},
])
def test_invalid_saved_interface_settings_are_rejected(api_clock, tmp_path, body):
    client, dev, _ = api_clock
    result = client.put('/api/config', json=body)
    assert result.status_code == 422, result.text
    dev._bridge.send_command.assert_not_called()
    assert not load_config(str(tmp_path))


@pytest.mark.parametrize('identity,mode,hz', [(0x2BA01477, 'SWD', 2000000), (0x1000563D, 'JTAG', 20000000)])
def test_connect_uses_actual_interface_clock_even_if_other_configuration_selected(tmp_path, identity, mode, hz):
    save_config(str(tmp_path), {'clock_interface': 'JTAG' if mode == 'SWD' else 'SWD',
                               'swd_clock': '2000000', 'jtag_clock': '20000000'})
    dev = Device(port='TEST', project_root=str(tmp_path), initialize_target_now=False)
    bridge = MagicMock()
    bridge.connect.return_value = True
    bridge.state = DeviceState.READY
    bridge._ctx = DeviceContext(state=DeviceState.READY)
    bridge.idcode = identity
    bridge._firmware_capabilities = frozenset()
    bridge.send_command.return_value = f'set clock {hz}\n{mode} profile={hz}'
    with patch('mklink.bridge.MKLinkSerialBridge', return_value=bridge), \
         patch('mklink.device.initialize_target', return_value=identity) as initialize:
        dev._connect()
    initialize.assert_called_once()
    bridge.send_command.assert_called_once()
    assert bridge.send_command.call_args.args[0] == f'cmd.set_swd_clock({hz})'
    assert dev.clock_hz == hz and not dev.clock_warning
    dev.close()


def test_unknown_target_keeps_saved_clocks_without_writing(tmp_path):
    save_config(str(tmp_path), {'clock_interface':'JTAG', 'swd_clock':'2000000', 'jtag_clock':'20000000'})
    dev = Device(port='TEST', project_root=str(tmp_path), initialize_target_now=False)
    bridge = MagicMock()
    bridge.connect.return_value = True
    bridge.state = DeviceState.READY
    bridge._ctx = DeviceContext(state=DeviceState.READY)
    bridge.idcode = 0
    bridge._firmware_capabilities = frozenset()
    with patch('mklink.bridge.MKLinkSerialBridge', return_value=bridge), \
         patch('mklink.device.initialize_target', return_value=0):
        dev._connect()
    bridge.send_command.assert_not_called()
    assert dev.connected and dev.clock_warning
    assert clock_snapshot(dev, load_config(str(tmp_path)))['active_interface'] == 'unknown'
    dev.close()

"""Exercise the headless shared attachment through the physical-bridge boundary."""

from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from mklink._types import DeviceContext, DeviceState
from mklink.device import Device, target_attach_status
from mklink.firmware_compatibility import FirmwareUpgradeRequired
from mklink.mux import MuxProfileError, PROFILE_DIAGNOSTIC
from mklink.project_config import save_config, save_project_info
from mklink.remote.api import create_app
from mklink.runtime_api import install_runtime


@pytest.fixture
def shared(tmp_path, monkeypatch):
    monkeypatch.setattr('mklink.hil_lock.LOCK_ROOT', tmp_path / 'hil-locks')
    class HardwareBridge(SimpleNamespace):
        def identify_swd_target(self, expected=None):
            from mklink.s32k3 import hardware_profile
            self.attach_profile = hardware_profile(0x0996001d)
            self.enable_multiplex()
            self.auto_recovery = False
            return dict(profile=self.current_mcu, mem_ap=4, source='SIUL2.MIDR1',
                        midr1=(0x2c00 | int(self.current_mcu[-3:])) << 16)

    bridge = HardwareBridge(
        state=DeviceState.READY, idcode=0, current_mcu='S32K314',
        _ctx=DeviceContext(), _transport_error=None, _mux=None,
        connect=Mock(return_value=True), close=Mock(),
        send_command=Mock(side_effect=AssertionError('Unexpected legacy target command')),
    )
    transport = Mock()
    transport.read_memory.return_value = bytes.fromhex('11223344')
    def claim():
        bridge._mux = transport
        transport.attach_profile = bridge.attach_profile
        return transport
    bridge.enable_multiplex = Mock(side_effect=claim)
    monkeypatch.setattr('mklink.transport_factory.create_bridge', lambda port: bridge)
    monkeypatch.setattr('mklink.remote.dashboards._managers', {})
    monkeypatch.setattr('mklink.probes.inventory', lambda: [
        {'probe_id': 'usb-test', 'port': 'TEST_PORT', 'serial_number': 'test', 'alias': ''}])
    def connect(**options):
        device = Device(**options)
        device._connect()
        return device
    monkeypatch.setattr('mklink.connect', connect)
    app = create_app(auth_token=None, project_root=str(tmp_path))
    info = {'port': 8765, 'token': 'fixture', 'instance_id': 'profile-test', 'probe_id': 'usb-test'}
    control = install_runtime(app, info)
    state = app.state.mklink_state
    with TestClient(app, base_url='http://127.0.0.1:8765',
                    headers={'X-Auth-Token': info['token']}) as client:
        yield client, control, state, bridge, transport
        if state['device'] is not None:
            state['device'].close()
        state['device'] = None


@pytest.mark.parametrize('selection', ['request', 'config', 'project_info'])
def test_headless_attach_reuses_acknowledged_ap_for_all_clients(tmp_path, shared, selection):
    client, _, state, bridge, transport = shared
    body = {'kind': 'mcp'}
    if selection == 'config':
        save_config(str(tmp_path), {'mcu_key': 's32k312', 'clock_interface': 'SWD'})
    elif selection == 'project_info':
        save_project_info(str(tmp_path), {'device': 'S32K312'})
    else:
        save_config(str(tmp_path), {'mcu_key': 'stm32f1'})
        body['mcu'] = 's32k314'
    assert client.get('/_runtime/status').json()['target_attach_version'] == 1
    result = client.post('/_runtime/attach', json=body)
    assert result.status_code == 200, result.text
    expected = {'profile': 'S32K314', 'mem_ap': 4, 'midr1': 0x2d3a0000, 'source': 'SIUL2.MIDR1'}
    assert result.json()['target_attach'] == expected
    assert result.json()['idcode'] == '0x0'
    session = result.json()['session_id']
    assert client.get('/api/device/status').json()['target_attach'] == expected
    joined = client.post('/_runtime/attach', json={'kind': 'cli', 'mcu': 'S32K314'})
    assert joined.status_code == 200, joined.text
    assert joined.json()['target_attach'] == expected
    assert bridge.auto_recovery is False
    bridge.enable_multiplex.assert_called_once_with()
    rejected = client.post('/api/device/connect', json={'mcu': 'stm32f1', 'reuse_connected': True})
    assert rejected.status_code == 409
    assert client.post('/_runtime/attach', json={'mcu': 'stm32f1'}).status_code == 409
    assert state['last_device_connection']['mcu'] == body.get('mcu')
    read = client.post('/_runtime/call', json={'session_id': session, 'capability': 'read_memory',
                                              'arguments': {'address': '0x20000000', 'size': 4}})
    assert read.status_code == 200, read.text
    assert read.json()['data_hex'] == '11223344'
    transport.read_memory.assert_called_once_with(0x20000000, 4)
    bridge.send_command.assert_not_called()
    transport.attach_profile = None
    assert not state['device'].connected
    assert target_attach_status(state['device']) is None
    assert client.get('/api/device/status').json()['target_attach'] is None


@pytest.mark.parametrize('failure', ['firmware', 'mismatch'])
def test_failed_profile_details_reach_headless_client_and_are_never_downgraded(shared, failure):
    client, control, state, bridge, _ = shared
    def refuse():
        if failure == 'firmware':
            raise FirmwareUpgradeRequired('Configured target attach', 'MUX HELLO 0x2000')
        diagnostic = PROFILE_DIAGNOSTIC.pack(1, 4, 3, 4, 0x1300)
        raise MuxProfileError(bridge.attach_profile, 5, diagnostic)
    bridge.enable_multiplex.side_effect = refuse
    for body in ({'kind': 'mcp', 'mcu': 'S32K314'}, {'kind': 'sdk'}):
        reply = client.post('/_runtime/attach', json=body)
        assert reply.status_code == 409, reply.text
        error = reply.json()['detail']
        if failure == 'firmware':
            assert error['code'] == 'firmware_upgrade_required'
            assert 'HELLO' in error['required']
        else:
            assert error['code'] == 'mux_profile_attach_failed'
            assert (error['profile'], error['mem_ap'], error['step'], error['reason'], error['actual']) == (
                'S32K3', 4, 3, 4, 0x1300)
        assert state['device'] is state['dispatcher'] is None
        assert not control.target_sessions
    assert bridge.close.call_count == 2
    assert bridge.enable_multiplex.call_count == 2
    state['last_device_connection'] = {'mcu': 'stm32f1', 'port': 'TEST_PORT'}
    retry = client.post('/api/device/connect', json={'restore_last': True})
    assert retry.status_code == 409 and retry.json()['detail']['code'] == error['code']
    assert bridge.enable_multiplex.call_count == 3
    bridge.send_command.assert_not_called()


def test_cpu_register_access_uses_selected_ap(shared):
    client, _, _, bridge, transport = shared
    from mklink.debug_control import _read_u32, _write_u32
    assert client.post('/_runtime/attach', json={'mcu': 'S32K314'}).status_code == 200
    assert _read_u32(bridge, 0xe000edf0) == 0x44332211
    _write_u32(bridge, 0xe000edf8, 0x11223344)
    transport.write_memory.assert_called_once_with(0xe000edf8, bytes.fromhex('44332211'))
    bridge.send_command.assert_not_called()


def test_flash_rejects_wrong_target_on_the_same_probe_before_driver_open(shared):
    from mklink.remote.api import prepare_online_flash_connect
    client, _, state, bridge, _ = shared
    assert client.post('/_runtime/attach', json={}).status_code == 200
    req = SimpleNamespace(target_part='S32K312', reset_mode='software', probe_id='TEST')
    with pytest.raises(ValueError, match='S32K312.*S32K314'):
        prepare_online_flash_connect(state, req)
    req.probe_id = 'other'
    prepare_online_flash_connect(state, req)
    bridge.close.assert_not_called()


def test_unsupported_hook_is_visible_before_probe_open(shared, monkeypatch):
    from mklink.profiles import load_mcu_profiles
    client, _, state, bridge, _ = shared
    catalog = load_mcu_profiles()
    recipe = catalog['s32k314']['mux_attach']
    recipe['hooks']['BeforeResetTarget'] = [{'kind': 'unsupported'}]
    monkeypatch.setattr('mklink.profiles.load_mcu_profiles', lambda: catalog)
    for body in ({'mcu': 'S32K314'}, {'mcu': 'NXPS32K314HMS'}):
        result = client.post('/_runtime/attach', json=body)
        assert result.status_code == 422, result.text
        detail = result.json()['detail']
        assert detail['code'] == 'unsupported_hook' and detail['hook'] == 'BeforeResetTarget'
    assert state['device'] is None
    bridge.connect.assert_not_called()


def test_hil_owner_prevents_profile_io_before_port_open(shared):
    from mklink.hil_lock import HilFileLock, transport_lock_name
    client, control, state, bridge, _ = shared
    external = HilFileLock(transport_lock_name('usb-serial', 'TEST_PORT'), owner_id='other-client')
    external.acquire()
    try:
        response = client.post('/_runtime/attach', json={'mcu': 'S32K314'})
        assert response.is_error and 'other-client' in response.text
        bridge.connect.assert_not_called()
        bridge.enable_multiplex.assert_not_called()
        assert state['device'] is None and not control.sessions
    finally:
        external.release()
    assert client.post('/_runtime/attach', json={'mcu': 'S32K314'}).status_code == 200


@pytest.mark.parametrize('phase,close_fails', [
    ('flash', False), ('symbols', False), ('symbols', True), ('bind', True),
])
def test_partial_profile_connect_releases_lease_even_if_bridge_close_fails(
        tmp_path, shared, monkeypatch, phase, close_fails):
    from mklink.device import connect
    from mklink.hil_lock import HilFileLock, transport_lock_name
    _, _, _, bridge, _ = shared
    old_hold = Device._hold_hil_lock
    owners = []
    def record_owner(device, bridge, port):
        old_hold(device, bridge, port)
        owners.append((device, device._hil_renew_thread))
    monkeypatch.setattr(Device, '_hold_hil_lock', record_owner)
    original = RuntimeError(f'{phase} initialization failed')
    if phase == 'flash':
        monkeypatch.setattr('mklink.flash.MKLinkFlash', Mock(side_effect=original))
    elif phase == 'symbols':
        monkeypatch.setattr(Device, '_load_dwarf_info', Mock(side_effect=original))
    else:
        bridge.enable_multiplex.side_effect = original
    cleanup = OSError('serial close unconfirmed')
    if close_fails:
        bridge.close.side_effect = cleanup
    with pytest.raises(RuntimeError) as caught:
        connect(port='TEST_PORT', mcu='S32K314', axf='test.axf', project_root=str(tmp_path))
    assert caught.value is original
    device, worker = owners[0]
    assert not device.connected and target_attach_status(device) is None
    assert not worker.is_alive() and device._hil_lock is None and device._flash is None
    bridge.close.assert_called_once_with()
    bridge.enable_multiplex.assert_called_once_with()
    with HilFileLock(transport_lock_name('usb-serial', 'TEST_PORT'), owner_id='next-client'):
        pass
    if close_fails:
        assert caught.value.__cause__ is cleanup and device._bridge is bridge
        bridge.close.side_effect = None
        device.close()
    assert device._bridge is None


@pytest.mark.parametrize('fail_second', [False, True])
def test_profile_flush_counts_confirmed_frames_and_never_replays(shared, fail_second):
    from mklink.memory_write import execute_flush
    client, _, state, bridge, transport = shared
    assert client.post('/_runtime/attach', json={'mcu': 'S32K314'}).status_code == 200
    address = 0x20000000
    data = bytes(range(11))
    transport.transfer_quantum = 4
    transport.read_memory.side_effect = lambda start, size: data[start-address:start-address+size]
    if fail_second:
        transport.write_memory.side_effect = [None, TimeoutError('write acknowledgement lost')]
        with pytest.raises(RuntimeError, match=r'completed 1/3 MUX write batches \(4/11 bytes\)'):
            execute_flush(state['device'], [(address, data)], verify=True)
        assert transport.write_memory.call_count == 2 and transport.read_memory.call_count == 1
    else:
        result = execute_flush(state['device'], [(address, data)], verify=True)
        assert result['ok'] and [row['bytes'] for row in result['results']] == [4, 4, 3]
        assert transport.write_memory.call_count == transport.read_memory.call_count == 3
    assert [call.args for call in transport.write_memory.call_args_list] == [
        (address + offset, data[offset:offset+4]) for offset in range(0, 8 if fail_second else 11, 4)]
    bridge.send_command.assert_not_called()

@pytest.mark.parametrize("open_first", [False, True])
def test_shared_image_connect_without_model(tmp_path, shared, monkeypatch, open_first):
    from test_image_target import bind_file, image
    from mklink.dwarf_parser import DwarfInfo
    client, _, state, bridge, _ = shared
    target = image(tmp_path, "firmware.elf")
    bind_file(target, "S32K344")
    monkeypatch.setattr("mklink.dwarf_parser.load_dwarf_info", lambda *a, **kw: DwarfInfo())
    if open_first:
        result = client.post("/api/device/parse-axf", json={"axf": str(target)})
        assert result.status_code == 200, result.text
        assert result.json()["image_target"]["device"] == "S32K344"
        bridge.connect.assert_not_called()
    body = {} if open_first else {"axf": str(target)}
    result = client.post("/_runtime/attach", json={"kind": "mcp", **body})
    assert result.status_code == 200, result.text
    assert result.json()["target_attach"]["profile"] == "S32K314"
    assert state["last_device_connection"]["mcu"] is None
    bridge.enable_multiplex.assert_called_once()
    bridge.send_command.assert_not_called()


@pytest.mark.parametrize('route', ['/api/device/connect', '/_runtime/attach'])
def test_customer_image_names_312_but_hardware_reports_344(tmp_path, shared, route, monkeypatch):
    from test_image_target import bind_file, image
    from mklink.dwarf_parser import DwarfInfo
    client, _, state, bridge, _ = shared
    bridge.current_mcu = "S32K344"
    target = image(tmp_path, "firmware.elf")
    bind_file(target, "S32K312")
    monkeypatch.setattr("mklink.dwarf_parser.load_dwarf_info", lambda *a, **kw: DwarfInfo())
    response = client.post(route, json={"axf": str(target)})
    assert response.status_code == 200, response.text
    actual = response.json()["target_attach"]
    assert actual["profile"] == "S32K344" and actual["midr1"] == 0x2d580000
    symbols = state["device"].axf_status["image_target"]
    assert symbols["device"] == "S32K312" and not symbols["matches_hardware"]
    assert symbols["hardware_model"] == "S32K344"
    bridge.connect.assert_called_once()
    bridge.enable_multiplex.assert_called_once()
    bridge.send_command.assert_not_called()

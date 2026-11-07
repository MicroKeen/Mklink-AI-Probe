from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from mklink import probes
from mklink.capture_clock import CONFIGURATION_CLOCKS, V3_CLOCKS
from mklink.runtime import RuntimeErrorResponse
from mklink.remote.api import create_app
from test_runtime_switch import window, A, B
from test_online_flash_api import app, services, request


@pytest.mark.parametrize('presence', ['unselected', 'missing'])
def test_online_probe_list_available_without_target_connection(app, presence):
    app.state.shared_runtime = SimpleNamespace(presence=lambda: {'status': presence})
    response = request(app, 'GET', '/api/online-flash/probes')
    assert response.status_code == 200
    assert [row['unique_id'] for row in response.json()] == ['mk']


@pytest.mark.parametrize('port,extra', [('COM1', True), ('com1', False), ('COM2', True)])
def test_online_clock_choices_use_only_the_selected_ports_interface_cache(app, port, extra):
    table = ','.join(map(str, V3_CLOCKS))
    caps = {'JTAG_CLOCK_ACK=1', 'JTAG_CLOCKS=' + table, 'SWD_CLOCK_ACK=1', 'SWD_CLOCKS=' + table}
    if extra:
        caps.add('JTAG_CLOCKS_EXTRA=4000000')
    bridge = SimpleNamespace(_firmware_capabilities=caps)
    app.state.mklink_state = {'device': SimpleNamespace(connected=True, port=port, _bridge=bridge)}
    app.state.shared_runtime = SimpleNamespace(presence=lambda: {
        'status': 'present', 'probe': {'port': 'COM1', 'serial_number': 'MK'}})
    row, = request(app, 'GET', '/api/online-flash/probes').json()
    if port == 'COM2':
        assert 'flash_clocks_hz' not in row
    else:
        assert row['flash_clocks_hz']['JTAG'] == list(CONFIGURATION_CLOCKS if extra else V3_CLOCKS)
        assert row['flash_clocks_hz']['SWD'] == list(V3_CLOCKS)


def test_dap_selection_reserves_identity_without_connecting_target(window, monkeypatch):
    client, control, device, state = window
    client.post('/api/device/disconnect')
    connect = Mock(side_effect=AssertionError('Target must not connect during selection'))
    monkeypatch.setattr('mklink.connect', connect)
    monkeypatch.setattr(probes, 'inventory', lambda: [
        {'probe_id': B, 'port': 'COM2', 'alias': '', 'serial_number': 'DAP123'}])
    response = client.post('/api/runtime/select', json={'cmsis_dap_id': 'dap123'})
    assert response.status_code == 200, response.text
    assert response.json()['probe_id'] == B
    assert state['device'] is None and control.info['probe_id'] == B
    same = client.post('/api/runtime/select', json={'cmsis_dap_id': 'DAP123'}).json()
    assert same['device_generation'] == response.json()['device_generation']
    connect.assert_not_called()


@pytest.mark.parametrize('serials', [[], ['DUP', 'DUP']])
def test_unavailable_or_ambiguous_dap_identity_keeps_current_binding(window, monkeypatch, serials):
    client, control, device, state = window
    monkeypatch.setattr(probes, 'inventory', lambda: [
        {'probe_id': identifier, 'port': f'COM{index}', 'alias': '', 'serial_number': serial}
        for index, (identifier, serial) in enumerate(zip([A, B], serials))])
    assert client.post('/api/runtime/select', json={'cmsis_dap_id': 'DUP'}).status_code == 409
    assert state['device'] is device and control.info['probe_id'] == A
    device.close.assert_not_called()


@pytest.mark.parametrize('count', [0, 1, 2])
def test_offline_disk_preview_does_not_bind_or_connect(tmp_path, monkeypatch, count):
    candidates = [{'probe_id': identifier, 'port': f'COM{index}', 'alias': ''}
                  for index, identifier in enumerate([A, B][:count])]
    monkeypatch.setattr(probes, 'inventory', lambda: candidates)
    monkeypatch.setattr('mklink.probe_volumes.resolve_volume', lambda probe: {'root': str(tmp_path / probe)})
    connect = Mock(side_effect=AssertionError('No target connection expected'))
    monkeypatch.setattr('mklink.connect', connect)
    app = create_app(auth_token=None, project_root=str(tmp_path))
    control = app.state.shared_runtime = SimpleNamespace(info={'probe_id': 'lobby'})
    with TestClient(app) as client:
        data = client.get('/api/offline-download/status').json()
        assert data['available'] == (count == 1)
        assert len(data['probes']) == count
        if count == 2:
            data = client.get('/api/offline-download/status', params={'probe': B}).json()
            assert data['available'] and data['probe_id'] == B
    assert control.info['probe_id'] == 'lobby'
    connect.assert_not_called()


def test_offline_algorithm_catalog_remains_available_in_lobby(tmp_path, monkeypatch):
    monkeypatch.setattr('mklink.discovery.find_microkeen_disk', Mock(side_effect=RuntimeErrorResponse('Select a physical probe')))
    discover = Mock(return_value=[{'id': 'host-pack-algorithm'}])
    monkeypatch.setattr('mklink.remote.offline_download_api.discover_algorithms', discover)
    app = create_app(auth_token=None, project_root=str(tmp_path))
    with TestClient(app) as client:
        response = client.get('/api/offline-download/algorithms', params={'part_number': 'STM32F103RC'})
    assert response.status_code == 200, response.text
    assert response.json() == [{'id': 'host-pack-algorithm'}]
    assert discover.call_args.args[2] is None


@pytest.mark.parametrize('version,model', [
    ('V2.9.2', 'V2'), ('V3.6.7', 'V3'), ('V4.7.1', 'V4'),
    ('V5.1.0', None), ('unrecognized', None), (None, None),
])
def test_offline_status_reads_model_without_opening_device(tmp_path, monkeypatch, version, model):
    monkeypatch.setattr(probes, 'inventory', lambda: [
        {'probe_id': A, 'port': 'COM1', 'alias': 'Bench', 'description': 'MicroLink'}])
    monkeypatch.setattr('mklink.probe_volumes.resolve_volume', lambda probe: {'root': str(tmp_path)})
    forbidden = Mock(side_effect=AssertionError('Passive discovery must not open the device'))
    monkeypatch.setattr('mklink.connect', forbidden)
    monkeypatch.setattr('mklink.firmware_check.read_device_version', forbidden)
    if version is not None:
        (tmp_path / 'readme.txt').write_text(f'MicroLink\n{version}\n', encoding='utf-8')
    app = create_app(auth_token=None, project_root=str(tmp_path))
    control = app.state.shared_runtime = SimpleNamespace(info={'probe_id': 'lobby'})
    with TestClient(app) as client:
        response = client.get('/api/offline-download/status')
    assert response.status_code == 200
    data = response.json()
    assert data['available'] and data['probe_id'] == A
    assert data['model'] == model
    assert data['version'] == (version if version and version.startswith('V') else None)
    assert data['probes'][0]['alias'] == 'Bench'
    assert control.info['probe_id'] == 'lobby'
    forbidden.assert_not_called()


def test_offline_model_comes_from_the_selected_probes_verified_volume(tmp_path, monkeypatch):
    monkeypatch.setattr(probes, 'inventory', lambda: [
        {'probe_id': A, 'port': 'COM1', 'alias': ''}, {'probe_id': B, 'port': 'COM2', 'alias': ''}])
    for probe, version in [(A, 'V2.9.2'), (B, 'V4.7.1')]:
        root = tmp_path / probe
        root.mkdir()
        (root / 'readme.txt').write_text(version, encoding='utf-8')
    resolve = Mock(side_effect=lambda probe: {'root': str(tmp_path / probe)})
    monkeypatch.setattr('mklink.probe_volumes.resolve_volume', resolve)
    app = create_app(auth_token=None, project_root=str(tmp_path))
    app.state.shared_runtime = SimpleNamespace(info={'probe_id': A})
    with TestClient(app) as client:
        bridge = SimpleNamespace(_ctx=SimpleNamespace(clock_interface='JTAG'), _firmware_capabilities={'V2.9.2'})
        app.state.mklink_state['device'] = SimpleNamespace(connected=True, port='COM1', _bridge=bridge)
        selected = client.get('/api/offline-download/status').json()
        assert selected['model'] == 'V2'
        assert selected['flash_clocks_hz']['JTAG'] == [4000000, 10000000, 20000000, 30000000]
        resolve.assert_called_once_with(A)
        resolve.reset_mock()
        other = client.get('/api/offline-download/status', params={'probe': B}).json()
        assert other['model'] == 'V4' and 'flash_clocks_hz' not in other
        resolve.assert_called_once_with(B)
        app.state.mklink_state['device'] = None


def test_offline_profile_catalog_does_not_rediscover_unbound_disk(tmp_path, monkeypatch):
    from mklink.remote.offline_download_api import _profile_candidates

    monkeypatch.setattr('mklink.discovery.check_flm_on_microkeen', Mock(side_effect=AssertionError('No implicit disk discovery')))
    monkeypatch.setattr('mklink.discovery.resolve_keil_flm_path', lambda name: str(tmp_path / name))
    candidates = _profile_candidates('STM32F103RC', None)
    assert candidates and candidates[0]['available']
    assert not candidates[0]['on_probe']

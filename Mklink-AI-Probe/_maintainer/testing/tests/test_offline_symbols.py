"""File configuration survives connection lifetime; reload drains real managers."""
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from mklink.remote import api, dashboards
from mklink.runtime_api import install_runtime
from mklink.device import Device
from test_remote_api import _connected_symbol_device


@pytest.fixture
def offline(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboards, '_managers', {})
    fixture, axf = _connected_symbol_device(tmp_path)
    monkeypatch.setattr('mklink.dwarf_parser.load_dwarf_info', lambda *a, **kw: fixture._dwarf_info)
    monkeypatch.setattr('mklink.elf_backend.writable_memory_ranges', lambda *a, **kw: [(0x20000000, 0x20010000)])
    monkeypatch.setattr('mklink.probes.inventory', Mock(side_effect=AssertionError('File loading must not access probes')))
    app = api.create_app(auth_token=None, project_root=str(tmp_path))
    control = install_runtime(app, {'port': 8765, 'token': 'test', 'instance_id': 'test', 'probe_id': 'lobby'})
    client = TestClient(app, base_url='http://127.0.0.1:8765', headers={'X-Auth-Token': 'test'})
    return app, client, axf, control


def test_offline_load_browse_select_reload_without_probe(offline, monkeypatch):
    app, client, axf, _ = offline
    response = client.post('/api/device/parse-axf', json={'axf': str(axf)})
    assert response.status_code == 200, response.text
    assert response.json()['loaded']
    assert app.state.mklink_state['device'] is None
    assert client.get('/api/device/status').json()['axf']['loaded']
    assert client.get('/api/symbols/browse').status_code == 200
    assert client.post('/api/dash/superwatch/add', json={'name': 'gain'}).status_code == 200
    response = client.post('/api/symbols/reload-sources', params={'source_path': str(axf), 'expected_axf': str(axf)})
    assert response.status_code == 200, response.text
    assert [row['name'] for row in client.get('/api/dash/superwatch/items').json()['items']] == ['gain']
    monkeypatch.setattr('mklink.probes.inventory', lambda: [])
    assert client.post('/api/dash/superwatch/write', json={'path': 'gain', 'generation': 2, 'value': 1}).status_code >= 400


@pytest.mark.parametrize('route', ['/api/device/parse-axf', '/api/symbols/reparse', '/api/symbols/reload-sources'])
def test_explicit_reload_stops_both_captures_before_parsing_and_does_not_restart(offline, monkeypatch, route):
    app, client, axf, _ = offline
    assert client.post('/api/device/parse-axf', json={'axf': str(axf)}).status_code == 200
    managers = dashboards.get_managers()
    order = []
    for name in ('rtt', 'superwatch'):
        manager = managers[name]
        manager._running = True
        def stop(m=manager, n=name):
            order.append(n); m._running = False
            if hasattr(m, '_collecting'): m._collecting.clear()
        monkeypatch.setattr(manager, 'stop', stop)
        monkeypatch.setattr(manager, 'start', Mock(side_effect=AssertionError('Reload must stay stopped')))
    device = app.state.mklink_state['symbol_device']
    original = device.reparse_axf_atomically
    def parse(*a, **kw):
        assert order == ['rtt', 'superwatch']
        return original(*a, **kw)
    monkeypatch.setattr(device, 'reparse_axf_atomically', parse)
    result = client.post(route, json={'axf': str(axf)})
    assert result.status_code == 200, result.text
    assert not managers['rtt'].running and not managers['superwatch'].running


def test_disconnect_keeps_catalog_and_selection_but_clears_samples(offline):
    app, client, axf, _ = offline
    assert client.post('/api/device/parse-axf', json={'axf': str(axf)}).status_code == 200
    device = app.state.mklink_state['symbol_device']
    app.state.mklink_state['device'] = device
    assert isinstance(device, Device)
    client.post('/api/dash/superwatch/add', json={'name': 'gain'})
    previous = dashboards.get_managers()['superwatch']
    previous._pending_values.append(123)
    catalog = device.symbol_catalog
    result = client.post('/api/device/disconnect')
    assert result.status_code == 200, result.text
    assert app.state.mklink_state['symbol_device'].symbol_catalog is catalog
    current = dashboards.get_managers()['superwatch']
    assert current is not previous and not current._pending_values
    assert [row['name'] for row in client.get('/api/dash/superwatch/items').json()['items']] == ['gain']
    assert client.get('/api/symbols/browse').status_code == 200


def test_failed_reload_keeps_previous_catalog_and_selection(offline, monkeypatch):
    app, client, axf, _ = offline
    assert client.post('/api/device/parse-axf', json={'axf': str(axf)}).status_code == 200
    client.post('/api/dash/superwatch/add', json={'name': 'gain'})
    device = app.state.mklink_state['symbol_device']
    catalog = device.symbol_catalog
    monkeypatch.setattr('mklink.dwarf_parser.load_dwarf_info', Mock(side_effect=ValueError('Invalid ELF')))
    result = client.post('/api/device/parse-axf', json={'axf': str(axf)})
    assert result.status_code >= 400
    assert device.symbol_catalog is catalog
    assert [row['name'] for row in client.get('/api/dash/superwatch/items').json()['items']] == ['gain']


def test_reload_does_not_parse_until_worker_has_stopped(offline, monkeypatch):
    app, client, axf, _ = offline
    assert client.post('/api/device/parse-axf', json={'axf': str(axf)}).status_code == 200
    device = app.state.mklink_state['symbol_device']
    parser = Mock(side_effect=AssertionError('Worker still owns old addresses'))
    monkeypatch.setattr(device, 'reparse_axf_atomically', parser)
    manager = dashboards.get_managers()['superwatch']
    manager._running = True
    monkeypatch.setattr(manager, 'stop', lambda: None)
    result = client.post('/api/device/parse-axf', json={'axf': str(axf)})
    assert result.status_code == 409, result.text
    parser.assert_not_called()

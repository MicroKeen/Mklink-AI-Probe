from types import SimpleNamespace

import pytest

from mklink import uart_baud
from mklink.serial import _port


def lines(rates=uart_baud.PROFILE_1_RATES):
    return ['V3.6.8', 'UART_BAUD_PROFILE=1', 'UART_BAUDS=' + ','.join(map(str, rates))]


def test_profile_one_uses_only_explicitly_advertised_rates():
    result = uart_baud.baud_options(lines())
    assert result == {'profile': 1, 'source': 'firmware', 'rates': list(uart_baud.PROFILE_1_RATES)}
    assert len(result['rates']) == 34
    assert uart_baud.baud_options(lines((115200, 4000000)))['rates'] == [115200, 4000000]


@pytest.mark.parametrize('response', [[], ['V4.7.2'], ['UART_BAUD_PROFILE=1'],
    ['UART_BAUDS=4000000'], ['UART_BAUD_PROFILE=2', 'UART_BAUDS=4000000'],
    lines(('4000000', '4000000')), lines(('3000001',)), lines(('-1',)),
    lines(('1.5',)), lines(('４００００００',)), lines(())])
def test_missing_or_invalid_profile_never_claims_old_high_rates(response):
    result = uart_baud.baud_options(response)
    warning = result.pop('firmware_warning', None)
    assert bool(warning) == (response == ['V4.7.2'])
    if warning:
        assert 'upgrade' in warning and '升级' in warning
    assert result == {
        'profile': None, 'rates': list(uart_baud.COMMON_RATES), 'source': 'common'}


def port(name, number, serial='unique'):
    return SimpleNamespace(device=name, vid=0x0D28, pid=0x0202,
        serial_number=serial, hwid=f'USB\\MI_{number:02X}', location='', description=name, manufacturer='')


def test_usb_roles_and_pairing_are_passive_and_ambiguous_serials_are_not_paired(monkeypatch):
    ports = [port('UART', 2), port('CMD', 4), port('RS485', 6)]
    monkeypatch.setattr(_port.serial.tools.list_ports, 'comports', lambda: ports)
    monkeypatch.setattr(_port.serial, 'Serial', lambda *a, **k: pytest.fail('Opened hardware'))
    uart, rs485 = _port.list_uart_ports()
    assert uart['uart_kind'] == 'mklink_uart' and uart['command_port'] == 'CMD'
    assert rs485['uart_kind'] == 'mklink_rs485' and rs485['command_port'] is None
    ports.append(port('OTHER_CMD', 4))
    assert _port.list_uart_ports()[0]['command_port'] is None


@pytest.fixture
def paired(monkeypatch):
    uart = dict(device='UART', command_port='CMD', uart_kind='mklink_uart', usb_serial='fixture')
    monkeypatch.setattr(_port, 'list_uart_ports', lambda: [uart])
    monkeypatch.setattr('mklink.probes.inventory', lambda: [dict(port='CMD', probe_id='probe', identity_stable=True)])
    return uart


def test_connected_capability_cache_does_not_send_commands_or_cross_devices(paired, monkeypatch):
    bridge = SimpleNamespace(_firmware_capabilities=frozenset(lines()), _transport_error=None)
    state = dict(shared_probe_id='probe', device=SimpleNamespace(connected=True, port='CMD', _bridge=bridge))
    monkeypatch.setattr('mklink.runtime.query_probe', lambda *a, **k: pytest.fail('Unnecessary query'))
    assert uart_baud.read_options(state, 'UART')['uart_baud']['source'] == 'firmware'
    state['shared_probe_id'] = 'other'
    assert uart_baud.cached_options(state, paired)['source'] == 'common'
    paired['uart_kind'] = 'mklink_rs485'
    state['shared_probe_id'] = 'probe'
    assert uart_baud.cached_options(state, paired)['source'] == 'common'


def test_explicit_query_uses_shared_owner_and_rejects_changed_port(paired, monkeypatch):
    queries = []
    def query(capability, **kwargs):
        queries.append((capability, kwargs))
        return {'raw': '\n'.join(lines())}
    monkeypatch.setattr('mklink.runtime.query_probe', query)
    assert uart_baud.read_options({}, 'UART')['uart_baud']['rates'][-1] == 10000000
    assert queries == [('probe_version', {'probe': 'probe'})]
    calls = 0
    def enumerate_ports():
        nonlocal calls
        calls += 1
        return [paired] if calls == 1 else [{**paired, 'usb_serial': 'changed'}]
    monkeypatch.setattr(_port, 'list_uart_ports', enumerate_ports)
    with pytest.raises(ValueError, match='identity changed'):
        uart_baud.read_options({}, 'UART')


def test_busy_probe_is_not_retried_or_stopped(paired, monkeypatch):
    from mklink.runtime import RuntimeErrorResponse
    queries = []
    def query(*a, **k):
        queries.append(a)
        raise RuntimeErrorResponse('busy')
    monkeypatch.setattr('mklink.runtime.query_probe', query)
    with pytest.raises(RuntimeErrorResponse, match='busy'):
        uart_baud.read_options({}, 'UART')
    assert len(queries) == 1


@pytest.mark.parametrize('kind', ['generic', 'mklink_rs485', 'mklink_unknown'])
def test_other_interfaces_cannot_request_uart_profile(paired, monkeypatch, kind):
    paired['uart_kind'] = kind
    monkeypatch.setattr('mklink.runtime.query_probe', lambda *a, **k: pytest.fail('Wrong interface queried'))
    with pytest.raises(ValueError, match='ordinary MKLink UART'):
        uart_baud.read_options({}, 'UART')


def test_http_port_refresh_is_passive_and_explicit_query_is_port_bound(paired, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from mklink.remote.api import create_app
    queries = []
    def query(*args, **kwargs):
        queries.append(kwargs)
        return {'raw': '\n'.join(lines())}
    monkeypatch.setattr('mklink.runtime.query_probe', query)
    app = create_app(auth_token=None, project_root=str(tmp_path))
    with TestClient(app) as client:
        response = client.get('/api/ports/uart')
        assert response.status_code == 200 and queries == []
        assert response.json()[0]['uart_baud']['source'] == 'common'
        response = client.post('/api/runtime/uart-baudrates', json={'port': 'UART'})
        assert response.status_code == 200 and response.json()['uart_baud']['profile'] == 1
        assert queries == [{'probe': 'probe'}]
        assert client.post('/api/runtime/uart-baudrates', json={'port': 'other'}).status_code == 400
        assert len(queries) == 1

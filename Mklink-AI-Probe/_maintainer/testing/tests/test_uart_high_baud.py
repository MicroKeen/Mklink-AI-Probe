"""Full firmware profile reaches shared serial/Modbus entry points unchanged."""
import asyncio
from types import SimpleNamespace

import pytest
from fastmcp import Client

from mklink.uart_baud import PROFILE_1_RATES
from test_runtime_uart import uart_app, client_factory


@pytest.mark.parametrize('rate', PROFILE_1_RATES)
def test_every_firmware_step_reaches_cli_and_http_modbus(uart_app, rate):
    from mklink.cli import _serial_connection
    http, _, managers, _, _ = uart_app
    args = SimpleNamespace(port='TEST', baud=rate, databits=8, stop=1, parity='N')
    assert _serial_connection(args)['baudrate'] == rate
    response = http.post('/api/dash/modbus/start', json={'port': 'TEST', 'baudrate': rate, 'registers': []})
    assert response.status_code == 200, response.text
    assert managers['modbus'].get_status()['connection']['baudrate'] == rate
    assert http.post('/api/dash/modbus/stop').status_code == 200


@pytest.mark.parametrize('rate', [10000001, 0, True, 1.5, '10M'])
def test_modbus_rejects_invalid_baud_before_open(uart_app, rate):
    http, _, managers, factory, _ = uart_app
    response = http.post('/api/dash/modbus/start', json={'port': 'TEST', 'baudrate': rate, 'registers': []})
    assert response.status_code in (400, 422), response.text
    assert not factory.instances and not managers['modbus'].running


def test_mcp_accepts_10m_for_both_streams(uart_app, monkeypatch):
    from mklink import runtime, runtime_mcp
    http, control, managers, _, _ = uart_app
    def request(info, method, path, payload=None, **kwargs):
        response = http.request(method, path, json=payload)
        response.raise_for_status()
        return response.json()
    monkeypatch.setattr(runtime, 'request', request)
    monkeypatch.setattr(runtime_mcp, 'RuntimeClient', lambda **kwargs: runtime.RuntimeClient(info=control.info, **kwargs))
    async def scenario():
        async with Client(runtime_mcp.build_server()) as mcp:
            await mcp.call_tool('connect', {'scope': 'uart'})
            for capability, arguments in [
                ('serial_start', {'ports': [{'port': 'TEST_SERIAL', 'baudrate': 10000000}]}),
                ('modbus_start', {'port': 'TEST_MODBUS', 'baudrate': 10000000, 'registers': []}),
            ]:
                result = await mcp.call_tool('gui_call', {'capability': capability, 'arguments': arguments})
                assert not result.is_error, result
            assert managers['serial'].get_status()['config'][0]['baudrate'] == 10000000
            assert managers['modbus'].get_status()['connection']['baudrate'] == 10000000
            for capability in ('serial_stop', 'modbus_stop'):
                assert not (await mcp.call_tool('gui_call', {'capability': capability})).is_error
            await mcp.call_tool('detach', {})
    asyncio.run(scenario())
    assert not control.sessions

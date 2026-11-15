from types import SimpleNamespace

import pytest

from mklink.capture_clock import V3_CLOCKS
from mklink.firmware_compatibility import compatibility_snapshot
from mklink.mux import MuxTargetError, MuxTransport, MuxError
from mklink.uart_baud import PROFILE_1_RATES


def bridge(version='V4.7.3', caps=0x1FFF):
    return SimpleNamespace(_firmware_capabilities=frozenset((version, 'MUX_TARGET=1',
        'SWD_CLOCK_ACK=1', 'SWD_CLOCKS=' + ','.join(map(str, V3_CLOCKS)),
        'UART_BAUD_PROFILE=1', 'UART_BAUDS=' + ','.join(map(str, PROFILE_1_RATES)),
        'OFFLINE_BIN_VERIFY=1', 'OFFLINE_HEX_VERIFY=1')),
        _mux_capabilities=caps, _ctx=SimpleNamespace(clock_interface='SWD'))


@pytest.mark.parametrize('version', ['V4.7.3', 'V4.7.4', 'V3.6.9', 'V4.5.2'])
def test_features_not_version_threshold(version):
    assert compatibility_snapshot(bridge(version))['warnings'] == []


@pytest.mark.parametrize('value', [None, SimpleNamespace(), bridge('V2.9.3'), bridge('garbage')])
def test_unknown_or_unsupported_model_has_no_upgrade_claim(value):
    assert compatibility_snapshot(value) == dict(checked=False, version=None, warnings=[])


@pytest.mark.parametrize('mask', [3, 0x618, 0x20, 0x40, 0x80, 0x100, 0x800, 0x1000])
def test_missing_hello_features_reported_from_cache_only(mask):
    candidate = bridge(caps=0x1FFF & ~mask)
    candidate.send_command = lambda *a: pytest.fail('status must never query the probe')
    warnings = compatibility_snapshot(candidate)['warnings']
    assert any(w['required'] == f'MUX HELLO 0x{mask:X}' for w in warnings)
    assert all(w['action'] == 'upgrade_probe_firmware' for w in warnings)


def test_unnegotiated_hello_is_unknown_not_missing():
    assert compatibility_snapshot(bridge(caps=None))['warnings'] == []


def test_old_text_contract_lists_compatibility_limits():
    candidate = bridge(caps=None)
    candidate._firmware_capabilities = frozenset({'V4.4.0', 'DUMP_WRITE=1'})
    required = {w['required'] for w in compatibility_snapshot(candidate)['warnings']}
    assert required == {'MUX_TARGET=1', 'SWD_CLOCKS / SWD_CLOCK_ACK=1',
                        'UART_BAUD_PROFILE=1 / UART_BAUDS', 'OFFLINE_BIN_VERIFY=1', 'OFFLINE_HEX_VERIFY=1'}


@pytest.mark.parametrize('status', [2, 3, 4, 5, 6])
def test_target_errors_are_not_capability_evidence(status):
    assert 'upgrade' not in str(MuxTargetError(status, 0x12))


@pytest.mark.parametrize('op', [0x12, 0x15, 0x16, 0x17, 0x20, 0x23, 0x25, 0x32, 0x33, 0x34])
def test_explicit_unsupported_host_command_requests_upgrade(op):
    assert 'upgrade' in str(MuxTargetError(1, op))
    assert '升级' in str(MuxTargetError(1, op))


def test_malformed_hello_does_not_claim_missing_firmware():
    transport = MuxTransport(lambda data: None)
    transport.request = lambda *args: b'bad'
    with pytest.raises(MuxError, match='unconfirmed') as error:
        transport.handshake()
    assert 'upgrade' not in str(error.value)


def test_web_shared_client_and_mcp_expose_identical_cached_guidance(tmp_path, monkeypatch):
    import asyncio
    from fastapi.testclient import TestClient
    from fastmcp import Client
    from mklink.remote.api import create_app
    from mklink.runtime_api import install_runtime
    from mklink import runtime, runtime_mcp

    app = create_app(project_root=str(tmp_path))
    state = app.state.mklink_state
    candidate = bridge(caps=0x61F)
    state['device'] = SimpleNamespace(connected=True, port='COM9', state=None, mcu_name='STM32F10x',
        idcode=0x1BA01477, axf_status={'loaded': False}, _bridge=candidate, symbol_catalog=None,
        close=lambda: None)
    info = dict(port=8765, token='fixture', instance_id='fixture')
    install_runtime(app, info)
    monkeypatch.setattr('mklink.probes.inventory', lambda: [])
    monkeypatch.setattr('mklink.runtime.ensure_runtime', lambda **kw: info)
    with TestClient(app, base_url='http://127.0.0.1:8765', headers={'X-Auth-Token': 'fixture'}) as web:
        def request(info, method, path, payload=None, **kw):
            reply = web.request(method, path, json=payload)
            if reply.is_error:
                raise runtime.RuntimeErrorResponse(reply.text)
            return reply.json()
        monkeypatch.setattr(runtime, 'request', request)
        expected = web.get('/api/device/status').json()['firmware_compatibility']
        assert expected['warnings']
        cli = runtime.RuntimeClient()
        try:
            assert cli.connect()['firmware_compatibility'] == expected
            assert cli.call('device_status')['firmware_compatibility'] == expected
        finally:
            cli.close()
        async def scenario():
            async with Client(runtime_mcp.build_server()) as mcp:
                connected = await mcp.call_tool('connect', {})
                assert connected.data['firmware_compatibility'] == expected
                result = await mcp.call_tool('gui_call', {'capability': 'device_status'})
                assert result.data['firmware_compatibility'] == expected
                await mcp.call_tool('detach', {})
        try:
            asyncio.run(scenario())
        finally:
            state['device'] = None

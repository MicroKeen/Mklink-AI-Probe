"""Firmware command audit regressions through real MCP and shared admission."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import Form
from fastmcp import Client
import pytest

from mklink import runtime_mcp
from mklink._types import DeviceState
from mklink.probe_commands import execute, validate
from test_shared_device import shared
from test_shared_runtime import runtime, attach, call


@pytest.mark.parametrize('hpm', [False, True])
def test_offline_accepts_all_advertised_clocks_but_checks_firmware_before_copy(hpm):
    from test_offline_download import _config
    from test_hpm_jtag_offline_cycles import config as hpm_config
    from mklink.capture_clock import V3_CLOCKS
    from mklink.offline_download import parse_offline_config, require_verify_capabilities, OfflineDownloadError
    payload = hpm_config() if hpm else _config()
    interface = 'JTAG' if hpm else 'SWD'
    response = f'{interface}_CLOCK_ACK=1\n{interface}_CLOCKS=' + ','.join(map(str, V3_CLOCKS))
    for hz in V3_CLOCKS:
        config = parse_offline_config({**payload, 'swd_clock_hz': hz})
        require_verify_capabilities(config, response)
        if hz < 100000 or hpm and hz not in (10000000, 20000000, 30000000):
            with pytest.raises(OfflineDownloadError, match='Upgrade'):
                require_verify_capabilities(config, 'V4.6.9')
    if hpm:
        with pytest.raises(OfflineDownloadError, match='JTAG'):
            parse_offline_config({**payload, 'swd_clock_hz': 8000000})


def test_generated_script_aborts_on_rejected_clock_before_any_target_command(monkeypatch):
    import sys
    from test_hpm_jtag_offline_cycles import config
    from mklink.offline_download import parse_offline_config, generate_offline_script
    monkeypatch.setitem(sys.modules, 'PikaStdLib', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'cmd', SimpleNamespace(set_swd_clock=Mock(return_value=-1)))
    monkeypatch.setitem(sys.modules, 'hpm', SimpleNamespace())  # No target operations may be reached.
    output = []
    scope = {'print': lambda *args: output.append(' '.join(map(str, args)))}
    exec(generate_offline_script(parse_offline_config(config())), scope)
    assert scope['abort'] is True and any('clock rejected' in line for line in output)


@pytest.mark.parametrize('code,present,ok', [(0, False, True), (0x1000563D, True, True),
                                           (-2, None, False), (-3, None, False), (-4, None, False)])
def test_live_presence_preserves_negative_codes(code, present, ok):
    bridge = SimpleNamespace(send_command=Mock(side_effect=[
        'MKLINK_HOST_RESULT 1\n', f'MKLINK_HOST_RESULT {code}\n']))
    result = execute(bridge, 'probe_presence', {'interface': 'JTAG'})
    assert result['present'] is present and result['ok'] is ok
    assert 'hpm.read_idcode()' in bridge.send_command.call_args_list[1].args[0]
    assert all('cmd.get_idcode' not in call.args[0] for call in bridge.send_command.call_args_list)


@pytest.mark.parametrize('raw', ['', 'print("MKLINK_HOST_RESULT", cmd.set_power_on(3300))',
                                  'MKLINK_HOST_RESULT 0\nMKLINK_HOST_RESULT 0'])
def test_missing_or_ambiguous_ack_never_replays_voltage_write(raw):
    bridge = SimpleNamespace(send_command=Mock(return_value=raw))
    with pytest.raises(ValueError, match='Outcome unknown'):
        execute(bridge, 'set_power_on', {'voltage_mv': 3300, 'confirm_user': True})
    assert bridge.send_command.call_count == 1


@pytest.mark.parametrize('capability,arguments', [
    ('set_power_on', {'voltage_mv': 3300}),
    ('set_power_on', {'voltage_mv': True, 'confirm_user': True}),
    ('set_power_on', {'voltage_mv': 5000, 'confirm_user': True}),
    ('set_power_off', {'confirm_user': 1}),
    ('probe_diagnostics', {'index': 32}),
    ('probe_presence', {'interface': 'JTAG); reboot()'}),
    ('isp_link_probe', {'baud_rate': 115200, 'duration_ms': 120001}),
    ('probe_control', {'setting': 'auto_follow_vref', 'enabled': True, 'confirm_user': True}),
])
def test_invalid_probe_request_has_no_io(capability, arguments):
    bridge = SimpleNamespace(send_command=Mock())
    with pytest.raises(ValueError):
        execute(bridge, capability, arguments)
    bridge.send_command.assert_not_called()


@pytest.mark.parametrize('capability,arguments', [
    ('probe_diagnostics', {'index': -1}),
    ('probe_control', {'setting': 'beep', 'enabled': True, 'confirm_user': True}),
    ('probe_control', {'setting': 'auto_scan', 'enabled': False, 'confirm_user': True}),
    ('probe_control', {'setting': 'auto_follow_vref', 'enabled': False, 'confirm_user': True}),
    ('set_power_on', {'voltage_mv': 3300, 'confirm_user': True}),
    ('set_power_off', {'confirm_user': True}),
])
def test_latest_v2_omissions_are_model_limits_without_sending_commands(capability, arguments):
    bridge = SimpleNamespace(_firmware_capabilities=frozenset({'V2.9.3', 'MUX_TARGET=1'}), send_command=Mock())
    with pytest.raises(ValueError, match='当前 V2 型号固件不支持'):
        execute(bridge, capability, arguments)
    bridge.send_command.assert_not_called()


def test_diagnostics_and_isp_require_actual_firmware_records():
    reset = 'RESET flags=00000001 status=0 live=0 ticks=234 port=2 idcode=1000563d'
    bridge = SimpleNamespace(send_command=Mock(return_value=reset+'\n>>>'))
    assert execute(bridge, 'probe_diagnostics', {'index': -2})['records'] == [reset]
    bridge.send_command.return_value = 'HPM_ISP_DIAG_RESULT {"schema":1,"operation":"query_only","code":-3}\nMKLINK_HOST_RESULT -3'
    result = execute(bridge, 'isp_link_probe', {'baud_rate': 115200})
    assert result['ok'] is False and result['code'] == -3
    bridge.send_command.return_value = 'MKLINK_HOST_RESULT 0'
    with pytest.raises(ValueError, match='diagnostic result'):
        execute(bridge, 'isp_link_probe', {'baud_rate': 115200})


def test_mcp_probe_workflow_reaches_backend_and_respects_capture(shared, monkeypatch):
    _, control, _, managers, app = shared
    device = app.state.mklink_state['device']
    device._bridge = SimpleNamespace(state=DeviceState.READY, send_command=Mock(return_value='MKLINK_HOST_RESULT 0'))
    monkeypatch.setattr('mklink.probes.select_probe', lambda *a, **kw: {'probe_id': None, 'port': 'COM9'})
    async def scenario():
        async with Client(runtime_mcp.build_server()) as mcp:
            await mcp.call_tool('connect', {})
            bad = await mcp.call_tool('set_power_on', {'voltage_mv': 3300}, raise_on_error=False)
            assert bad.is_error
            device._bridge.send_command.assert_not_called()
            good = await mcp.call_tool('set_power_on', {'voltage_mv': 3300, 'confirm_user': True})
            assert good.data['acknowledged'] is True and good.data['measured'] is False
            managers['rtt'].running = True
            busy = await mcp.call_tool('set_power_off', {'confirm_user': True}, raise_on_error=False)
            assert busy.is_error
            assert device._bridge.send_command.call_count == 1
            managers['rtt'].running = False
    asyncio.run(scenario())
    assert not control.operation_lock.locked()


def test_offline_mcp_deploy_form_and_jtag_otp_validation(shared, monkeypatch, tmp_path):
    client, control, _, _, app = shared
    seen = []
    monkeypatch.setattr('mklink.probe_volumes.resolve_volume', lambda *a: {'root': str(tmp_path)})
    @app.post('/api/offline-download/deploy')
    async def deploy(config_json: str = Form(...), request_id: str = Form(...)):
        seen.append((json.loads(config_json), request_id))
        return {'status': 'deployed'}
    @app.post('/api/device/configuration/hpm-user-otp/program')
    async def program(body: dict):
        seen.append(body)
        return {'ok': True}
    session = attach(client)
    assert call(client, session, 'hpm_otp_jtag_program', {'part_number': 'HPM5301'}).status_code == 422
    assert not seen
    async def scenario():
        async with Client(runtime_mcp.build_server()) as mcp:
            await mcp.call_tool('connect', {})
            config = {'model': 'V4', 'firmwares': [{'source_path': 'local.bin'}]}
            assert (await mcp.call_tool('offline_download', {'action': 'deploy', 'config': config,
                                    'request_id': 'once', 'confirm': True})).data['status'] == 'deployed'
            assert (await mcp.call_tool('hpm_otp', {'transport': 'jtag', 'action': 'batch-plan',
                                                  'arguments': {}}, raise_on_error=False)).is_error
    asyncio.run(scenario())
    assert seen == [({'model': 'V4', 'firmwares': [{'source_path': 'local.bin'}]}, 'once')]


@pytest.mark.parametrize('status,state', [('complete', 'succeeded'), ('failed', 'failed'), ('unknown', 'unknown')])
def test_offline_trigger_is_journaled_and_deduplicated(runtime, tmp_path, monkeypatch, status, state):
    client, control, _, _, app = runtime
    control.jobs.path = tmp_path / 'jobs.json'
    monkeypatch.setattr('mklink.probe_volumes.resolve_volume', lambda *a: {'root': str(tmp_path)})
    calls = []
    @app.post('/api/offline-download/trigger-job')
    async def trigger(body: dict):
        calls.append(body)
        return {'status': status}
    payload = {'action': 'offline_trigger', 'request_id': 'single', 'confirm': True,
               'arguments': {'model': 'V4', 'script_name': 'checked.py'}}
    first = client.post('/api/runtime/jobs/', json=payload)
    assert first.status_code == 202, first.text
    # TestClient waits for application tasks at each boundary; explicitly drain
    # the retained task when the endpoint returns before its worker.
    async def drain():
        await asyncio.gather(*control.jobs.tasks)
    client.portal.call(drain)
    second = client.post('/api/runtime/jobs/', json=payload)
    assert second.json()['job_id'] == first.json()['job_id']
    assert second.json()['state'] == state, second.text
    assert len(calls) == 1


def test_legacy_burn_prepares_first_jtag_clock_before_rejecting_low_frequency(tmp_path, monkeypatch):
    from test_clock_first_use import fresh_bridge
    from mklink.flash import MKLinkFlash, burn_hex_file
    b = fresh_bridge()
    flash = MKLinkFlash(b)
    image = tmp_path / 'test.bin'
    image.write_bytes(b'test')
    monkeypatch.setattr(MKLinkFlash, 'connect', lambda *a, **k: flash)
    monkeypatch.setattr(flash, 'close', lambda: None)
    monkeypatch.setattr(flash, 'get_idcode', Mock(side_effect=RuntimeError('stop before programming')))
    monkeypatch.setattr('mklink.project_config.load_config', lambda *a, **k: {})
    monkeypatch.setattr('mklink.project_config.load_keil_project', lambda *a, **k: {'device': 'HPM5301', 'board': 'hpm5301evklite'})
    with pytest.raises(RuntimeError, match='stop before programming'):
        burn_hex_file(str(image), port='fixture', swd_clock=5000, project_root=str(tmp_path))
    assert [c.args[0] for c in b.send_command.call_args_list] == ['cmd.get_version()', 'cmd.set_swd_clock(5000)']

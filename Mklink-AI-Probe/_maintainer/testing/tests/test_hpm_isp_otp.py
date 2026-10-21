import asyncio
import json
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from mklink import hpm_isp_otp as otp
from mklink.remote.hpm_isp_otp_api import create_hpm_isp_otp_router
from mklink.remote.resource_manager import ResourceGroup, ResourceManager, ResourceError
from test_shared_runtime import runtime


def record(**changes):
    return dict(schema=1, event="result", request_id="test", code=0, rom_status=0,
                chip_id=otp.CHIP_ID, hard_lock=1 << 18,
                part='HPM5301', memory_id=0x20000, start_word=69,
                read_source='rom_otp', read_semantics='unknown', values=list(range(69, 80)),
                **changes)


def parse(data):
    return otp.parse_snapshot('HPM_OTP ' + json.dumps(data), 'test', 'HPM5301')


def test_read_values_and_unknown_locks():
    result = parse(record())
    assert result['words'][0] == dict(word=69, current=69, shadow=None, locked=None)
    assert result['words'][3]['locked'] is None
    assert result['words'][7]['locked'] is None


@pytest.mark.parametrize('key,value', [('request_id', 'stale'), ('schema', True), ('schema', 2),
    ('code', False), ('code', -3), ('rom_status', 1), ('chip_id', 0), ('hard_lock', -1),
    ('values', []), ('values', [None] * 11), ('start_word', 68), ('start_word', True),
    ('memory_id', 0), ('part', 'HPM5300'), ('read_source', 'ram'), ('read_semantics', 'invalid')])
def test_invalid_or_stale_result_is_not_a_snapshot(key, value):
    data = record(); data[key] = value
    with pytest.raises(ValueError): parse(data)


@pytest.mark.parametrize('value', [True, -1, 2**32, '0', None])
def test_invalid_word_is_not_displayed(value):
    data = record(); data['values'][0] = value
    with pytest.raises(ValueError): parse(data)


def test_duplicate_results_and_echo_are_not_success():
    line = 'HPM_OTP ' + json.dumps(record())
    for text in (line + '\n' + line, 'print(' + line + ')', 'HPM_OTP broken'):
        with pytest.raises(ValueError): otp.parse_snapshot(text, 'test', 'HPM5301')


def test_read_sends_only_capability_and_fixed_read(monkeypatch):
    monkeypatch.setattr(otp.uuid, 'uuid4', lambda: SimpleNamespace(hex='test'))
    bridge = SimpleNamespace(send_command=Mock(side_effect=['MKLINK_HPM_ISP_OTP_API 1', 'HPM_OTP ' + json.dumps(record())]))
    assert otp.read_snapshot(bridge, 'HPM5301')['chip_id'] == otp.CHIP_ID
    assert [c.args[0] for c in bridge.send_command.call_args_list] == [otp.CAPABILITY_COMMAND, 'hpm.isp_otp_read("test",30000,1000)']


@pytest.mark.parametrize('response', ['', '1', 'MKLINK_HPM_ISP_OTP_API 0', 'print("MKLINK_HPM_ISP_OTP_API 1")'])
def test_old_firmware_is_not_given_read_command(response):
    bridge = SimpleNamespace(send_command=Mock(return_value=response))
    with pytest.raises(ValueError, match='Upgrade'): otp.read_snapshot(bridge, 'HPM5301')
    assert bridge.send_command.call_count == 1


def app_fixture(monkeypatch, device=None):
    app = FastAPI()
    manager = ResourceManager()
    app.include_router(create_hpm_isp_otp_router(manager, lambda: device))
    reader = Mock(return_value={'words': []})
    monkeypatch.setattr(otp, 'read_snapshot', reader)
    return app, manager, reader


URL = '/api/device/configuration/hpm-isp-otp/read'


@pytest.mark.parametrize('extra', [{'part_number': 'HPM6280'}, {'model': 'V3'}, {'word': 1}, {'desired': 1}, {'port': 'other'}])
def test_api_rejects_other_chips_and_write_parameters(monkeypatch, extra):
    app, manager, reader = app_fixture(monkeypatch)
    with TestClient(app) as client:
        assert client.post(URL, json={'part_number': 'HPM5301', **extra}).status_code == 422
        assert client.post(URL.replace('/read', '/program'), json={}).status_code == 404
    reader.assert_not_called()
    assert not manager.get_status()


def test_no_jtag_no_sd_read_opens_and_closes_owned_bridge(monkeypatch):
    app, manager, reader = app_fixture(monkeypatch)
    bridge = Mock(); bridge.connect.return_value = True
    monkeypatch.setattr('mklink.discovery.find_mklink_cdc_port', lambda: 'FIXTURE')
    factory = Mock(return_value=bridge)
    monkeypatch.setattr('mklink.bridge.MKLinkSerialBridge', factory)
    with TestClient(app) as client:
        assert client.post(URL, json={'part_number': 'HPM5301'}).status_code == 200
    factory.assert_called_once_with('FIXTURE')
    reader.assert_called_once_with(bridge, 'HPM5301')
    bridge.close.assert_called_once()
    assert not manager.get_status()


@pytest.mark.parametrize('group', list(ResourceGroup))
def test_read_never_preempts_existing_owner(monkeypatch, group):
    app, manager, reader = app_fixture(monkeypatch)
    manager.acquire(group, 'ai:existing')
    with TestClient(app) as client:
        assert client.post(URL, json={'part_number': 'HPM5301'}).status_code == 409
    reader.assert_not_called()
    assert manager.get_active_lease(group).owner == 'ai:existing'
    assert len(manager.get_status()) == 1


def test_cancellation_holds_all_leases_until_reader_finishes(monkeypatch):
    bridge = Mock()
    app, manager, reader = app_fixture(monkeypatch, SimpleNamespace(connected=True, _bridge=bridge))
    started, release = Event(), Event()
    def slow_read(*_):
        started.set()
        assert release.wait(5)
        return {'words': []}
    reader.side_effect = slow_read
    endpoint = next(r.endpoint for r in app.routes if r.path == URL)
    from mklink.remote.hpm_isp_otp_api import OtpReadRequest
    async def scenario():
        task = asyncio.create_task(endpoint(SimpleNamespace(app=app), OtpReadRequest(part_number='HPM5301')))
        assert await asyncio.to_thread(started.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        for group in ResourceGroup:
            with pytest.raises(ResourceError): manager.acquire(group, 'user:other')
        release.set()
        with pytest.raises(asyncio.CancelledError): await task
        assert not manager.get_status()
    asyncio.run(scenario())
    bridge.close.assert_not_called()


def test_shared_runtime_binds_otp_to_probe_and_blocks_uart_clients(runtime, monkeypatch):
    client, control, _, _, app = runtime
    control.info['probe_id'] = 'fixture-probe'
    monkeypatch.setattr('mklink.probes.inventory', lambda: [{'probe_id': 'fixture-probe', 'port': 'COM9'}])
    monkeypatch.setattr('mklink.probes.select_probe', lambda _: {'probe_id': 'fixture-probe', 'port': 'COM9'})
    state = app.state.mklink_state
    bridge = Mock(); state['device']._bridge = bridge
    app.include_router(create_hpm_isp_otp_router(state['resource_manager'], lambda: state['device']))
    def reader(*_):
        assert control.current_operation['uart_exclusive'] is True
        return {'words': []}
    read = Mock(side_effect=reader)
    monkeypatch.setattr(otp, 'read_snapshot', read)
    assert client.post(URL, json={'part_number': 'HPM5301'}, headers={'X-MKLink-Probe': 'other'}).status_code == 409
    assert client.post(URL, json={'part_number': 'HPM5301'}, headers={'X-MKLink-Device-Generation': '999'}).status_code == 409
    read.assert_not_called()
    session = client.post('/_runtime/attach', json={'scope': 'uart'}).json()['session_id']
    assert client.post(URL, json={'part_number': 'HPM5301'}).status_code == 409
    read.assert_not_called()
    control.sessions.pop(session)
    assert client.post(URL, json={'part_number': 'HPM5301'}).status_code == 200
    read.assert_called_once_with(bridge, 'HPM5301')
    assert not state['resource_manager'].get_status()

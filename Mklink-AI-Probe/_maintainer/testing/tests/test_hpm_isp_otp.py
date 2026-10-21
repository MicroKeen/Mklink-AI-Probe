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
        assert client.post(URL.replace('/read', '/program'), json={}).status_code == 422
    reader.assert_not_called()
    assert not manager.get_status()


@pytest.mark.parametrize('word,old,new', [(68, 0, 1), (80, 0, 1), (True, 0, 1), (69, True, 1),
    (69, 5, 1), (69, 0, -1), (69, 0, 2**32), (69, 0, 'bad'), (69, 5, 5)])
def test_invalid_write_change_never_reaches_hardware(word, old, new):
    with pytest.raises(ValueError): otp.validate_change(word, old, new)


def test_write_change_reuses_jtag_unsigned_and_monotonic_bit_rules():
    assert otp.validate_change(69, 5, '0x80000007') == dict(word=69, expected=5, desired=0x80000007, delta=0x80000002)


def test_write_plan_requires_bound_runtime(monkeypatch):
    app, manager, reader = app_fixture(monkeypatch)
    with TestClient(app) as client:
        response = client.post(URL.replace('/read', '/plan'), json=dict(part_number='HPM5301', word=69, expected=0, desired=1))
        assert response.status_code == 409
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


def write_runtime(runtime, monkeypatch):
    client, control, _, _, app = runtime
    control.info['probe_id'] = 'fixture-probe'
    monkeypatch.setattr('mklink.probes.inventory', lambda: [{'probe_id': 'fixture-probe', 'port': 'COM9'}])
    monkeypatch.setattr('mklink.probes.select_probe', lambda _: {'probe_id': 'fixture-probe', 'port': 'COM9'})
    state = app.state.mklink_state
    bridge = Mock(); state['device']._bridge = bridge
    app.include_router(create_hpm_isp_otp_router(state['resource_manager'], lambda: state['device']))
    prepare = Mock(side_effect=lambda _bridge, _part, **change: dict(change, qualified=True, write_supported=True, before=change['expected'], reason=None))
    program = Mock(return_value=dict(word=69, after=7, verified=True))
    monkeypatch.setattr(otp, 'plan_change', prepare, raising=False)
    monkeypatch.setattr(otp, 'program_change', program, raising=False)
    monkeypatch.setattr(otp, 'read_snapshot', Mock(return_value={'words': []}))
    return client, state, prepare, program


def test_server_preview_is_required_confirmed_single_use_and_not_client_editable(runtime, monkeypatch):
    client, state, prepare, program = write_runtime(runtime, monkeypatch)
    body = dict(part_number='HPM5301', word=69, expected=5, desired='0x7')
    result = client.post(URL.replace('/read', '/plan'), json=body)
    assert result.status_code == 200, result.text
    plan = result.json()
    assert plan['expected'] == 5 and plan['delta'] == 2
    payload = dict(part_number='HPM5301', plan_id=plan['plan_id'], confirm_irreversible=False)
    assert client.post(URL.replace('/read', '/program'), json=payload).status_code == 422
    payload['confirm_irreversible'] = True
    assert client.post(URL.replace('/read', '/program'), json={**payload, 'desired': 0xffffffff}).status_code == 422
    program.assert_not_called()
    assert client.post(URL.replace('/read', '/program'), json=payload).status_code == 200
    assert program.call_args.kwargs == dict(word=69, expected=5, desired=7, delta=2)
    assert client.post(URL.replace('/read', '/program'), json=payload).status_code == 422
    assert program.call_count == 1
    assert not state['resource_manager'].get_status()


@pytest.mark.parametrize('invalidate', ['read', 'generation', 'failure'])
def test_read_switch_and_unknown_failure_do_not_leave_reusable_write_approval(runtime, monkeypatch, invalidate):
    client, state, prepare, program = write_runtime(runtime, monkeypatch)
    plan = client.post(URL.replace('/read', '/plan'), json=dict(part_number='HPM5301', word=69, expected=5, desired=7)).json()
    if invalidate == 'read':
        assert client.post(URL, json={'part_number': 'HPM5301'}).status_code == 200
    elif invalidate == 'generation':
        state['device_generation'] = state.get('device_generation', 0) + 1
    else:
        program.side_effect = RuntimeError('Unknown ROM result; do not retry')
    payload = dict(part_number='HPM5301', plan_id=plan['plan_id'], confirm_irreversible=True)
    assert client.post(URL.replace('/read', '/program'), json=payload).status_code == 422
    assert client.post(URL.replace('/read', '/program'), json=payload).status_code == 422
    assert program.call_count == (1 if invalidate == 'failure' else 0)
    assert not state['resource_manager'].get_status()


CHANGE = dict(word=69, expected=5, desired=7, delta=2)


def change_record(**changes):
    result = dict(schema=1, event='result', request_id='test', code=0, rom_status=0,
        operation='plan', part='HPM5301', chip_id=otp.CHIP_ID, read_source='rom_otp',
        read_semantics='unknown', hard_lock=0, before=5, after=None, qualified=False,
        write_supported=False, write_attempted=False, verified=False,
        reason='read_semantics_and_locks_unknown', locked=None, fuse_lock=None, shadow_lock=None, **CHANGE)
    result.update(changes)
    return result


def qualified_record(**changes):
    result = change_record(qualified=True, write_supported=True, reason='ok',
                          rom_version=0x56010200, soc_revision=0x56010000, lifecycle=4,
                          memory_id=0x20000, write_method='rom_write_memory',
                          verification_source='rom_otp', write_status=None)
    result.update(changes)
    return result


def change_line(data):
    return 'HPM_OTP ' + json.dumps(data)


def test_unqualified_preflight_is_displayable_but_never_issues_commit(monkeypatch):
    monkeypatch.setattr(otp.uuid, 'uuid4', lambda: SimpleNamespace(hex='test'))
    bridge = Mock()
    bridge.send_command.side_effect = ['MKLINK_HPM_ISP_OTP_USER_API 1', change_line(change_record())]
    preview = otp.plan_change(bridge, 'HPM5301', **CHANGE)
    assert preview['qualified'] is False and preview['before'] == 5
    assert bridge.send_command.call_args.args[0] == 'hpm.isp_otp_user("test",69,5,7,0,30000,1000)'
    bridge.reset_mock()
    bridge.send_command.side_effect = ['MKLINK_HPM_ISP_OTP_USER_API 1', change_line(change_record())]
    with pytest.raises(ValueError, match='unavailable'):
        otp.program_change(bridge, 'HPM5301', **CHANGE)
    assert len(bridge.send_command.call_args_list) == 2
    assert ',7,1,' not in bridge.send_command.call_args.args[0]


@pytest.mark.parametrize('field,value', [('before', 4), ('hard_lock', 1 << 17), ('read_semantics', 'invalid'),
    ('rom_version', 0), ('soc_revision', 0), ('memory_id', 0), ('write_method', 'jtag'), ('verification_source', 'fuse'),
    ('locked', True), ('locked', 0), ('locked', 0.0), ('fuse_lock', 1),
    ('fuse_lock', 4), ('shadow_lock', 1), ('shadow_lock', True), ('word', 70), ('expected', 4),
    ('desired', 15), ('delta', 10), ('chip_id', 0), ('qualified', 1), ('write_supported', False),
    ('write_attempted', True), ('write_status', 0), ('verified', True), ('after', 7), ('operation', 'program')])
def test_firmware_cannot_qualify_stale_locked_or_mismatched_change(field, value):
    record = qualified_record(); record[field] = value
    with pytest.raises(ValueError):
        otp.parse_change(change_line(record), 'test', CHANGE, commit=False)


def test_commit_requires_fresh_preflight_and_exact_verified_result_without_retry(monkeypatch):
    monkeypatch.setattr(otp.uuid, 'uuid4', lambda: SimpleNamespace(hex='test'))
    bridge = Mock()
    bridge.send_command.side_effect = ['MKLINK_HPM_ISP_OTP_USER_API 2', change_line(qualified_record()),
        'MKLINK_HPM_ISP_OTP_USER_API 2', change_line(qualified_record(operation='program', write_attempted=True, verified=True, after=7, write_status=0))]
    result = otp.program_change(bridge, 'HPM5301', **CHANGE)
    assert result['verified'] is True
    assert result['verification_source'] == 'rom_otp' and result['read_semantics'] == 'unknown'
    assert bridge.send_command.call_args.args[0] == 'hpm.isp_otp_user("test",69,5,7,1,30000,1000)'
    bridge.reset_mock()
    bridge.send_command.side_effect = ['MKLINK_HPM_ISP_OTP_USER_API 2', change_line(qualified_record()),
        'MKLINK_HPM_ISP_OTP_USER_API 2', 'HPM_OTP truncated']
    with pytest.raises(ValueError): otp.program_change(bridge, 'HPM5301', **CHANGE)
    assert bridge.send_command.call_count == 4


def test_rom_command_preflight_allows_unknown_transient_locks_and_read_origin():
    result = otp.parse_change(change_line(qualified_record()), 'test', CHANGE, commit=False)
    assert result['qualified'] is True
    assert result['read_semantics'] == 'unknown'
    assert result['verification_source'] == 'rom_otp'


def test_preflight_only_firmware_cannot_grant_write_permission(monkeypatch):
    monkeypatch.setattr(otp.uuid, 'uuid4', lambda: SimpleNamespace(hex='test'))
    bridge = Mock()
    bridge.send_command.side_effect = ['MKLINK_HPM_ISP_OTP_USER_API 1', change_line(qualified_record())]
    with pytest.raises(ValueError, match='preflight-only'):
        otp.program_change(bridge, 'HPM5301', **CHANGE)
    assert bridge.send_command.call_count == 2


@pytest.mark.parametrize('capability', ['MKLINK_HPM_ISP_OTP_USER_API 1',
    'MKLINK_HPM_ISP_OTP_USER_API 0', 'MKLINK_HPM_ISP_OTP_USER_API 3',
    'MKLINK_HPM_ISP_OTP_USER_API 2\nMKLINK_HPM_ISP_OTP_USER_API 2', '2', ''])
def test_capability_change_before_commit_never_sends_program(monkeypatch, capability):
    monkeypatch.setattr(otp.uuid, 'uuid4', lambda: SimpleNamespace(hex='test'))
    bridge = Mock()
    bridge.send_command.side_effect = ['MKLINK_HPM_ISP_OTP_USER_API 2', change_line(qualified_record()), capability]
    with pytest.raises(ValueError, match='Upgrade'):
        otp.program_change(bridge, 'HPM5301', **CHANGE)
    assert bridge.send_command.call_count == 3
    assert bridge.send_command.call_args.args[0] == otp.USER_CAPABILITY_COMMAND


@pytest.mark.parametrize('field,value', [('write_status', None), ('write_status', 1),
    ('write_status', False), ('rom_status', 1), ('code', -3), ('verified', False),
    ('write_attempted', False), ('after', 5), ('after', None), ('after', True),
    ('verification_source', 'fuse'), ('qualified', False)])
def test_program_requires_rom_write_success_and_complete_matching_readback(field, value):
    record = qualified_record(operation='program', write_attempted=True, verified=True, after=7, write_status=0)
    record[field] = value
    with pytest.raises(ValueError):
        otp.parse_change(change_line(record), 'test', CHANGE, commit=True)


@pytest.mark.parametrize('reason,code,message', [
    ('write_outcome_unknown', -3, 'write result is unknown'),
    ('readback_failed', -3, 'ROM readback failed'),
    ('readback_mismatch', -2, 'does not match'),
    ('rom_rejected', -6, 'ROM rejected OTP programming'),
])
def test_write_errors_report_rom_outcome_without_suggesting_replay(reason, code, message):
    record = qualified_record(operation='program', code=code, reason=reason,
                              write_attempted=True, write_status=0)
    with pytest.raises(ValueError) as caught:
        otp.parse_change(change_line(record), 'test', CHANGE, commit=True)
    assert message in str(caught.value)
    assert 'may already have changed' in str(caught.value)
    assert 'do not retry' in str(caught.value)
    assert 'ROM write status 0' in str(caught.value)


def test_unqualified_firmware_receives_no_execution_token(runtime, monkeypatch):
    client, _, prepare, program = write_runtime(runtime, monkeypatch)
    prepare.side_effect = lambda *_, **change: dict(change, before=5, qualified=False, write_supported=False,
                                                  reason='read_semantics_and_locks_unknown')
    response = client.post(URL.replace('/read', '/plan'), json=dict(part_number='HPM5301', word=69, expected=5, desired=7))
    assert response.status_code == 200
    assert response.json()['plan_id'] is None
    assert response.json()['expires_in'] == 0
    program.assert_not_called()

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink._types import DeviceState
from mklink.hpm_debug import HpmDebugError, command_arguments, execute


def receipt(op, **changes):
    data = dict(v=1, op=op, rc=0, issued=0, cleanup=0, value=511 if op == 0 else 0,
                dmstatus=0, state=2, slot=0, tdata1=0, tdata2=0, xlen=32, hart=0, max_slot=7)
    data.update(changes)
    return 'diagnostic\nHPM_DEBUG ' + json.dumps(data) + '\n0\n'


def device(response, capabilities=None):
    return SimpleNamespace(_require_connected=Mock(), _bridge=SimpleNamespace(
        state=DeviceState.READY, send_command=Mock(side_effect=['hpm.debug_version()\n1\n',
        capabilities or receipt(0), response])))


@pytest.mark.parametrize('body', [
    {'action': 'read-register', 'register': 'SCB.CFSR'},
    {'action': 'read-register', 'register': 'x32'},
    {'action': 'write-register', 'register': 'x0', 'value': 1},
    {'action': 'write-register', 'register': 'mstatus', 'value': 1},
    {'action': 'write-register', 'register': 'pc', 'value': 3},
    {'action': 'breakpoint-set', 'slot': 8, 'address': 0x80000400},
    {'action': 'breakpoint-clear', 'slot': 0},
    {'action': 'breakpoint-set', 'slot': True, 'address': 0},
    {'action': 'breakpoint-set', 'slot': 0, 'address': '0x80000400);bad()'},
    {'action': 'halt', 'timeout_ms': 1001}, {'action': 'halt', 'timeout_ms': True},
    {'action': 'status', 'timeout_ms': 100}, {'action': 'status', 'reset': True},
])
def test_invalid_requests_never_touch_probe(body):
    d = device('')
    with pytest.raises(ValueError):
        execute(d, body)
    d._bridge.send_command.assert_not_called()


@pytest.mark.parametrize('body,op,command', [
    ({'action': 'status'}, 1, 'hpm.debug(1)'),
    ({'action': 'halt'}, 2, 'hpm.debug(2,500)'),
    ({'action': 'resume', 'timeout_ms': 1000}, 3, 'hpm.debug(3,1000)'),
    ({'action': 'step'}, 4, 'hpm.debug(4,500)'),
    ({'action': 'read-register', 'register': 'mcause'}, 5, 'hpm.debug(5,1,834)'),
    ({'action': 'read-register', 'register': 'sp'}, 5, 'hpm.debug(5,0,2)'),
    ({'action': 'write-register', 'register': 'pc', 'value': 0x80000400}, 6, 'hpm.debug(6,0,32,2147484672)'),
    ({'action': 'breakpoint-query', 'slot': 3}, 7, 'hpm.debug(7,3)'),
    ({'action': 'breakpoint-set', 'slot': 0, 'address': 0x80000402}, 8, 'hpm.debug(8,0,2147484674)'),
    ({'action': 'breakpoint-clear', 'slot': 0, 'address': 0x80000402}, 9, 'hpm.debug(9,0,2147484674)'),
])
def test_negotiated_commands_preserve_riscv_registers_and_u32_addresses(body, op, command):
    d = device(receipt(op, value=0x80000402))
    assert execute(d, body)['value'] == 0x80000402
    assert [c.args[0] for c in d._bridge.send_command.call_args_list] == [
        'hpm.debug_version()', 'hpm.debug(0)', command]


@pytest.mark.parametrize('response', ['NameError', '0', '', '1\n0', 'hpm.debug_version()'])
def test_old_firmware_never_receives_an_arm_or_mutating_fallback(response):
    d = device('')
    d._bridge.send_command.side_effect = [response]
    with pytest.raises(HpmDebugError, match='does not expose'):
        execute(d, {'action': 'halt'})
    assert d._bridge.send_command.call_count == 1


def test_capability_mask_blocks_unavailable_operation():
    d = device('', receipt(0, value=1))
    with pytest.raises(HpmDebugError, match='does not advertise'):
        execute(d, {'action': 'halt'})
    assert d._bridge.send_command.call_count == 2


@pytest.mark.parametrize('response', [
    '0\n', receipt(3), receipt(4, v=2), receipt(4, issued=True),
    receipt(4) + receipt(4), 'HPM_DEBUG {"v":1}', receipt(4, value=-1),
])
def test_malformed_step_receipt_is_unknown_and_never_replayed(response):
    d = device(response)
    with pytest.raises(HpmDebugError) as failure:
        execute(d, {'action': 'step'})
    assert failure.value.detail['outcome_unknown']
    assert d._bridge.send_command.call_count == 3


def test_failed_step_preserves_issued_and_cleanup_without_recovery():
    d = device(receipt(4, rc=-5, issued=1, cleanup=1, state=1))
    with pytest.raises(HpmDebugError) as failure:
        execute(d, {'action': 'step'})
    assert failure.value.detail['record']['state'] == 1
    assert failure.value.detail['record']['cleanup'] == 1
    assert failure.value.detail['outcome_unknown']
    assert d._bridge.send_command.call_count == 3


def test_register_read_does_not_implicitly_halt():
    d = device(receipt(5, rc=-7, state=1))
    with pytest.raises(HpmDebugError, match='already be halted'):
        execute(d, {'action': 'read-register', 'register': 'pc'})
    assert d._bridge.send_command.call_count == 3


def test_live_stream_is_not_interrupted_for_cpu_debug():
    d = device('')
    d._bridge.state = DeviceState.DUMP_STREAM
    with pytest.raises(ValueError, match='active acquisition'):
        execute(d, {'action': 'status'})
    d._bridge.send_command.assert_not_called()


def test_http_preserves_uncertain_receipt_and_releases_lease(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from mklink.remote.api import create_app
    managers = {name: SimpleNamespace(running=False) for name in ('rtt', 'superwatch', 'systemview', 'vofa', 'serial', 'modbus')}
    monkeypatch.setattr('mklink.remote.dashboards.get_managers', lambda: managers)
    d = device(receipt(4, rc=-9, issued=1))
    d.connected = True
    d.hpm_debug = lambda **body: execute(d, body)
    d.close = Mock()
    app = create_app(project_root=str(tmp_path))
    app.state.mklink_state['device'] = d
    with TestClient(app) as client:
        result = client.post('/api/device/hpm-debug', json={'action': 'step'})
        assert result.status_code == 409
        assert result.json()['detail']['record']['issued'] == 1
        assert result.json()['detail']['outcome_unknown']
        assert app.state.mklink_state['resource_manager'].get_status() == {}


def test_mcp_schema_and_dispatch_use_shared_hpm_interface(monkeypatch):
    from fastmcp import Client
    from mklink import runtime_mcp
    calls = []
    class Runtime:
        info = {}
        def __init__(self, **kwargs): pass
        def connect(self, **kwargs): return {'connected': True}
        def close(self): pass
        def call(self, capability, arguments):
            command_arguments(arguments)
            calls.append((capability, arguments))
            return {'op': 5, 'value': 42}
    monkeypatch.setattr(runtime_mcp, 'RuntimeClient', Runtime)
    async def scenario():
        async with Client(runtime_mcp.build_server()) as mcp:
            assert 'hpm_debug' in [tool.name for tool in await mcp.list_tools()]
            await mcp.call_tool('connect', {})
            result = await mcp.call_tool('hpm_debug', {'action': 'read-register', 'register': 'mcause'})
            assert result.data['value'] == 42
            invalid = await mcp.call_tool('hpm_debug', {'action': 'step', 'timeout_ms': True}, raise_on_error=False)
            assert invalid.is_error
    asyncio.run(scenario())
    assert calls == [('hpm_debug', {'action': 'read-register', 'register': 'mcause'})]

"""FPBv1/v2 shared operations exercise actual bridge encoding and readback."""
import re
import struct
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink import debug_control as debug
from mklink.remote import debug_api


class RegisterBridge:
    def __init__(self, revision=1, count=8):
        self.ctrl_id = (revision << 28) | ((count & 15) << 4) | ((count & 0x70) << 8)
        self.memory = {debug.FP_CTRL: self.ctrl_id, debug.DHCSR: 0}
        self.reads, self.writes = [], []
        self.ignore_address = None
        self.fail_address = None

    def send_command(self, command, **kwargs):
        if command.startswith('cmd.read_ram('):
            address = int(command.split('(')[1].split(',')[0], 16)
            self.reads.append(address)
            value = self.memory.get(address, 0)
            data = struct.pack('<I', value)
            return f'{address:08x} ' + ' '.join(f'{v:02x}' for v in data) + '\n'
        assert command.startswith('cmd.write_ram('), command
        numbers = [int(n, 16) for n in re.findall(r'0x[0-9A-Fa-f]+', command)]
        address, value = numbers[0], int.from_bytes(bytes(numbers[1:]), 'little')
        self.writes.append((address, value))
        if address != self.ignore_address:
            self.memory[address] = self.ctrl_id | (value & 1) if address == debug.FP_CTRL else value
        if address == self.fail_address:
            raise TimeoutError('ACK lost after write; outcome unknown')
        return 'ok\n'


def device_for(bridge):
    return SimpleNamespace(
        _bridge=bridge, _axf=None, _elf_backend=None, _project_root='.',
        _require_cortex_m_debug=Mock(),
        set_breakpoint=lambda address, slot: debug.set_breakpoint(bridge, address, slot),
        clear_breakpoint=lambda slot: debug.clear_breakpoint(bridge, slot),
    )


@pytest.mark.parametrize('revision,address,word', [
    (0, 0, 0x40000001), (0, 0x08005000, 0x48005001),
    (0, 0x08005002, 0x88005001), (0, 0x1ffffffe, 0x9ffffffd),
    (1, 0, 1), (1, 0x08005000, 0x08005001), (1, 0x08005002, 0x08005003),
    (1, 0x20000000, 0x20000001), (1, 0x60000002, 0x60000003),
    (1, 0x80000002, 0x80000003), (1, 0xfffffffe, 0xffffffff),
])
def test_shared_set_query_clear_round_trip(revision, address, word):
    bridge = RegisterBridge(revision)
    device = device_for(bridge)
    state = debug_api.breakpoints(device, {'action': 'status'})
    assert state['fpb_version'] == revision + 1 and not state['fpb_enabled']
    assert state['num_breakpoints'] == 8 and not state['breakpoints'] and bridge.writes == []
    result = debug_api.breakpoints(device, {'action': 'set', 'target': hex(address), 'slot': 7})
    assert result == {'action': 'set', 'slot': 7, 'address': address, 'verified': True}
    assert bridge.memory[debug.FP_COMP_BASE + 28] == word
    assert bridge.writes == [(debug.FP_CTRL, 3), (debug.FP_COMP_BASE + 28, word)]
    state = debug_api.breakpoints(device, {'action': 'list'})
    assert state['fpb_enabled'] and not state['halted']
    assert state['breakpoints'] == [{'index': 7, 'address': address, 'enabled': True}]
    assert debug_api.breakpoints(device, {'action': 'clear', 'slot': 7})['verified']
    assert not debug_api.breakpoints(device, {'action': 'list'})['breakpoints']
    assert bridge.memory[debug.FP_CTRL] == bridge.ctrl_id | 1  # No blanket disable/reset.


@pytest.mark.parametrize('revision', [2, 15])
@pytest.mark.parametrize('action', ['status', 'list', 'set', 'clear', 'clear_all'])
def test_unknown_revision_is_rejected_without_comparator_access(revision, action):
    bridge = RegisterBridge(revision)
    body = {'action': action}
    if action == 'set': body.update(target='0x08005002', slot=0)
    if action == 'clear': body['slot'] = 0
    with pytest.raises(ValueError, match='Unsupported FPB revision'):
        debug_api.breakpoints(device_for(bridge), body)
    assert bridge.writes == []
    assert all(a in (debug.DHCSR, debug.FP_CTRL) for a in bridge.reads)


@pytest.mark.parametrize('operation', ['set', 'clear', 'clear_all', 'list'])
def test_direct_breakpoint_helpers_also_reject_unknown_revision(operation):
    bridge = RegisterBridge(2)
    with pytest.raises(ValueError, match='Unsupported FPB revision'):
        if operation == 'set': debug.set_breakpoint(bridge, 0x08005000, 0)
        elif operation == 'clear': debug.clear_breakpoint(bridge, 0)
        elif operation == 'clear_all': debug.clear_all_breakpoints(bridge)
        else: debug.list_breakpoints(bridge)
    assert not bridge.writes


@pytest.mark.parametrize('revision', [0, 1])
def test_occupied_slots_preserved_and_auto_assignment_skips_them(revision):
    bridge = RegisterBridge(revision)
    bridge.memory[debug.FP_COMP_BASE] = 0x48006001 if revision == 0 else 0x08006001
    device = device_for(bridge)
    with pytest.raises(ValueError, match='free'):
        debug_api.breakpoints(device, {'action': 'set', 'target': '0x08005002', 'slot': 0})
    with pytest.raises(ValueError, match='occupied'):
        debug.set_breakpoint(bridge, 0x08005002, 0)
    assert not bridge.writes
    assert debug_api.breakpoints(device, {'action': 'set', 'target': '0x08005002'})['slot'] == 1
    old = bridge.memory[debug.FP_COMP_BASE]
    debug_api.breakpoints(device, {'action': 'clear', 'slot': 1})
    assert bridge.memory[debug.FP_COMP_BASE] == old
    assert debug_api.breakpoints(device, {'action': 'clear_all'})['cleared'] == [0]
    assert bridge.memory[debug.FP_COMP_BASE] == 0


@pytest.mark.parametrize('address', [-1, 1, 0x08005001, 0x100000000, True, 1.5, '0x08005000'])
def test_invalid_direct_address_has_no_register_access(address):
    bridge = RegisterBridge()
    with pytest.raises(ValueError): debug.set_breakpoint(bridge, address, 0)
    assert not bridge.reads and not bridge.writes


@pytest.mark.parametrize('count,slot', [(0, 0), (8, 8), (17, 17)])
def test_target_comparator_count_limits_writes(count, slot):
    bridge = RegisterBridge(count=count)
    with pytest.raises((ValueError, RuntimeError)):
        debug_api.breakpoints(device_for(bridge), {'action': 'set', 'target': '0x08005000', 'slot': slot})
    assert not bridge.writes


def test_extended_comparator_count_and_last_slot():
    bridge = RegisterBridge(count=17)
    device = device_for(bridge)
    assert debug_api.breakpoints(device, {'action': 'status'})['num_breakpoints'] == 17
    assert debug_api.breakpoints(device, {'action': 'set', 'target': '0x60000002', 'slot': 16})['verified']
    assert bridge.memory[debug.FP_COMP_BASE + 64] == 0x60000003


@pytest.mark.parametrize('failed_address', [debug.FP_CTRL, debug.FP_COMP_BASE])
def test_shared_v2_failed_write_readback_is_not_retried(failed_address):
    bridge = RegisterBridge()
    bridge.ignore_address = failed_address
    with pytest.raises(RuntimeError, match='verification failed'):
        debug_api.breakpoints(device_for(bridge), {'action': 'set', 'target': '0x08005002', 'slot': 0})
    assert bridge.writes == [(debug.FP_CTRL, 3), (debug.FP_COMP_BASE, 0x08005003)]


def test_unknown_write_outcome_is_not_replayed_or_rolled_back():
    bridge = RegisterBridge()
    bridge.fail_address = debug.FP_COMP_BASE
    with pytest.raises(TimeoutError, match='outcome unknown'):
        debug_api.breakpoints(device_for(bridge), {'action': 'set', 'target': '0x08005002', 'slot': 0})
    assert bridge.writes == [(debug.FP_CTRL, 3), (debug.FP_COMP_BASE, 0x08005003)]


def test_clear_all_stops_at_first_failed_readback():
    bridge = RegisterBridge()
    bridge.memory.update({debug.FP_COMP_BASE: 0x08005001, debug.FP_COMP_BASE + 4: 0x08005003})
    bridge.ignore_address = debug.FP_COMP_BASE
    with pytest.raises(RuntimeError, match='clear verification failed'):
        debug_api.breakpoints(device_for(bridge), {'action': 'clear_all'})
    assert bridge.writes == [(debug.FP_COMP_BASE, 0)]
    assert bridge.memory[debug.FP_COMP_BASE + 4] == 0x08005003


def test_slot_claimed_after_shared_snapshot_is_not_overwritten():
    bridge = RegisterBridge()
    device = device_for(bridge)
    def competing_set(address, slot):
        bridge.memory[debug.FP_COMP_BASE + 4 * slot] = 0x08006001
        return debug.set_breakpoint(bridge, address, slot)
    device.set_breakpoint = competing_set
    with pytest.raises(ValueError, match='occupied'):
        debug_api.breakpoints(device, {'action': 'set', 'target': '0x08005002'})
    assert not bridge.writes and bridge.memory[debug.FP_COMP_BASE] == 0x08006001


def test_v2_full_slots_reject_without_enabling_global_fpb():
    bridge = RegisterBridge()
    bridge.memory.update({debug.FP_COMP_BASE + 4 * i: 0x08006001 + 2 * i for i in range(8)})
    with pytest.raises(ValueError, match='free'):
        debug_api.breakpoints(device_for(bridge), {'action': 'set', 'target': '0x08005002'})
    assert not bridge.writes and bridge.memory[debug.FP_CTRL] == bridge.ctrl_id


@pytest.mark.parametrize('revision,word', [(0, 0x88005001), (1, 0x08005003)])
def test_direct_auto_slot_keeps_encoded_address(revision, word):
    bridge = RegisterBridge(revision)
    bridge.memory[debug.FP_COMP_BASE] = 0x08006001
    assert debug.set_breakpoint(bridge, 0x08005002) == 1
    assert bridge.memory[debug.FP_COMP_BASE + 4] == word
    assert debug.list_breakpoints(bridge)[1].address == 0x08005002


@pytest.mark.parametrize('revision,expected_status', [(0, 200), (1, 200), (2, 422)])
def test_shared_http_contract_and_lease_release(revision, expected_status):
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    bridge = RegisterBridge(revision)
    device = device_for(bridge)
    device.connected = True
    leases = []
    @asynccontextmanager
    async def lease(state, operation):
        leases.append(('acquire', operation))
        try: yield
        finally: leases.append(('release', operation))
    app = FastAPI()
    app.include_router(debug_api.create_debug_router({'device': device}, lease))
    with TestClient(app) as client:
        for body in ({'action': 'status'}, {'action': 'set', 'target': '0x08005002', 'slot': 0},
                     {'action': 'list'}, {'action': 'clear', 'slot': 0}):
            response = client.post('/api/device/breakpoints', json=body)
            assert response.status_code == expected_status, response.text
            if revision == 2:
                assert 'Unsupported FPB revision 2' in response.json()['detail']
            elif body['action'] == 'list':
                assert response.json()['fpb_version'] == revision + 1
                assert response.json()['breakpoints'][0]['address'] == 0x08005002
        if revision == 1:
            bridge.ignore_address = debug.FP_COMP_BASE
            response = client.post('/api/device/breakpoints', json={'action': 'set', 'target': '0x08005002'})
            assert response.status_code == 500 and 'verification failed' in response.json()['detail']
    assert leases == [('acquire', 'breakpoints'), ('release', 'breakpoints')] * (5 if revision == 1 else 4)
    if revision == 2: assert not bridge.writes

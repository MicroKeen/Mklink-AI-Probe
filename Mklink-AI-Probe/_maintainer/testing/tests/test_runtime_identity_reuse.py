from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException

from mklink._types import DeviceState
from mklink.bridge import MKLinkSerialBridge
from mklink.device import Device
from mklink.runtime_api import RuntimeControl


@pytest.fixture
def identity(monkeypatch):
    app = FastAPI()
    bridge = MKLinkSerialBridge('COM9')
    bridge._running = True
    bridge._ctx.state = DeviceState.READY
    bridge._port_lock = SimpleNamespace(_locked=True)
    bridge._serial = SimpleNamespace(is_open=True)
    device = Device(port='COM9')
    device._connected, device._bridge = True, bridge
    app.state.mklink_state = {'device': device, 'device_generation': 1, 'connection_recovery': {'state': 'idle'}}
    control = RuntimeControl(app, {'probe_id': 'usb-fixture'})
    inventory = Mock(return_value=[{'probe_id': 'usb-fixture', 'port': 'COM9'}])
    monkeypatch.setattr('mklink.probes.inventory', inventory)
    now = [10.0]
    monkeypatch.setattr('mklink.runtime_api.time.monotonic', lambda: now[0])
    return control, bridge, device, inventory, now


def test_memory_reuses_only_short_continuously_owned_handle_identity(identity):
    control, bridge, _, inventory, now = identity
    control.require_identity(memory_snapshot=True)
    for _ in range(3):
        now[0] += .05
        control.require_identity(memory_snapshot=True)
    assert inventory.call_count == 1
    now[0] += .2
    control.require_identity(memory_snapshot=True)
    assert inventory.call_count == 2


@pytest.mark.parametrize('change', ['closed', 'new_handle', 'new_connection', 'generation', 'error',
    'state', 'unlock', 'reader_stopped', 'new_device', 'new_identity', 'recovery'])
def test_connection_change_invalidates_cached_identity_before_admission(identity, change):
    control, bridge, device, inventory, _ = identity
    control.require_identity(memory_snapshot=True)
    state = control.app.state.mklink_state
    if change == 'closed': bridge._serial.is_open = False
    elif change == 'new_handle': bridge._serial = SimpleNamespace(is_open=True)
    elif change == 'new_connection': bridge._diagnostic_id = 'new'
    elif change == 'generation': state['device_generation'] += 1
    elif change == 'error': bridge._transport_error = ConnectionError('USB removed')
    elif change == 'state': bridge._ctx.state = DeviceState.ERROR
    elif change == 'unlock': bridge._port_lock._locked = False
    elif change == 'reader_stopped': bridge._running = False
    elif change == 'new_device':
        replacement = Device(port='COM9')
        replacement._connected, replacement._bridge = True, bridge
        state['device'] = replacement
    elif change == 'new_identity': control.info['probe_id'] = 'usb-other'
    elif change == 'recovery': state['connection_recovery'] = {'state': 'recovering'}
    inventory.return_value = []
    with pytest.raises(HTTPException) as caught:
        control.require_identity(memory_snapshot=True)
    assert caught.value.status_code == 409 and inventory.call_count == 2
    assert control._memory_identity_cache is None


@pytest.mark.parametrize('operation', ['other', 'reconnect', 'snapshot'])
def test_other_operations_and_observed_removal_never_trust_memory_cache(identity, operation):
    control, _, _, inventory, _ = identity
    control.require_identity(memory_snapshot=True)
    inventory.return_value = []
    if operation == 'snapshot':
        assert control.presence()['status'] == 'missing'
    with pytest.raises(HTTPException):
        control.require_identity(memory_snapshot=operation == 'snapshot', reconnect=operation == 'reconnect')
    assert inventory.call_count >= 2


def test_same_port_replacement_is_rejected_when_cache_expires(identity):
    control, _, _, inventory, now = identity
    control.require_identity(memory_snapshot=True)
    inventory.return_value = [{'probe_id': 'usb-other', 'port': 'COM9'}]
    now[0] += .251
    with pytest.raises(HTTPException):
        control.require_identity(memory_snapshot=True)
    assert inventory.call_count == 2



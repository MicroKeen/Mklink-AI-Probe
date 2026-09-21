from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink.device import Device


@pytest.mark.parametrize('mcu', ['HPM6E80', 'Unknown'])
@pytest.mark.parametrize('method,args', [
    ('halt', ()), ('resume', ()), ('step', ()),
    ('set_breakpoint', (0x80000400,)), ('clear_breakpoint', (0,)),
    ('clear_all_breakpoints', ()), ('read_core_registers', ()),
])
def test_hpm_rejects_cortex_debug_without_target_access(method, args, mcu):
    device = SimpleNamespace(mcu_name=mcu, _require_connected=Mock(), _bridge=Mock(idcode=0x1000563D))
    device._require_cortex_m_debug = lambda: Device._require_cortex_m_debug(device)
    with pytest.raises(ValueError, match='Cortex-M'):
        getattr(Device, method)(device, *args)
    device._require_connected.assert_called_once()
    assert device._bridge.mock_calls == []


@pytest.mark.parametrize('method,implementation', [('halt','halt_cpu'),('resume','resume_cpu'),('step','step_cpu')])
def test_arm_debug_still_dispatches(monkeypatch, method, implementation):
    device = SimpleNamespace(mcu_name='STM32F103RE', _require_connected=Mock(), _bridge=Mock())
    device._require_cortex_m_debug = lambda: Device._require_cortex_m_debug(device)
    operation = Mock(return_value='state')
    monkeypatch.setattr('mklink.debug_control.'+implementation, operation)
    assert getattr(Device, method)(device) == 'state'
    operation.assert_called_once_with(device._bridge)

@pytest.mark.parametrize('mcu', ['HPM6E80', 'Unknown'])
def test_hpm_hardfault_rejected_without_read(mcu):
    device = SimpleNamespace(mcu_name=mcu, _require_connected=Mock(), _bridge=Mock(idcode=0x1000563D), read_memory=Mock())
    with pytest.raises(ValueError, match='Cortex-M'):
        Device.check_hardfault(device)
    device.read_memory.assert_not_called()


def test_shared_hpm_id_rejects_cortex_named_register(monkeypatch):
    device = SimpleNamespace(mcu_name='Unknown', _require_connected=Mock(), _bridge=Mock(idcode=0x1000563D), _project_root=None, read_memory=Mock())
    monkeypatch.setattr('mklink.peripheral_watch.load_catalog', lambda _: None)
    with pytest.raises(ValueError, match='HPM peripheral catalog'):
        Device.read_register(device, 'SCB.CFSR')
    device.read_memory.assert_not_called()

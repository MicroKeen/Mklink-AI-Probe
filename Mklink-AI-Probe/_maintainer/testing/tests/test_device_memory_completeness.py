from unittest.mock import Mock

import pytest

from mklink.device import Device, DeviceError


@pytest.mark.parametrize('response', [
    'SBA unavailable: debug disabled, unauthenticated or unsupported\n<<<',
    '20000000 01 02\n<<<',
])
def test_inaccessible_or_partial_memory_is_not_success(response):
    device = Device(project_root='')
    device._connected = True
    device._bridge = Mock()
    device._bridge.send_command.return_value = response
    with pytest.raises(DeviceError, match='expected 4'):
        device.read_memory(0x20000000, 4)
    assert device._bridge.send_command.call_count == 1


def test_actual_zero_memory_is_still_valid():
    device = Device(project_root='')
    device._connected = True
    device._bridge = Mock()
    device._bridge.send_command.return_value = '20000000 00 00 00 00\n<<<'
    assert device.read_memory(0x20000000, 4) == bytes(4)

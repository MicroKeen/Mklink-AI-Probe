from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from mklink._types import DeviceState
from mklink.debug_speed import apply_profile, profile_clock


def device(ident=0x1000563D, response='JTAG profile=20000000 scans=1', state=DeviceState.READY):
    return SimpleNamespace(_require_connected=Mock(), state=state, idcode=ident,
        _bridge=SimpleNamespace(state=state, idcode=ident, send_command=Mock(return_value=response), _ctx=SimpleNamespace(swd_clock_hz=0)))


@pytest.mark.parametrize('name,hz', [('low',4000000),('medium',10000000),('high',20000000)])
def test_qualified_profile(name,hz):
    d=device(response=f'JTAG profile={hz} scans=1')
    r=apply_profile(d,name)
    assert r['clock_hz']==hz and r['profile_confirmed']
    d._bridge.send_command.assert_called_once_with(f'cmd.set_swd_clock({hz})')


def test_old_firmware_restores_conservative_clock():
    d=device(response='set clock 20000000\nJTAG profile=0 scans=1')
    with pytest.raises(ValueError,match='restored 1 MHz'): apply_profile(d,'high')
    assert d._bridge._ctx.swd_clock_hz==1000000
    assert d._bridge.send_command.call_args.args==('cmd.set_swd_clock(1000000)',)


def test_arm_high_is_not_silently_mislabeled():
    d=device(ident=0x1BA01477)
    with pytest.raises(ValueError,match='qualification'): apply_profile(d,'high')
    d._bridge.send_command.assert_not_called()


def test_live_stream_is_not_interrupted_by_raw_command():
    d=device(state=DeviceState.DUMP_STREAM)
    with pytest.raises(ValueError,match='Stop'): apply_profile(d,'high')
    d._bridge.send_command.assert_not_called()


@pytest.mark.parametrize('profile', ['20M','fast',None,20,{},''])
def test_invalid_profile(profile):
    with pytest.raises(ValueError): profile_clock(profile)

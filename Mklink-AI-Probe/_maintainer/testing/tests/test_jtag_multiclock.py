"""Advertised JTAG clocks require their own exact configured/applied reply."""
import pytest

from mklink.capture_clock import V3_CLOCKS, clock_options
from mklink.debug_speed import apply_bridge_clock
from mklink.flash import MKLinkFlash
from mklink.project_config import load_config
from mklink.runtime import RuntimeErrorResponse
from test_clock_interface_ack import bridge
from test_runtime_memory import batch
from test_runtime_watch_timing import shared_client


def modern_jtag():
    b = bridge(interface='JTAG')
    b._firmware_capabilities |= {'JTAG_CLOCK_ACK=1', 'JTAG_CLOCKS='+','.join(map(str,V3_CLOCKS))}
    return b


@pytest.mark.parametrize('state', ['configured','applied'])
@pytest.mark.parametrize('hz', [*V3_CLOCKS,4000000])
@pytest.mark.parametrize('entry', ['numeric','flash'])
def test_jtag_multiclock_requires_exact_interface_profile_and_state(hz,state,entry):
    b = modern_jtag()
    b.send_command.return_value = f'set clock {hz}\nJTAG profile={hz}\nJTAG clock_state={state}'
    if entry == 'numeric':
        result = apply_bridge_clock(b,hz)
        assert result['interface'] == 'JTAG' and result['apply_state'] == state
        assert result['applied_hz'] == (hz if state == 'applied' else None)
    else:
        MKLinkFlash(b).set_swd_clock(hz)
    assert b._ctx.swd_clock_hz == hz
    assert b._ctx.applied_clock_hz == (hz if state == 'applied' else 0)
    assert b.send_command.call_count == 1
    assert b.send_command.call_args.args[0] == f'cmd.set_swd_clock({hz})'


@pytest.mark.parametrize('reply', [
    'set clock 2000000\nJTAG profile=2000000',
    'set clock 2000000\nJTAG clock_state=applied',
    'set clock 2000000\nJTAG profile=2000000\nSWD clock_state=applied',
    'set clock 2000000\nSWD profile=2000000\nJTAG clock_state=applied',
    'set clock 2000000\nJTAG profile=2000000\nJTAG clock_state=unknown',
    'set clock 2000000\nJTAG profile=2000000\nJTAG clock_state=applied\nJTAG clock_state=configured',
    'set clock 2000000\nJTAG profile=10000000\nJTAG clock_state=applied',
    'set clock 2000000\nJTAG profile=0',
    'JTAG profile=2000000\nJTAG clock_state=applied',
    'set clock 2000000\nJTAG profile=2000000\nJTAG clock_state=applied\n-1',
])
def test_invalid_new_ack_clears_confirmation_without_replaying(reply):
    b = modern_jtag()
    b.send_command.return_value = reply
    with pytest.raises(ValueError): apply_bridge_clock(b,2000000)
    b.send_command.assert_called_once()
    assert b._ctx.swd_clock_hz == b._ctx.applied_clock_hz == 0


@pytest.mark.parametrize('missing', ['JTAG_CLOCK_ACK=1', 'JTAG_CLOCKS='+','.join(map(str,V3_CLOCKS))])
def test_both_capabilities_are_required_for_new_jtag_frequencies(missing):
    b = modern_jtag()
    b._firmware_capabilities -= {missing}
    with pytest.raises(ValueError): apply_bridge_clock(b,2000000)
    b.send_command.assert_not_called()
    assert clock_options(b)['clocks_hz'] == [4000000,10000000,20000000,30000000]


@pytest.mark.parametrize('state', ['configured','applied'])
@pytest.mark.parametrize('hz', V3_CLOCKS)
def test_shared_numeric_clock_keeps_existing_admission_and_does_not_save(batch,monkeypatch,hz,state):
    _,runtime,device,control,_ = batch
    b = modern_jtag()
    device._bridge = b
    device._flash = MKLinkFlash(b)
    b.send_command.return_value = f'set clock {hz}\nJTAG profile={hz}\nJTAG clock_state={state}'
    client = shared_client(batch,monkeypatch)
    result = client.call('set_debug_speed',{'clock_hz':hz,'save':False})
    assert result['interface'] == 'JTAG' and result['apply_state'] == state
    assert result['configured_hz'] == hz and result['applied_hz'] == (hz if state == 'applied' else None)
    assert result['stopped'] == [] and not result['saved']
    assert not load_config(runtime['project_root'])
    b.send_command.assert_called_once()
    assert not control.operation_lock.locked() and not runtime['resource_manager'].get_status()


def test_old_firmware_rejects_shared_low_jtag_clock_before_write(batch,monkeypatch):
    _,_,device,_,_ = batch
    b = bridge(interface='JTAG')
    device._bridge = b
    device._flash = MKLinkFlash(b)
    client = shared_client(batch,monkeypatch)
    with pytest.raises(RuntimeErrorResponse): client.call('set_debug_speed',{'clock_hz':2000000,'save':False})
    b.send_command.assert_not_called()


def test_new_jtag_clock_does_not_stop_busy_capture(batch,monkeypatch):
    _,_,device,_,managers = batch
    b = modern_jtag()
    device._bridge = b
    device._flash = MKLinkFlash(b)
    managers['rtt'].running = True
    client = shared_client(batch,monkeypatch)
    with pytest.raises(RuntimeErrorResponse): client.call('set_debug_speed',{'clock_hz':2000000,'save':False})
    assert managers['rtt'].running
    b.send_command.assert_not_called()

"""Global SWD capabilities cannot change the JTAG acknowledgement contract."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink._types import DeviceContext, DeviceState
from mklink.capture_clock import V3_CLOCKS, clock_options
from mklink.debug_speed import PROFILES, apply_bridge_profile
from mklink.flash import FlashError, MKLinkFlash
from mklink.project_config import load_config, save_config
from mklink.runtime import RuntimeErrorResponse
from test_runtime_memory import batch
from test_runtime_watch_timing import shared_client


def bridge(*, modern=True, identity=0x1000563D, interface='unknown'):
    context = DeviceContext(state=DeviceState.READY)
    context.clock_interface = interface
    context.swd_clock_hz = 10_000_000
    context.applied_clock_hz = 10_000_000
    context.clock_apply_state = 'applied'
    caps = {'V4.7.2'}
    if modern:
        caps |= {'SWD_CLOCK_ACK=1', 'SWD_CLOCKS='+','.join(map(str, V3_CLOCKS))}
    return SimpleNamespace(_ctx=context, idcode=identity, state=DeviceState.READY,
                           _firmware_capabilities=frozenset(caps), send_command=Mock())


@pytest.mark.parametrize('modern', [False, True])
@pytest.mark.parametrize('identity', [0, 0x1000563D])
@pytest.mark.parametrize('profile,hz', PROFILES.items())
@pytest.mark.parametrize('entry', ['profile', 'flash'])
def test_jtag_old_new_and_deferred_identity_confirm_without_claiming_applied(modern, identity, profile, hz, entry):
    b = bridge(modern=modern, identity=identity)
    b.send_command.return_value = f'set clock {hz}\r\nJTAG profile={hz}\r\n'
    if entry == 'profile':
        result = apply_bridge_profile(b, profile)
        assert result['interface'] == 'JTAG' and result['profile_confirmed']
        assert result['apply_state'] == 'acknowledged' and result['applied_hz'] is None
        assert 'IDE clock are not confirmed' in result['qualification']
    else:
        MKLinkFlash(b).set_swd_clock(hz)
    assert b._ctx.swd_clock_hz == hz and b._ctx.clock_interface == 'JTAG'
    assert b._ctx.clock_apply_state == 'acknowledged' and b._ctx.applied_clock_hz == 0
    assert b.send_command.call_count == 1
    assert b.send_command.call_args.args[0] == f'cmd.set_swd_clock({hz})'
    assert clock_options(b)['clocks_hz'] == list(PROFILES.values())


@pytest.mark.parametrize('state', ['configured', 'applied'])
@pytest.mark.parametrize('hz', V3_CLOCKS)
def test_global_v4_swd_ack_keeps_exact_applied_configured_semantics(state, hz):
    b = bridge(identity=0x1BA01477, interface='SWD')
    profile = f'SWD profile={hz}\r\n' if hz >= 10_000_000 else ''
    b.send_command.return_value = f'set clock {hz}\r\n{profile}SWD clock_state={state}\r\n'
    MKLinkFlash(b).set_swd_clock(hz)
    assert b._ctx.clock_interface == 'SWD' and b._ctx.clock_apply_state == state
    assert b._ctx.applied_clock_hz == (hz if state == 'applied' else 0)
    b.send_command.assert_called_once()


@pytest.mark.parametrize('modern', [False, True])
@pytest.mark.parametrize('reply', [
    '', 'cmd.set_swd_clock(30000000)\r\n0', 'set clock 30000000',
    'set clock 30000000\nJTAG profile=20000000',
    'set clock 30000000\nJTAG profile=30000000\n-1',
    'set clock 30000000\nJTAG profile=30000000\nError: busy',
    'set clock 30000000\nJTAG profile=30000000\nSWD profile=30000000',
    'set clock 30000000\nJTAG profile=30000000\nJTAG profile=30000000',
    'set clock 30000000\nset clock 30000000\nJTAG profile=30000000',
    'set clock 30000000\nJTAG profile=30000000\nSWD clock_state=applied',
    'set clock 30000000\nJTAG profile=30000000\nSWD clock_state=configured',
    'set clock 30000000\nSWD profile=30000000\nSWD clock_state=applied',
    'set clock 30000000\nJTAG profile=30000000bad',
    'set clock 30000000\nJTAG profile=30000000\nJTAG clock_state=applied',
    'set clock 20000000\nJTAG profile=0',
])
def test_unknown_or_conflicting_jtag_ack_never_replays_or_retains_success(modern, reply):
    b = bridge(modern=modern)
    b.send_command.return_value = reply
    with pytest.raises(ValueError):
        apply_bridge_profile(b, 'ultra')
    b.send_command.assert_called_once()
    assert b._ctx.swd_clock_hz == b._ctx.applied_clock_hz == 0
    assert b._ctx.clock_apply_state == 'unknown'


@pytest.mark.parametrize('entry', ['profile', 'flash'])
@pytest.mark.parametrize('modern', [False, True])
def test_lost_ack_never_tries_another_clock(entry, modern):
    b = bridge(modern=modern)
    b.send_command.side_effect = TimeoutError('outcome unknown')
    with pytest.raises(TimeoutError):
        if entry == 'profile':
            apply_bridge_profile(b, 'high')
        else:
            MKLinkFlash(b).set_swd_clock(10_000_000)
    b.send_command.assert_called_once()
    assert b._ctx.swd_clock_hz == b._ctx.applied_clock_hz == 0
    assert b._ctx.clock_apply_state == 'unknown'


def test_modern_profile_zero_is_not_confirmed_or_automatically_replaced():
    b = bridge()
    b.send_command.return_value = 'set clock 30000000\nJTAG profile=0'
    with pytest.raises(ValueError):
        apply_bridge_profile(b, 'ultra')
    b.send_command.assert_called_once()


def test_swd_context_rejects_jtag_reply_even_before_idcode():
    b = bridge(identity=0, interface='SWD')
    b.send_command.return_value = 'set clock 30000000\nJTAG profile=30000000'
    with pytest.raises(ValueError, match='interface'):
        apply_bridge_profile(b, 'ultra')
    b.send_command.assert_called_once()


def test_deferred_jtag_does_not_certify_an_arbitrary_swd_frequency():
    b = bridge(identity=0)
    b.send_command.return_value = 'set clock 8000000\nJTAG profile=8000000'
    with pytest.raises(FlashError, match='JTAG'):
        MKLinkFlash(b).set_swd_clock(8_000_000)
    assert b._ctx.swd_clock_hz == 0
    b.send_command.assert_called_once()


def test_known_jtag_context_rejects_swd_only_frequency_before_command():
    b = bridge(identity=0, interface='JTAG')
    with pytest.raises(FlashError, match='HPM JTAG'):
        MKLinkFlash(b).set_swd_clock(8_000_000)
    b.send_command.assert_not_called()
    assert b._ctx.swd_clock_hz == 10_000_000


@pytest.mark.parametrize('modern', [False, True])
def test_shared_runtime_returns_jtag_ack_and_keeps_saved_request_after_failed_change(batch, monkeypatch, modern):
    _, state, device, control, _ = batch
    b = bridge(modern=modern)
    device._bridge = b
    device._flash = MKLinkFlash(b)
    b.send_command.return_value = 'set clock 20000000\nJTAG profile=20000000'
    client = shared_client(batch, monkeypatch)
    result = client.call('set_debug_speed', {'profile':'high', 'save':False})
    assert result['apply_state'] == 'acknowledged' and result['applied_hz'] is None
    assert result['interface'] == 'JTAG' and result['stopped'] == []
    assert not load_config(state['project_root'])
    save_config(state['project_root'], {'swd_clock':'20000000'})
    b.send_command.reset_mock()
    b.send_command.return_value = 'set clock 30000000\nJTAG profile=20000000'
    with pytest.raises(RuntimeErrorResponse):
        client.call('set_debug_speed', {'profile':'ultra', 'save':True})
    b.send_command.assert_called_once()
    assert load_config(state['project_root'])['swd_clock'] == '20000000'
    assert b._ctx.swd_clock_hz == b._ctx.applied_clock_hz == 0
    assert not control.operation_lock.locked() and not state['resource_manager'].get_status()

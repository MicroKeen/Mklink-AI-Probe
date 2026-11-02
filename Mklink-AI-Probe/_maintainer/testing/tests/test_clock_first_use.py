"""A first clock change must negotiate on the command bridge, before writing."""
from unittest.mock import Mock

import pytest

from mklink._types import DeviceState
from mklink.bridge import MKLinkSerialBridge
from mklink.capture_clock import V3_CLOCKS, clock_snapshot
from mklink.debug_speed import apply_bridge_clock, apply_bridge_profile
from mklink.flash import MKLinkFlash, FlashError
from test_runtime_memory import batch
from test_runtime_watch_timing import shared_client

VERSION = 'V4.7.2\nJTAG_CLOCK_ACK=1\nJTAG_CLOCKS=' + ','.join(map(str,V3_CLOCKS))


def fresh_bridge(version=VERSION):
    bridge = MKLinkSerialBridge('TEST_CLOCK_FIRST_USE')
    bridge._ctx.state = DeviceState.READY
    bridge._ctx.idcode = 0x1000563D
    def respond(command, **kwargs):
        if command == 'cmd.get_version()': return version
        hz = int(command.removeprefix('cmd.set_swd_clock(').removesuffix(')'))
        return f'set clock {hz}\nJTAG profile={hz}\nJTAG clock_state=applied'
    bridge.send_command = Mock(side_effect=respond)
    return bridge


@pytest.mark.parametrize('entry,hz',[(entry,hz) for entry in ('numeric','profile','flash')
                                  for hz in (1000,10000000,20000000) if entry != 'profile' or hz != 1000])
def test_first_clock_queries_capabilities_before_validation_or_write_and_reuses_cache(entry,hz):
    b = fresh_bridge()
    for _ in range(2):
        if entry == 'numeric': apply_bridge_clock(b,hz)
        elif entry == 'profile': apply_bridge_profile(b,'medium' if hz == 10000000 else 'high')
        else: MKLinkFlash(b).set_swd_clock(hz)
    assert [c.args[0] for c in b.send_command.call_args_list] == [
        'cmd.get_version()',f'cmd.set_swd_clock({hz})',f'cmd.set_swd_clock({hz})']
    assert b._ctx.applied_clock_hz == hz and b._ctx.clock_interface == 'JTAG'


@pytest.mark.parametrize('reply',['','cmd.get_version()\n0\n>>>','Error: busy'])
def test_unrecognized_capability_reply_never_becomes_legacy_permission_to_write(reply):
    b = fresh_bridge(reply)
    with pytest.raises(ValueError,match='firmware version'): apply_bridge_clock(b,10000000)
    assert [c.args[0] for c in b.send_command.call_args_list] == ['cmd.get_version()']
    assert b._firmware_capabilities is None


def test_capability_timeout_does_not_send_or_replay_clock():
    b = fresh_bridge()
    b.send_command.side_effect = TimeoutError('query outcome unknown')
    with pytest.raises(TimeoutError): apply_bridge_clock(b,10000000)
    b.send_command.assert_called_once_with('cmd.get_version()',timeout=3.0)
    assert b._firmware_capabilities is None


@pytest.mark.parametrize('version',['V4.6.9','MicroLink V4.6.9'])
def test_legacy_version_without_clock_caps_still_uses_legacy_contract(version):
    b = fresh_bridge(version)
    b.send_command.side_effect = [version,'set clock 10000000\nJTAG profile=10000000']
    result = apply_bridge_clock(b,10000000)
    assert result['apply_state'] == 'acknowledged' and result['applied_hz'] is None
    assert [c.args[0] for c in b.send_command.call_args_list] == ['cmd.get_version()','cmd.set_swd_clock(10000000)']


@pytest.mark.parametrize('entry',['numeric','flash'])
def test_busy_first_use_does_not_query_or_stop_a_stream(entry):
    b = fresh_bridge()
    b._ctx.state = DeviceState.DUMP_STREAM
    with pytest.raises((ValueError,FlashError),match='Stop'):
        apply_bridge_clock(b,10000000) if entry == 'numeric' else MKLinkFlash(b).set_swd_clock(10000000)
    b.send_command.assert_not_called()
    assert b.state == DeviceState.DUMP_STREAM


def test_passive_snapshot_does_not_negotiate_or_enumerate():
    b = fresh_bridge()
    from types import SimpleNamespace
    d = SimpleNamespace(_bridge=b,connected=True)
    clock_snapshot(d,{})
    b.send_command.assert_not_called()
    assert b._firmware_capabilities is None


@pytest.mark.parametrize('warm_version',[False,True])
def test_first_shared_clock_succeeds_without_memory_or_mux_warmup(batch,monkeypatch,warm_version):
    _,_,device,control,_ = batch
    b = fresh_bridge()
    device._bridge = b
    device._flash = MKLinkFlash(b)
    if warm_version:
        # probe_version returns raw text on this same bridge, without caching.
        b.send_command('cmd.get_version()')
        assert b._firmware_capabilities is None
        b.send_command.reset_mock()
    result = shared_client(batch,monkeypatch).call('set_debug_speed',{'clock_hz':10000000,'save':False})
    assert result['apply_state'] == 'applied' and result['applied_hz'] == 10000000
    assert [c.args[0] for c in b.send_command.call_args_list] == ['cmd.get_version()','cmd.set_swd_clock(10000000)']
    assert b._mux is None and not control.operation_lock.locked()

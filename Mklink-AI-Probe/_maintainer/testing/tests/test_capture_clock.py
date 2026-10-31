"""Clock ACKs distinguish pending application; status must never touch hardware."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from mklink._types import DeviceContext, DeviceState
from mklink.capture_clock import V3_CLOCKS, clock_options, clock_snapshot
from mklink.device import Device
from mklink.flash import MKLinkFlash
from mklink.project_config import load_config, save_config
from mklink.remote.api import create_app


def v3_device(tmp_path, *, state='applied'):
    dev = Device(project_root=str(tmp_path))
    dev._connected = True
    ctx = DeviceContext(state=DeviceState.READY)
    def respond(command, **kwargs):
        hz = int(command.removeprefix('cmd.set_swd_clock(').removesuffix(')'))
        return f'set clock {hz}\nSWD clock_state={state}\n'
    dev._bridge = SimpleNamespace(state=DeviceState.READY, idcode=0, _ctx=ctx,
        _firmware_capabilities=frozenset({'V3.6.8', 'SWD_CLOCK_ACK=1', 'SWD_CLOCKS='+','.join(map(str,V3_CLOCKS))}),
        send_command=Mock(side_effect=respond))
    dev._flash = MKLinkFlash(dev._bridge)
    return dev


@pytest.mark.parametrize('hz', V3_CLOCKS)
@pytest.mark.parametrize('state', ['configured', 'applied'])
def test_all_advertised_clocks_require_exact_setting_and_state(tmp_path, hz, state):
    dev = v3_device(tmp_path, state=state)
    result = dev.set_debug_clock(hz)
    assert result['configured_hz'] == hz and result['apply_state'] == state
    assert result['applied_hz'] == (hz if state == 'applied' else None)
    dev._bridge.send_command.assert_called_once()
    assert dev._bridge.send_command.call_args.args[0] == f'cmd.set_swd_clock({hz})'


@pytest.mark.parametrize('reply', [
    'set clock 30000000', 'cmd.set_swd_clock(30000000)\nSWD clock_state=applied',
    'set clock 30000000\nSWD profile=20000000\nSWD clock_state=applied',
    'set clock 30000000\nSWD clock_state=applied\n-1',
    'set clock 30000000\nSWD clock_state=configured\nSWD clock_state=applied',
    'set clock 30000000\nSWD clock_state=unknown',
    'set clock 10000000\nset clock 30000000\nSWD clock_state=applied',
    'set clock 30000000\nJTAG profile=30000000\nSWD clock_state=applied',
])
def test_modern_failure_invalidates_confirmation_without_fallback_or_replay(tmp_path, reply):
    dev = v3_device(tmp_path)
    dev.set_debug_clock(10000000)
    dev._bridge.send_command.reset_mock()
    dev._bridge.send_command.side_effect = lambda *a, **k: reply
    with pytest.raises(ValueError): dev.set_debug_clock(30000000)
    result = clock_snapshot(dev, {'swd_clock':'10000000'})
    assert result['configured_hz'] is None and result['applied_hz'] is None
    assert result['apply_state'] == 'unknown' and result['requested_hz'] == 10000000
    dev._bridge.send_command.assert_called_once()


def test_timeout_does_not_replay_or_leave_old_confirmation(tmp_path):
    dev=v3_device(tmp_path)
    dev.set_debug_clock(10000000)
    dev._bridge.send_command.reset_mock()
    dev._bridge.send_command.side_effect=TimeoutError('outcome unknown')
    with pytest.raises(TimeoutError): dev.set_debug_clock(2000000)
    assert dev.clock_hz is None
    dev._bridge.send_command.assert_called_once()


@pytest.mark.parametrize('model,hpm,expected', [('V3.6.8',False,list(V3_CLOCKS)),
    ('V4.7.2',False,[4000000,10000000,20000000,30000000]),
    ('V2.9.3',False,[4000000,10000000,20000000,30000000]),
    ('V3.6.8',True,[4000000,10000000,20000000,30000000])])
def test_product_and_interface_do_not_inherit_v3_options(tmp_path, model, hpm, expected):
    dev=v3_device(tmp_path)
    dev._bridge._firmware_capabilities=(dev._bridge._firmware_capabilities-{'V3.6.8'})|{model}
    assert clock_options(dev._bridge,hpm=hpm)['clocks_hz'] == expected
    dev._bridge.send_command.assert_not_called()


def test_unadvertised_legacy_v3_does_not_gain_new_options(tmp_path):
    dev=v3_device(tmp_path)
    dev._bridge._firmware_capabilities=frozenset({'V3.6.8'})
    assert 1000 not in clock_options(dev._bridge)['clocks_hz']


def test_unsaved_connection_defaults_to_ten_megahertz_without_inventing_application():
    status = clock_snapshot(None, {})
    assert status['requested_hz'] == 10_000_000
    assert status['configured_hz'] is None and status['applied_hz'] is None
    assert status['apply_state'] == 'unknown' and not status['connected']


def test_disconnected_clock_saves_into_the_same_connection_config(api_clock, tmp_path):
    client, dev, _ = api_clock
    client.app.state.mklink_state['device'] = None
    response = client.put('/api/config', json={'swd_clock': '20000000'})
    assert response.status_code == 200, response.text
    assert load_config(str(tmp_path))['swd_clock'] == '20000000'
    status = client.get('/api/device/debug-speed').json()
    assert status['requested_hz'] == 20_000_000 and status['applied_hz'] is None
    dev._bridge.send_command.assert_not_called()


@pytest.mark.parametrize('kind', ['number','profile'])
def test_old_four_megahertz_requires_explicit_migration(tmp_path,kind):
    dev=v3_device(tmp_path)
    with pytest.raises(ValueError):
        dev.set_debug_clock(4000000) if kind=='number' else dev.set_debug_speed('low')
    dev._bridge.send_command.assert_not_called()


@pytest.fixture
def api_clock(tmp_path,monkeypatch):
    managers={name:SimpleNamespace(running=False,stop=Mock()) for name in ('rtt','superwatch','systemview','vofa','serial','modbus')}
    monkeypatch.setattr('mklink.remote.dashboards.get_managers',lambda:managers)
    app=create_app(auth_token=None,project_root=str(tmp_path))
    dev=v3_device(tmp_path)
    app.state.mklink_state['device']=dev
    with TestClient(app) as client:
        try:
            yield client,dev,managers
        finally:
            app.state.mklink_state['device']=None


def test_migration_is_explicit_and_only_saved_after_ack(api_clock,tmp_path):
    client,dev,_=api_clock
    save_config(str(tmp_path),{'swd_clock':'4000000','debug_speed':'low'})
    dev._bridge._ctx.swd_clock_hz=4000000
    for _ in range(3):
        status=client.get('/api/device/debug-speed').json()
        assert status['migration']=={'from_hz':4000000,'to_hz':2000000,'pending':True}
        assert status['requested_hz']==status['configured_hz']==4000000
    dev._bridge.send_command.assert_not_called()
    dev._bridge.send_command.side_effect=lambda *a,**k:'set clock 2000000'
    assert client.post('/api/device/debug-speed',json={'clock_hz':2000000}).status_code==400
    assert load_config(str(tmp_path))['swd_clock']=='4000000'
    dev._bridge.send_command.side_effect=lambda *a,**k:'set clock 2000000\nSWD clock_state=configured'
    result=client.post('/api/device/debug-speed',json={'clock_hz':2000000})
    assert result.status_code==200,result.text
    assert result.json()['apply_state']=='configured' and result.json()['applied_hz'] is None
    saved=load_config(str(tmp_path))
    assert saved['swd_clock']=='2000000' and 'debug_speed' not in saved
    assert client.get('/api/device/debug-speed').json()['migration'] is None


@pytest.mark.parametrize('shared',[False,True])
def test_active_capture_is_not_stopped_for_clock_change(api_clock,shared):
    client,dev,managers=api_clock
    client.app.state.mklink_state['shared_runtime']=shared
    managers['superwatch'].running=True
    result=client.post('/api/device/debug-speed',json={'clock_hz':2000000})
    assert result.status_code==409,result.text
    dev._bridge.send_command.assert_not_called()
    for m in managers.values(): m.stop.assert_not_called()


@pytest.mark.parametrize('body',[{}, {'clock_hz':True},{'clock_hz':1.5},{'clock_hz':'2000000'},
    {'clock_hz':2000000,'profile':'medium'},{'clock_hz':4000000}])
def test_bad_requests_do_not_write_or_save(api_clock,tmp_path,body):
    client,dev,_=api_clock
    result=client.post('/api/device/debug-speed',json=body)
    assert result.status_code in (400,422),result.text
    dev._bridge.send_command.assert_not_called()
    assert not load_config(str(tmp_path))

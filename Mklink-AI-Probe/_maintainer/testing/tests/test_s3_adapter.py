import json
from unittest.mock import Mock

import pytest

from mklink.s3_registry import register_node, load_nodes, inventory
from mklink.s3_transport import WirelessLink


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setenv('MKLINK_RUNTIME_DIR', str(tmp_path))
    return dict(node_id='0123456789ab', transport='http',
                address='http://127.0.0.1:1424', token='a' * 32)


def test_identity_shared_between_radio_routes_and_credentials_not_discovered(registry):
    first = register_node(registry)
    second = register_node({**registry, 'transport': 'ble', 'address': '01:23:45:67:89:AD'})
    assert first['probe_id'] == second['probe_id'] == 's3-0123456789ab'
    assert len(inventory()) == 1
    assert 'token' not in json.dumps(inventory())
    assert load_nodes()[first['probe_id']]['transport'] == 'ble'


def test_active_owner_blocks_route_change(registry):
    from mklink.runtime import runtime_lock, RuntimeErrorResponse
    register_node(registry)
    with runtime_lock('owner.lock', 's3-0123456789ab'):
        with pytest.raises(RuntimeErrorResponse):
            register_node({**registry, 'address': 'http://127.0.0.1:9999'})
    assert load_nodes()['s3-0123456789ab']['address'] == registry['address']


@pytest.mark.parametrize('address', ['http://user:secret@example.org', 'file:///tmp/x', 'http://a/x', 'http://a/#token=secret'])
def test_reject_ambiguous_credential_origins(registry, address):
    with pytest.raises(ValueError):
        register_node({**registry, 'address': address})


def test_s3_does_not_resolve_a_local_volume(registry, monkeypatch):
    from mklink.probe_volumes import resolve_volume
    register_node(registry)
    monkeypatch.setattr('mklink.discovery.discover_mklink_command_ports', lambda: [])
    scan = Mock(side_effect=AssertionError('Must not enumerate local disks'))
    monkeypatch.setattr('mklink.probe_volumes.volume_inventory', scan)
    with pytest.raises(RuntimeError, match='no local USB'):
        resolve_volume('s3-0123456789ab')
    scan.assert_not_called()


def test_unknown_write_is_not_replayed():
    rpc = Mock(side_effect=TimeoutError())
    link = WirelessLink(rpc, '0123456789ab')
    link.lease = 'lease'
    link.renewed = __import__('time').monotonic()
    link.generation = 1
    link.sequence = 1
    with pytest.raises(ConnectionError, match='no replay'):
        link.stream('write', b'command')
    with pytest.raises(ConnectionError, match='no replay'):
        link.stream('write', b'command')
    assert rpc.call_count == 1


def test_mux_budget_is_per_instance():
    from mklink.mux import MuxTransport
    usb = MuxTransport(lambda b: len(b))
    radio = MuxTransport(lambda b: len(b), command_timeout=60)
    usb._send(1, b'')
    radio._send(1, b'')
    assert 56 < radio._pending[2] - usb._pending[2] < 58


def test_factory_never_falls_back_for_missing_s3(registry, monkeypatch):
    from mklink.transport_factory import create_bridge
    native = Mock(side_effect=AssertionError('No fallback'))
    monkeypatch.setattr('mklink.bridge.MKLinkSerialBridge', native)
    with pytest.raises(ConnectionError, match='no USB fallback'):
        create_bridge('s3-0123456789ab')
    native.assert_not_called()


def test_ble_timeout_settles_coroutine_before_loop_exit():
    import asyncio
    import threading
    from mklink.s3_rpc import Endpoint
    endpoint = Endpoint({'transport': 'ble'})
    endpoint.operation_timeout = .02
    endpoint.loop = asyncio.new_event_loop()
    endpoint.thread = threading.Thread(target=endpoint.loop.run_forever)
    endpoint.thread.start()
    finished = threading.Event()
    async def stalled_write():
        try:
            await asyncio.sleep(10)
        finally:
            finished.set()
    try:
        with pytest.raises(ConnectionError, match='outcome unknown'):
            endpoint._await(stalled_write())
        assert finished.is_set() and endpoint.settled.is_set()
    finally:
        endpoint.close()
    assert not endpoint.thread.is_alive()


def test_long_lived_remote_mcp_discovers_new_workbench_site(tmp_path):
    from mklink.remote.sites import SiteRegistry
    from mklink.remote.mcp import register_tools
    class Tools:
        def __init__(self):
            self.functions = {}
        def tool(self):
            def decorate(fn):
                self.functions[fn.__name__] = fn
                return fn
            return decorate
    path = tmp_path / 'sites' / 'sites.json'
    old = SiteRegistry(path)
    tools = Tools()
    register_tools(tools, old)
    assert tools.functions['remote_sites']() == []
    SiteRegistry(path).add('wireless', 'ws://127.0.0.1:9000', 'private')
    assert tools.functions['remote_sites']()[0]['name'] == 'wireless'


def test_reload_preserves_an_active_remote_socket(tmp_path):
    from mklink.remote.sites import SiteRegistry
    path = tmp_path / 'sites' / 'sites.json'
    socket = Mock(connected=True)
    registry = SiteRegistry(path, client_factory=lambda *a, **k: socket)
    registry.add('existing', 'ws://127.0.0.1:9001', 'private')
    assert registry.client('existing') is socket
    SiteRegistry(path).add('new', 'ws://127.0.0.1:9002', 'private2')
    registry.reload()
    assert registry.client('existing') is socket
    socket.close.assert_not_called()


def test_quarantined_remote_allows_idempotent_local_retirement(monkeypatch):
    from mklink.s3_transport import WirelessBridge
    link = WirelessLink(Mock(), '0123456789ab')
    link.opened = True
    link.poisoned = True
    link.lease = 'lease'
    link.renewed = __import__('time').monotonic()
    bridge = WirelessBridge(link)
    endpoint = bridge._endpoint = Mock()
    held = Mock()
    bridge._held_locks = [held]
    monkeypatch.setattr('mklink.bridge.MKLinkSerialBridge.close', lambda self: None)
    bridge.close()
    bridge.close()
    endpoint.close.assert_called_once()
    held.release.assert_called_once()
    assert bridge._retired and link.poisoned
    assert [c.args[0] for c in link.rpc.call_args_list] == ['probe.stream.abort']


def test_live_endpoint_prevents_ownership_release(monkeypatch):
    from mklink.s3_transport import WirelessBridge
    link = WirelessLink(Mock(), '0123456789ab')
    bridge = WirelessBridge(link)
    bridge._endpoint = Mock()
    bridge._endpoint.close.side_effect = ConnectionError('worker still alive')
    held = Mock()
    bridge._held_locks = [held]
    monkeypatch.setattr('mklink.bridge.MKLinkSerialBridge.close', lambda self: None)
    with pytest.raises(ConnectionError, match='worker still alive'):
        bridge.close()
    held.release.assert_not_called()
    assert not bridge._retired


def test_wireless_capture_stop_waits_once_for_its_io_budget():
    from types import SimpleNamespace
    from mklink.remote.api import stop_dashboard_manager
    manager = Mock(worker_alive=False)
    resources = Mock()
    state = {'device': SimpleNamespace(_bridge=SimpleNamespace(capture_stop_timeout=30.0)), 'resource_manager': resources}
    stop_dashboard_manager(state, 'systemview', manager)
    manager.stop.assert_called_once_with(timeout=30.0)
    resources.release.assert_called_once_with('user:dashboard:systemview')


@pytest.mark.parametrize('replacement', [{'url':'ws://127.0.0.1:9002','token':'private'}, {'url':'ws://127.0.0.1:9001','token':'changed'}, {'url':'ws://127.0.0.1:9001','token':'private','flash_timeout':1200}])
def test_site_route_change_requires_explicit_reconnect(tmp_path, replacement):
    from mklink.remote.sites import SiteRegistry, SiteError
    path = tmp_path / 'sites.json'
    old = Mock(connected=True)
    fresh = Mock(connected=True)
    factory = Mock(side_effect=[old, fresh])
    registry = SiteRegistry(path, client_factory=factory)
    registry.add('node', 'ws://127.0.0.1:9001', 'private')
    assert registry.client('node') is old
    SiteRegistry(path).add('node', **replacement)
    registry.reload()
    assert registry.list()[0]['connected'] is False
    with pytest.raises(SiteError, match='explicitly reconnect'):
        registry.call('node', 'memory.write', address=0, data_b64='AA==')
    old.call.assert_not_called()
    old.close.assert_not_called()
    assert registry.reconnect('node') is fresh
    old.close.assert_called_once()


@pytest.mark.parametrize('malformed_json', [True, False])
def test_broken_wireless_registry_does_not_block_usb(registry, monkeypatch, caplog, malformed_json):
    from types import SimpleNamespace
    from mklink.s3_registry import _path
    from mklink.probes import inventory as discover, select_probe
    from mklink.runtime import RuntimeErrorResponse
    invalid = '{corrupt' if malformed_json else json.dumps({'s3-0123456789ab': {**registry, 'address': 123}})
    _path().write_text(invalid, encoding='utf-8')
    usb = SimpleNamespace(vid=0x0d28, pid=0x0202, serial_number='UNITTEST', location='fixture', device='COM99', description='MKLink')
    monkeypatch.setattr('mklink.discovery.discover_mklink_command_ports', lambda: [usb])
    assert discover()[0]['port'] == 'COM99'
    assert select_probe('COM99')['port'] == 'COM99'
    with pytest.raises(RuntimeErrorResponse):
        select_probe('s3-0123456789ab')
    assert 'S3 registration unavailable' in caplog.text


def test_wireless_site_timeout_persists_without_changing_defaults(tmp_path):
    from mklink.remote.sites import SiteRegistry
    path = tmp_path / 'sites.json'
    registry = SiteRegistry(path)
    registry.add('wireless', 'ws://127.0.0.1:9001', 'private', timeout=60, flash_timeout=1200)
    registry.add('usb', 'ws://127.0.0.1:9002', 'private')
    factory = Mock(return_value=Mock(connected=True))
    fresh = SiteRegistry(path, client_factory=factory)
    fresh.client('wireless')
    assert factory.call_args.kwargs == dict(token='private', timeout=60, flash_timeout=1200)
    fresh.client('usb')
    assert factory.call_args.kwargs == dict(token='private', timeout=10)


@pytest.mark.parametrize('bad', [True, 0, -1, float('nan'), float('inf'), 3601, '60'])
def test_invalid_site_timeout_rejected(tmp_path, bad):
    from mklink.remote.sites import SiteRegistry
    registry = SiteRegistry(tmp_path / 'sites.json')
    with pytest.raises(ValueError, match='site timeout'):
        registry.add('invalid', 'ws://127.0.0.1:9001', 'private', timeout=bad)


def test_frozen_remote_mcp_entry_reuses_existing_server(monkeypatch):
    import sys
    from mklink import cli
    called = Mock(return_value=0)
    monkeypatch.setattr('mklink.remote.mcp.main', called)
    monkeypatch.setattr(sys, 'argv', ['mklink-sidecar', 'remote-mcp'])
    assert cli.main() == 0
    called.assert_called_once_with()

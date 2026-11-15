import asyncio
import threading
from types import SimpleNamespace

import pytest

from mklink import firmware_check as fc
from mklink.firmware_notice import FirmwareNotice, cached_identity


def state(version='V4.7.3', product='MKLINK', port='COM9'):
    lines = {version, 'MUX_TARGET=1'}
    if product:
        lines.add('PROBE_PRODUCT=' + product)
    def forbidden(*args, **kwargs):
        pytest.fail('Automatic advice must never query or enumerate a probe')
    bridge = SimpleNamespace(_firmware_capabilities=frozenset(lines), send_command=forbidden,
                             _get_firmware_capabilities=forbidden)
    device = SimpleNamespace(connected=True, port=port, _bridge=bridge)
    return dict(device=device, shared_probe_id=port, device_generation=1)


def firmware(version='V4.7.4', prefix='MicroLink'):
    return fc.parse_firmware_filename(f'{prefix}_{version}.{"rbl" if version.startswith("V2") else "uf2"}')


@pytest.mark.parametrize('version,product,family', [
    ('V4.7.3', 'MKLINK', 'microlink'), ('V4.7.3', 'HPMLINK', 'hpmlink'),
    ('V3.6.8', None, 'microlink'), ('V2.9.0', None, 'microlink'),
    ('V4.7.3', None, 'microlink'), ('V4.7.3', 'unknown', None),
    ('V3.6.8', 'HPMLINK', None), ('V5.0.0', 'MKLINK', None), ('bad', 'MKLINK', None),
])
def test_cached_identity_requires_unambiguous_family(version, product, family):
    result = cached_identity(state(version, product)['device'])
    assert (result[0] if result else None) == family


def test_unrecognized_recommends_upgrade_without_cloud_and_disconnect_clears_it():
    monitor = FirmwareNotice()
    candidate = state()
    candidate['device']._bridge._firmware_capabilities |= {'V4.7.1'}
    assert monitor.snapshot(candidate) == dict(status='unrecognized', probe_id='COM9',
        device_generation=1, action='upgrade_probe_firmware')
    candidate['device'].connected = False
    assert monitor.snapshot(candidate) is None
    assert monitor.snapshot({}) is None
    assert not monitor._tasks


def test_handshake_preserves_current_version_before_history_without_an_extra_query():
    from mklink.bridge import MKLinkSerialBridge
    from mklink.firmware_compatibility import compatibility_snapshot
    bridge = MKLinkSerialBridge('fixture')
    calls = []
    response = 'cmd.get_version()\r\nV4.7.3\r\nHistory:\r\n  V4.7.2\r\n  V4.7.1\r\n'
    def command(*args, **kwargs):
        calls.append((args, kwargs))
        return response
    bridge.send_command = command
    assert 'V4.7.2' in bridge._get_firmware_capabilities()
    assert 'V4.7.1' in bridge._get_firmware_capabilities()
    candidate = SimpleNamespace(connected=True, _bridge=bridge)
    assert str(cached_identity(candidate)[2]) == 'V4.7.3'
    assert compatibility_snapshot(bridge)['version'] == 'V4.7.3'
    assert len(calls) == 1
    # Cache reset happens even when reconnect cannot acquire the port lock.
    bridge._port_lock = SimpleNamespace(acquire=lambda: False, last_error=None)
    assert bridge.connect() is False
    assert bridge._firmware_version_response is None
    assert cached_identity(candidate) is None


@pytest.mark.parametrize('raw,expected', [
    ('V2.9.4\nHistory:\n  V2.9.3\n  V2.9.2\n', 'V2.9.4'),
    ('V3.6.8\nHistory:\n  V3.6.10\n', 'V3.6.8'),
    ('V5.0.0\nHistory:\n  V4.7.3\n', None),
    ('unreadable', None),
])
def test_ordered_version_is_authoritative_not_max_or_history(raw, expected):
    candidate = state()['device']
    candidate._bridge._firmware_version_response = raw
    candidate._bridge._firmware_capabilities |= {'V2.9.3', 'V4.7.2'}
    result = cached_identity(candidate)
    assert (str(result[2]) if result else None) == expected


@pytest.mark.parametrize('raw,expected,family', [
    ('cmd.get_version()\nRead Me See: https://microkeenai.com/\r\nV2.9.4\r\nHistory:\r\n  V2.9.3\nDUMP_WRITE=1\n', 'V2.9.4', 'microlink'),
    ('WATCH_TIMING=2\r\nUART_BAUD_PROFILE=1\r\nV3.7.0\r\n使用手册: https://microkeenai.com/\r\nMUX_TARGET=1\r\n', 'V3.7.0', 'microlink'),
    ('UART_BAUD_PROFILE=1\r\nRS485_BAUD_PROFILE=1\r\nWATCH_TIMING=2\r\nV4.7.4\r\nDUMP_MEMORY=1\r\n', 'V4.7.4', 'microlink'),
    ('UART_BAUD_PROFILE=1\r\nPROBE_PRODUCT=HPMLINK\r\nWATCH_TIMING=2\r\nV4.7.4\r\nDUMP_MEMORY=1\r\n', 'V4.7.4', 'hpmlink'),
])
def test_firmware_source_response_formats(raw, expected, family):
    candidate = state()['device']
    candidate._bridge._firmware_version_response = raw
    candidate._bridge._firmware_capabilities = frozenset(line.strip() for line in raw.splitlines())
    result = cached_identity(candidate)
    assert result[0] == family and str(result[2]) == expected


def test_check_is_deferred_and_shutdown_cancels_before_network(monkeypatch):
    monkeypatch.setattr('mklink.firmware_notice._remote_firmwares', lambda **kw: pytest.fail('too early'))
    async def run():
        monitor = FirmwareNotice()
        candidate = state()
        for _ in range(100):
            assert monitor.snapshot(candidate)['status'] == 'checking'
        assert len(monitor._tasks) == 1
        await asyncio.sleep(0)
        await monitor.close()
        assert not monitor._tasks
    asyncio.run(run())


@pytest.mark.parametrize('installed,product,expected,latest', [
    ('V4.7.3', 'MKLINK', 'available', 'V4.7.4'),
    ('V4.7.3', None, 'available', 'V4.7.4'),
    ('V4.7.4', 'MKLINK', 'current', 'V4.7.4'),
    ('V4.7.5', 'MKLINK', 'current', 'V4.7.4'),
    ('V4.7.3', 'HPMLINK', 'current', 'V4.7.2'),
    ('V3.6.8', None, 'available', 'V3.6.10'),
    ('V2.9.0', None, 'available', 'V2.9.3'),
])
def test_exact_family_model_semantic_order_and_channel(monkeypatch, installed, product, expected, latest):
    calls = []
    entries = [firmware(), firmware('V4.7.2', 'HPMLink'), firmware('V3.6.10'), firmware('V2.9.3')]
    def fetch(**kwargs):
        calls.append(kwargs)
        return entries
    monkeypatch.setattr('mklink.firmware_notice._remote_firmwares', fetch)
    monkeypatch.setattr(FirmwareNotice, 'DELAY', 0)
    async def run():
        monitor = FirmwareNotice()
        candidate = state(installed, product)
        assert monitor.snapshot(candidate)['status'] == 'checking'
        await asyncio.gather(*monitor._tasks.values())
        result = monitor.snapshot(candidate)
        assert (result['status'], result['latest_version']) == (expected, latest)
        assert (result.get('action') == 'upgrade_probe_firmware') == (expected == 'available')
        assert calls == [dict(timeout=3.0, v2=installed.startswith('V2'), include_bundled=False)]
        for _ in range(100):
            assert monitor.snapshot(candidate) == result
        assert not monitor._tasks
        await monitor.close()
    asyncio.run(run())


def test_slow_cloud_does_not_block_status_or_publish_stale_probe(monkeypatch):
    entered, finish = threading.Event(), threading.Event()
    def fetch(**kwargs):
        entered.set()
        assert finish.wait(5)
        return [firmware(), firmware('V4.9.0', 'HPMLink')]
    monkeypatch.setattr('mklink.firmware_notice._remote_firmwares', fetch)
    monkeypatch.setattr(FirmwareNotice, 'DELAY', 0)
    async def run():
        monitor = FirmwareNotice()
        first = state()
        try:
            monitor.snapshot(first)
            assert await asyncio.to_thread(entered.wait, 2)
            for _ in range(100):
                assert monitor.snapshot(first)['status'] == 'checking'
            assert monitor.snapshot({}) is None
            replacement = state('V4.8.0', 'HPMLINK', 'COM10')
            replacement['device_generation'] = 3
            pending = monitor.snapshot(replacement)
            assert pending['current_version'] == 'V4.8.0'
            finish.set()
            await asyncio.gather(*monitor._tasks.values())
            result = monitor.snapshot(replacement)
            assert result['probe_id'] == 'COM10' and result['device_generation'] == 3
            assert result['latest_version'] == 'V4.9.0'
            assert monitor.snapshot({}) is None
        finally:
            finish.set()
            await monitor.close()
    asyncio.run(run())


@pytest.mark.parametrize('outcome,status', [(None, 'unavailable'), ([], 'no_firmware'), ('error', 'unavailable')])
def test_failure_and_empty_catalog_are_quiet_cached_and_retry(monkeypatch, outcome, status):
    calls = []
    def fetch(**kwargs):
        calls.append(kwargs)
        if outcome == 'error':
            raise OSError('offline')
        return outcome
    monkeypatch.setattr('mklink.firmware_notice._remote_firmwares', fetch)
    monkeypatch.setattr(FirmwareNotice, 'DELAY', 0)
    async def run():
        monitor = FirmwareNotice()
        candidate = state()
        monitor.snapshot(candidate)
        await asyncio.gather(*monitor._tasks.values())
        for _ in range(10):
            assert monitor.snapshot(candidate)['status'] == status
        assert len(calls) == 1
        monitor._cache[False] = (-1, monitor._cache[False][1])
        assert monitor.snapshot(candidate)['status'] == 'checking'
        await asyncio.gather(*monitor._tasks.values())
        assert len(calls) == 2
        await monitor.close()
    asyncio.run(run())


def test_cloud_advice_does_not_misrepresent_bundled_catalog(monkeypatch):
    monkeypatch.setattr(fc, '_remote_firmwares_from_source', lambda *a, **k: None)
    monkeypatch.setattr(fc, 'bundled_firmwares', lambda: [firmware()])
    assert fc._remote_firmwares(include_bundled=False) is None
    assert fc._remote_firmwares()[0].version_str == 'V4.7.4'


def test_web_cli_mcp_share_notice_without_hardware_admission(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from fastmcp import Client
    from mklink.remote.api import create_app
    from mklink.runtime_api import install_runtime
    from mklink import runtime, runtime_mcp

    app = create_app(project_root=str(tmp_path))
    shared = app.state.mklink_state
    candidate = state()['device']
    candidate.state, candidate.mcu_name, candidate.idcode = None, 'STM32F10x', 0
    candidate.axf_status, candidate.symbol_catalog, candidate.close = {'loaded': False}, None, lambda: None
    shared['device'] = candidate
    app.state.firmware_notice._cache[False] = (float('inf'), [firmware()])
    info = dict(port=8765, token='fixture', instance_id='fixture')
    install_runtime(app, info)
    monkeypatch.setattr('mklink.probes.inventory', lambda: pytest.fail('status must not enumerate USB'))
    monkeypatch.setattr(runtime, 'ensure_runtime', lambda **kw: info)
    with TestClient(app, base_url='http://127.0.0.1:8765', headers={'X-Auth-Token': 'fixture'}) as web:
        def request(info, method, path, payload=None, **kw):
            reply = web.request(method, path, json=payload)
            if reply.is_error:
                raise runtime.RuntimeErrorResponse(reply.text)
            return reply.json()
        monkeypatch.setattr(runtime, 'request', request)
        expected = web.get('/api/device/status').json()['firmware_update']
        assert expected['status'] == 'available'
        cli = runtime.RuntimeClient()
        try:
            assert cli.connect()['firmware_update'] == expected
            assert cli.call('device_status')['firmware_update'] == expected
        finally:
            cli.close()
        async def run():
            async with Client(runtime_mcp.build_server()) as mcp:
                assert (await mcp.call_tool('connect', {})).data['firmware_update'] == expected
                assert (await mcp.call_tool('gui_call', {'capability': 'device_status'})).data['firmware_update'] == expected
                await mcp.call_tool('detach', {})
        try:
            asyncio.run(run())
        finally:
            shared['device'] = None

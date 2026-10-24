import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mklink.offline_download import (
    OfflineDownloadError, deploy_offline_bundle, generate_offline_script,
    parse_offline_config, required_verify_capabilities, require_verify_capabilities,
)
from mklink.remote.api import create_app
from test_offline_download import _config


@pytest.mark.parametrize('model', ['V2', 'V3', 'V4'])
def test_default_and_disabled_mixed_scripts_keep_reset_independent(model):
    payload = dict(_config(model), auto_download_count=1, reset_after_download=False)
    enabled = parse_offline_config(payload)
    assert enabled.verify_after_download is True
    script = generate_offline_script(enabled)
    assert 'load.bin("boot.bin", 0x08000000)' in script
    assert 'load.hex("rt-thread.hex")' in script
    assert required_verify_capabilities(enabled) == ()
    disabled = parse_offline_config(dict(payload, verify_after_download=False))
    script = generate_offline_script(disabled)
    for call in ['load.bin("boot.bin", 0x08000000, 0)', 'load.hex("rt-thread.hex", 0)',
                 'load.bin("assets.bin", 0x90000000, 0)']:
        assert f'if {call} != 0:' in script
    assert 'cmd.set_reset()' not in script


@pytest.mark.parametrize('value', [None, 'false', 0, 1])
def test_verify_requires_boolean(value):
    with pytest.raises(OfflineDownloadError, match='boolean'):
        parse_offline_config(dict(_config(), verify_after_download=value))


@pytest.mark.parametrize('formats', [('bin',), ('hex',), ('bin', 'hex')])
def test_capabilities_are_exact_format_specific_and_not_version_based(formats):
    payload = dict(_config(), verify_after_download=False)
    payload['firmwares'] = [f for f in payload['firmwares'] if f['format'] in formats]
    config = parse_offline_config(payload)
    required = required_verify_capabilities(config)
    require_verify_capabilities(config, 'V2.0.0\r\n' + '\r\n'.join(required))
    for response in ['V99.99.99', '\n'.join(c.replace('=1', '=0') for c in required),
                     '\n'.join('prefix ' + c for c in required), '\n'.join(required[:-1])]:
        with pytest.raises(OfflineDownloadError, match='Upgrade downloader firmware'):
            require_verify_capabilities(config, response)


def test_direct_deploy_rejects_missing_capabilities_before_touching_disk(tmp_path):
    config = parse_offline_config(dict(_config(), verify_after_download=False))
    existing = tmp_path / 'python'; existing.mkdir()
    script = existing / config.script_name; script.write_text('old script')
    with pytest.raises(OfflineDownloadError, match='OFFLINE_BIN_VERIFY'):
        deploy_offline_bundle(config, tmp_path, firmware_sources={}, algorithm_sources={})
    assert script.read_text() == 'old script'
    assert list(tmp_path.iterdir()) == [existing]


def test_hpm_does_not_silently_ignore_disabled_verification():
    with pytest.raises(OfflineDownloadError, match='only supported for ARM'):
        parse_offline_config(dict(_config(), target_part='HPM5301', verify_after_download=False))


def test_preview_declares_requirements_without_opening_hardware(monkeypatch):
    monkeypatch.setattr('mklink.probes.select_probe', lambda *a: pytest.fail('preview selected hardware'))
    with TestClient(create_app(auth_token=None, project_root='.')) as client:
        response = client.post('/api/offline-download/preview', json=dict(_config(), verify_after_download=False))
    assert response.status_code == 200, response.text
    assert response.json()['required_capabilities'] == ['OFFLINE_BIN_VERIFY=1', 'OFFLINE_HEX_VERIFY=1']
    assert 'load.hex("rt-thread.hex", 0)' in response.json()['script']


@pytest.mark.parametrize('capability,match_disk,expected', [
    ('OFFLINE_HEX_VERIFY=1', True, 200),
    ('V4.99.99\nOFFLINE_BIN_VERIFY=1', True, 422),
    ('OFFLINE_HEX_VERIFY=0', True, 422),
    ('OFFLINE_HEX_VERIFY=1', False, 422),
])
def test_http_deployment_checks_bound_probe_before_writes(tmp_path, monkeypatch, capability, match_disk, expected):
    payload = dict(_config(), verify_after_download=False)
    payload['firmwares'] = [dict(payload['firmwares'][1], upload_index=0)]
    payload['algorithms'] = payload['algorithms'][:1]
    monkeypatch.setattr('mklink.discovery.find_microkeen_disk', lambda: str(tmp_path))
    monkeypatch.setattr('mklink.probes.select_probe', lambda *_: {'probe_id': 'fixture', 'port': 'FIXTURE'})
    monkeypatch.setattr('mklink.probe_volumes.resolve_volume', lambda *_: {'root': str(tmp_path if match_disk else tmp_path / 'other')})
    commands = []
    def send(command, **kwargs):
        commands.append(command)
        return capability
    app = create_app(auth_token=None, project_root='.')
    app.state.mklink_state['device'] = SimpleNamespace(connected=True, port='FIXTURE',
        _bridge=SimpleNamespace(send_command=send), close=lambda: None)
    with TestClient(app) as client:
        response = client.post('/api/offline-download/deploy', data={'config_json': json.dumps(payload)},
            files=[('firmware_files', ('image.hex', b':00000001FF\n')),
                   ('flm_files', ('algo.flm', b'fixture algorithm'))])
    assert response.status_code == expected, response.text
    assert commands == (['cmd.get_version()'] if match_disk else [])
    if expected == 200:
        script = (tmp_path / 'python' / payload['script_name']).read_text()
        assert 'load.hex("rt-thread.hex", 0)' in script
        assert (tmp_path / 'rt-thread.hex').read_bytes() == b':00000001FF\n'
    else:
        assert not list(tmp_path.iterdir())

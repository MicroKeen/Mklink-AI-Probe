"""Offline H7 safety ABI is separate from successful online programming."""
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
@pytest.mark.parametrize('part', ['STM32H745ZITx', 'STM32H747XIHx', 'stm32h755zitx', 'STM32H757xx'])
def test_dualcore_all_images_and_chip_erase_use_explicit_profile(model, part):
    config = parse_offline_config(dict(_config(model), target_part=part,
                                       erase_all_before_download=True, auto_download_count=1))
    script = generate_offline_script(config)
    flm_calls = [line for line in script.splitlines() if 'if load.flm(' in line]
    assert len(flm_calls) == 2
    assert all(', 1) != 0:' in line for line in flm_calls)
    assert script.count('completion_rc = cmd.reset_target(1)') == 1
    assert script.index('load.bin("assets.bin"') < script.index('completion_rc =')
    assert 'cmd.set_reset()' not in script and 'cmd.cpu_run()' not in script
    assert required_verify_capabilities(config) == ('OFFLINE_H7_DUALCORE=1',)


@pytest.mark.parametrize('part', [None, 'STM32H743IITx', 'STM32H750VBTx', 'STM32F767xx',
                                'STM32H7', 'custom', 'STM32H745ZITx;bad'])
def test_other_targets_do_not_enable_dualcore_by_device_id_or_family_prefix(part):
    config = parse_offline_config(dict(_config(), target_part=part))
    script = generate_offline_script(config)
    assert all(', 1) != 0:' not in line for line in script.splitlines() if 'load.flm(' in line)
    assert required_verify_capabilities(config) == ()
    assert 'cmd.set_reset()' in script


def test_dualcore_capability_is_required_even_with_default_verification():
    config = parse_offline_config(dict(_config(), target_part='STM32H745ZITx'))
    for version in ['', 'V4.99.99', 'OFFLINE_H7_DUALCORE=0', 'prefix OFFLINE_H7_DUALCORE=1']:
        with pytest.raises(OfflineDownloadError, match='Upgrade downloader firmware.*OFFLINE_H7_DUALCORE'):
            require_verify_capabilities(config, version)
    require_verify_capabilities(config, 'V4.7.2\r\nOFFLINE_H7_DUALCORE=1\r\n')


def test_dualcore_verify_controls_require_each_independent_capability():
    config = parse_offline_config(dict(_config(), target_part='STM32H745ZITx', verify_after_download=False))
    required = required_verify_capabilities(config)
    assert required == ('OFFLINE_BIN_VERIFY=1', 'OFFLINE_H7_DUALCORE=1', 'OFFLINE_HEX_VERIFY=1')
    for missing in required:
        with pytest.raises(OfflineDownloadError, match=missing):
            require_verify_capabilities(config, '\n'.join(x for x in required if x != missing))
    require_verify_capabilities(config, '\n'.join(required))


def test_missing_dualcore_capability_rejects_before_any_destination_write(tmp_path):
    config = parse_offline_config(dict(_config(), target_part='STM32H745ZITx'))
    sentinel = tmp_path / 'existing.txt'; sentinel.write_text('keep')
    with pytest.raises(OfflineDownloadError, match='OFFLINE_H7_DUALCORE'):
        deploy_offline_bundle(config, tmp_path, firmware_sources={}, algorithm_sources={},
                              firmware_capability_response='OFFLINE_BIN_VERIFY=1\nOFFLINE_HEX_VERIFY=1')
    assert list(tmp_path.iterdir()) == [sentinel] and sentinel.read_text() == 'keep'


@pytest.mark.parametrize('mode,expected', [(None, 1), ('software', 1), ('hardware', 2)])
def test_dualcore_completion_uses_checked_reset(mode, expected):
    config = parse_offline_config(dict(_config(), target_part='STM32H745ZITx', reset_mode=mode))
    script = generate_offline_script(config)
    assert f'completion_rc = cmd.reset_target({expected})' in script
    assert 'if completion_rc != 0:' in script
    assert script.index('if completion_rc != 0:') < script.index('board download OK')


def test_no_reset_keeps_cores_halted_and_power_cycle_is_not_substituted():
    config = parse_offline_config(dict(_config(), target_part='STM32H745ZITx', reset_after_download=False))
    script = generate_offline_script(config)
    assert 'cmd.reset_target(' not in script and 'cmd.cpu_run()' not in script
    assert 'cmd.set_reset()' not in script
    assert 'cmd.read_swd_idcode()' in script and 'cmd.get_idcode()' not in script
    with pytest.raises(OfflineDownloadError, match='system or hardware reset'):
        parse_offline_config(dict(_config(), target_part='STM32H745ZITx', reset_mode='power_cycle',
                                  reset_voltage_mv=3300))


def test_preview_surfaces_dualcore_requirement_without_hardware(monkeypatch):
    monkeypatch.setattr('mklink.probes.select_probe', lambda *a: pytest.fail('preview selected hardware'))
    with TestClient(create_app(auth_token=None, project_root='.')) as client:
        response = client.post('/api/offline-download/preview', json=dict(_config(), target_part='STM32H745ZITx'))
    assert response.status_code == 200, response.text
    assert response.json()['required_capabilities'] == ['OFFLINE_H7_DUALCORE=1']


@pytest.mark.parametrize('response,expected', [('V4.7.1\nOFFLINE_BIN_VERIFY=1\nOFFLINE_HEX_VERIFY=1', 422),
                                            ('V4.7.2\nOFFLINE_H7_DUALCORE=1', 200)])
def test_http_default_verified_dualcore_deploy_checks_bound_firmware(tmp_path, monkeypatch, response, expected):
    payload = dict(_config(), target_part='STM32H745ZITx')
    payload['firmwares'] = [dict(payload['firmwares'][1], upload_index=0)]
    payload['algorithms'] = payload['algorithms'][:1]
    monkeypatch.setattr('mklink.discovery.find_microkeen_disk', lambda: str(tmp_path))
    monkeypatch.setattr('mklink.probes.select_probe', lambda *_: {'probe_id': 'fixture', 'port': 'FIXTURE'})
    monkeypatch.setattr('mklink.probe_volumes.resolve_volume', lambda *_: {'root': str(tmp_path)})
    commands = []
    def send(command, **kwargs):
        commands.append(command)
        return response
    app = create_app(auth_token=None, project_root='.')
    app.state.mklink_state['device'] = SimpleNamespace(connected=True, port='FIXTURE',
        _bridge=SimpleNamespace(send_command=send), close=lambda: None)
    with TestClient(app) as client:
        result = client.post('/api/offline-download/deploy', data={'config_json': json.dumps(payload)},
            files=[('firmware_files', ('image.hex', b':00000001FF\n')),
                   ('flm_files', ('algo.flm', b'fixture algorithm'))])
    assert result.status_code == expected, result.text
    assert commands == ['cmd.get_version()']
    if expected == 200:
        script = (tmp_path / 'python' / payload['script_name']).read_text()
        assert '0x20000000, 1)' in script
    else:
        assert 'OFFLINE_H7_DUALCORE=1' in result.text
        assert not list(tmp_path.iterdir())

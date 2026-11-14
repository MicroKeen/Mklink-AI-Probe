"""Optional project setup works without an IDE or a connected probe."""
import sys

import pytest
from fastapi.testclient import TestClient

from mklink import cli
from mklink.project_config import load_config, load_project_info, save_config, save_project_info


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Project initialization must remain offline')
    monkeypatch.setattr('mklink.discovery.find_mklink_cdc_port', forbidden)
    monkeypatch.setattr('mklink.mcu_detect.inspect_mcu', forbidden)
    monkeypatch.setattr('mklink.probes.inventory', forbidden)


def run_init(monkeypatch, root, *options):
    monkeypatch.setattr(sys, 'argv', ['mklink', 'project-init', '--project-root', str(root), *options])
    return cli.main()


@pytest.mark.parametrize('firmware_option,symbol_option,suffix,key', [
    ('--firmware', '--elf', '.hex', 'hex_path'),
    ('--hex', '--axf', '.bin', 'bin_path'),
])
def test_generic_cli_saves_explicit_inputs_without_build_outputs(
    tmp_path, monkeypatch, firmware_option, symbol_option, suffix, key,
):
    root = tmp_path / 'CMake project'
    root.mkdir()
    (root / 'CMakeLists.txt').write_text('project(firmware C)', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    assert run_init(monkeypatch, root, '--target-part', 'STM32G071GBU6',
                    firmware_option, f'build/Debug/firmware{suffix}',
                    symbol_option, 'build/Debug/firmware.elf') == 0
    info = load_project_info(str(root))
    assert info['device'] == 'STM32G071GBU6'
    assert info[key] == str(root / 'build' / 'Debug' / f'firmware{suffix}')
    assert info['axf_path'] == str(root / 'build' / 'Debug' / 'firmware.elf')
    assert info['elf_path'] == info['axf_path']
    assert load_config(str(root)) == {'swd_clock': 1000000}
    assert not {'mcu_key', 'flm_path', 'com_port'} & info.keys()


def test_generic_reinitialization_preserves_settings_and_accepts_path_update(tmp_path, monkeypatch):
    assert run_init(monkeypatch, tmp_path, '--target-part', 'STM32G071GBU6') == 0
    save_config(str(tmp_path), {'com_port': 'COM8', 'swd_clock': 2000000})
    rtt = tmp_path / '.mklink' / 'rtt_config.json'
    rtt.write_text('{"channel": 2}', encoding='utf-8')
    assert run_init(monkeypatch, tmp_path, '--elf', 'build/debug.axf') == 0
    assert run_init(monkeypatch, tmp_path) == 0
    assert load_project_info(str(tmp_path))['device'] == 'STM32G071GBU6'
    assert load_project_info(str(tmp_path))['axf_path'] == str(tmp_path / 'build' / 'debug.axf')
    assert load_config(str(tmp_path)) == {'com_port': 'COM8', 'swd_clock': 2000000}
    assert rtt.read_text(encoding='utf-8') == '{"channel": 2}'


def test_explicit_path_update_keeps_existing_ide_identity(tmp_path, monkeypatch):
    save_project_info(str(tmp_path), {'ide_type': 'Keil', 'device': 'STM32G071GBU6',
                                     'uvprojx_path': 'Blinky.uvprojx', 'target_name': 'Debug'})
    assert run_init(monkeypatch, tmp_path, '--target-part', 'STM32G071GBU6',
                    '--firmware', 'build/debug.hex') == 0
    info = load_project_info(str(tmp_path))
    assert info['ide_type'] == 'Keil'
    assert info['target_name'] == 'Debug' and info['uvprojx_path'] == 'Blinky.uvprojx'
    assert info['hex_path'] == str(tmp_path / 'build' / 'debug.hex')


def test_unsupported_project_requests_target_and_returns_failure_without_writes(tmp_path, monkeypatch, capsys):
    assert run_init(monkeypatch, tmp_path) == 1
    assert '--target-part' in capsys.readouterr().out
    assert not (tmp_path / '.mklink').exists()


@pytest.mark.parametrize('options', [
    ['--target-part', '   '], ['--target-part', 'X' * 129],
    ['--target-part', 'STM32G071GBU6', '--firmware', ''],
    ['--target-part', 'STM32G071GBU6', '--firmware', 'firmware.elf'],
    ['--target-part', 'STM32G071GBU6', '--elf', 'firmware.hex'],
])
def test_invalid_inputs_do_not_modify_saved_settings(tmp_path, monkeypatch, options):
    save_config(str(tmp_path), {'swd_clock': 2000000})
    save_project_info(str(tmp_path), {'device': 'STM32G071GBU6', 'hex_path': 'old.hex'})
    before = {p.name: p.read_bytes() for p in (tmp_path / '.mklink').iterdir()}
    assert run_init(monkeypatch, tmp_path, *options) == 1
    assert {p.name: p.read_bytes() for p in (tmp_path / '.mklink').iterdir()} == before


def test_malformed_existing_configuration_is_not_replaced(tmp_path, monkeypatch):
    config = tmp_path / '.mklink'
    config.mkdir()
    (config / 'project_info.json').write_bytes(b'{broken')
    assert run_init(monkeypatch, tmp_path, '--target-part', 'STM32G071GBU6') == 1
    assert (config / 'project_info.json').read_bytes() == b'{broken'
    assert not (config / 'config.json').exists()


def test_generic_init_rejects_nonexistent_root(tmp_path, monkeypatch):
    root = tmp_path / 'typo'
    assert run_init(monkeypatch, root, '--target-part', 'STM32G071GBU6') == 1
    assert not root.exists()


@pytest.mark.parametrize('legacy_profile', [False, True])
def test_explicit_target_conflict_preserves_all_existing_configuration(tmp_path, monkeypatch, capsys, legacy_profile):
    if legacy_profile:
        save_config(str(tmp_path), {'mcu_key': 'hpm5301', 'com_port': 'COM8'})
    else:
        save_project_info(str(tmp_path), {'device': 'HPM5301', 'vendor': 'HPMicro',
                                         'board': 'hpm5301evklite', 'bin_base': '0x80000400'})
    before = {p.name: p.read_bytes() for p in (tmp_path / '.mklink').iterdir()}
    assert run_init(monkeypatch, tmp_path, '--target-part', 'STM32G071GBU6') == 1
    assert 'STM32G071GBU6' in capsys.readouterr().out
    assert {p.name: p.read_bytes() for p in (tmp_path / '.mklink').iterdir()} == before


def test_project_init_api_reports_failure_for_unrecognized_project(tmp_path):
    from mklink.remote.api import create_app
    with TestClient(create_app(project_root=str(tmp_path))) as client:
        response = client.post('/api/project-init')
    assert response.status_code == 200
    assert response.json()['success'] is False
    assert '--target-part' in response.json()['output']

"""Combined deployment must not silently omit OTP or start a partial recipe."""
import sys
import json
from types import SimpleNamespace
import pytest

from mklink.offline_download import parse_offline_config, generate_offline_script, deploy_offline_bundle, OfflineDownloadError
from mklink.hpm_isp import script_metadata


def payload():
    return dict(model='V4', target_part='HPM5301', programming_protocol='hpm_rom_isp_uart',
                hpm_isp={}, algorithms=[], firmwares=[dict(id='app', file_name='app.bin', format='bin',
                base_address='0x80023000', upload_index=0)], hpm_isp_otp=dict(
                    target_identity=dict(chip_id=0x11705142, rom_version=1, soc_revision=2),
                    words=[dict(word=69, expected=1, desired=3)], confirm_irreversible=True))


@pytest.mark.parametrize('stage', ['supported', 'config', 'otp_config', 'otp_add', 'program', 'ok'])
def test_combined_script_stops_on_recipe_failure_and_submits_once(monkeypatch, stage):
    calls = []
    def run(name, *args):
        calls.append((name, args))
        return -7 if name == stage else 0
    monkeypatch.setitem(sys.modules, 'hpm', SimpleNamespace(
        isp_supported=lambda: 1, isp_otp_job_supported=lambda: int(stage != 'supported'),
        isp_config=lambda *a: run('config', *a),
        isp_otp_job_config=lambda *a: run('otp_config', *a),
        isp_otp_job_add=lambda *a: run('otp_add', *a),
        isp_program=lambda *a: run('program', *a),
        isp_otp_job_clear=lambda: run('clear')))
    script = generate_offline_script(parse_offline_config(payload()))
    assert script_metadata(script)['otp'] is True
    exec(script, {})
    names = [name for name, _ in calls]
    assert names.count('program') == int(stage in ('program', 'ok'))
    if stage != 'supported':
        assert names[-1] == 'clear'
    if stage == 'ok':
        assert names == ['config', 'otp_config', 'otp_add', 'program', 'clear']
        assert calls[2][1] == (69, 1, 3)
    assert max(len(line.encode()) for line in script.splitlines()) < 512


@pytest.mark.parametrize('supported', [False, True])
def test_http_deploy_checks_joint_capability_before_copy(tmp_path, monkeypatch, supported):
    from fastapi.testclient import TestClient
    from mklink.remote.api import create_app
    from mklink.hpm_isp import CAPABILITY_COMMAND, OTP_JOB_CAPABILITY_COMMAND
    monkeypatch.setattr('mklink.discovery.find_microkeen_disk', lambda: str(tmp_path))
    app = create_app(auth_token=None, project_root=str(tmp_path))
    commands = []
    def command(text, **_):
        commands.append(text)
        if text == CAPABILITY_COMMAND: return 'MKLINK_HPM_ISP_API 1'
        if text == OTP_JOB_CAPABILITY_COMMAND: return f'MKLINK_HPM_ISP_OTP_JOB_API {int(supported)}'
        raise AssertionError(text)
    app.state.mklink_state['device'] = SimpleNamespace(connected=True, port='fixture', close=lambda: None, _bridge=SimpleNamespace(send_command=command))
    with TestClient(app) as client:
        response = client.post('/api/offline-download/deploy', data={'config_json': json.dumps(payload())},
                               files={'firmware_files': ('app.bin', b'\x01\x02\x03\x04')})
    assert commands == [CAPABILITY_COMMAND, OTP_JOB_CAPABILITY_COMMAND]
    assert response.status_code == (200 if supported else 422), response.text
    assert (tmp_path / 'app.bin').exists() is supported


@pytest.mark.parametrize('field,value', [
    ('confirm_irreversible', False), ('confirm_irreversible', 1),
    ('target_identity', {}), ('words', []),
    ('words', [dict(word=64, expected=0, desired=1)]),
    ('words', [dict(word=69, expected=3, desired=1)]),
    ('words', [dict(word=True, expected=0, desired=1)]),
    ('words', [dict(word=69, expected=0, desired=1)] * 2),
])
def test_invalid_recipe_rejected(field, value):
    data = payload(); data['hpm_isp_otp'][field] = value
    with pytest.raises(OfflineDownloadError): parse_offline_config(data)


def test_no_otp_recipe_for_arm_or_jtag():
    for target in ('STM32F103RC', 'HPM5301'):
        data = payload(); data.update(programming_protocol='debug', target_part=target)
        with pytest.raises(OfflineDownloadError, match='USART ISP'): parse_offline_config(data)


def test_equal_words_remain_for_firmware_skip_and_locks_are_last():
    data = payload()
    data['hpm_isp_otp']['words'] = [dict(word=w, expected=1, desired=1) for w in (0, 2, 69, 1)]
    config = parse_offline_config(data)
    assert [w[0] for w in config.hpm_isp_otp.words] == [69, 1, 2, 0]


def test_bundle_requires_joint_capability_before_writing_disk(tmp_path):
    source = tmp_path / 'input.bin'; source.write_bytes(b'\x01\x02\x03\x04')
    disk = tmp_path / 'disk'; disk.mkdir()
    config = parse_offline_config(payload())
    with pytest.raises(OfflineDownloadError, match='combined'):
        deploy_offline_bundle(config, disk, firmware_sources={'app': source}, algorithm_sources={},
                              isp_capability_response='MKLINK_HPM_ISP_API 1')
    assert list(disk.iterdir()) == []
    deploy_offline_bundle(config, disk, firmware_sources={'app': source}, algorithm_sources={},
                         isp_capability_response='MKLINK_HPM_ISP_API 1\nMKLINK_HPM_ISP_OTP_JOB_API 1')
    assert (disk / 'app.bin').read_bytes() == source.read_bytes()
    script = (disk / 'python' / config.script_name).read_text()
    assert 'hpm.isp_otp_job_add(69, 1, 3)' in script
    assert script_metadata(script)['otp'] is True

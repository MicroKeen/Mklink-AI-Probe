import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink import hpm_jtag_otp_rom as rom
from mklink.hpm_offline_otp import resolve, script_lines


def board():
    profile = rom.PROFILES['HPM6E80']
    device = SimpleNamespace(idcode=0x1000563D, mcu_name='HPM6E80', current=0, uid=bytes(range(16)))

    def read(address, size):
        if address == profile.otp_base + 0x420 and size == 16:
            return device.uid
        values = {profile.otp_base + 0x500: profile.chip_id, profile.otp_base + 0x400 + 72 * 4: device.current}
        return values.get(address, 0).to_bytes(size, 'little')

    def command(line, timeout):
        if 'otp_rom_version()' in line:
            return 'MKLINK_OTP_ROM 1\r\n'
        if 'MKLINK_OTP_PROFILE' in line:
            return 'MKLINK_OTP_PROFILE ' + profile.encode()
        if line.startswith('mkotp='):
            return ''
        _, nonce, _, word, expected, desired, commit = line.removeprefix('hpm.otp_rom_word(').rstrip(')').split(',')
        w, old, new, issue = map(int, (word, expected, desired, commit))
        if issue:
            device.current = new
        result = dict(v=1, id=int(nonce), word=w, commit=issue, rc=0, issued=issue, valid=63 if issue else 15,
                      chip=profile.chip_id, mv=3299, before=old, delta=new & ~old, after=device.current, rom_status=0)
        return 'HPM_OTP_ROM ' + json.dumps(result) + '\r\n0\r\n'

    device.read_memory = read
    device._bridge = SimpleNamespace(send_command=Mock(side_effect=command))
    return device


def test_profile_and_bound_single_word():
    d = board()
    args = (d, 'HPM6E80IVM', 'V4', 72, 0, 1)
    plan = rom.run(*args)
    assert d.current == 0 and plan['delta'] == 1
    with pytest.raises(ValueError, match='UID'):
        rom.run(*args, commit=True)
    assert d.current == 0
    result = rom.run(*args, commit=True, target_identity=plan['target_identity'])
    assert result['verified'] and result['after'] == 1
    assert result['target_identity'] == plan['target_identity']


@pytest.mark.parametrize('part,w,old,new', [('HPM6E00',72,0,1), ('HPM6E84',72,0,1), ('HPM6E80',0,0,1),
                                            ('HPM6E80',72,1,0), ('HPM6E80',72,1,1)])
def test_unknown_profile_or_forbidden_change_rejected_before_io(part,w,old,new):
    d = board()
    with pytest.raises(ValueError):
        rom.run(d, part, 'V4', w, old, new)
    d._bridge.send_command.assert_not_called()


def test_old_firmware_stops_without_legacy_fallback():
    d = board()
    d._bridge.send_command.side_effect = None
    d._bridge.send_command.return_value = 'NameError\r\n0'
    with pytest.raises(ValueError, match='OTP ROM API v1'):
        rom.run(d, 'HPM6E80', 'V4', 72, 0, 1)
    assert d._bridge.send_command.call_count == 1


@pytest.mark.parametrize('part', ['HPM5151', 'HPM5361', 'HPM5E31', 'HPM6280', 'HPM6360', 'HPM6450',
                                  'HPM6750', 'HPM6880', 'HPM6E84', 'HPM6P81'])
def test_qualified_part_uses_its_sdk_geometry(tmp_path, monkeypatch, part):
    from mklink.hpm_jtag_otp import otp_base
    path = tmp_path/'qualified.json'
    monkeypatch.setenv('MKLINK_HPM_OTP_QUALIFICATIONS', str(path))
    # Synthetic identities only. They do not qualify a physical board.
    row = dict(chip_id=17, driver_version=1, scratch_offset=0x1000, min_mv=3100,
               max_mv=3500, user_words=[69,79], evidence='simulated board')
    path.write_text(json.dumps({'schema':1,'parts':{part:row}}))
    profile = rom.profile_for(part,'V4')
    assert profile.otp_base == otp_base(part)
    assert profile.ram_bus == rom.ILM_AND_LDO[part[:5]][0] + 0x1000
    assert rom.profile_for(part,'V3') is None
    row['scratch_offset'] = 2**31
    path.write_text(json.dumps({'schema':1,'parts':{part:row}}))
    with pytest.raises(ValueError, match='ILM'):
        rom.profile_for(part,'V4')


@pytest.mark.parametrize('bad', [dict(id=2),dict(issued=1),dict(mv=2900),dict(valid=8),dict(rc=-7),
                                 dict(before=2),dict(delta=0),dict(chip=1)])
def test_invalid_preflight_evidence(bad):
    p = rom.PROFILES['HPM6E80']
    record = dict(v=1,id=1,word=72,commit=0,rc=0,issued=0,valid=15,chip=p.chip_id,mv=3300,
                  before=0,delta=1,after=0,rom_status=0)
    record.update(bad)
    with pytest.raises(ValueError):
        rom._result('HPM_OTP_ROM '+json.dumps(record)+'\n0\n', 1, p, dict(word=72,expected=0,desired=1,delta=1), False)


def test_offline_compiles_the_same_guarded_profile_and_rejects_permanent_lock():
    cfg = dict(words=[dict(word=72, expected=0, desired=1)], confirm_irreversible=True)
    plan = resolve(cfg, 'HPM6E80', 'V4')
    for mode in (False, True):
        script = '\n'.join(script_lines(plan, commit=mode))
        assert 'otp_rom_version()' in script and rom.word_call(1,72,0,1,mode) in script
        assert 'otp_user(' not in script
    with pytest.raises(ValueError, match='application data'):
        resolve(dict(cfg, locks=[18], expected_hard_lock=0), 'HPM6E80', 'V4')


def test_http_plan_is_fixed_bound_and_consumed(tmp_path):
    from fastapi.testclient import TestClient
    from mklink.remote.api import create_app
    app = create_app(project_root=str(tmp_path))
    d = board()
    d.port, d.connected = 'COM12', True
    state = app.state.mklink_state
    state.update(device=d, device_generation=1)
    app.state.shared_runtime = SimpleNamespace(info={'probe_id': 'test-probe'})
    base = '/api/device/configuration/hpm-user-otp/'
    args = dict(part_number='HPM6E80', word=72, expected=0, desired=1)
    client = TestClient(app)
    def preview():
        response = client.post(base+'plan', json=args)
        assert response.status_code == 200, response.text
        assert 'target_identity' not in response.json()
        return dict(part_number='HPM6E80', plan_id=response.json()['plan_id'], confirm_irreversible=True)
    commit = preview()
    state['device_generation'] += 1
    assert client.post(base+'program', json=commit).status_code == 422
    commit = preview()
    assert client.post(base+'program', json=dict(commit, desired=3)).status_code == 422
    d.uid = b'B' * 16
    assert client.post(base+'program', json=commit).status_code == 422
    assert d.current == 0
    commit = preview()
    assert client.post(base+'program', json=commit).json()['verified'] is True
    assert client.post(base+'program', json=commit).status_code == 422

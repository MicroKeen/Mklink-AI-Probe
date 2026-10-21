import json
import re
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mklink import hpm_isp_otp_profile as otp
from mklink.hpm_otp_profiles import family, ordered_changes, validate_change
from mklink.remote.hpm_isp_otp_api import create_hpm_isp_otp_router
from mklink.remote.hpm_isp_otp_plans import OtpBinding, OtpPlans
from mklink.remote.resource_manager import ResourceManager


IDENTITY = dict(chip_id=0x12345678, rom_version=0x56010200, soc_revision=0x56010000)


class Bridge:
    def __init__(self):
        self.calls = []
        self.values = [0] * 128
        self.mutate = lambda result: result

    def send_command(self, command, **kwargs):
        self.calls.append(command)
        if command == otp.CAPABILITY:
            return 'MKLINK_HPM_ISP_OTP_PROFILE_API 1'
        match = re.fullmatch(r'hpm.isp_otp_profile_(read|word)\("([a-f0-9]+)","([A-Z0-9/]+)",(.*)\)', command)
        assert match, command
        action, nonce, profile, args = match.groups()
        args = [int(item) for item in args.split(',')]
        result = dict(schema=1, event='result', api='profile_v1', request_id=nonce, code=0, rom_status=0,
                      profile=profile, profile_verified=None, chip_id=IDENTITY['chip_id'], rom_version=0x56010200,
                      soc_revision=0x56010000, memory_id=0x20000, hard_lock=0, lifecycle=0x10000001,
                      read_source='rom_otp', read_semantics='unknown')
        if action == 'read':
            start, count = args[:2]
            result.update(operation='read', start_word=start, values=self.values[start:start+count], statuses=[0]*count, codes=[0]*count)
        else:
            chip, rom, soc, word, expected, desired, commit = args[:7]
            result.update(operation='program' if commit else 'plan', word=word, expected=expected, desired=desired,
                          delta=desired & ~expected, before=self.values[word], qualified=True, write_supported=True,
                          write_method='rom_write_memory', verification_source='rom_otp', locked=None, reason=None,
                          write_attempted=bool(commit), verified=bool(commit), after=desired if commit else None,
                          write_status=0 if commit else None)
            if commit:
                self.values[word] = desired
        return 'HPM_OTP ' + json.dumps(self.mutate(result))


@pytest.mark.parametrize('part,name', [('HPM5301XEGX', 'HPM5300'), ('HPM6280', 'HPM6200'),
    ('HPM6360', 'HPM6300'), ('HPM6450', 'HPM6700/HPM6400'), ('HPM6750', 'HPM6700/HPM6400'),
    ('HPM6880', 'HPM6800'), ('HPM6E80', 'HPM6E00'), ('HPM6P81', 'HPM6P00'), ('HPM5E31', 'HPM5E00')])
def test_family_profiles_and_bounded_reads(part, name):
    bridge = Bridge()
    result = otp.read_snapshot(bridge, part)
    assert family(part) == name == result['profile']
    assert len(result['words']) == 128
    assert len(bridge.calls) == 17
    assert not any('_word(' in command for command in bridge.calls)


def test_denied_words_remain_unknown():
    bridge = Bridge()
    def denied(result):
        if result['start_word'] == 80:
            result['values'][0] = None
            result['statuses'][0] = 200
            result['codes'][0] = -7
            result['rom_status'] = 200
        return result
    bridge.mutate = denied
    assert otp.read_snapshot(bridge, 'HPM5301')['words'][80]['current'] is None


@pytest.mark.parametrize('patch', [dict(profile='HPM6200'), dict(profile_verified=False),
    dict(chip_id=0), dict(chip_id=True), dict(start_word=True), dict(values=[0]),
    dict(statuses=[1]*8), dict(api='unknown'), dict(memory_id=0)])
def test_bad_or_wrong_profile_snapshot_is_discarded(patch):
    bridge = Bridge()
    bridge.mutate = lambda result: dict(result, **patch)
    with pytest.raises(ValueError): otp.read_snapshot(bridge, 'HPM5301')


def test_mid_read_identity_change_discards_entire_snapshot():
    bridge = Bridge()
    bridge.mutate = lambda result: dict(result, chip_id=123 if result['start_word'] else 0x11705142)
    with pytest.raises(ValueError, match='changed'): otp.read_snapshot(bridge, 'HPM5301')


def test_data_preflight_before_any_program_and_locks_last():
    bridge = Bridge()
    changes = [validate_change(word, 0, 1) for word in (0, 1, 69, 80)]
    result = otp.program_changes(bridge, 'HPM6750', changes, IDENTITY)
    assert [item['word'] for item in result['completed']] == [69, 80, 1, 0]
    word_calls = [call for call in bridge.calls if '_word(' in call]
    assert all(call.endswith(',0,30000,1000)') for call in word_calls[:4])
    assert all(call.endswith(',1,30000,1000)') for call in word_calls[4:])


def test_unknown_commit_stops_without_replay_or_locks():
    bridge = Bridge()
    def unknown(result):
        if result.get('operation') == 'program' and result['word'] == 80:
            result.update(code=-3, reason='write_outcome_unknown')
        return result
    bridge.mutate = unknown
    result = otp.program_changes(bridge, 'HPM5301', [validate_change(word, 0, 1) for word in (0, 69, 80)], IDENTITY)
    assert result['status'] == 'failed'
    assert [item['word'] for item in result['completed']] == [69]
    assert result['remaining'] == [0]
    assert len([call for call in bridge.calls if '_word(' in call and call.endswith(',1,30000,1000)')]) == 2


def test_failing_batch_preflight_never_programs():
    bridge = Bridge()
    bridge.mutate = lambda result: dict(result, qualified=False, write_supported=False, reason='hard_locked') if result.get('word') == 80 else result
    with pytest.raises(ValueError): otp.program_changes(bridge, 'HPM5301', [validate_change(word, 0, 1) for word in (69, 80)], IDENTITY)
    assert bridge.values == [0]*128


def test_old_firmware_does_not_receive_new_family_or_security_writes(monkeypatch):
    bridge = SimpleNamespace(send_command=Mock(return_value='unsupported'))
    fallback = Mock(return_value={'words': []})
    monkeypatch.setattr(otp.legacy, 'read_snapshot', fallback)
    assert otp.read_snapshot(bridge, 'HPM5301')['capability'] == 'legacy_user'
    with pytest.raises(ValueError, match='升级'): otp.read_snapshot(bridge, 'HPM6280')
    with pytest.raises(ValueError, match='升级'): otp.plan_changes(bridge, 'HPM5301', [validate_change(1, 0, 1)])
    assert all(call.args[0] == otp.CAPABILITY for call in bridge.send_command.call_args_list)


def test_api_accepts_official_family_without_opening_jtag(monkeypatch):
    app = FastAPI(); manager = ResourceManager()
    bridge = SimpleNamespace(connect=lambda: True, close=Mock())
    monkeypatch.setattr('mklink.discovery.find_mklink_cdc_port', lambda: 'fixture')
    monkeypatch.setattr('mklink.bridge.MKLinkSerialBridge', lambda port: bridge)
    read = Mock(return_value={'words': []})
    monkeypatch.setattr(otp, 'read_snapshot', read)
    app.include_router(create_hpm_isp_otp_router(manager, lambda: None))
    with TestClient(app) as client:
        response = client.post('/api/device/configuration/hpm-isp-otp/read', json={'part_number': 'HPM6280', 'extended': True})
        assert response.status_code == 200
        for part in ('HPM5100', 'HPM53\"bad', 'STM32F103'):
            assert client.post('/api/device/configuration/hpm-isp-otp/read', json={'part_number': part, 'extended': True}).status_code == 422
    read.assert_called_once_with(bridge, 'HPM6280')
    bridge.close.assert_called_once()
    assert not manager.get_status()


def test_tokens_cannot_cross_legacy_and_extended_scope():
    plans = OtpPlans()
    binding = OtpBinding('probe', 'port', 1, 'HPM5301', True)
    token = plans.remember(binding, {'changes': [validate_change(69, 0, 1)]})['plan_id']
    with pytest.raises(ValueError): plans.consume(token, OtpBinding('probe', 'port', 1, 'HPM5301'))


@pytest.mark.parametrize('word,expected,desired', [(-1, 0, 1), (128, 0, 1), (True, 0, 1), (0, 1, 0), (0, 0, 2**32)])
def test_invalid_extended_changes(word, expected, desired):
    with pytest.raises(ValueError): validate_change(word, expected, desired)


def test_identity_in_token_is_fixed_and_not_mutable_by_client():
    plans = OtpPlans()
    binding = OtpBinding('probe', 'port', 1, 'HPM5301', True)
    response = plans.remember(binding, dict(changes=[validate_change(69, 0, 1)], target_identity=IDENTITY.copy()))
    response['target_identity']['chip_id'] = 999
    assert plans.consume(response['plan_id'], binding)['target_identity'] == IDENTITY


def test_extended_write_rechecks_snapshot_identity():
    bridge = Bridge()
    bridge.mutate = lambda result: dict(result, chip_id=999)
    with pytest.raises(ValueError, match='identity changed'):
        otp.plan_changes(bridge, 'HPM5301', [validate_change(24, 0, 1)], IDENTITY)
    assert bridge.values == [0]*128


def test_known_5301_cannot_use_another_family_template():
    bridge = Bridge()
    bridge.mutate = lambda result: dict(result, chip_id=otp.legacy.CHIP_ID)
    with pytest.raises(ValueError, match='conflicts'):
        otp.read_snapshot(bridge, 'HPM6280')


def test_chip_id_word_requires_a_separate_batch():
    bridge = Bridge()
    with pytest.raises(ValueError, match='CHIP_ID'):
        otp.plan_changes(bridge, 'HPM5301', [validate_change(word, 0, 1) for word in (64, 69)], IDENTITY)
    assert bridge.calls == []

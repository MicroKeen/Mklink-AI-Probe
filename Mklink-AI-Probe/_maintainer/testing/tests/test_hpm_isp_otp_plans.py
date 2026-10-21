from dataclasses import replace
import pytest
from mklink.remote.hpm_isp_otp_plans import OtpBinding, OtpPlans


BINDING = OtpBinding('probe', 'COM9', 2, 'HPM5301')
CHANGE = dict(word=69, expected=5, desired=7, delta=2)


def test_plan_is_immutable_and_single_use():
    plans = OtpPlans()
    response = plans.remember(BINDING, CHANGE)
    response['desired'] = 0xffffffff
    assert plans.consume(response['plan_id'], BINDING) == CHANGE
    with pytest.raises(ValueError, match='already used'):
        plans.consume(response['plan_id'], BINDING)


@pytest.mark.parametrize('changed', [dict(probe_id='other'), dict(port='COM10'), dict(generation=3), dict(part='HPM5301XEGX')])
def test_plan_cannot_follow_probe_port_generation_or_part_change(changed):
    plans = OtpPlans()
    token = plans.remember(BINDING, CHANGE)['plan_id']
    with pytest.raises(ValueError, match='selection changed'):
        plans.consume(token, replace(BINDING, **changed))
    with pytest.raises(ValueError, match='already used'):
        plans.consume(token, BINDING)


def test_expired_and_superseded_previews_cannot_execute():
    now = [10]
    plans = OtpPlans(clock=lambda: now[0])
    old = plans.remember(BINDING, CHANGE)['plan_id']
    new = plans.remember(BINDING, CHANGE)['plan_id']
    with pytest.raises(ValueError): plans.consume(old, BINDING)
    now[0] += plans.TTL
    with pytest.raises(ValueError, match='expired'): plans.consume(new, BINDING)
    fresh = plans.remember(BINDING, CHANGE)['plan_id']
    plans.clear()
    with pytest.raises(ValueError): plans.consume(fresh, BINDING)


def test_batch_token_copies_all_words_and_is_single_use():
    plans = OtpPlans()
    change = dict(changes=[CHANGE.copy(), dict(word=70, expected=0, desired=1, delta=1)])
    result = plans.remember(BINDING, change)
    result['changes'][0]['desired'] = 999
    fixed = plans.consume(result['plan_id'], BINDING)
    assert fixed['changes'][0] == CHANGE
    assert fixed['changes'][1]['word'] == 70
    with pytest.raises(ValueError): plans.consume(result['plan_id'], BINDING)

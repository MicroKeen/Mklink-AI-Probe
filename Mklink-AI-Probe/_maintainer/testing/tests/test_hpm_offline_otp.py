import sys
from types import SimpleNamespace

import pytest

from mklink.hpm_offline_otp import resolve
from mklink.offline_download import parse_offline_config, generate_offline_script


def recipe():
    return dict(words=[dict(word=72, expected=0, desired=1), dict(word=79, expected=0, desired=3)],
                locks=[18, 19], expected_hard_lock=0x30400016, confirm_irreversible=True)


def payload():
    return dict(model='V4', script_name='otp.py', auto_download_count=1,
                target_part='HPM5301', board='hpm5301evklite', algorithms=[],
                swd_clock_hz=30000000, wait_idcode_timeout_ms=1000, hpm_user_otp=recipe(),
                firmwares=[dict(id=str(i), file_name=f'app{i}.bin', format='bin',
                                base_address=hex(0x80000400+i*0x10000), algorithm_id='', upload_index=i)
                           for i in range(2)])


@pytest.mark.parametrize('failure', [None, 'capability', 'pre-word', 'pre-lock', 'first-file', 'second-file', 'first-word', 'second-word', 'first-lock', 'second-lock', 'missing-api'])
def test_generated_recipe_stops_before_any_following_operation(monkeypatch, failure):
    events = []
    def verified(*args):
        if not args:
            events.append('capability')
            return 0 if failure == 'capability' else -1
        label = 'first-file' if args[0] == 'app0.bin' else 'second-file'
        events.append(label)
        return -1 if failure == label else 0
    def word(w, old, new, commit):
        label = ('first-word' if w == 72 else 'second-word') if commit else 'pre-word'
        events.append(label)
        return -1 if failure == label else 0
    def lock(g, old, commit):
        label = ('first-lock' if g == 18 else 'second-lock') if commit else 'pre-lock'
        if commit:
            assert old == (0x30400016 if g == 18 else 0x30440016)
        else:
            assert old == 0x30400016
        events.append(label)
        return -1 if failure == label else 0
    hpm = SimpleNamespace(otp_user=word, otp_user_lock=lock, board=lambda _: 0)
    if failure != 'missing-api':
        hpm.program_verified = verified
    for name, obj in dict(hpm=hpm, PikaStdLib=SimpleNamespace(),
                          time=SimpleNamespace(sleep_ms=lambda _: None),
                          cmd=SimpleNamespace(set_swd_clock=lambda _: None, get_idcode=lambda: 0x1000563D,
                                              set_beep_on=lambda: None, set_beep_off=lambda: None)).items():
        monkeypatch.setitem(sys.modules, name, obj)
    script = generate_offline_script(parse_offline_config(payload()))
    namespace = {}
    if failure == 'missing-api':
        with pytest.raises(AttributeError):
            exec(script, namespace)
        assert events == []
        return
    exec(script, namespace)
    assert namespace['abort'] is bool(failure)
    if failure:
        assert events[-1] == failure
    else:
        assert events == ['capability', 'pre-word', 'pre-word', 'pre-lock', 'pre-lock',
                          'first-file', 'second-file', 'first-word', 'second-word', 'first-lock', 'second-lock']


@pytest.mark.parametrize('change', [
    {'words': [] ,'locks': []}, {'confirm_irreversible': False},
    {'words': [dict(word=68, expected=0, desired=1)]},
    {'words': [dict(word=80, expected=0, desired=1)]},
    {'words': [dict(word=69, expected=3, desired=1)]},
    {'words': [dict(word=69, expected=0, desired=1)]*2},
    {'locks': [17]}, {'locks': [19,19]}, {'expected_hard_lock': 0x30480016},
    {'words': [dict(word=True, expected=0, desired=1)]},
])
def test_recipe_rejects_unsafe_or_ambiguous_values(change):
    raw=recipe();raw.update(change)
    with pytest.raises(ValueError):
        resolve(raw,'HPM5301','V4')


@pytest.mark.parametrize('part,model', [('HPM6E80','V4'),('STM32F103RE','V4'),('HPM5301','V3')])
def test_recipe_only_qualified_model(part,model):
    with pytest.raises(ValueError):
        resolve(recipe(),part,model)

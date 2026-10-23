"""Execute generated HPM scripts against deterministic connection timelines."""
import sys
from types import SimpleNamespace

import pytest

from mklink.offline_download import generate_offline_script, parse_offline_config


def config(count=2):
    return dict(model='V4', script_name='hpm.py', target_part='HPM5301',
                board='hpm5301evklite', auto_download_count=count,
                wait_idcode_timeout_ms=1000, swd_clock_hz=10000000,
                beep_duration_ms=125, algorithms=[], firmwares=[
                    dict(id=str(i), file_name=f'app{i}.bin', format='bin',
                         base_address=0x80000400+i*0x100000, algorithm_id='', upload_index=i)
                    for i in range(2)])


def execute(monkeypatch, ids, *, count=2, supported=1, fail_image=0):
    events, output = [], []
    iterator = iter(ids)
    def record(name, result=0):
        def run(*args):
            events.append((name, *args))
            return result
        return run
    def read():
        result = next(iterator)
        events.append(('presence', result))
        return result
    def program(*args):
        events.append(('image', *args))
        return -1 if sum(e[0] == 'image' for e in events) == fail_image else 0
    monkeypatch.setitem(sys.modules, 'PikaStdLib', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'time', SimpleNamespace(sleep_ms=record('sleep')))
    # Cached get_idcode and generic reset are intentionally unavailable.
    monkeypatch.setitem(sys.modules, 'cmd', SimpleNamespace(set_swd_clock=record('clock'),
                        set_beep_on=record('beep_on'), set_beep_off=record('beep_off')))
    monkeypatch.setitem(sys.modules, 'hpm', SimpleNamespace(
        jtag_presence_supported=record('capability', supported), read_idcode=read,
        board=record('board'), program=program))
    namespace = {'print': lambda *args: output.append(' '.join(map(str, args)))}
    exec(generate_offline_script(parse_offline_config(config(count))), namespace)
    return events, output, namespace['abort']


ID = 0x1000563D


def test_two_boards_wait_for_real_removal_not_reset_or_single_dropout(monkeypatch):
    # Connect, reset transient, stable recovery, a transient loss, real removal,
    # next board, stable recovery; never poll removal after the final board.
    ids = [ID, 0, ID, ID, 0, ID, 0, 0, 0, 0, ID, ID, ID]
    events, output, aborted = execute(monkeypatch, ids)
    assert not aborted
    assert [e[0] for e in events].count('image') == 4
    assert events.count(('beep_on',)) == events.count(('beep_off',)) == 2
    assert events.count(('sleep', 125)) == 2
    assert output.count('target connected') == 2
    assert output.count('target disconnected') == 1
    assert output.count('waiting for target removal') == 1
    assert output[-1] == 'auto download finished'
    third_image = [i for i, e in enumerate(events) if e[0] == 'image'][2]
    assert [e[1] for e in events[:third_image] if e[0] == 'presence'] == ids[:11]
    assert not any('IDCODE' in line or 'idcode =' in line for line in output)


def test_single_board_finishes_without_post_program_connection_wait(monkeypatch):
    events, output, aborted = execute(monkeypatch, [ID], count=1)
    assert not aborted and events.count(('presence', ID)) == 1
    assert events.count(('beep_on',)) == 1
    assert 'waiting for target removal' not in output
    assert output[-1] == 'auto download finished'


@pytest.mark.parametrize('code', [-2, -3, -4, -6, -12])
@pytest.mark.parametrize('prefix,expected_images', [([], 0), ([ID], 2), ([ID, ID, ID], 2)])
def test_presence_errors_abort_without_advancing_board(monkeypatch, code, prefix, expected_images):
    events, output, aborted = execute(monkeypatch, prefix+[code])
    assert aborted
    assert sum(e[0] == 'image' for e in events) == expected_images
    assert 'target disconnected' not in output
    assert output[-1] == 'auto download aborted'


@pytest.mark.parametrize('ids,message,images,beeps', [
    ([0]*20, 'target connection timeout', 0, 0),
    ([ID]+[0]*20, 'target connection timeout after programming', 2, 0),
    ([ID]*20, 'board replacement timeout: waiting for target removal', 2, 1),
])
def test_timeouts_do_not_reprogram_a_board(monkeypatch, ids, message, images, beeps):
    events, output, aborted = execute(monkeypatch, ids)
    assert aborted and message in output
    assert sum(e[0] == 'image' for e in events) == images
    assert events.count(('beep_on',)) == beeps


@pytest.mark.parametrize('supported', [0, -12, 4294967295])
def test_unsupported_probe_stops_before_target_or_image_access(monkeypatch, supported):
    events, output, aborted = execute(monkeypatch, [], supported=supported)
    assert aborted
    assert not any(e[0] in ('presence', 'image', 'beep_on', 'board') for e in events)
    assert any('Upgrade HPMLink' in line for line in output)


def test_failed_image_does_not_beep_or_wait_for_replacement(monkeypatch):
    events, output, aborted = execute(monkeypatch, [ID], fail_image=2)
    assert aborted and events.count(('beep_on',)) == 0
    assert 'waiting for target removal' not in output

"""Named presentation presets: atomic updates, isolation and no implicit default change."""
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

from mklink.frontend_layout import load_layout, search_layouts, load_named_layout, save_named_layout
from mklink.watch_preferences import PreferencesConflict


def preset(name='电机 RTT', revision=0):
    return {'name': name, 'revision': revision, 'layout': {'version': 2, 'revision': 7, 'panels': [], 'docks': []}}


def test_search_roundtrip_unicode_names_and_project_isolation(tmp_path):
    result = save_named_layout(tmp_path, preset(' 电机 RTT '))
    assert result['name'] == '电机 RTT' and result['revision'] == 1
    assert search_layouts(tmp_path, 'rtt')['layouts'] == [result]
    assert search_layouts(tmp_path, '电机')['layouts'] == [result]
    assert search_layouts(tmp_path, 'missing')['layouts'] == []
    assert search_layouts(tmp_path / 'other')['layouts'] == []
    assert load_named_layout(tmp_path, '电机 rtt')['layout'] == preset()['layout']
    assert load_layout(tmp_path)['revision'] == 0
    with pytest.raises(HTTPException) as missing:
        load_named_layout(tmp_path, 'absent')
    assert missing.value.status_code == 404


def test_duplicate_names_and_concurrent_updates_require_observed_revision(tmp_path):
    save_named_layout(tmp_path, preset())
    with pytest.raises(PreferencesConflict):
        save_named_layout(tmp_path, preset('电机 rtt'))
    def update(_):
        try:
            return save_named_layout(tmp_path, preset(revision=1))['revision']
        except PreferencesConflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(update, range(4)))
    assert results.count(2) == 1 and results.count('conflict') == 3
    assert load_named_layout(tmp_path, '电机 RTT')['revision'] == 2


@pytest.mark.parametrize('patch', [{'name': ''}, {'name': ' '}, {'name': 'x' * 81}, {'name': 'x\ny'}, {'revision': True}, {'layout': {}}, {'extra': 1}])
def test_invalid_presets_never_write(tmp_path, patch):
    with pytest.raises(HTTPException):
        save_named_layout(tmp_path, {**preset(), **patch})
    assert not (tmp_path / '.mklink').exists()


def test_commit_failure_and_target_guard_keep_old_layout(tmp_path, monkeypatch):
    saved = save_named_layout(tmp_path, preset())
    def fail(*args):
        raise OSError('injected failure')
    with pytest.raises(OSError):
        save_named_layout(tmp_path, preset(revision=1), before_commit=fail)
    monkeypatch.setattr('mklink.frontend_layout.os.replace', fail)
    with pytest.raises(OSError):
        save_named_layout(tmp_path, preset(revision=1))
    assert search_layouts(tmp_path)['layouts'] == [saved]
    assert not list((tmp_path / '.mklink').glob('*.tmp'))


def test_full_library_still_allows_updates(tmp_path):
    for number in range(64):
        save_named_layout(tmp_path, preset(str(number)))
    with pytest.raises(HTTPException, match='full'):
        save_named_layout(tmp_path, preset('65'))
    assert save_named_layout(tmp_path, preset('0', 1))['revision'] == 2
    assert len(search_layouts(tmp_path)['layouts']) == 64


def test_global_templates_are_shared_and_builtins_are_readonly(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    monkeypatch.setattr(Path, 'home', lambda: home)
    root = tmp_path / 'project'
    assert search_layouts(root)['layouts'] == []
    builtin = search_layouts(root, scope='global')
    assert len(builtin['layouts']) == 3 and all(item['builtin'] for item in builtin['layouts'])
    assert not home.exists()
    for entry in builtin['layouts']:
        template = load_named_layout(root, entry['name'], 'global')
        assert len(template['layout']['panels']) >= 3
        with pytest.raises(HTTPException, match='read-only'):
            save_named_layout(root, {**preset(entry['name']), 'scope': 'global'})
    save_named_layout(root, {**preset('Shared'), 'scope': 'global'})
    assert load_named_layout(tmp_path / 'second', 'Shared', 'global')['revision'] == 1
    assert search_layouts(root)['layouts'] == []
    assert (home / '.mklink/frontend_layouts.json').is_file()
    assert search_layouts(home)['layouts'] == []
    private = save_named_layout(home, preset('Shared'))
    assert private['revision'] == 1
    assert search_layouts(home)['location'] != search_layouts(home, scope='global')['location']
    with pytest.raises(HTTPException):
        search_layouts(root, scope='../outside')


@pytest.mark.parametrize('kind', ['named', 'current'])
def test_separate_runtime_processes_cannot_overwrite_the_same_revision(tmp_path, kind):
    from mklink.frontend_layout import save_layout
    save_named_layout(tmp_path, preset('shared'))
    save_layout(tmp_path, {'version': 1, 'revision': 0, 'panels': []})
    code = """
import sys, time
from pathlib import Path
from mklink.frontend_layout import save_layout, save_named_layout
from mklink.watch_preferences import PreferencesConflict
root = Path(sys.argv[1])
layout = {'version':1,'revision':1,'panels':[]}
def delay_commit():
    time.sleep(0.15)
try:
    if sys.argv[2] == 'current':
        save_layout(root, layout, before_commit=delay_commit)
    else:
        save_named_layout(root, {'name':'shared','revision':1,'layout':layout}, before_commit=delay_commit)
    print('saved')
except PreferencesConflict:
    print('conflict')
"""
    processes = [subprocess.Popen([sys.executable, '-c', code, str(tmp_path), kind], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
    output = [process.communicate(timeout=15) for process in processes]
    assert all(process.returncode == 0 for process in processes), output
    assert [result[0].strip() for result in output].count('saved') == 1
    assert [result[0].strip() for result in output].count('conflict') == 3

from pathlib import Path
import sys

import pytest

from mklink.work_files import capture_directory


@pytest.fixture
def skill(tmp_path):
    root = tmp_path / 'installed skill'
    (root / 'mklink').mkdir(parents=True)
    (root / 'SKILL.md').touch()
    (root / 'mklink/__init__.py').touch()
    return root


def test_project_log_path_is_preserved_without_creation(tmp_path):
    output = tmp_path / 'user project/.mklink/logs'
    assert capture_directory(output) == output.resolve()
    assert not output.exists()


def test_skill_install_and_directory_alias_are_rejected(skill, tmp_path):
    with pytest.raises(ValueError, match='project .mklink/logs'):
        capture_directory(skill / 'logs')
    alias = tmp_path / 'alias'
    try:
        alias.symlink_to(skill, target_is_directory=True)
    except OSError:
        pytest.skip('directory symlinks unavailable')
    with pytest.raises(ValueError):
        capture_directory(alias / 'logs')
    assert not (skill / 'logs').exists()


def test_frozen_application_install_is_rejected(monkeypatch, tmp_path):
    root = tmp_path / 'desktop'
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(root/'mklink-sidecar.exe'))
    with pytest.raises(ValueError):
        capture_directory(root / 'logs')


def test_conversion_does_not_add_files_to_an_old_installation_capture(skill):
    from mklink.recording_text import ManualExport
    source = skill / 'rtt-previous-0001.jsonl'
    source.write_text('old original capture', encoding='utf-8')
    export = ManualExport('rtt')
    export.start(dict(state='completed', active=False, path=str(source), parts=1, started_at=0))
    status = export.status()
    assert status['export_state'] == 'failed' and 'Skill' in status['export_error']
    assert source.read_text(encoding='utf-8') == 'old original capture'
    assert not list(skill.glob('*-export.json')) and not list(skill.glob('*.txt'))


@pytest.mark.parametrize('kind', ['rtt', 'superwatch', 'systemview', 'serial'])
def test_recorders_do_not_create_or_truncate_installation_logs(skill, kind):
    before = sorted(str(p.relative_to(skill)) for p in skill.rglob('*'))
    with pytest.raises(ValueError, match='Skill'):
        if kind == 'rtt':
            from mklink.traffic_recording import TrafficRecorder
            TrafficRecorder(skill, 'rtt')
        elif kind == 'superwatch':
            from mklink.superwatch_recording import SuperWatchRecorder
            SuperWatchRecorder(skill)
        elif kind == 'systemview':
            from mklink.systemview_logger import SystemViewJsonlLogger
            SystemViewJsonlLogger(str(skill), {})
        else:
            from mklink.serial._logger import FileLogger
            FileLogger(str(skill/'serial.txt')).start()
    assert sorted(str(p.relative_to(skill)) for p in skill.rglob('*')) == before

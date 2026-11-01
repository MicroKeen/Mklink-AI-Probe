from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink.flash import MKLinkFlash
from mklink.online_files import cleanup_firmware


@pytest.fixture
def staged(tmp_path, monkeypatch):
    disk = tmp_path / 'disk'
    disk.mkdir()
    source = tmp_path / 'demo.bin'
    source.write_bytes(b'image')
    original = disk / 'demo.bin'
    original.write_bytes(b'user offline image')
    flash = MKLinkFlash(SimpleNamespace(_leave_multiplex=Mock()))
    monkeypatch.setattr('mklink.flash.find_microkeen_disk', lambda: str(disk))
    monkeypatch.setattr('mklink.discovery.find_microkeen_disk', lambda: str(disk))
    name = flash._copy_to_microkeen(str(source))
    assert name and name != source.name
    return flash, disk, source, original, name


def test_only_successful_owned_copy_removed_after_idle_mux_exit(staged):
    flash, disk, source, original, name = staged
    failed = flash._copy_to_microkeen(str(source))
    flash._bridge._leave_multiplex.side_effect = lambda: (
        (disk / name).read_bytes() == b'image' or pytest.fail('deleted before MUX exit'))
    result = cleanup_firmware(flash, {'success': True, 'filename': name})
    assert result == {'deleted': [name], 'retained': [], 'errors': []}
    assert not (disk / name).exists()
    assert (disk / failed).exists()  # A previous task's copy is never swept.
    assert source.read_bytes() == b'image'
    assert original.read_bytes() == b'user offline image'


@pytest.mark.parametrize('success', [False, None, 'unknown'])
def test_failed_or_unknown_result_retains_copy(staged, success):
    flash, disk, _, _, name = staged
    assert not cleanup_firmware(flash, {'success': success, 'filename': name})['deleted']
    assert (disk / name).exists()
    flash._bridge._leave_multiplex.assert_not_called()


@pytest.mark.parametrize('reason', ['changed', 'volume', 'mux', 'unlink'])
def test_uncertain_cleanup_retains_and_reports_without_replaying(staged, monkeypatch, tmp_path, reason):
    flash, disk, _, original, name = staged
    if reason == 'changed':
        (disk / name).write_bytes(b'other')
    elif reason == 'volume':
        monkeypatch.setattr('mklink.discovery.find_microkeen_disk', lambda: str(tmp_path))
    elif reason == 'mux':
        flash._bridge._leave_multiplex.side_effect = TimeoutError('exit unknown')
    else:
        monkeypatch.setattr(Path, 'unlink', Mock(side_effect=PermissionError('busy')))
    result = cleanup_firmware(flash, {'success': True, 'filename': name})
    assert result['retained'] == [name] and result['errors'] and not result['deleted']
    assert (disk / name).exists() and original.read_bytes() == b'user offline image'


def test_explicit_existing_filename_is_not_owned(staged):
    flash, disk, _, original, _ = staged
    # Same source/destination is supported without deleting the user's input.
    name = flash._copy_to_microkeen(str(original), original.name)
    result = cleanup_firmware(flash, {'success': True, 'filename': name})
    assert result['deleted'] == []
    assert original.read_bytes() == b'user offline image'


def test_multiple_regions_only_clean_their_owned_files(staged):
    flash, disk, source, _, first = staged
    second = flash._copy_to_microkeen(str(source))
    result = cleanup_firmware(flash, {'success': True, 'regions': [
        {'filename': first}, {'filename': second}, {'filename': '../outside.bin'}]})
    assert result['deleted'] == [first, second]
    assert not result['errors']


def test_collision_does_not_overwrite_existing_file(staged, monkeypatch):
    flash, disk, source, _, name = staged
    monkeypatch.setattr('mklink.online_files.uuid.uuid4', lambda: SimpleNamespace(hex=name[14:-4]))
    assert flash._copy_to_microkeen(str(source)) is None
    assert (disk / name).read_bytes() == b'image'

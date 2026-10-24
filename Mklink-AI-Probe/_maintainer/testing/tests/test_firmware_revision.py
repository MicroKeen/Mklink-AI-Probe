"""Same-version repairs require package integrity and installed build identity."""
from dataclasses import replace
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from mklink import firmware_check as fc


def uf2(payload=b'new repair'):
    block = bytearray(512)
    for start, number in [(0, 0x0A324655), (4, 0x9E5D5157), (16, len(payload)),
                          (24, 1), (508, 0x0AB16F30)]:
        block[start:start+4] = number.to_bytes(4, 'little')
    block[32:32+len(payload)] = payload
    return bytes(block)


def readme(root, stamp='Oct 24 2026 23:23:05', family='microlink', version='V4.7.0'):
    prefix = 'HPM ' if family == 'hpmlink' else ''
    (root/'readme.txt').write_text(f'{prefix}Firmware Build Date:{stamp}\n{version}\n', encoding='utf-8')


@pytest.fixture
def repair(monkeypatch, tmp_path):
    disk = tmp_path/'application'; disk.mkdir()
    boot = tmp_path/'boot'; boot.mkdir()
    image = tmp_path/'MicroLink_V4.7.0.uf2'; image.write_bytes(uf2())
    info = fc.parse_firmware_filename(image)
    info.build_id = '2026-10-24T23:23:05'
    info.size = image.stat().st_size
    info.sha256 = hashlib.sha256(image.read_bytes()).hexdigest()
    monkeypatch.setattr(fc, 'latest_firmware', lambda *a, **kw: info)
    monkeypatch.setattr(fc, '_remote_firmwares', lambda: [info])
    return disk, boot, info


@pytest.mark.parametrize('stamp,status', [('Oct 23 2026 12:00:00', 'upgrade_required'),
    ('unknown', 'revision_unknown'), ('Oct 24 2026 23:23:05', 'ok')])
def test_same_version_check_uses_build_identity(repair, stamp, status):
    disk, boot, info = repair
    readme(disk, stamp)
    result = fc.check_probe_firmware(None, boot, disk_reader=lambda: str(disk))
    assert result.status == status
    assert result.to_dict()['recommended_uf2']['sha256'] == info.sha256


@pytest.mark.parametrize('stamp', ['Oct 23 2026 12:00:00', 'unknown'])
def test_same_version_old_or_unknown_reinstalls_and_verifies(repair, stamp):
    disk, boot, info = repair
    readme(disk, stamp)
    entered = []
    def enter():
        entered.append(1)
        readme(disk)
    result = fc.upgrade_probe_firmware(SimpleNamespace(enter_bootloader=enter), boot,
        confirm=True, disk_reader=lambda: str(disk), bootloader_finder=lambda: str(boot), verify_timeout=.01)
    assert entered == [1] and result['status'] == 'updated'
    assert result['verified_build_id'] == info.build_id
    assert (boot/info.name).read_bytes() == info.path.read_bytes()


@pytest.mark.parametrize('stamp,version,status', [('Oct 24 2026 23:23:05','V4.7.0','up_to_date'),
    ('Oct 25 2026 12:00:00','V4.7.0','downgrade_blocked'), ('unknown','V4.8.0','downgrade_blocked')])
def test_matching_build_or_newer_device_never_writes(repair, stamp, version, status):
    disk, boot, _ = repair
    readme(disk, stamp, version=version)
    device = SimpleNamespace(enter_bootloader=lambda: pytest.fail('unexpected reboot'))
    assert fc.upgrade_probe_firmware(device, boot, confirm=True, disk_reader=lambda: str(disk))['status'] == status


@pytest.mark.parametrize('identity', ['old_build', 'unknown_build', 'wrong_product', 'newer_version'])
def test_copy_does_not_prove_installed_repair(repair, identity):
    disk, boot, info = repair
    readme(disk, 'Oct 23 2026 12:00:00')
    def enter():
        if identity == 'unknown_build': readme(disk, 'unknown')
        if identity == 'wrong_product': readme(disk, family='hpmlink')
        if identity == 'newer_version': readme(disk, version='V4.7.1')
    result = fc.upgrade_probe_firmware(SimpleNamespace(enter_bootloader=enter), boot,
        confirm=True, disk_reader=lambda: str(disk), bootloader_finder=lambda: str(boot), verify_timeout=.01)
    assert result['status'] == 'copied_unverified'


def test_corrupt_same_name_cache_is_rejected_before_reboot(repair):
    disk, boot, info = repair
    readme(disk, 'unknown')
    info.path.write_bytes(uf2(b'old repair'))
    result = fc.upgrade_probe_firmware(SimpleNamespace(enter_bootloader=lambda: pytest.fail('rebooted')),
        boot, confirm=True, disk_reader=lambda: str(disk))
    assert result['status'] == 'manual_required' and 'SHA-256' in result['message']


def test_newer_same_version_mirror_wins_and_bad_download_falls_back(monkeypatch, repair):
    _, _, info = repair
    newer = replace(info, download_urls={'tencent':'https://cos.test/new.uf2', 'github':'https://github.test/new.uf2'},
                    download_source='tencent', download_url='https://cos.test/new.uf2')
    old = replace(newer, build_id='2026-10-23T12:00:00')
    monkeypatch.undo()
    monkeypatch.setattr(fc, 'bundled_firmwares', lambda: [])
    monkeypatch.setattr(fc, '_remote_firmwares_from_source', lambda source, **kw: [old] if source == 'tencent' else [newer])
    selected = fc._remote_firmware('V4')
    assert selected.build_id == newer.build_id
    selected.download_source = 'tencent'; selected.download_url = newer.download_urls['tencent']
    requested = []
    def get(request, timeout):
        requested.append(request.full_url)
        return io.BytesIO(uf2(b'old content') if 'cos.test' in request.full_url else info.path.read_bytes())
    monkeypatch.setattr(fc, 'urlopen', get)
    path, owned, source = fc._materialize_firmware(selected)
    try:
        assert owned and source == 'github' and len(requested) == 2
        assert hashlib.sha256(path.read_bytes()).hexdigest() == info.sha256
    finally:
        path.unlink()


def test_packaged_catalog_pins_all_four_delivery_products():
    entries = fc.bundled_firmwares()
    assert {(i.family,i.model,i.version_str) for i in entries} == {
        ('microlink','V2','V2.9.1'),('microlink','V3','V3.6.6'),
        ('microlink','V4','V4.7.0'),('hpmlink','V4','V4.7.0')}
    assert all(i.sha256 and i.size and i.build_id and 'github' in i.download_urls for i in entries)

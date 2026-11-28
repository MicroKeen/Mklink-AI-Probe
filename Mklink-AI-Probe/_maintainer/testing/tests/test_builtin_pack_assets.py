import hashlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[3]


def load_script(relative):
    spec = importlib.util.spec_from_file_location('pack_test_module', ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def assets():
    return load_script('skills/tauri-gui-builder/scripts/builtin_pack_assets.py')


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / 'bundle'
    root.mkdir()
    pack = root / 'vendor.pack'
    with ZipFile(pack, 'w') as archive:
        archive.writestr('Vendor.pdsc', '<package><vendor>Vendor</vendor><name>DFP</name>'
                        '<devices><family><device Dname="STM32F407VETx">'
                        '<debug svd="SVD/chip.svd"/></device></family></devices></package>')
        archive.writestr('SVD/chip.svd', '<device/>')
    manifest = {'schema': 1, 'packs': [{'pack_id': 'Vendor.DFP', 'version': '1.0',
        'file': pack.name, 'sha256': hashlib.sha256(pack.read_bytes()).hexdigest(),
        'targets': [{'part_number': 'STM32F407VETx', 'vendor': 'Vendor'}]}]}
    (root / 'manifest.json').write_text(json.dumps(manifest))
    return root


def test_pack_payload_is_required_and_verified(assets, bundle, monkeypatch, tmp_path):
    monkeypatch.delenv('MKLINK_BUILTIN_PACK_BUNDLE', raising=False)
    monkeypatch.delenv('MKLINK_BUILTIN_PACK_ROOTS', raising=False)
    with pytest.raises(RuntimeError, match='SVD Packs are required'):
        assets.prepare_bundle(tmp_path)
    monkeypatch.setenv('MKLINK_BUILTIN_PACK_BUNDLE', str(bundle))
    assert assets.prepare_bundle(tmp_path) == bundle
    assert assets.validate_bundle(bundle)['svd_target_count'] == 1
    (bundle / 'vendor.pack').write_bytes(b'changed')
    with pytest.raises(ValueError, match='integrity'):
        assets.validate_bundle(bundle)


def test_pack_payload_rejects_descriptor_only_svd(assets, bundle):
    path = bundle / 'vendor.pack'
    with ZipFile(path) as original:
        descriptor = original.read('Vendor.pdsc')
    with ZipFile(path, 'w') as archive:
        archive.writestr('Vendor.pdsc', descriptor)
    manifest_path = bundle / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['packs'][0]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='missing SVD'):
        assets.validate_bundle(bundle)


def test_skill_archive_contains_the_same_verified_pack_payload(assets, bundle, monkeypatch, tmp_path):
    release = load_script('_maintainer/release/prepare_release.py')
    monkeypatch.setattr(release, '_builtin_pack_assets', lambda: assets)
    monkeypatch.setenv('MKLINK_BUILTIN_PACK_BUNDLE', str(bundle))
    output = tmp_path / 'skill.zip'
    with ZipFile(output, 'w'):
        pass
    release._append_builtin_pack_assets(output, 'Skill')
    with ZipFile(output) as archive:
        assert archive.read('Skill/mklink/builtin_packs/vendor.pack') == (bundle / 'vendor.pack').read_bytes()
        assert 'Skill/mklink/builtin_packs/manifest.json' in archive.namelist()

def test_windows_compaction_preserves_every_member_and_excludes_unlisted_packs(assets, bundle, tmp_path):
    from zipfile import ZIP_LZMA

    (bundle / 'unused.pack').write_bytes(b'unlisted')
    manifest = assets.validate_bundle(bundle)
    original = (bundle / 'vendor.pack').read_bytes()
    out = tmp_path / 'staged'
    assets.stage_windows_packs(bundle, out, manifest)
    assert assets.validate_bundle(out)['svd_target_count'] == 1
    assert (bundle / 'vendor.pack').read_bytes() == original
    assert {p.name for p in out.iterdir()} == {'manifest.json', 'vendor.pack'}
    with ZipFile(bundle / 'vendor.pack') as before, ZipFile(out / 'vendor.pack') as after:
        assert after.namelist() == before.namelist()
        for name in before.namelist():
            assert after.read(name) == before.read(name)
        assert after.getinfo('SVD/chip.svd').compress_type == ZIP_LZMA
        assert after.getinfo('Vendor.pdsc').compress_type == before.getinfo('Vendor.pdsc').compress_type


def test_pyocd_xml_named_svd_is_losslessly_compressed(assets, tmp_path):
    from zipfile import ZIP_LZMA

    original = tmp_path / 'pyocd.zip'
    compact = tmp_path / 'compact.zip'
    with ZipFile(original, 'w') as archive:
        archive.writestr('LPC54114_cm4.xml', b'<device/>')
    assets.compress_svd_members(original, compact)
    with ZipFile(compact) as archive:
        assert archive.getinfo('LPC54114_cm4.xml').compress_type == ZIP_LZMA
        assert archive.read('LPC54114_cm4.xml') == b'<device/>'

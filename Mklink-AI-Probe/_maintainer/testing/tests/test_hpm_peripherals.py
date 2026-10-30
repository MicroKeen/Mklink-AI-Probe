"""Vendor XML payloads and series selection shared by CLI, MCP and SuperWatch."""
import asyncio
from dataclasses import replace
import io
from pathlib import Path
import subprocess
from zipfile import ZipFile

import pytest

from mklink import peripheral_watch as pw
from mklink.remote.api import create_app
from route_utils import find_route
from test_peripheral_watch import SVD


SERIES = ('HPM5100', 'HPM5300', 'HPM5E00', 'HPM6200', 'HPM6300',
          'HPM6700', 'HPM6800', 'HPM6E00', 'HPM6P00')


@pytest.mark.parametrize('series', SERIES)
def test_bundled_vendor_xml_is_intact_and_parses_without_sdk(series):
    targets = pw.builtin_hpm_targets()
    assert tuple(t.target for t in targets) == SERIES
    target = next(t for t in targets if t.series == series)
    catalog = pw.load_catalog(target=target)  # read() verifies the vendor digest
    assert catalog.selection['series'] == series
    assert catalog.selection['pack'] == 'HPMicro.SDK@1.13.0'
    assert len(catalog.items) > 20000
    assert catalog.resolve('UART0.GPR').size == 4
    assert catalog.resolve('UART0.GPR.DATA').metadata['writable'] is False
    assert 'UART0.THR' not in catalog.items  # write-only
    assert 'UART0.RBR' not in catalog.items  # FIFO pop


@pytest.mark.parametrize('chip,series', [
    ('hpm5151', 'HPM5100'), ('HPM5300', 'HPM5300'), ('HPM5301', 'HPM5300'),
    ('HPM5361', 'HPM5300'), ('HPM53M1', 'HPM5300'), ('HPM5301CAV', 'HPM5300'),
    ('HPM5E31', 'HPM5E00'), ('HPM5E3Y', 'HPM5E00'), ('HPM6280', 'HPM6200'),
    ('HPM6360', 'HPM6300'), ('HPM6750', 'HPM6700'), ('HPM6880', 'HPM6800'),
    ('HPM6E80', 'HPM6E00'), ('HPM6P81', 'HPM6P00'),
    ('HPM9901', None), ('STM32H743', None), ('HPM53', None), ('XHPM5301', None),
])
def test_model_and_package_suffix_match_only_their_series(chip, series):
    matches = [t.series for t in pw.builtin_hpm_targets() if t.matches_chip(chip)]
    assert matches == ([series] if series else [])


def test_cached_web_index_and_offline_index_use_series_matching(tmp_path, monkeypatch):
    targets = pw.builtin_hpm_targets()
    monkeypatch.setattr(pw, 'discover_svd_targets', lambda root: targets)
    endpoint = find_route(create_app(project_root=str(tmp_path)),
                          '/api/dash/superwatch/peripherals/targets').endpoint

    async def verify():
        for query in ('HPM', 'hpm53m1', 'HPM536', 'HPM5E3Y', 'HPM6P81', 'unknown'):
            assert (await endpoint(q=query))['targets'] == pw.list_svd_targets(str(tmp_path), query)['targets']
        assert len((await endpoint(q='HPM'))['targets']) == 9
        assert (await endpoint(q='HPM5361'))['targets'][0]['target'] == 'HPM5300'
    asyncio.run(verify())


def test_series_selection_restore_exact_pack_priority_and_ambiguity(tmp_path, monkeypatch):
    # Tiny fixture isolates selection behavior from the separately tested SDK payloads.
    (tmp_path / 'chip.xml').write_bytes(SVD)
    family = pw.SvdTarget('HPM5300', 'SDK@1', tmp_path / 'manifest.json',
                          'chip.xml', series='HPM5300')
    targets = [family]
    monkeypatch.setattr(pw, 'discover_svd_targets', lambda root: targets)
    catalog = pw.load_catalog(tmp_path, chip='HPM53M1')
    assert catalog.selection['id'] == family.key
    pw.save_catalog_selection(tmp_path, catalog)
    assert pw.load_catalog(tmp_path).selection == catalog.selection
    exact = replace(family, target='HPM53M1', pack='Exact.DFP@1', series='')
    targets.append(exact)
    assert pw.load_catalog(tmp_path, chip='HPM53M1').selection['id'] == exact.key
    targets.append(replace(exact, pack='Exact.DFP@2'))
    with pytest.raises(ValueError, match='multiple Packs'):
        pw.load_catalog(tmp_path, chip='HPM53M1')
    with pytest.raises(ValueError):
        pw.load_catalog(tmp_path, chip='HPM9901')
    assert pw.load_catalog(tmp_path, target_id=family.key).selection['series'] == 'HPM5300'


def test_modified_vendor_xml_is_rejected_before_parsing(tmp_path):
    target = pw.builtin_hpm_targets()[0]
    (tmp_path / target.svd).write_bytes(target.read() + b'\n')
    with pytest.raises(ValueError, match='integrity'):
        pw.load_catalog(target=replace(target, source=tmp_path / 'manifest.json'))


def test_subtree_skill_archive_preserves_vendor_bytes_with_windows_autocrlf(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', '-c', 'core.autocrlf=true', '-c', 'user.name=Test',
            '-c', 'user.email=test@example.invalid', *args], cwd=tmp_path)
    git('init', '-q')
    source = tmp_path / 'project'
    assets = source / 'mklink/hpm_svd'
    assets.mkdir(parents=True)
    (source / '.gitattributes').write_bytes((Path(pw.__file__).parents[1] / '.gitattributes').read_bytes())
    original = b'<device>\n<name>Vendor</name>\n</device>\n'
    (assets / 'test.xml').write_bytes(original)
    git('add', '.')
    git('commit', '-qm', 'fixture')
    with ZipFile(io.BytesIO(git('archive', '--format=zip', 'HEAD:project', '--', 'mklink'))) as archive:
        assert archive.read('mklink/hpm_svd/test.xml') == original

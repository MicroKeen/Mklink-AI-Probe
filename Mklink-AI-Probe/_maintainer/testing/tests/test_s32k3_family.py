"""Public family catalog, exclusive programming limits and exact Pack target selection."""

import os
import struct
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile

import pytest

from mklink import profiles
from mklink.cmsis_dap import s32k3_flm
from mklink.cmsis_dap.errors import FlashError
from mklink.cmsis_dap.models import TargetRecord
from mklink.cmsis_dap.pack_catalog import PackCatalog
from mklink.cmsis_dap.pack_session import create_profile_pack_session
from mklink.cmsis_dap.paths import PackPaths
from mklink.cmsis_dap.profile_reset import system_reset_handler
from mklink.mux import encode_attach_profile
from mklink.remote.online_flash_api import _job_flash_algorithms, default_target_memory_provider
from mklink.s32k3 import flash_workspace


# From the enumerations in S32K3XXRM table MIDR1 and S32K396RM p208.
EXPECTED = {
    310: 0x2D36, 311: 0x2D37, 312: 0x2D38, 314: 0x2D3A, 322: 0x2D42,
    324: 0x2D44, 328: 0x2D48, 338: 0x2D52, 341: 0x2D55, 342: 0x2D56,
    344: 0x2D58, 348: 0x2D5C, 356: 0x2D64, 358: 0x2D66, 364: 0x2D6C,
    366: 0x2D6E, 374: 0x2D76, 376: 0x2D78, 388: 0x2D84, 389: 0x2D85,
    394: 0x2D8A, 396: 0x2D8C,
}


@pytest.mark.parametrize("number,midr", EXPECTED.items())
def test_primary_core_recipe(number, midr):
    part = f"S32K{number}"
    profile = profiles.resolve_attach_profile(part)
    wire = encode_attach_profile(profile)
    assert wire[:4] == bytes((1, 4, 8, 0))
    steps = list(struct.iter_unpack("<BBHIII", wire[4:]))
    assert [s[1] for s in steps] == [4, 6, 7, 7, 6, 7, 4, 4]
    assert steps[-1] == (3, 4, 0, 0x40290004, 0xFFFF0000, midr << 16)
    assert steps[-2] == (3, 4, 0, 0xE000ED00, 0xFF0FFFF0, 0x410FC270)


def test_exact_models_are_discoverable_without_a_pack_or_hardware(tmp_path, monkeypatch):
    from mklink.cmsis_dap import builtin_flm_bundle, builtin_pack_bundle
    monkeypatch.setattr(builtin_flm_bundle, "load_builtin_flm_targets", lambda: [])
    monkeypatch.setattr(builtin_pack_bundle, "load_builtin_pack_records", lambda: [])
    catalog = PackCatalog(PackPaths(tmp_path))
    online = catalog.search("S32K3", installed=True)
    family = {f"S32K{n}" for n in EXPECTED}
    assert {r.part_number for r in online if r.source == "target-profile"} == family
    rows = profiles.target_profile_catalog()["profiles"]
    assert {r["name"] for r in rows if r.get("mem_ap") == 4 and r["name"].startswith("S32K3")} == family
    target = TargetRecord("S32K396", "NXP", installed=True, source="target-profile")
    assert default_target_memory_provider(target.part_number, catalog._paths) == ()
    body = SimpleNamespace(actions=["connect", "erase", "disconnect"])
    with pytest.raises(FlashError, match="matching vendor Pack or FLM"):
        _job_flash_algorithms(target, body, None, [])
    body.actions = ["connect", "reset", "disconnect"]
    assert _job_flash_algorithms(target, body, None, []) == []


@pytest.mark.parametrize("number", EXPECTED)
def test_routed_reset_and_sram_bound(number):
    part = f"S32K{number}"
    profile = profiles.resolve_attach_profile(part)
    dp = Mock()
    dp.read_ap.side_effect = [0x001C0030, 0x00400900]
    evidence = {}
    prepare = system_reset_handler(profile.online_system_reset, part, 4)
    name, run = prepare(dp, evidence, profile)
    assert name == part + ".FunctionalReset"
    run()
    expected = ([0x00400B00, 0x00400B20, 0x00400B00, 0x00400000] if number in {312, 314, 324, 344}
                else [0x00400920, 0x00400900])
    assert [c.args for c in dp.write_ap.call_args_list] == [(0x06000004, v) for v in expected]
    assert dp.flush.call_count == len(expected)
    assert flash_workspace(part) == (0x20400000, {310: 0x4000, 311: 0x8000}.get(number, 0x10000))


def test_s32k322_requires_the_identified_x2_vendor_blobs():
    x2 = s32k3_flm.layout("S32K322")
    assert x2.code_end == 0x005E0000
    rows = [{"part_number": "S32K342", "algorithms": [{"sha256": x2.code_sha}]}]
    s32k3_flm.extend_builtin_catalog(rows)
    assert len(rows) == 1
    rows[0]["algorithms"].append({"sha256": x2.data_sha})
    s32k3_flm.extend_builtin_catalog(rows)
    assert rows[-1]["part_number"] == "S32K322"
    assert rows[-1]["ram_size"] == 0x10000
    assert s32k3_flm.layout("S32K396") is None


@pytest.mark.parametrize("part,digest", [("S32K396", s32k3_flm.CODE_SHA256),
                                       ("S32K342", s32k3_flm.DATA_SHA256),
                                       ("S32K344", s32k3_flm.X2_CODE_SHA256)])
def test_no_cross_geometry_use_of_identified_vendor_loaders(part, digest):
    from mklink.cmsis_dap.flash_bounds import check_flm_model
    with pytest.raises(FlashError, match="does not match"):
        check_flm_model(part, digest)


def test_selected_pack_wins_over_pyocd_same_name_before_probe_open(tmp_path):
    from pyocd.target import TARGET
    path = tmp_path / "Test.S32K.pack"
    pdsc = """<package schemaVersion="1.7.0"><vendor>Test</vendor><name>S32K</name>
    <releases><release version="1.0.0">Test</release></releases>
    <devices><family Dfamily="S32K" Dvendor="NXP:11"><processor Dcore="Cortex-M7" Dendian="Little-endian"/>
    <device Dname="S32K344"><memory name="ChosenPackRAM" start="0x20400000" size="0x10000" access="rwx"/>
    </device></family></devices></package>"""
    with ZipFile(path, "w") as archive:
        archive.writestr("Test.S32K.pdsc", pdsc)
    builtin_class = TARGET["s32k344"]
    probe = Mock(unique_id="fixture")
    probe.create_associated_board.return_value = None
    options = dict(target_override="S32K344", pack=str(path), no_config=True,
                   project_dir=os.getcwd(), user_script=os.devnull)
    session = create_profile_pack_session(probe, options)
    try:
        assert session.target._pack_device.part_number == "S32K344"
        assert any(region.name == "ChosenPackRAM" for region in session.target.memory_map)
        assert not isinstance(session.target, builtin_class)
        assert TARGET["s32k344"] is builtin_class
        assert session.board.target_type not in TARGET
        probe.open.assert_not_called()
    finally:
        session.close()
    with pytest.raises(FlashError, match="exactly one device"):
        create_profile_pack_session(probe, dict(options, target_override="S32K396"))
    probe.open.assert_not_called()


def test_job_honors_explicit_algorithm_pack_and_builtin_source():
    from mklink.remote.online_flash_api import _profile_job_pack
    target = TargetRecord("S32K344", "NXP", installed=True, source="index", pack_path="old.pack")
    old = SimpleNamespace(pack_path="old.pack", source_kind="installed-pack")
    new = SimpleNamespace(pack_path="new.pack", source_kind="installed-pack")
    builtin = SimpleNamespace(pack_path=None, source_kind="daplink-builtin")
    assert _profile_job_pack(target, [new]) == "new.pack"
    assert _profile_job_pack(target, [builtin]) is None
    assert _profile_job_pack(target, []) == "old.pack"
    with pytest.raises(FlashError, match="one device Pack"):
        _profile_job_pack(target, [old, new])

"""Catalog, CLI discovery and refusal at the shared-client boundary."""
import json
import struct
import sys

import pytest

from mklink import cli, profiles, runtime
from mklink.device import Device
from mklink.mux import encode_attach_profile


def test_s32k314_compiles_exact_firmware_recipe_in_lifecycle_order():
    model = profiles.load_mcu_profiles()["s32k314"]
    recipe = model["mux_attach"]
    recipe["hooks"] = dict(reversed(list(recipe["hooks"].items())))
    recipe["hooks"]["BeforeResetTarget"] = []
    compiled = profiles.compile_attach_profile(model["name"], recipe)
    assert compiled.requires_reset_released
    wire = encode_attach_profile(compiled)
    assert wire[:4] == bytes((1, 4, 8, 0))
    assert list(struct.iter_unpack("<BBHIII", wire[4:])) == [
        (1, 4, 0, 0xfc, 0xffffffff, 0x84770001),
        (1, 6, 0, 0xfc, 0xffffffff, 0x001c0030),
        (1, 7, 0, 0xfc, 0xffffffff, 0x001c0040),
        (1, 7, 0, 0, 0x40000000, 0x40000000),
        (1, 6, 0, 0, 4, 0),
        (2, 7, 0, 0x80, 0x300000f0, 0x300000f0),
        (3, 4, 0, 0xe000ed00, 0xff0ffff0, 0x410fc270),
        (3, 4, 0, 0x40290004, 0xffff0000, 0x2d3a0000),
    ]
    assert profiles.resolve_attach_profile(" S32K314 ") == compiled
    assert profiles.resolve_attach_profile("stm32f1") is None
    assert profiles.resolve_attach_profile(None) is None


@pytest.mark.parametrize("hook,code", [
    ("BeforeResetTarget", "unsupported_hook"), ("UnknownHook", "unsupported_hook"),
    ("ConfigTargetSettings", "invalid_hook"), ("InitTarget", "invalid_hook"),
    ("SetupTarget", "invalid_hook"), ("version", "unsupported_profile_version"),
])
def test_invalid_declaration_precedes_any_hardware(monkeypatch, tmp_path, hook, code):
    models = profiles.load_mcu_profiles()
    recipe = models["s32k314"]["mux_attach"]
    hooks = recipe["hooks"]
    if hook == "version":
        recipe["version"] = 2
    elif hook == "InitTarget":
        hooks[hook] = hooks["SetupTarget"]
    else:
        hooks[hook] = hooks["InitTarget"]
    monkeypatch.setattr(profiles, "load_mcu_profiles", lambda: models)
    monkeypatch.setattr("mklink.transport_factory.create_bridge", lambda *_: pytest.fail("opened probe"))
    dev = Device(port="fake", mcu="s32k314", project_root=str(tmp_path))
    with pytest.raises(profiles.TargetProfileError) as error:
        dev._connect()
    assert error.value.detail["code"] == code
    if hook != "version":
        assert error.value.detail["hook"] == hook
    described = next(row for row in profiles.target_profile_catalog()["profiles"] if row["key"] == "s32k314")
    assert described["error"] == error.value.detail


def test_cli_lists_target_and_complete_hook_support_without_probe(monkeypatch, capsys):
    monkeypatch.setattr("mklink.probes.inventory", lambda: pytest.fail("enumerated hardware"))
    monkeypatch.setattr(sys, "argv", ["mklink", "target-profiles"])
    cli.main()
    catalog = json.loads(capsys.readouterr().out)
    supported = catalog["hook_support"]["supported"]
    reserved = catalog["hook_support"]["reserved"]
    assert supported == ["ConfigTargetSettings", "InitTarget", "SetupTarget"]
    assert len(set(supported + reserved)) == 44
    assert "BeforeResetTarget" in reserved and "StopNTRACEATB" in reserved
    assert {"key": "s32k314", "name": "S32K314", "mem_ap": 4, "hooks": supported} in catalog["profiles"]


@pytest.mark.parametrize("service_version,receipt,expected", [
    (None, None, "Shared backend"), (1, None, "not confirmed"),
    (1, {"profile": "S32K314", "mem_ap": 0}, "not confirmed"),
])
def test_unconfirmed_profile_cannot_reuse_old_client_session(monkeypatch, service_version, receipt, expected):
    paths = []
    def request(info, method, path, payload=None, **kwargs):
        paths.append(path)
        if path == "/_runtime/status":
            return {"target_attach_version": service_version}
        assert path == "/_runtime/attach"
        return {"session_id": "unconfirmed", "target_attach": receipt}
    monkeypatch.setattr(runtime, "request", request)
    client = runtime.RuntimeClient(info={"port": 8765})
    client.session_id = "previous"
    with pytest.raises(runtime.RuntimeErrorResponse, match=expected):
        client.connect(mcu="s32k314")
    assert client.session_id is None
    with pytest.raises(runtime.RuntimeErrorResponse):
        client.call("write_memory", {"address": "0x20000000", "data_hex": "01"})
    assert paths == (["/_runtime/status"] if service_version is None else ["/_runtime/status", "/_runtime/attach"])


@pytest.mark.parametrize("set_in_constructor", [True, False])
def test_explicit_project_model_cannot_attach_through_old_host(tmp_path, monkeypatch, set_in_constructor):
    from mklink.project_config import save_project_info
    save_project_info(str(tmp_path), {"device": "S32K314"})
    def status_only(info, method, path, **kwargs):
        assert (method, path) == ("GET", "/_runtime/status")
        return {}
    monkeypatch.setattr(runtime, "request", status_only)
    with pytest.raises(runtime.RuntimeErrorResponse, match="Shared backend"):
        options = {"project_root": str(tmp_path)}
        runtime.RuntimeClient(info={"port": 8765}, **(options if set_in_constructor else {})).connect(
            **({} if set_in_constructor else options)
        )

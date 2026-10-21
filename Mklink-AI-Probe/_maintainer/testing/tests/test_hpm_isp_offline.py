"""Host-side ISP contract checks; no real probe or target access."""
import json
import sys
from types import SimpleNamespace

import pytest

from mklink.hpm_isp import require_capability, script_metadata, trigger_result
from mklink.offline_download import (
    OfflineDownloadError, parse_offline_config, generate_offline_script, deploy_offline_bundle,
)


def payload():
    return {
        "model": "V4", "target_part": "HPM5301", "script_name": "isp-test.py",
        "programming_protocol": "hpm_rom_isp_uart",
        "hpm_isp": {"flash_size": "0x800000"},
        "algorithms": [],
        "firmwares": [{"id": "app", "file_name": "app.bin", "format": "bin",
                       "base_address": "0x80000400", "upload_index": 0}],
    }


@pytest.mark.parametrize("change", [
    {"model": "V3"}, {"model": "V2"}, {"target_part": "STM32F103RE"},
    {"board": "hpm5301evklite"}, {"hpm_flash_cfg": [1, 2, 3, 0xF3000000]},
    {"programming_protocol": "guess"}, {"erase_all_before_download": True},
    {"unlock_before_download": True}, {"lock_after_download": True},
])
def test_reject_inapplicable_protocol_configuration(change):
    data = payload()
    data.update(change)
    with pytest.raises(OfflineDownloadError):
        parse_offline_config(data)


@pytest.mark.parametrize("change", [
    {"baud_rate": 0}, {"baud_rate": -1}, {"baud_rate": 0x100000000},
    {"baud_rate": ""}, {"baud_rate": None}, {"baud_rate": "2M"},
    {"baud_rate": 1}, {"baud_rate": 921600}, {"baud_rate": 1234567}, {"baud_rate": 0xFFFFFFFF},
    {"baud_rate": 4000000}, {"baud_rate": 12500000},
    {"baud_rate": True}, {"baud_rate": 2000000.0}, {"connect_timeout_ms": 1.5},
    {"flash_size": "garbage"}, {"flash_size": 0}, {"flash_size": "0xFFFFFFFF"},
    {"sector_size": 1234}, {"memory_id": 0}, {"config_address": "0x1000"},
    {"nor_options": [0xFCF90002, 6, 0x1000, 0xF3000000]},
    {"rearm_mode": "uart_timeout"},
    {"completion": {"beep": "false"}}, {"completion": {"reset": "power_cycle"}},
    {"completion": {"reset": "hardware"}},
    {"completion": {"reset": "power_cycle", "restore_voltage_mv": 5500}},
    {"completion": {"reset": "software", "restore_voltage_mv": 3300}},
])
def test_reject_invalid_isp_parameters(change):
    data = payload()
    data["hpm_isp"].update(change)
    with pytest.raises(OfflineDownloadError):
        parse_offline_config(data)


def test_explicit_addresses_and_bin_only():
    data = payload()
    data["firmwares"][0].update(file_name="app.hex", format="hex", base_address=None)
    with pytest.raises(OfflineDownloadError, match="BIN"):
        parse_offline_config(data)
    data = payload()
    data["firmwares"][0]["base_address"] = "0x100000000"
    with pytest.raises(OfflineDownloadError, match="32 bits"):
        parse_offline_config(data)


def test_default_baud_is_2m():
    assert parse_offline_config(payload()).hpm_isp.baud_rate == 2000000


@pytest.mark.parametrize("part", ["HPM5301", "HPM5300", "HPM5E31", "HPM6280", "HPM6E80", "HPM6750", "HPM6880", "HPM6P81"])
def test_profile_capacity_allows_offset_images_without_user_capacity(tmp_path, part):
    data = payload()
    data["target_part"] = part
    data["hpm_isp"] = {}
    data["firmwares"].append({"id": "second", "file_name": "app-2.bin", "format": "bin",
                              "base_address": "0x80010400", "upload_index": 1})
    config = parse_offline_config(data)
    assert config.hpm_isp.flash_size == 0x200000
    script = generate_offline_script(config)
    assert 'path0, 2147484672, path1, 2147550208' in script
    first, second = tmp_path / "first.bin", tmp_path / "second.bin"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    disk = tmp_path / "disk"
    disk.mkdir()
    deploy_offline_bundle(config, disk, firmware_sources={"app": first, "second": second},
                          algorithm_sources={}, isp_capability_response="MKLINK_HPM_ISP_API 1")
    assert (disk / "app.bin").read_bytes() == b"first"
    assert (disk / "app-2.bin").read_bytes() == b"second"
    # The default memory map must still reject an image crossing its upper bound.
    data["firmwares"][1]["base_address"] = "0x801FFFFF"
    with pytest.raises(OfflineDownloadError, match="outside configured Flash"):
        deploy_offline_bundle(parse_offline_config(data), disk,
                              firmware_sources={"app": first, "second": second},
                              algorithm_sources={}, isp_capability_response="MKLINK_HPM_ISP_API 1")


@pytest.mark.parametrize("baud", [115200, 1000000, 2000000, 5000000, 10000000])
def test_script_calls_contract_and_does_not_access_debug(monkeypatch, baud):
    data = payload()
    data["hpm_isp"]["baud_rate"] = baud
    config = parse_offline_config(data)
    script = generate_offline_script(config)
    calls = []
    fake = SimpleNamespace(
        isp_supported=lambda: 1,
        isp_config=lambda *args: calls.append(("config", args)) or 0,
        isp_program=lambda *args: calls.append(("program", args)) or 0,
    )
    monkeypatch.setitem(sys.modules, "hpm", fake)
    exec(compile(script, "<isp>", "exec"), {})
    assert calls[0][1] == (baud, 10000, 10000, 0x200, 0x10000,
                           0x80000000, 0x800000, 4096, 0xFCF90002, 6, 4096, 0)
    assert calls[1][1][1:] == (1, 1, 0, 0, 200, "/app.bin", 0x80000400)
    assert calls[1][1][0] == script_metadata(script)["job_id"]
    assert "get_idcode" not in script and "set_swd" not in script and "import load" not in script
    calls.clear()
    fake.isp_supported = lambda: 0
    exec(script, {})
    assert not calls
    fake.isp_supported = lambda: 1
    fake.isp_config = lambda *args: -3
    exec(script, {})
    assert not calls


def test_voltage_is_passed_only_when_explicitly_configured():
    data = payload()
    data["hpm_isp"]["completion"] = {"beep": False, "reset": "power_cycle", "restore_voltage_mv": 3300}
    script = generate_offline_script(parse_offline_config(data))
    assert ', 1, 0, 3, 3300, 200, path0' in script


@pytest.mark.parametrize("filename", ["0:/app.bin", "3:/app.bin", "/app.bin", "../app.bin",
                                      "folder/app.bin", r"folder\app.bin"])
def test_isp_input_accepts_only_root_file_names(filename):
    data = payload()
    data["firmwares"][0]["file_name"] = filename
    with pytest.raises(OfflineDownloadError, match="file name"):
        parse_offline_config(data)


def test_eight_long_paths_fit_pika_line_buffer():
    data = payload()
    data["firmwares"] = [
        {"id": f"f{i}", "file_name": f"{i}" + "a" * 230 + ".bin", "format": "bin",
         "base_address": hex(0x80000000 + i * 4096), "upload_index": i}
        for i in range(8)
    ]
    script = generate_offline_script(parse_offline_config(data))
    assert max(len(line.encode()) for line in script.splitlines()) < 512
    assert "path7" in script
    data["firmwares"][0]["file_name"] = "a" * 241 + ".bin"
    with pytest.raises(OfflineDownloadError, match="240"):
        parse_offline_config(data)


def test_repeated_isp_rounds_require_explicit_reconnect_semantics():
    data = payload()
    data["auto_download_count"] = 3
    with pytest.raises(OfflineDownloadError, match="does not identify"):
        parse_offline_config(data)
    data["hpm_isp"]["confirm_reconnect_cycles"] = True
    config = parse_offline_config(data)
    assert script_metadata(generate_offline_script(config))["total"] == 3


def test_debug_completion_options_keep_existing_defaults():
    from test_offline_download import _config
    data = _config()
    data.update(beep_on_completion=False, reset_after_download=False)
    script = generate_offline_script(parse_offline_config(data))
    assert "cmd.set_beep_on()" not in script
    assert "cmd.set_reset()" not in script
    assert "cmd.get_idcode()" in script
    old = generate_offline_script(parse_offline_config(_config()))
    assert "cmd.set_beep_on()" in old and "cmd.set_reset()" in old


@pytest.mark.parametrize("response", ["", "1", "MKLINK_HPM_ISP_API 0", "MKLINK_HPM_ISP_API 11",
                                      "print('MKLINK_HPM_ISP_API 1')", "NameError: isp_supported"])
def test_capability_probe_fails_closed(response):
    with pytest.raises(ValueError, match="Upgrade"):
        require_capability(response)


def test_deployment_requires_capability_and_checks_all_files_before_copy(tmp_path):
    disk = tmp_path / "disk"
    disk.mkdir()
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    first.write_bytes(b"a" * 32)
    second.write_bytes(b"b" * 32)
    data = payload()
    data["firmwares"].append({"id": "b", "file_name": "b.bin", "format": "bin",
                              "base_address": "0x80000800", "upload_index": 1})
    sources = {"app": first, "b": second}
    config = parse_offline_config(data)
    with pytest.raises(OfflineDownloadError, match="Upgrade"):
        deploy_offline_bundle(config, disk, firmware_sources=sources, algorithm_sources={})
    with pytest.raises(OfflineDownloadError, match="erase sector"):
        deploy_offline_bundle(config, disk, firmware_sources=sources, algorithm_sources={},
                              isp_capability_response="MKLINK_HPM_ISP_API 1")
    assert list(disk.iterdir()) == []
    # Adjacent files are supported and firmware combines their write transaction.
    data["firmwares"][1]["base_address"] = "0x80000420"
    result = deploy_offline_bundle(parse_offline_config(data), disk,
        firmware_sources=sources, algorithm_sources={}, isp_capability_response="MKLINK_HPM_ISP_API 1")
    assert result["status"] == "deployed"
    assert (disk / "app.bin").read_bytes() == first.read_bytes()
    assert (disk / "b.bin").read_bytes() == second.read_bytes()
    # Resolve the paths actually passed to firmware against the deployed SD root.
    calls = []
    fake = SimpleNamespace(isp_supported=lambda: 1, isp_config=lambda *args: 0,
                           isp_program=lambda *args: calls.append(args) or 0)
    from unittest.mock import patch
    with patch.dict(sys.modules, {"hpm": fake}):
        exec((disk / "python" / "isp-test.py").read_text(encoding="utf-8"), {})
    assert calls[0][6::2] == ("/app.bin", "/b.bin")
    assert [(disk / path.removeprefix("/")).read_bytes() for path in calls[0][6::2]] == [
        first.read_bytes(), second.read_bytes()]


def test_missing_or_wrong_final_response_is_not_success():
    expected = {"job_id": "test", "total": 2}
    assert trigger_result(["offline download finished"], expected)["status"] == "unknown"
    result = {"schema": 1, "job_id": "other", "event": "result", "code": 0,
              "completed": 2, "total": 2, "rom_status": 0}
    line = lambda: "HPM_ISP " + json.dumps(result)
    assert trigger_result([line()], expected)["status"] == "unknown"
    result["job_id"] = "test"
    assert trigger_result([line()], expected)["status"] == "completed"
    result["code"] = -7
    assert trigger_result([line(), "offline download finished"], expected)["status"] == "failed"
    result.update(code=0, completed=1)
    assert trigger_result([line()], expected)["status"] == "failed"
    assert trigger_result(['HPM_ISP {"schema":1,"event":"connected"}', "finished"])["status"] == "unknown"


@pytest.mark.parametrize("stream", [False, True])
def test_http_isp_trigger_reserves_uart_and_requires_matching_final_result(tmp_path, monkeypatch, stream):
    from fastapi.testclient import TestClient
    from mklink.remote.api import create_app
    from mklink.remote.resource_manager import ResourceGroup, ResourceError
    script = generate_offline_script(parse_offline_config(payload()))
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "isp-test.py").write_text(script, encoding="utf-8")
    monkeypatch.setattr("mklink.discovery.find_microkeen_disk", lambda: str(tmp_path))
    app = create_app(auth_token=None, project_root=".")
    manager = app.state.mklink_state["resource_manager"]
    commands = []
    metadata = script_metadata(script)

    def send(command, **kwargs):
        commands.append(command)
        if "isp_supported" in command:
            return "MKLINK_HPM_ISP_API 1"
        assert command == 'load.offline("Python/isp-test.py")'
        for resource in (ResourceGroup.SERIAL_PORT, ResourceGroup.MODBUS_PORT):
            with pytest.raises(ResourceError):
                manager.acquire(resource, "user:another-tool")
        result = {"schema": 1, "job_id": metadata["job_id"], "event": "result",
                  "code": 0, "rom_status": 0, "completed": 1, "total": 1}
        line = "HPM_ISP " + json.dumps(result)
        if kwargs.get("on_output"):
            kwargs["on_output"](line)
        return line

    app.state.mklink_state["device"] = SimpleNamespace(
        connected=True, port="FIXTURE", _bridge=SimpleNamespace(send_command=send), close=lambda: None)
    with TestClient(app) as client:
        response = client.post("/api/offline-download/trigger",
            json={"model": "V4", "script_name": "isp-test.py"},
            headers={"Accept": "application/x-ndjson"} if stream else {})
    assert response.status_code == 200
    result = json.loads(response.text.splitlines()[-1])["result"] if stream else response.json()
    assert result["status"] == "completed"
    assert len(commands) == 2
    assert manager.get_status() == {}


def test_http_deploy_old_firmware_does_not_write_files(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from mklink.remote.api import create_app
    monkeypatch.setattr("mklink.discovery.find_microkeen_disk", lambda: str(tmp_path))
    app = create_app(auth_token=None, project_root=".")
    app.state.mklink_state["device"] = SimpleNamespace(
        connected=True, port="FIXTURE",
        _bridge=SimpleNamespace(send_command=lambda *a, **kw: "NameError: isp_supported"),
        close=lambda: None)
    with TestClient(app) as client:
        response = client.post("/api/offline-download/deploy",
            data={"config_json": json.dumps(payload())},
            files={"firmware_files": ("app.bin", b"test")})
    assert response.status_code == 422
    assert "Upgrade" in response.text
    assert list(tmp_path.iterdir()) == []

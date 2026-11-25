"""Exercise the online flash HTTP routes and job manager with a simulated probe."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mklink.cmsis_dap import s32k314_flm
from mklink.cmsis_dap.builtin_flm_bundle import (BuiltinFlmBundleError, discover_builtin_flm_algorithms,
                                                extract_builtin_flm, load_builtin_flm_targets)
from mklink.cmsis_dap.images import ImageInspector
from mklink.cmsis_dap.jobs import OnlineFlashJobManager
from mklink.cmsis_dap.models import JobState, MemoryRegion, ProbeRecord
from mklink.cmsis_dap.pack_catalog import PackCatalog
from mklink.cmsis_dap.paths import PackPaths
from mklink.remote.online_flash_api import OnlineFlashServices, create_online_flash_router
from mklink.remote.resource_manager import ResourceManager


PART = "S32K314"
PROBE = "simulated-dap"
BANKS = ((0x00400000, 0x400000), (0x10000000, 0x20000))
SECTOR_SIZE = 0x2000
API = "/api/online-flash"


@pytest.fixture
def routes(tmp_path, monkeypatch):
    # Reproduce the shipped manifest and both content-addressed blobs with
    # inert fixture bytes. Only the Code FLM is referenced by the bad rows.
    algorithms = []
    for start, size in BANKS:
        content = f"simulated algorithm for {start:#x}".encode()
        digest = hashlib.sha256(content).hexdigest()
        blob = Path("blobs", digest[:2], digest + ".flm")
        (tmp_path / blob).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / blob).write_bytes(content)
        algorithms.append({
            "file_name": "S32K3x4_Code.FLM", "flash_start": start, "flash_size": size,
            "page_size": SECTOR_SIZE, "sector_sizes": [[0, SECTOR_SIZE]],
            "blob": blob.as_posix(), "sha256": digest,
        })
    monkeypatch.setattr(s32k314_flm, "CODE_SHA256", algorithms[0]["sha256"])
    monkeypatch.setattr(s32k314_flm, "DATA_SHA256", algorithms[1]["sha256"])
    legacy = [algorithms[0], dict(algorithms[1], blob=algorithms[0]["blob"], sha256=algorithms[0]["sha256"])]
    (tmp_path / "manifest.json").write_text(json.dumps({"schema": 1, "targets": [{
        "part_number": PART, "manufacturer": "NXP", "ram_start": 0x20400000,
        "ram_size": 0x28000, "algorithms": legacy,
    }]}), encoding="utf-8")
    monkeypatch.setenv("MKLINK_BUILTIN_FLM_ROOT", str(tmp_path))

    regions = [MemoryRegion("flash", a.flash_start, a.flash_size, True, True, SECTOR_SIZE)
               for a in discover_builtin_flm_algorithms(PART)]
    memory = {}
    backend = Mock(spec_set=("connect", "disconnect", "memory_regions", "erase_sectors", "program", "verify", "read_memory"))
    backend.memory_regions.return_value = regions

    def program(image, progress_callback):
        memory[image.start] = Path(image.file_path).read_bytes()

    def verify(image, progress_callback=None):
        assert memory[image.start] == Path(image.file_path).read_bytes()

    backend.program.side_effect = program
    backend.verify.side_effect = verify
    backend.read_memory.side_effect = lambda address, size: memory[address][:size]
    inspector = ImageInspector(snapshot_root=tmp_path / "images")
    manager = OnlineFlashJobManager(lambda: backend, ResourceManager(), inspector.validate_unchanged)
    paths = PackPaths(tmp_path / "packs")
    services = OnlineFlashServices(
        catalog=PackCatalog(paths, builtin_provider=load_builtin_flm_targets), paths=paths,
        pack_manager=None, image_inspector=inspector, job_manager=manager,
        probe_provider=lambda: [ProbeRecord(PROBE, product_name="Simulated MKLink DAP")],
        target_memory_provider=lambda part: regions,
    )
    app = FastAPI()
    app.include_router(create_online_flash_router(services))
    try:
        with TestClient(app) as client:
            yield client, manager, backend, algorithms
    finally:
        manager.shutdown()


@pytest.mark.parametrize("bank", (0, 1), ids=("code-flash", "data-flash"))
def test_online_s32k314_flash_program_verify_and_readback(routes, bank):
    client, manager, backend, algorithms = routes
    start, size = BANKS[bank]
    payload = b"S32K314\x00\x80\xff"
    choices = client.get(f"{API}/targets/{PART}/algorithms")
    assert choices.status_code == 200, choices.text
    algorithm = next(row for row in choices.json() if row["flash_start"] == start)
    assert algorithm["target_part"] == PART and algorithm["source_kind"] == "daplink-builtin"
    size = size if bank else 0x3E0000
    assert algorithm["flash_size"] == size
    assert algorithm["file_name"] == ("S32K3x4_Data.FLM" if bank else "S32K3x4_Code.FLM")
    assert (algorithm["ram_start"], algorithm["ram_size"]) == (0x20400000, 0x10000)
    uploaded = client.post(f"{API}/images/inspect", files={"file": ("fixture.bin", payload)},
                           data={"part_number": PART, "base_address": hex(start),
                                 "algorithm_ids": algorithm["algorithm_id"]})
    assert uploaded.status_code == 200, uploaded.text
    image = uploaded.json()
    assert image["sectors"] == [{"address": start, "size": SECTOR_SIZE}]
    assert [part["algorithm_id"] for part in image["algorithm_plan"]] == [algorithm["algorithm_id"]]

    selection = {"target_part": PART, "probe_id": PROBE, "frequency": 1_000_000, "connect_mode": "halt"}
    started = client.post(f"{API}/jobs", json={
        **selection, "actions": ["connect", "erase", "program", "verify", "disconnect"],
        "image_id": image["image_id"], "sector_addresses": [start],
        "algorithm_ids": [algorithm["algorithm_id"]],
    })
    assert started.status_code == 200, started.text
    job = manager.wait(started.json()["job_id"], timeout=5)
    assert job.state is JobState.SUCCEEDED, job.error
    backend.erase_sectors.assert_called_once_with((start,))
    backend.program.assert_called_once()
    backend.verify.assert_called_once()

    read = client.post(f"{API}/memory/read-stream", json={
        **selection, "address": hex(start), "size": len(payload), "chunk_sizes": [len(payload)],
    })
    assert read.status_code == 200, read.text
    assert read.content == payload
    backend.read_memory.assert_called_once_with(start, len(payload))
    assert backend.disconnect.call_count == 2
    assert backend.connect.call_count == 2
    for call in backend.connect.call_args_list:
        assert (call.kwargs["probe"], call.kwargs["target"]) == (PROBE, PART)
        assert (call.kwargs["frequency"], call.kwargs["connect_mode"]) == (1_000_000, "halt")
        assert call.kwargs["custom_flm_regions"] == ((start, size),)
        assert call.kwargs["custom_flm_digests"] == (algorithms[bank]["sha256"],)
        assert (call.kwargs["custom_flm_ram_start"], call.kwargs["custom_flm_ram_size"]) == (0x20400000, 0x10000)


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_bad_data_blob_leaves_code_flash_available_and_old_data_id_unusable(routes, tmp_path, damage):
    client, _, backend, rows = routes
    blob = tmp_path / rows[1]["blob"]
    if damage == "missing":
        blob.unlink()
    else:
        blob.write_bytes(b"invalid Data FLM")
    records = client.get(f"{API}/targets/{PART}/algorithms").json()
    assert [record["file_name"] for record in records] == ["S32K3x4_Code.FLM"]
    old_id = hashlib.sha256(f"daplink-builtin|s32k314|0|1|{rows[0]['sha256']}|0x10000000|0x20000".encode()).hexdigest()
    assert client.get(f"{API}/targets/{PART}/memory-map", params={"algorithm_ids": old_id}).status_code >= 400
    read = client.post(f"{API}/memory/read", json={"target_part": PART, "probe_id": PROBE,
                                                  "address": "0x10000000", "size": 4})
    assert read.status_code >= 400
    backend.connect.assert_not_called()


def test_repaired_data_record_invalidates_stale_selection_and_extraction(routes):
    client, _, backend, rows = routes
    code, data = discover_builtin_flm_algorithms(PART)
    stale = hashlib.sha256(f"daplink-builtin|s32k314|0|1|{rows[0]['sha256']}|0x10000000|0x20000".encode()).hexdigest()
    assert data.algorithm_id != stale
    result = client.post(f"{API}/images/inspect", files={"file": ("data.bin", b"abcd")}, data={
        "part_number": PART, "base_address": "0x10000000", "algorithm_ids": stale})
    assert result.status_code >= 400
    with pytest.raises(BuiltinFlmBundleError, match="exceeds"):
        extract_builtin_flm(replace(code, algorithm_id=stale, flash_start=data.flash_start, flash_size=data.flash_size))
    backend.connect.assert_not_called()


@pytest.mark.parametrize(("bank", "address", "allowed"), [(0, 0x007DFFFC, True), (0, 0x007DFFFE, False),
                                                         (0, 0x007E0000, False), (1, 0x1001FFFC, True),
                                                         (1, 0x1001FFFE, False), (1, 0x10020000, False)])
def test_flashdevice_end_is_exclusive_for_manual_binary_address(routes, bank, address, allowed):
    client, _, backend, _ = routes
    choices = client.get(f"{API}/targets/{PART}/algorithms").json()
    selected = next(a for a in choices if a["flash_start"] == BANKS[bank][0])
    result = client.post(f"{API}/images/inspect", files={"file": ("edge.bin", b"\x00\xffAB")},
                         data={"part_number": PART, "base_address": hex(address), "algorithm_ids": selected["algorithm_id"]})
    assert result.status_code == 200, result.text
    image = result.json()
    assert image.get("preview_only", False) is (not allowed)
    if not allowed:
        started = client.post(f"{API}/jobs", json={
            "probe_id": PROBE, "target_part": PART, "image_id": image["image_id"],
            "actions": ["connect", "erase", "program", "disconnect"], "algorithm_ids": [selected["algorithm_id"]],
        })
        assert started.status_code >= 400
        read = client.post(f"{API}/memory/read", json={"target_part": PART, "probe_id": PROBE,
                                                      "address": hex(address), "size": 4})
        assert read.status_code >= 400
    backend.connect.assert_not_called()

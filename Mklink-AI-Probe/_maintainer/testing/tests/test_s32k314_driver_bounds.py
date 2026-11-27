"""Destructive admission uses the loaded S32K314 FLM bytes and the actual selected core."""

import hashlib
import io
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pyocd.core.memory_map import FlashRegion, MemoryMap

from mklink.cmsis_dap import s32k3_flm
from mklink.cmsis_dap.backend import PyOcdBackend, _install_custom_flm_regions, _prepare_pack_flm_regions
from mklink.cmsis_dap.errors import FlashError, FlashErrorCode
from mklink.profiles import resolve_attach_profile


CODE = b"fixture S32K314 Code"
DATA = b"fixture S32K314 Data"
START, END = s32k3_flm.CODE_START, s32k3_flm.CODE_END
PAGE = 0x2000


def region(start, size, payload, *, pname="CM7", erase_all=True):
    stream = io.BytesIO(payload)
    stream.seek(3)
    flm = SimpleNamespace(elf=SimpleNamespace(_file=stream), flash_start=start, flash_size=size)
    result = FlashRegion(start=start, length=size, pname=pname, name=f"{pname}-{start:X}", flm=flm)
    def info(address):
        return SimpleNamespace(base_addr=address & ~(PAGE - 1), size=PAGE)
    result.flash = SimpleNamespace(is_erase_all_supported=erase_all, get_sector_info=info, get_page_info=info)
    return result


@pytest.fixture(autouse=True)
def identify_fixture(monkeypatch):
    monkeypatch.setattr(s32k3_flm, "CODE_SHA256", hashlib.sha256(CODE).hexdigest())


def driver(*regions):
    backend = PyOcdBackend(programmer_factory=Mock(), eraser_factory=Mock())
    target = SimpleNamespace(memory_map=MemoryMap(*regions), selected_core=SimpleNamespace(node_name="CM7"))
    backend._session = SimpleNamespace(target=target, close=Mock())
    backend._flash_profile = resolve_attach_profile("S32K314")
    backend._algorithm_reset_required = True
    backend._prepare_profile_flash = Mock()
    backend._check_profile_workspace = Mock()
    backend._flash_interrupt_guard = lambda _target: nullcontext()
    return backend, target


def image(tmp_path, start, size):
    path = tmp_path / "image.bin"
    path.write_bytes(bytes(size))
    return SimpleNamespace(format="bin", file_path=path, base_address=start)


def test_pack_memory_map_intersects_only_the_matching_elf_without_consuming_it():
    code = region(START, 0x400000, CODE)
    data = region(s32k3_flm.DATA_START, 0x20000, DATA)
    shared = MemoryMap(code, data)
    target = SimpleNamespace(memory_map=shared, part_number="S32K314")
    _prepare_pack_flm_regions(target, ((START, 0x400000),))
    assert target.memory_map.get_region_for_address(START).end == END-1
    assert target.memory_map.get_region_for_address(END) is None
    assert target.memory_map.get_region_for_address(data.start).length == data.length
    assert shared.get_region_for_address(END) is code
    assert code.flm.elf._file.tell() == 3


@pytest.mark.parametrize("issue", [None, "digest", "end", "late-gap"])
def test_explicit_code_range_checks_every_sector_without_chip_erase(issue):
    code = region(START, END-START, CODE)
    backend, _ = driver(code, region(s32k3_flm.DATA_START, PAGE, DATA))
    if issue == "late-gap":
        sector_info = code.flash.get_sector_info
        code.flash.get_sector_info = lambda addr: None if addr == END-PAGE else sector_info(addr)
    def run():
        backend.erase_algorithm_range(START, END+1 if issue == "end" else END,
                                      "invalid" if issue == "digest" else s32k3_flm.CODE_SHA256)
    if issue:
        with pytest.raises(FlashError):
            run()
        backend._eraser_factory.assert_not_called()
    else:
        run()
        _, mode = backend._eraser_factory.call_args.args
        assert mode.name == "SECTOR"
        args = backend._eraser_factory.return_value.erase.call_args.args
        assert args == (list(range(START, END, PAGE)),) and len(args[0]) == 496


@pytest.mark.parametrize("address,size", [(END, PAGE), (START, 0x400000), (0x10000000, PAGE)])
def test_custom_flm_override_rejected_by_driver_before_open_and_during_install(tmp_path, monkeypatch, address, size):
    constructor = Mock()
    backend = PyOcdBackend(session_factory=constructor)
    file = tmp_path / "renamed.flm"
    file.write_bytes(CODE)
    override = ((address, size),)
    with pytest.raises(FlashError) as error:
        backend.connect(object(), "NXPS32K314HMS", 1_000_000, custom_flm_paths=(str(file),),
                        custom_flm_digests=(s32k3_flm.CODE_SHA256,), custom_flm_regions=override)
    assert error.value.code is FlashErrorCode.IMAGE_OUT_OF_RANGE
    constructor.assert_not_called()
    target = SimpleNamespace(memory_map=MemoryMap(), part_number="S32K314")
    monkeypatch.setattr("pyocd.target.pack.flash_algo.PackFlashAlgo", lambda _: SimpleNamespace())
    with pytest.raises(FlashError) as error:
        _install_custom_flm_regions(target, (CODE,), flash_regions=override)
    assert error.value.code is FlashErrorCode.IMAGE_OUT_OF_RANGE


@pytest.mark.parametrize("operation", ["erase", "image-end", "page-end", "sector-end"])
def test_live_pack_geometry_fails_before_any_target_command(tmp_path, operation):
    code = region(START, 0x400000, CODE)
    backend, _ = driver(code)
    if operation == "erase":
        run = lambda: backend.erase_sectors([START, END])
    else:
        start = END-1
        size = 2 if operation == "image-end" else 1
        if operation in {"page-end", "sector-end"}:
            getter = "get_page_info" if operation == "page-end" else "get_sector_info"
            setattr(code.flash, getter, lambda addr: SimpleNamespace(base_addr=END-PAGE, size=2*PAGE))
        firmware = image(tmp_path, start, size)
        run = lambda: backend.program(firmware)
    with pytest.raises(FlashError) as error:
        run()
    assert error.value.code is FlashErrorCode.IMAGE_OUT_OF_RANGE
    backend._prepare_profile_flash.assert_not_called()
    backend._eraser_factory.assert_not_called()
    backend._programmer_factory.assert_not_called()


def test_last_byte_can_program_and_raw_read_still_reaches_reserved_tail(tmp_path):
    backend, target = driver(region(START, 0x400000, CODE))
    firmware = image(tmp_path, END-1, 1)
    firmware.file_path = firmware.file_path.rename(tmp_path / "misnamed.hex")
    firmware.sha256 = hashlib.sha256(b"\x00").hexdigest()
    # The pathname changes after bounds admission. Only the checked bytes can be sent.
    backend._prepare_profile_flash.side_effect = lambda _, *, destructive: firmware.file_path.write_bytes(b"grown")
    progress = Mock()
    backend.program(firmware, progress)
    programmer = backend._programmer_factory.return_value
    assert backend._programmer_factory.call_args.kwargs["progress"] is progress
    args, kwargs = programmer.add_file.call_args
    assert args[0].read() == b"\x00" and kwargs == {"file_format": "bin", "base_address": END-1}
    programmer.commit.assert_called_once_with()
    target.read_memory_block8 = Mock(return_value=[0xFF])
    assert backend.read_memory(END, 1) == b"\xff"
    target.read_memory_block8.assert_called_once_with(END, 1)


@pytest.mark.parametrize("invalid", ["digest", "base", "format"])
def test_inconsistent_direct_image_never_reaches_the_target(tmp_path, invalid):
    backend, _ = driver(region(START, 0x400000, CODE))
    firmware = image(tmp_path, START, 1)
    if invalid == "digest":
        firmware.sha256 = "0" * 64
    elif invalid == "format":
        firmware.format = "elf"
    else:
        firmware.base_address = None
    with pytest.raises(FlashError):
        backend.program(firmware)
    backend._prepare_profile_flash.assert_not_called()
    backend._programmer_factory.assert_not_called()


@pytest.mark.parametrize("scenario,allowed", [
    ("mixed", False), ("data-only", True), ("other-core", True), ("sector-fallback", True),
    ("oversized-sector-fallback", False),
])
def test_chip_erase_checks_all_dispatched_algorithms_before_first_erase(scenario, allowed):
    regions = [region(0x1000, PAGE, DATA)]
    if scenario != "data-only":
        size = 0x400000 if scenario == "oversized-sector-fallback" else END-START
        regions.append(region(START, size, CODE, pname="CM0" if scenario == "other-core" else "CM7",
                              erase_all="fallback" not in scenario))
    backend, _ = driver(*regions)
    if allowed:
        backend.erase_chip()
        backend._eraser_factory.return_value.erase.assert_called_once_with()
    else:
        with pytest.raises(FlashError):
            backend.erase_chip()
        backend._prepare_profile_flash.assert_not_called()
        backend._eraser_factory.assert_not_called()

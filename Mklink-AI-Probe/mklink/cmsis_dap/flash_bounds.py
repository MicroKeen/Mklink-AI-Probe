"""Write bounds for the identified S32K314 Code FLM in pyOCD's live memory map."""

import hashlib
import io

from . import s32k314_flm
from .errors import FlashError, FlashErrorCode


def _is_limited_code(part, region):
    if part != "S32K314":
        return False
    # pyOCD 0.44.1 retains the original FLM in PackFlashAlgo.elf._file.
    # Both CmsisPack.get_file() and MKLink's custom loader return BytesIO.
    algorithm = getattr(region, "flm", None)
    stream = getattr(getattr(algorithm, "elf", None), "_file", None)
    if isinstance(stream, io.BytesIO):
        return hashlib.sha256(stream.getbuffer()).hexdigest() == s32k314_flm.CODE_SHA256
    return False


def _require_code_range(start, end):
    if not s32k314_flm.CODE_START <= start < end <= s32k314_flm.CODE_END:
        raise FlashError(FlashErrorCode.IMAGE_OUT_OF_RANGE,
                         f"S32K314 Code FLM cannot modify 0x{start:X}..0x{end:X} (end exclusive)",
                         {"start": start, "end": end, "allowed_start": s32k314_flm.CODE_START,
                          "allowed_end": s32k314_flm.CODE_END})


def check_flm_override(part, digest, start, size):
    if part == "S32K314" and digest == s32k314_flm.CODE_SHA256:
        _require_code_range(start, start + size)


def check_flash_span(part, region, start, end, *, program):
    """pyOCD may fill a whole page and erase a whole sector for a one-byte image."""
    if not _is_limited_code(part, region):
        return
    flash = region.flash
    _require_code_range(start, end)
    getters = [flash.get_sector_info]
    if program:
        getters.append(flash.get_page_info)
    for get_info in getters:
        address = start
        while address < end:
            info = get_info(address)
            if info is None or not info.base_addr <= address < info.base_addr + info.size:
                raise FlashError(FlashErrorCode.IMAGE_OUT_OF_RANGE,
                                 f"Invalid S32K314 Code FLM geometry at 0x{address:X}")
            address = info.base_addr + info.size
            _require_code_range(info.base_addr, address)


def check_chip_erase(part, region):
    if region.flash is None or not _is_limited_code(part, region):
        return
    if region.flash.is_erase_all_supported:
        raise FlashError(FlashErrorCode.TARGET_NOT_SUPPORTED,
                         "S32K314 Code FLM chip erase has no address bounds. Select sectors to erase.")
    check_flash_span(part, region, region.start, region.start + region.length, program=False)


def limit_pack_code_regions(target):
    """The Keil 1.0.1 PDSC describes more PFlash than its Code FLM implements."""
    if getattr(target, "part_number", "") != "S32K314":
        return
    memory_map = target.memory_map.clone()
    for region in tuple(memory_map):
        if not region.is_flash or not _is_limited_code(target.part_number, region):
            continue
        start, size = s32k314_flm.code_range(region.start, region.length)
        if (start, size) == (region.start, region.length):
            continue
        memory_map.remove_region(region)
        if size:
            memory_map.add_region(region.clone_with_changes(start=start, length=size))
    target.memory_map = memory_map

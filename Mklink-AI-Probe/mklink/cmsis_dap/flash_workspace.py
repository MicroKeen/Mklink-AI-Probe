"""Check a halted Cortex-M7's effective access to the selected Pack FLM's RAM."""
from dataclasses import dataclass

from .errors import FlashError, FlashErrorCode

CCR = 0xe000ed14
MPU_TYPE, MPU_CTRL, MPU_RNR, MPU_RBAR, MPU_RASR = range(0xe000ed90, 0xe000eda4, 4)
ITCMCR, DTCMCR, CACR = 0xe000ef90, 0xe000ef94, 0xe000ef9c
DC, IC = 1 << 16, 1 << 17


def _error(reason, message, **details):
    return FlashError(FlashErrorCode.CONNECT_FAIL, f"FLM workspace: {message}",
                      {"reason": reason, **details})


@dataclass(frozen=True)
class _Span:
    name: str
    start: int
    end: int  # exclusive
    access: str  # privileges required by the running CPU


def _workspace(flash):
    # PackFlashAlgo emits [header + RO][RW + ZI]; static_base is the start of RW.
    try:
        algo = flash.flash_algo
        if algo["analyzer_supported"]:
            raise _error("analyzer", "a separate CRC analyzer workspace is unsupported")
        load = algo["load_address"]
        end = load + len(algo["instructions"]) * 4
        rw = algo["static_base"]
        if not load < rw <= end:
            raise ValueError("static_base does not divide the loaded code and data")
        for key in ("pc_erase_sector", "pc_program_page", "pc_init", "pc_unInit", "pc_eraseAll", "pc_verify"):
            pc = algo.get(key, 0xffffffff)
            if pc != 0xffffffff and (not pc & 1 or not load <= (pc & ~1) < rw):
                raise ValueError(f"{key} is not a Thumb entry point within the FLM code")
        spans = [_Span("code", load, rw, "rx"), _Span("stack", algo["end_stack"], algo["begin_stack"], "rw")]
        if rw < end:
            spans.append(_Span("static data", rw, end, "rw"))
        size = flash.region.page_size
        if not algo["page_buffers"]:
            raise ValueError("page_buffers is empty")
        spans.extend(_Span(f"page buffer {index}", addr, addr + size, "r")
                     for index, addr in enumerate(algo["page_buffers"]))
        for span in spans:
            if not (type(span.start) is int and type(span.end) is int and 0 <= span.start < span.end <= 1 << 32):
                raise ValueError(f"invalid address range for {span.name}")
        ordered = sorted(spans, key=lambda span: span.start)
        if any(a.end > b.start for a, b in zip(ordered, ordered[1:])):
            raise ValueError("code, data, stack or page buffers overlap")
        return spans
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise _error("layout", f"cannot establish the selected FLM layout: {exc}") from exc


def _read(target, address):
    try:
        value = target.read32(address)
        if type(value) is not int or not 0 <= value <= 0xffffffff:
            raise ValueError(f"invalid word {value!r}")
        return value
    except Exception as exc:
        raise _error("register_read", f"unable to read register 0x{address:08x}: {exc}", address=address) from exc


def _select(target, index):
    try:
        target.write32(MPU_RNR, index)
        target.flush()
        if _read(target, MPU_RNR) != index:
            raise ValueError("selector readback mismatch")
    except Exception as exc:
        raise _error("mpu_selector", f"unable to select MPU region {index}: {exc}", region=index) from exc


def _mpu_ranges(target):
    mpu_type = _read(target, MPU_TYPE)
    count = (mpu_type >> 8) & 0xff
    if mpu_type & 1 or count not in (8, 16):
        raise _error("mpu_type", f"unsupported Cortex-M7 MPU_TYPE 0x{mpu_type:08x}", actual=mpu_type)
    saved = _read(target, MPU_RNR)
    if saved >= count:
        raise _error("mpu_selector", f"current MPU selector {saved} is outside the {count} implemented banks",
                     region=saved)
    regions = []
    try:
        for index in range(count):
            _select(target, index)
            attr = _read(target, MPU_RASR)
            if not attr & 1:
                continue
            base = _read(target, MPU_RBAR) & ~31
            size = 1 << (1 + ((attr >> 1) & 31))
            disabled = (attr >> 8) & 0xff
            if size < 32 or base % size or (size < 256 and disabled):
                # Retain uncertainty at this bank's priority. A misaligned RBAR can
                # affect its SIZE-aligned window; include the literal base window too.
                # Reserved SIZE encodings do not establish any usable bounds.
                lo, hi = (0, 1 << 32) if size < 32 else (base & -size, min(base + size, 1 << 32))
                regions.append((lo, hi, index, attr, base))
                continue
            stride = size // 8 if disabled else size
            for offset in range(0, size, stride):
                if not (disabled & (1 << (offset // stride))):
                    regions.append((base + offset, base + offset + stride, index, attr, None))
    finally:
        _select(target, saved)
    return regions


def _tcm_ranges(target, spans):
    result = []
    for base, register in ((0, ITCMCR), (0x20000000, DTCMCR)):
        if any(span.start < base + 0x1000000 and span.end > base for span in spans):
            ctrl = _read(target, register)
            if ctrl & 1:
                size = (ctrl >> 3) & 15
                if size < 3 or ctrl & ~0x7f:
                    raise _error("tcm_layout", f"unsupported TCM control 0x{ctrl:08x}", address=register)
                result.append((base, base + (512 << size)))
    return result


def _cacheable(attr):
    # Arm DUI 0646, MPU access permission attributes (TEX, C, B).
    tex, cb = (attr >> 19) & 7, (attr >> 16) & 3
    if tex >= 4:
        return cb != 0  # inner cache policy
    if (tex, cb) == (1, 0):
        return False
    if (tex, cb) in ((0, 2), (0, 3), (1, 3)):
        return True
    return None  # Device, strongly ordered, reserved, or implementation-defined


def check_flash_workspace(target, flash, *, icache_sync=False):
    """Check the actual allocation while halted in privileged Thread mode on the bound core.

    icache_sync promises instruction-cache maintenance after upload and before running the FLM.
    Reading MPU banks temporarily changes only MPU_RNR and restores its original selection.
    """
    spans = _workspace(flash)
    ccr, ctrl = _read(target, CCR), _read(target, MPU_CTRL)
    if ctrl & ~7 or ccr == 0xffffffff:
        raise _error("core_state", "invalid Cortex-M7 CCR or MPU_CTRL", ccr=ccr, mpu_ctrl=ctrl)
    regions = _mpu_ranges(target) if ctrl & 1 else []
    tcm = _tcm_ranges(target, spans) if ccr & (IC | DC) else []
    # Each open interval between boundaries has a single effective region (highest number wins).
    bounds = {0x40000000} | {v for start, end, *_ in [*regions, *tcm] for v in (start, end)}
    shared_wt = None
    for span in spans:
        cursor = span.start
        while cursor < span.end:
            details = dict(workspace=span.name, address=cursor, ccr=ccr, mpu_ctrl=ctrl)
            def deny(reason, message):
                raise _error(reason, f"{span.name} at 0x{cursor:08x}: {message}", **details)

            try:
                ram = target.memory_map.get_region_for_address(cursor, target.selected_core.node_name)
            except (AttributeError, TypeError, ValueError) as exc:
                deny("ram_map", f"cannot resolve the selected core's RAM map: {exc}")
            if ram is None or not ram.is_ram or not ram.is_writable or not ram.is_readable:
                deny("ram_map", "outside the selected core's writable RAM")
            if "x" in span.access and not ram.is_executable:
                deny("ram_map", "the memory map marks this RAM non-executable")
            match = next((r for r in reversed(regions) if r[0] <= cursor < r[1]), None)
            shared = False
            if match is None:
                if ctrl & 1 and not ctrl & 4:
                    deny("mpu_unmapped", "no matching MPU region and privileged background map is disabled")
                if cursor >= 0x40000000:
                    deny("background_map", "unsupported default memory type outside internal Code/SRAM")
                cacheable = True
            else:
                _, _, index, attr, invalid_base = match
                details.update(region=index, rasr=attr)
                if invalid_base is not None:
                    details["rbar"] = invalid_base
                    deny("mpu_layout", f"cannot establish the effective coverage of MPU region {index}")
                ap = (attr >> 24) & 7
                if ap in (0, 4) or ("w" in span.access and ap not in (1, 2, 3)):
                    deny("mpu_permission", f"MPU region {index} AP={ap} denies required privileged {span.access}")
                if "x" in span.access and attr & (1 << 28):
                    deny("mpu_xn", f"MPU region {index} is execute-never")
                cacheable = _cacheable(attr)
                if cacheable is None:
                    deny("mpu_type", f"MPU region {index} lacks supported Normal memory attributes")
                shared = bool(attr & (1 << 18))
            if cacheable and not any(start <= cursor < end for start, end in tcm):
                if ccr & DC:
                    if shared and shared_wt is None:
                        shared_wt = bool(_read(target, CACR) & 1)
                    if not shared or shared_wt:
                        deny("dcache", "active D-cache can conceal CPU or debugger updates")
                if ccr & IC and "x" in span.access and not shared and not icache_sync:
                    deny("icache", "active I-cache needs synchronization after FLM upload")
            cursor = min(span.end, ram.end + 1, min((v for v in bounds if v > cursor), default=span.end))

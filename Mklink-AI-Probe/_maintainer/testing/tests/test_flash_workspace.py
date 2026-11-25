from types import SimpleNamespace

import pytest
from pyocd.core.memory_map import FlashRegion, MemoryMap, RamRegion
from pyocd.flash.flash import Flash

from mklink.cmsis_dap import flash_workspace as ws
from mklink.cmsis_dap.errors import FlashError


BASE = 0x20400000


class Target:
    def __init__(self, base=BASE):
        self.selected_core = SimpleNamespace(node_name="Cortex-M7_0")
        self.memory_map = MemoryMap(RamRegion(start=base, length=0x1000))
        self.regs = {ws.CCR: 0, ws.MPU_CTRL: 1, ws.MPU_TYPE: 8 << 8,
                     ws.MPU_RNR: 5, ws.DTCMCR: 0, ws.CACR: 0}
        self.banks = [(0, 0)] * 8
        self.writes = []

    def read32(self, addr):
        if addr in (ws.MPU_RBAR, ws.MPU_RASR):
            bank = self.banks[self.regs[ws.MPU_RNR]]
            return bank[addr == ws.MPU_RASR]
        return self.regs[addr]

    def write32(self, addr, value):
        assert addr == ws.MPU_RNR
        self.regs[addr] = value
        self.writes.append(value)

    def flush(self):
        pass


def flash_region(target, base=BASE):
    # Gaps between allocations are intentionally absent from the permission checks.
    algo = dict(load_address=base + 0x800, instructions=[0] * 128,
                static_base=base + 0x900, begin_stack=base + 0x200, end_stack=base,
                page_buffers=[base + 0x400, base + 0x600], analyzer_supported=False,
                pc_program_page=base + 0x805, pc_erase_sector=base + 0x809)
    flash = Flash(target, algo)
    flash.region = FlashRegion(start=0x400000, length=0x2000, sector_size=0x1000, page_size=0x100)
    return flash


def region(size=0x1000, *, ap=3, xn=False, tex=1, cb=0, subregions=0, shared=False):
    return (1 | ((size.bit_length() - 2) << 1) | (subregions << 8) | (cb << 16)
            | (int(shared) << 18) | (tex << 19) | (ap << 24) | (int(xn) << 28))


def test_split_code_static_data_and_read_only_page_buffers():
    target = Target()
    flash = flash_region(target)
    target.regs[ws.CCR] = ws.DC | ws.IC
    target.banks[0] = BASE, region(xn=True)
    target.banks[3] = BASE + 0x800, region(0x100, ap=5)
    target.banks[4] = BASE + 0x400, region(0x400, ap=5, xn=True)
    target.banks[7] = BASE + 0x300, region(0x100, ap=0)
    ws.check_flash_workspace(target, flash)
    assert target.regs[ws.MPU_RNR] == 5


@pytest.mark.parametrize('address,flags,reason,workspace', [
    (0x880, dict(xn=True), 'mpu_xn', 'code'),
    (0x920, dict(ap=5), 'mpu_permission', 'static data'),
    (0x040, dict(ap=6), 'mpu_permission', 'stack'),
    (0x420, dict(ap=4), 'mpu_permission', 'page buffer 0'),
    (0x620, dict(tex=0, cb=1), 'mpu_type', 'page buffer 1'),
])
def test_higher_priority_region_inside_allocation(address, flags, reason, workspace):
    target = Target()
    target.banks[0] = BASE, region()
    target.banks[7] = BASE + address, region(32, **flags)
    with pytest.raises(FlashError) as failure:
        ws.check_flash_workspace(target, flash_region(target))
    assert failure.value.details['reason'] == reason
    assert failure.value.details['address'] == BASE + address
    assert failure.value.details['workspace'] == workspace
    assert failure.value.details['region'] == 7
    assert target.regs[ws.MPU_RNR] == 5


def test_subregion_falls_through_to_lower_region_or_privileged_default():
    target = Target()
    target.banks[4] = BASE, region(subregions=1 << 4)
    with pytest.raises(FlashError, match="privileged background map is disabled"):
        ws.check_flash_workspace(target, flash_region(target))
    target.banks[1] = BASE, region()
    ws.check_flash_workspace(target, flash_region(target))
    target.banks[1] = 0, 0
    target.regs[ws.MPU_CTRL] = 5
    ws.check_flash_workspace(target, flash_region(target))


def test_recorded_s32k314_mpu_and_pack_workspace():
    # online-mpu-map.log, Keil.S32K3xx_DFP.1.0.1 S32K3x4_Code.FLM
    target = Target()
    target.regs.update({ws.MPU_TYPE: 16 << 8, ws.MPU_CTRL: 3, ws.CCR: 0x60200})
    target.banks = [
        (0, 0x1004003f), (1, 0x0308001d), (0x00420002, 0x070b002b),
        (0x10000003, 0x160b0023), (0x1b000004, 0x160b0019), (0x20000005, 0x0308001f),
        (0x20400006, 0x030bc023), (0x20430007, 0x130c001f), (0x20440008, 0x130c001b),
        (0x40000009, 0x1304c02d), (0x6700000a, 0x13040013), (0x6800000b, 0x030b0035),
        (0xe000000c, 0x13040027), (13, 0), (14, 0), (15, 0),
    ]
    target.memory_map = MemoryMap(RamRegion(start=BASE, length=0x28000))
    algo = dict(load_address=0x2040e67c, instructions=[0] * 1633, static_base=0x2040f808,
                begin_stack=0x2040a670, end_stack=BASE, page_buffers=[0x2040c670, 0x2040a670],
                pc_erase_sector=0x2040e9bd, pc_program_page=0x2040f625, analyzer_supported=False)
    flash = Flash(target, algo)
    flash.region = FlashRegion(start=0x400000, length=0x400000, sector_size=8192, page_size=8192)
    ws.check_flash_workspace(target, flash, icache_sync=True)
    with pytest.raises(FlashError, match="active I-cache") as failure:
        ws.check_flash_workspace(target, flash)
    assert failure.value.details['region'] == 6
    assert target.regs[ws.MPU_RNR] == 5


@pytest.mark.parametrize('unknown,valid,reason', [
    (0, 7, None),              # Known higher region covers the whole FLM.
    (7, 0, 'mpu_layout'),      # Unknown higher region might cover it.
])
def test_misaligned_region_is_resolved_at_its_own_priority(unknown, valid, reason):
    target = Target()
    target.banks[valid] = BASE, region()
    target.banks[unknown] = BASE + 0x600, region()
    flash = flash_region(target)
    if reason:
        with pytest.raises(FlashError) as failure:
            ws.check_flash_workspace(target, flash)
        assert failure.value.details['reason'] == reason
        assert failure.value.details['region'] == unknown
    else:
        ws.check_flash_workspace(target, flash)


def test_unknown_bank_affects_only_hole_in_higher_priority_coverage():
    target = Target()
    target.banks[1] = BASE + 0x20, region()
    target.banks[2] = BASE, region(subregions=1 << 4)
    with pytest.raises(FlashError) as failure:
        ws.check_flash_workspace(target, flash_region(target))
    assert failure.value.details['reason'] == 'mpu_layout'
    assert failure.value.details['address'] == BASE + 0x800
    assert failure.value.details['region'] == 1


@pytest.mark.parametrize('ccr, sync, expected', [
    (ws.IC, False, 'icache'), (ws.IC, True, None), (ws.DC, True, 'dcache'), (0, False, None),
])
def test_default_sram_caches(ccr, sync, expected):
    target = Target()
    target.regs.update({ws.MPU_CTRL: 0, ws.CCR: ccr})
    if expected:
        with pytest.raises(FlashError) as failure:
            ws.check_flash_workspace(target, flash_region(target), icache_sync=sync)
        assert failure.value.details['reason'] == expected
    else:
        ws.check_flash_workspace(target, flash_region(target), icache_sync=sync)
    assert not target.writes


def test_shared_normal_memory_and_siwt():
    target = Target()
    target.banks[2] = BASE, region(tex=0, cb=3, shared=True)
    target.regs[ws.CCR] = ws.DC | ws.IC
    ws.check_flash_workspace(target, flash_region(target))
    target.regs[ws.CACR] = 1
    with pytest.raises(FlashError, match="active D-cache"):
        ws.check_flash_workspace(target, flash_region(target))


def test_enabled_tcm_bypasses_cache_but_enforces_mpu_permissions():
    base = 0x20000000
    target = Target(base)
    flash = flash_region(target, base)
    target.regs.update({ws.CCR: ws.IC | ws.DC, ws.DTCMCR: (3 << 3) | 1})
    target.banks[1] = base, region(tex=0, cb=3)
    ws.check_flash_workspace(target, flash)
    target.banks[2] = base + 0x800, region(0x100, xn=True)
    with pytest.raises(FlashError, match="execute-never"):
        ws.check_flash_workspace(target, flash)


def test_selector_restored_after_transport_failure(monkeypatch):
    target = Target()
    read = target.read32
    def broken_read(addr):
        if addr == ws.MPU_RASR and target.regs[ws.MPU_RNR] == 3:
            raise IOError("lost ACK")
        return read(addr)
    monkeypatch.setattr(target, "read32", broken_read)
    with pytest.raises(FlashError, match="lost ACK"):
        ws.check_flash_workspace(target, flash_region(target))
    assert target.writes == [0, 1, 2, 3, 5]


@pytest.mark.parametrize('change', [
    {'analyzer_supported': True}, {'end_stack': None}, {'static_base': BASE},
    {'page_buffers': [BASE + 0x80]}, {'pc_program_page': BASE + 0x8110},
])
def test_unsupported_layout_stops_before_mpu_selection(change):
    target = Target()
    flash = flash_region(target)
    flash.flash_algo.update(change)
    with pytest.raises(FlashError):
        ws.check_flash_workspace(target, flash)
    assert not target.writes

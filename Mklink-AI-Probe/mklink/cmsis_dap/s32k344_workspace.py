"""Initialize missing ECC in the S32K344 supplier FLM allocation using a 64-bit eDMA transfer."""
import hashlib
import io
import time

from .errors import FlashError, FlashErrorCode
from .flash_workspace import CCR, DC, _workspace
from .pyocd_runtime import import_pyocd_attr
from .s32k3_flm import CODE_SHA256, DATA_SHA256, CODE_START


# Keil S32K3xx_DFP 1.0.1 RAMInitialize, partition 1 and eDMA0 channel 0.
CLK, STAT, CONF, UPD, KEY = 0x402dc330, 0x402dc310, 0x402dc300, 0x402dc304, 0x402dc000
CSR, ES, TCD = 0x40210000, 0x40210004, 0x40210020
DONE, ACTIVE, GATES = 1 << 30, 1 << 31, 0x18


def _require(condition, message):
    if not condition:
        raise FlashError(FlashErrorCode.CONNECT_FAIL, "S32K344 FLM SRAM: " + message)


def _clock(target, value):
    _require(target.read32(CONF) & 1 and not target.read32(UPD) & 1, "时钟切换尚未就绪")
    target.write32(CLK, value)
    target.write32(UPD, 1)
    target.write32(KEY, 0x5af0)
    target.write32(KEY, 0xa50f)
    target.flush()
    until = time.monotonic() + .25
    while target.read32(UPD) & 1 or target.read32(STAT) & GATES != value & GATES:
        _require(time.monotonic() < until, "eDMA 时钟状态未确认")
        time.sleep(.001)


def prepare_workspace(target, flash):
    flm = getattr(getattr(flash, "region", None), "flm", None)
    source = getattr(getattr(flm, "elf", None), "_file", None)
    if not isinstance(source, io.BytesIO) or hashlib.sha256(source.getbuffer()).hexdigest() not in (CODE_SHA256, DATA_SHA256):
        return
    # Only touch doublewords covering code, static data, stack or page buffers.
    spans = sorted((s.start & ~7, (s.end + 7) & ~7) for s in _workspace(flash))
    _require(all(0x20400000 <= lo < hi <= 0x20410000 for lo, hi in spans), "工作区超出已验证的 SRAM0 区间")
    transfer_fault = import_pyocd_attr("pyocd.core.exceptions", "TransferFaultError")
    missing = []
    for lo, hi in spans:
        for addr in range(lo, hi, 1024):
            end = min(addr + 1024, hi)
            try:
                data = target.read_memory_block8(addr, end - addr)
                _require(len(data) == end - addr, "读取工作区长度不符")
            except transfer_fault:
                if missing and addr <= missing[-1][1]:
                    missing[-1] = (missing[-1][0], max(end, missing[-1][1]))
                else:
                    missing.append((addr, end))
    if not missing:
        return
    _require(target.selected_core.ap.address.apsel == 4 and target.read32(0x40290004) >> 16 == 0x2d58,
             "目标型号或 AP4 已改变")
    _require(target.selected_core.get_state().name == "HALTED" and not target.read32(CCR) & DC,
             "eDMA 初始化需要内核已暂停且 D-cache 已关闭")
    expected = bytes(target.read_memory_block8(CODE_START, 8))
    _require(len(expected) == 8, "无法确认 eDMA 源地址")
    gates = target.read32(CLK)
    _require(not (gates | target.read32(STAT)) & GATES, "应用正在使用 eDMA 时钟，无法独占通道")
    _clock(target, gates | GATES)
    saved = None
    in_flight = False
    try:
        _require(not target.read32(CSR) & (ACTIVE | DONE | 7) and target.read32(ES) == 0,
                 "eDMA 通道忙或带有未处理的状态")
        descriptor = [target.read32(TCD + i) for i in range(0, 32, 4)]
        _require(not descriptor[-1] & 1, "eDMA 描述符已启动")
        saved = descriptor
        for addr, end in missing:
            size = end - addr
            words = [CODE_START, 0x03030000, size, 0, addr, 0x10008, (-size) & 0xffffffff, 0x10000]
            for i, word in enumerate(words):
                target.write32(TCD + 4*i, word)
            target.flush()
            _require(all(target.read32(TCD + 4*i) == word for i, word in enumerate(words)), "描述符回读不符")
            in_flight = True
            target.write16(TCD + 28, 1)
            target.flush()
            until = time.monotonic() + .5
            while True:
                status = target.read32(CSR)
                _require(target.read32(ES) == 0, "eDMA 返回错误，传输结果未确认")
                if status & DONE and not status & ACTIVE:
                    break
                _require(time.monotonic() < until, "eDMA 传输结果未确认")
                time.sleep(.001)
            in_flight = False
            target.write32(CSR, DONE)
            target.flush()
            _require(not target.read32(CSR) & (DONE | ACTIVE), "eDMA 完成状态未清除")
            _require(bytes(target.read_memory_block8(addr, size)) == expected * (size // 8),
                     f"0x{addr:08X} 工作区回读不符")
    finally:
        # Never reconfigure or stop an engine whose transfer could still be active.
        if not in_flight:
            if saved is not None:
                for i, word in enumerate(saved):
                    target.write32(TCD + 4*i, word)
                target.flush()
                _require(all(target.read32(TCD + 4*i) == word for i, word in enumerate(saved)), "描述符恢复未确认")
            _clock(target, gates)

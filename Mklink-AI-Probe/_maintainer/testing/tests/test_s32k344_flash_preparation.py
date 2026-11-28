import hashlib
import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pyocd.core.exceptions import TransferFaultError
from pyocd.core.target import Target
from pyocd.coresight.cortex_m import CortexM as CM

from mklink.cmsis_dap import flash_thread, profile_reset, s32k344_workspace as ecc
from mklink.cmsis_dap.errors import FlashError
from mklink.cmsis_dap.target_attach import ProfileAttachDelegate
from mklink.profiles import resolve_attach_profile


@pytest.mark.parametrize("failure", [None, "lost reset ACK", "wrong profile", "handler", "wrong thumb", "PSP"])
def test_single_reset_catch_and_rebind(monkeypatch, failure):
    core = Mock()
    core.ap.address.apsel = 4
    core.get_state.return_value = Target.State.HALTED
    reg = {CM.DEMCR: 0x1000000, CM.DFSR: CM.DFSR_VCATCH, CM.DHCSR: CM.S_HALT}
    core.read32.side_effect = reg.__getitem__
    def write(addr, value):
        reg[addr] = (reg[addr] & ~value) if addr == CM.DFSR else value
    core.write32.side_effect = write
    core.read_core_registers_raw.return_value = {
        "handler": [0x1000067, 4], "PSP": [0x1000000, 2], "wrong thumb": [0, 0]
    }.get(failure, [0x1000000, 0])
    session = Mock()
    session.target.selected_core = core
    profile = resolve_attach_profile("S32K344")
    def reset():
        assert reg[CM.DEMCR] & 1 and reg[CM.DFSR] == 0
        reg.update({CM.DFSR: CM.DFSR_VCATCH, CM.DHCSR: CM.S_HALT | CM.S_RESET_ST})
        if failure == "lost reset ACK":
            raise OSError(failure)
    command = Mock(side_effect=reset)
    monkeypatch.setattr(profile_reset, "reset_command", lambda *a, **kw: ("FunctionalReset", command))
    bind = Mock(side_effect=OSError(failure) if failure == "wrong profile" else None)
    monkeypatch.setattr(ProfileAttachDelegate, "rebind_after_reset", bind)
    def run():
        flash_thread.catch_flash_reset(session, profile, "software", {"ipsr": 103, "control": 4})
    if failure:
        with pytest.raises(FlashError) as error:
            run()
        assert error.value.details["reset_outcome"] == ("unknown" if failure == "lost reset ACK" else "acknowledged")
    else:
        run()
    command.assert_called_once()
    assert bind.call_count == int(failure != "lost reset ACK")
    assert bool(reg[CM.DEMCR] & 1) == (failure in ("lost reset ACK", "wrong profile"))
    core.resume.assert_not_called()


@pytest.mark.parametrize("failure", [None, "readable", "busy", "wrong-part", "unknown-start", "outside"])
def test_ecc_is_limited_to_the_unreadable_flm_allocation(monkeypatch, failure):
    start = 0x2040e800
    span = SimpleNamespace(start=start, end=start + 1024)
    if failure == "outside":
        span.end = 0x20410008
    monkeypatch.setattr(ecc, "_workspace", lambda f: [span])
    monkeypatch.setattr(ecc, "CODE_SHA256", hashlib.sha256(b"FLM").hexdigest())
    flash = SimpleNamespace(region=SimpleNamespace(flm=SimpleNamespace(elf=SimpleNamespace(_file=io.BytesIO(b"FLM")))))
    t = Mock()
    t.selected_core.ap.address.apsel = 4
    t.selected_core.get_state.return_value.name = "HALTED"
    regs = {0x40290004: 0x2d380000 if failure == "wrong-part" else 0x2d580000,
            ecc.CSR: 0, ecc.ES: 0, ecc.CLK: ecc.GATES if failure == "busy" else 0,
            ecc.STAT: 0, ecc.CCR: 0, ecc.CONF: 1, ecc.UPD: 0}
    result = []
    def read(addr, size):
        if addr == ecc.CODE_START:
            return bytes(range(8))
        assert (addr, size) == (start, 1024)
        if not result and failure != "readable":
            raise TransferFaultError()
        return bytes(range(8)) * 128
    t.read_memory_block8.side_effect = read
    t.read32.side_effect = lambda addr: regs.get(addr, 0)
    def write(addr, value):
        if addr == ecc.CSR:
            regs[addr] &= ~value
        elif addr == ecc.KEY and value == 0xa50f:
            regs[ecc.UPD], regs[ecc.STAT] = 0, regs[ecc.CLK]
        else:
            regs[addr] = value
    t.write32.side_effect = write
    def launch(addr, value):
        assert (addr, value) == (ecc.TCD + 28, 1)
        result.append((regs[ecc.TCD + 16], regs[ecc.TCD + 8]))
        if failure == "unknown-start":
            raise OSError("lost DMA start ACK")
        regs[ecc.CSR] = ecc.DONE
    t.write16.side_effect = launch
    if failure not in (None, "readable"):
        with pytest.raises((FlashError, OSError)):
            ecc.prepare_workspace(t, flash)
    else:
        ecc.prepare_workspace(t, flash)
    assert result == ([(start, 1024)] if failure in (None, "unknown-start") else [])
    if failure in ("outside", "readable", "busy", "wrong-part"):
        t.write32.assert_not_called()
    elif failure == "unknown-start":
        assert regs[ecc.CLK] == ecc.GATES
    else:
        assert not regs[ecc.CLK] and all(not regs[ecc.TCD + i] for i in range(0, 32, 4))

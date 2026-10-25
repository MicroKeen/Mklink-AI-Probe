"""STM32H7 dual-core Pack compatibility: program both banks with CM7.

pyOCD 0.44 merges algorithm elements by Flash range before considering Pname.
The later CM4 entry then supplies CM7 with CM4-only algorithm RAM. Select the
CM7 definition BEFORE this lossy merge, without modifying the vendor archive.
Only the four specified device families use this execution policy.
"""
from __future__ import annotations

import re
import time
import json
import logging
from datetime import datetime, timezone
from threading import RLock

_LOCK = RLock()
_PART = re.compile(r"^stm32h7(?:45|47|55|57)[a-z0-9]+$", re.I)
_LOG = logging.getLogger(__name__)
_DHCSR = 0xE000EDF0
_DBG_CR_APB = 0xE00E1004
_DBG_CR_AXI = 0x5C001004
# Vendor SVD/OpenOCD: D1/D2 sleep/stop/standby debug, D1/D3 debug clocks.
# DFP 4.1.3 defaults DbgMCU_CR to 7, leaving CM4's D2 low-power bits clear.
_FLASH_DEBUG_MASK = 0x0060003F


def _debug_access(target):
    for ap in getattr(target, "aps", {}).values():
        if getattr(ap.address, "apsel", None) == 2:
            return ap, _DBG_CR_APB
    return target.selected_core.ap, _DBG_CR_AXI


def _snapshot(target, stage, started):
    """Best-effort read-only evidence; failure to read is itself diagnostic."""
    def read(reader, address):
        try:
            return f"0x{int(reader.read32(address)):08X}"
        except Exception as exc:
            return f"unavailable ({type(exc).__name__}: {exc})"

    result = {"at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
              "stage": stage, "elapsed_ms": round((time.monotonic() - started) * 1000),
              "cores": []}
    for core in target.cores.values():
        try:
            state = core.get_state().name
        except Exception as exc:
            state = f"unavailable ({type(exc).__name__}: {exc})"
        result["cores"].append({"core": core.node_name, "ap": core.ap.address.apsel,
                                "state": state, "DHCSR": read(core.ap, _DHCSR)})
    reader, address = _debug_access(target)
    result["DBGMCU_CR"] = read(reader, address)
    # Read status only. Never set BOOT_C2, change option bytes or wake CM4 by
    # running an unverified application to make a failed halt look successful.
    ap = target.selected_core.ap
    for name, address in (("RCC_CR", 0x58024400), ("RCC_GCR", 0x580244A0),
                          ("PWR_CPUCR", 0x58024810)):
        result[name] = read(ap, address)
    return result


def _wait_halted(core, State):
    deadline = time.monotonic() + 1.0
    while True:
        state = core.get_state()
        if state == State.HALTED:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(f"{core.node_name}/AP{core.ap.address.apsel} did not halt "
                               f"within 1000ms (state={state.name})")
        time.sleep(0.01)


def prepare_flash(target, *, hardware_reset=False) -> None:
    """Keep D2 debug alive and catch CM4 BEFORE a whole-system reset.

    CM4 can enter D2 Stop in the Cube dual-core boot handshake while CM7 is
    reset-caught. A late CM4 halt alone cannot reliably recover that state.
    Only volatile debug controls are changed; no boot/option/clock-tree writes.
    """
    bind_cm7(target)
    core = secondary_core(target)
    from .pyocd_runtime import import_pyocd_attr
    Target = import_pyocd_attr("pyocd.core.target", "Target")
    started = time.monotonic()
    stage = "debug-domain-setup"
    catch = None
    error = None
    try:
        _LOG.info("H7 flash preparation: %s", json.dumps(_snapshot(target, "before", started)))
        ap, address = _debug_access(target)
        value = ap.read32(address)
        ap.write32(address, value | _FLASH_DEBUG_MASK)
        if ap.read32(address) & _FLASH_DEBUG_MASK != _FLASH_DEBUG_MASK:
            raise RuntimeError("DBGMCU_CR D1/D2 debug configuration did not latch")
        stage = "CM4-reset-catch"
        catch = core.get_vector_catch()
        core.set_vector_catch(catch | Target.VectorCatch.CORE_RESET)
        core.halt()  # Enable halting debug before reset; confirmation follows reset.
        stage = "system-reset" if not hardware_reset else "hardware-reset"
        kind = Target.ResetType.HARDWARE if hardware_reset else Target.ResetType.SYSTEM
        target.reset_and_halt(kind)
        stage = "CM7-halt"
        _wait_halted(target.selected_core, Target.State)
        stage = "CM4-halt"
        halt_other_cores(target)
    except Exception as exc:
        error = exc
        evidence = _snapshot(target, stage, started)
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        _LOG.error("H7 flash preparation failed: %s", json.dumps(evidence))
        raise RuntimeError(f"STM32H7 {stage}: {exc}; Flash was not erased. "
                           "Check CM4 boot/low-power state and NRST; export diagnostics. "
                           + json.dumps(evidence)) from exc
    finally:
        if catch is not None:
            try:
                core.set_vector_catch(catch)
            except Exception as exc:
                _LOG.exception("Could not restore CM4 reset catch")
                if error is None:
                    evidence = _snapshot(target, "CM4-reset-catch-restore", started)
                    evidence["error"] = f"{type(exc).__name__}: {exc}"
                    _LOG.error("H7 flash preparation failed: %s", json.dumps(evidence))
                    raise RuntimeError("STM32H7 CM4 reset-catch restore failed; "
                                       f"Flash was not erased: {exc}. " + json.dumps(evidence)) from exc


def uses_cm7_flash(part: str) -> bool:
    return bool(_PART.fullmatch(str(part)))


def install_pack_compatibility() -> None:
    from .pyocd_runtime import import_pyocd_attr

    cls = import_pyocd_attr("pyocd.target.pack.cmsis_pack", "CmsisPackDescription")
    with _LOCK:
        original = cls._extract_algos
        if getattr(original, "_mklink_cm7_flash", False):
            return

        def extract(self):
            names = [state.element.get("Dvariant") or state.element.get("Dname", "")
                     for state in self._state_stack]
            if not any(uses_cm7_flash(name) for name in names):
                return original(self)

            # Preserve inheritance/overrides within one processor. Do not let
            # an explicit CM4 algorithm override its CM7 counterpart, even if
            # the vendor changes their XML order. Generic algorithms still work.
            def select(result, element):
                if element.get("style", "Keil").casefold() != "keil":
                    return
                if element.get("Pname", "CM7") != "CM7":
                    return
                key = (int(element.attrib["start"], 0), int(element.attrib["size"], 0))
                result[key] = element

            return self._extract_items("algos", select)

        extract._mklink_cm7_flash = True
        cls._extract_algos = extract


def bind_cm7(target) -> None:
    """Bind by Pack processor name AND AP, never by enumeration order alone."""
    matches = [core for core in target.cores.values()
               if core.node_name == "CM7" and getattr(core.ap.address, "apsel", None) == 0]
    if len(matches) != 1:
        raise RuntimeError("STM32H7 dual-core Flash requires an accessible CM7 on AP0; "
                           "check core boot configuration and connect under reset")
    target.selected_core = matches[0].core_number


def secondary_core(target):
    """Do not erase shared Flash while an undiscovered CM4 may still execute."""
    matches = [core for core in target.cores.values()
               if core.node_name == "CM4" and getattr(core.ap.address, "apsel", None) == 3]
    if len(matches) != 1:
        raise RuntimeError("STM32H7 dual-core Flash requires an accessible CM4 on AP3 "
                           "to stop both cores safely; check core boot/debug configuration")
    return matches[0]


def halt_other_cores(target) -> None:
    """Called only for an authorized erase/program, after resetting CM7."""
    bind_cm7(target)
    secondary_core(target)
    from .pyocd_runtime import import_pyocd_attr
    State = import_pyocd_attr("pyocd.core.target", "Target").State
    for core in target.cores.values():
        if core is target.selected_core:
            continue
        core.halt()
        _wait_halted(core, State)


def finish_system_reset(target) -> None:
    """Release CM4's debug halt only after a successful whole-system reset.

    Never use this after a core-only reset or a failed Flash operation: CM4's
    previous PC could refer to an application that has just been replaced.
    """
    from .pyocd_runtime import import_pyocd_attr
    State = import_pyocd_attr("pyocd.core.target", "Target").State
    core = secondary_core(target)
    if core.get_state() == State.HALTED:
        core.resume()
    if core.get_state() not in (State.RUNNING, State.SLEEPING):
        raise RuntimeError("STM32H7 CM4 did not start after system reset; "
                           "check boot configuration and NRST connection")

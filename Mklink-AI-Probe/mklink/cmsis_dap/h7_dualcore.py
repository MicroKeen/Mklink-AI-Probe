"""STM32H7 dual-core Pack compatibility: program both banks with CM7.

pyOCD 0.44 merges algorithm elements by Flash range before considering Pname.
The later CM4 entry then supplies CM7 with CM4-only algorithm RAM. Select the
CM7 definition BEFORE this lossy merge, without modifying the vendor archive.
Only the four specified device families use this execution policy.
"""
from __future__ import annotations

import re
import time
from threading import RLock

_LOCK = RLock()
_PART = re.compile(r"^stm32h7(?:45|47|55|57)[a-z0-9]+$", re.I)


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
        deadline = time.monotonic() + 1.0
        while core.get_state() != State.HALTED:
            if time.monotonic() >= deadline:
                raise RuntimeError("STM32H7 secondary core did not halt; Flash was not erased")
            time.sleep(0.01)


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

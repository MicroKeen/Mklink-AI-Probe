"""Acquire a privileged Thread/MSP context for an admitted Cortex-M Flash operation."""
import time

from .errors import FlashError, FlashErrorCode


def acquire_flash_thread(core, state_type, *, allow_resume):
    """Briefly let an originally running handler return naturally before launching an FLM."""
    state = core.get_state()
    running = state in (state_type.RUNNING, state_type.SLEEPING)
    evidence = {"initial_state": state.name, "attempts": 0}
    if not running and state != state_type.HALTED:
        raise FlashError(FlashErrorCode.CONNECT_FAIL, "Core state does not permit Flash preparation", evidence)

    def halt():
        core.halt()
        deadline = time.monotonic() + 1.0
        while core.get_state() != state_type.HALTED:
            if time.monotonic() >= deadline:
                raise FlashError(FlashErrorCode.CONNECT_FAIL, "Core did not confirm halt before Flash", evidence)
            time.sleep(0.005)

    if running:
        halt()
    # Vary the interval so a periodic ISR is not sampled at a fixed phase.
    windows = iter((0.002, 0.004, 0.007, 0.011, 0.017, 0.029, 0.043, 0.061))
    while True:
        xpsr, control = core.read_core_registers_raw(["xpsr", "control"])
        ipsr = xpsr & 0x1ff
        evidence.update(ipsr=ipsr, xpsr=xpsr, control=control)
        if xpsr & (1 << 24) and not ipsr and control in (0, 4):
            return evidence
        # Never resume an independently halted target or try to escape a fault handler.
        regular_handler = ipsr in (11, 14, 15) or 16 <= ipsr <= 255
        if not (allow_resume or running) or not regular_handler or not xpsr & (1 << 24) or control & ~7:
            break
        interval = next(windows, None)
        if interval is None:
            break
        evidence["attempts"] += 1
        core.resume()
        time.sleep(interval)
        halt()
    raise FlashError(
        FlashErrorCode.CONNECT_FAIL,
        f"Flash requires privileged Thumb Thread mode on MSP. Core is halted at IPSR={ipsr}, "
        f"CONTROL=0x{control:X}. Stop at a Thread-mode point and retry the selected Flash operation.",
        evidence,
    )

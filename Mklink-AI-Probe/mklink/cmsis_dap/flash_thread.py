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
        dict(evidence, reason="flash_thread_context"),
    )


def catch_flash_reset(session, profile, mode, before):
    """Catch one selected reset and prove its exception entry before admitting an FLM."""
    from .profile_reset import reset_command
    from .pyocd_runtime import import_pyocd_attr
    from .target_attach import ProfileAttachDelegate

    Target = import_pyocd_attr("pyocd.core.target", "Target")
    CM = import_pyocd_attr("pyocd.coresight.cortex_m", "CortexM")
    target = session.target
    core = target.selected_core
    evidence = dict(before, reset_mode=mode, reset_outcome="not_issued")
    catch_bit = CM.DEMCR_VC_CORERESET
    access_confirmed = True
    restore_catch = False
    try:
        name, command = reset_command(core, session.probe, mode, profile=profile, dp=target.dp, evidence=evidence)
        evidence["command"] = name
        if core.get_state() != Target.State.HALTED or core.ap.address.apsel != profile.mem_ap:
            raise ValueError("core or MEM-AP changed before reset catch")
        original = core.read32(CM.DEMCR)
        if not original & catch_bit:
            restore_catch = True
            core.write32(CM.DEMCR, original | catch_bit)
        core.write32(CM.DFSR, CM.DFSR_VCATCH)
        core.flush()
        if not core.read32(CM.DEMCR) & catch_bit or core.read32(CM.DFSR) & CM.DFSR_VCATCH:
            raise ValueError("could not arm a fresh reset vector catch")
        core.read32(CM.DHCSR)  # Clear the previous sticky reset indication.
        access_confirmed = False
        evidence["reset_outcome"] = "unknown"
        command()
        session.probe.flush()
        evidence["reset_outcome"] = "acknowledged"
        session.notify(Target.Event.POST_RESET, core)
        target.dp.post_reset_recovery()
        ProfileAttachDelegate.rebind_after_reset(profile, target.dp)
        if core is not target.selected_core or core.ap.address.apsel != profile.mem_ap:
            raise ValueError("core or MEM-AP changed following reset")
        access_confirmed = True
        deadline = time.monotonic() + 1
        saw_reset = False
        while True:
            status = core.read32(CM.DHCSR)
            saw_reset |= bool(status & CM.S_RESET_ST)
            if saw_reset and status & CM.S_HALT and core.read32(CM.DFSR) & CM.DFSR_VCATCH:
                break
            if time.monotonic() >= deadline:
                raise ValueError("no confirmed halt on the reset vector")
            time.sleep(.005)
        xpsr, control = core.read_core_registers_raw(["xpsr", "control"])
        if not xpsr & (1 << 24) or xpsr & 0x1ff or control not in (0, 4):
            raise ValueError(f"reset catch left IPSR={xpsr & 0x1ff}, CONTROL=0x{control:X}")
    except Exception as exc:
        raise FlashError(FlashErrorCode.CONNECT_FAIL,
                         f"{profile.name} Flash preparation stopped: {exc} (reset {evidence['reset_outcome']})",
                         evidence) from exc
    finally:
        # A lost ACK or unverified target must not receive another command.
        if restore_catch and not access_confirmed:
            evidence["reset_catch_restore"] = "unconfirmed"
        if restore_catch and access_confirmed:
            current = core.read32(CM.DEMCR)
            core.write32(CM.DEMCR, current & ~catch_bit)
            core.flush()
            if core.read32(CM.DEMCR) & catch_bit:
                raise FlashError(FlashErrorCode.CONNECT_FAIL, "Could not restore reset vector catch", evidence)

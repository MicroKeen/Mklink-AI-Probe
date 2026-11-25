"""Issue the selected Cortex-M reset without pyOCD polling the pre-reset core."""

from .pyocd_runtime import import_pyocd_attr
from . import s32k314_reset


_SYSTEM_RESET_HANDLERS = {"s32k314_functional": s32k314_reset}


def system_reset_handler(strategy, model, mem_ap):
    """Resolve only a shipped handler certified for the catalog's model and AP."""
    if strategy == "default":
        return None
    handler = _SYSTEM_RESET_HANDLERS.get(strategy) if isinstance(strategy, str) else None
    if handler is None or (model, mem_ap) != (handler.MODEL, handler.MEM_AP):
        raise ValueError(f"Unsupported online_system_reset {strategy!r} for {model} on AP{mem_ap}")
    return handler


def reset_command(core, probe, mode, *, profile, dp, evidence):
    """Resolve the active Pack sequence or the matching generic Cortex-M operation."""
    sequence = {
        "default": "ResetSystem",
        "software": "ResetSystem",
        "system": "ResetSystem",
        "core": "ResetProcessor",
        "hardware": "ResetHardware",
    }[mode]
    delegate = core.debug_sequence_delegate
    if delegate is not None:
        pname = core.node_name
        if mode in {"default", "software"}:
            sequence = delegate.default_reset_sequence(pname)
        if core.has_debug_sequence(sequence, pname=pname):
            def run_pack_sequence():
                if delegate.run_sequence(sequence, pname=pname) is None:
                    raise RuntimeError(f"Pack reset sequence {sequence} was disabled")
            return sequence, run_pack_sequence

    if sequence == "ResetSystem":
        handler = system_reset_handler(profile.online_system_reset, profile.name, profile.mem_ap)
        if handler is not None:
            return handler.prepare(dp, evidence)

    if sequence == "ResetHardware":
        return "nRESET", probe.reset
    cortex_m = import_pyocd_attr("pyocd.coresight.cortex_m", "CortexM")
    if sequence == "ResetSystem":
        mask = cortex_m.NVIC_AIRCR_SYSRESETREQ
        name = "SYSRESETREQ"
    elif sequence == "ResetProcessor":
        mask = cortex_m.NVIC_AIRCR_VECTRESET
        name = "VECTRESET"
    else:
        raise ValueError(f"The configured reset sequence {sequence!r} is unavailable")

    def write_aircr():
        core.write32(cortex_m.NVIC_AIRCR, cortex_m.NVIC_AIRCR_VECTKEY | mask)

    return name, write_aircr


def close_reset_transport(probe):
    # Session.close() would run board.uninit(), including callbacks and
    # breakpoint cleanup through the stale core. Only release the probe here.
    try:
        probe.disconnect()
    finally:
        probe.close()

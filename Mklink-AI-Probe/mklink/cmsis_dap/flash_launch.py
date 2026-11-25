"""Check the interrupt mask and synchronize uploaded code before a pyOCD FLM launch."""

from .errors import FlashError, FlashErrorCode
from .pyocd_runtime import import_pyocd_attr


def install_flash_launch_checks(target, core, flash):
    """Return a cleanup callback and whether instruction-cache sync is available."""
    Flash = import_pyocd_attr("pyocd.flash.flash", "Flash")
    if type(flash) is not Flash or flash.target is not target:
        return None, False
    invalidate = getattr(core, "invalidate_instruction_cache", None)
    has_sync = getattr(core, "has_cache", False) is True and callable(invalidate) and callable(core.flush)
    expected_ap = core.ap.address.apsel
    halted = import_pyocd_attr("pyocd.core.target", "Target").State.HALTED

    original_prepare = flash.prepare_target
    original_launch = flash._call_function
    overrides = {name: vars(flash)[name] for name in ("prepare_target", "_call_function")
                 if name in vars(flash)}
    sync_pending = True

    def prepare():
        nonlocal sync_pending
        # Flash.init() calls prepare_target immediately before every upload.
        original_prepare()
        sync_pending = True

    def launch(pc, *args, **kwargs):
        nonlocal sync_pending
        if target.selected_core is not core or core.ap.address.apsel != expected_ap:
            raise FlashError(FlashErrorCode.CONNECT_FAIL, "Selected core or MEM-AP changed before FLM launch")
        if core.get_state() != halted or core.read_core_register("primask") != 1:
            raise FlashError(FlashErrorCode.CONNECT_FAIL, "Cannot confirm halted core and PRIMASK=1 before FLM launch",
                             {"reason": "primask_launch", "pc": pc, "mem_ap": expected_ap})
        if sync_pending and has_sync:
            try:
                core.flush()
                invalidate()
                core.flush()
            except Exception as exc:
                raise FlashError(FlashErrorCode.CONNECT_FAIL,
                                 f"Instruction cache synchronization failed before FLM launch: {exc}",
                                 {"reason": "instruction_cache_sync", "pc": pc}) from exc
            sync_pending = False
        return original_launch(pc, *args, **kwargs)

    flash.prepare_target = prepare
    flash._call_function = launch

    def uninstall():
        for name in ("prepare_target", "_call_function"):
            if name in overrides:
                setattr(flash, name, overrides[name])
            else:
                delattr(flash, name)

    return uninstall, has_sync

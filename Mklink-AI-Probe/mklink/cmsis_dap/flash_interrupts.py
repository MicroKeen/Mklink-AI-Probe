"""Scope an application's interrupt mask to one admitted online FLM operation."""
from contextlib import contextmanager

from .errors import FlashError, FlashErrorCode
from .pyocd_runtime import import_pyocd_attr


@contextmanager
def mask_flash_interrupts(target, core):
    expected_ap = core.ap.address.apsel
    halted = import_pyocd_attr("pyocd.core.target", "Target").State.HALTED

    def check_halt():
        if target.selected_core is not core or core.ap.address.apsel != expected_ap:
            raise RuntimeError("selected core or MEM-AP changed")
        if core.get_state() != halted:
            raise RuntimeError("the selected core is not confirmed halted")

    def read_mask():
        value = core.read_core_register("primask")
        if type(value) is not int or value not in (0, 1):
            raise RuntimeError(f"invalid PRIMASK readback {value!r}")
        return value

    def set_mask(value):
        core.write_core_register("primask", value)
        core.flush()
        if read_mask() != value:
            raise RuntimeError(f"PRIMASK={value} was not confirmed")

    try:
        check_halt()
        saved = read_mask()
    except Exception as exc:
        raise FlashError(FlashErrorCode.CONNECT_FAIL, f"Cannot save PRIMASK before FLM launch: {exc}",
                         {"reason": "primask_save", "mem_ap": expected_ap}) from exc

    operation_error = None
    try:
        if saved != 1:
            try:
                set_mask(1)
            except Exception as exc:
                raise FlashError(FlashErrorCode.CONNECT_FAIL, f"Cannot mask interrupts before FLM launch: {exc}",
                                 {"reason": "primask_set", "mem_ap": expected_ap}) from exc
        yield
    except BaseException as exc:
        operation_error = exc
        raise
    finally:
        try:
            check_halt()
            if read_mask() != saved:
                set_mask(saved)
        except Exception as exc:
            details = {"reason": "primask_restore", "saved_primask": saved, "mem_ap": expected_ap}
            message = f"Application PRIMASK={saved} restoration is unconfirmed: {exc}"
            code = FlashErrorCode.CONNECT_FAIL
            if operation_error is not None:
                details["operation_error"] = str(operation_error)
                message = f"{operation_error}. {message}"
                if isinstance(operation_error, FlashError):
                    code = operation_error.code
                    details["operation_details"] = operation_error.details
            raise FlashError(code, message, details) from exc

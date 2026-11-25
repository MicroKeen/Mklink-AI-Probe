from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from mklink.cmsis_dap.errors import FlashError
from mklink.cmsis_dap.flash_interrupts import mask_flash_interrupts
from mklink.cmsis_dap.pyocd_runtime import import_pyocd_attr


class Core:
    def __init__(self, primask):
        self.State = import_pyocd_attr("pyocd.core.target", "Target").State
        self.state = self.State.HALTED
        self.ap = SimpleNamespace(address=SimpleNamespace(apsel=4))
        self.primask = primask
        self.events = []

    def get_state(self):
        return self.state

    def read_core_register(self, name):
        assert name == "primask"
        self.events.append(("read", self.primask))
        return self.primask

    def write_core_register(self, name, value):
        assert name == "primask"
        self.events.append(("write", value))
        self.primask = value

    def flush(self):
        self.events.append("flush")


def setup_core(primask):
    core = Core(primask)
    target = SimpleNamespace(selected_core=core)
    return target, core


@pytest.mark.parametrize("initial", [0, 1])
def test_interrupts_stay_masked_until_the_operation_finishes(initial):
    target, core = setup_core(initial)
    with mask_flash_interrupts(target, core):
        begin = list(core.events)
        assert core.primask == 1
        core.events.extend(["Init", "EraseSector", "ProgramPage", "Verify", "UnInit"])
    assert core.primask == initial
    writes = [event for event in core.events if isinstance(event, tuple) and event[0] == "write"]
    assert writes == ([("write", 1), ("write", 0)] if initial == 0 else [])
    if not initial:
        after_mask = begin[begin.index(("write", 1)) + 1:]
        assert after_mask.index("flush") < after_mask.index(("read", 1))
        after_restore = core.events[core.events.index(("write", 0)) + 1:]
        assert after_restore.index("flush") < after_restore.index(("read", 0))
        assert core.events.index("UnInit") < core.events.index(("write", 0))


def test_ignored_mask_write_stops_before_algorithm_and_does_not_retry():
    target, core = setup_core(0)
    core.write_core_register = Mock()  # Fake an acknowledged write that did not stick.
    run = Mock()
    with pytest.raises(FlashError):
        with mask_flash_interrupts(target, core):
            run()
    run.assert_not_called()
    assert core.write_core_register.call_args_list.count(call("primask", 1)) == 1


def test_safe_cleanup_restores_original_mask_and_propagates_operation_failure():
    target, core = setup_core(0)
    error = OSError("EraseSector returned No ACK")
    operation = Mock(side_effect=error)
    with pytest.raises(OSError) as caught:
        with mask_flash_interrupts(target, core):
            operation()
    operation.assert_called_once_with()
    assert caught.value is error
    assert core.primask == 0 and core.events.count(("write", 0)) == 1


def test_invalid_initial_mask_stops_before_target_write():
    target, core = setup_core(0xffffffff)
    with pytest.raises(FlashError) as caught:
        with mask_flash_interrupts(target, core):
            pytest.fail("FLM admitted with invalid PRIMASK readback")
    assert caught.value.details["reason"] == "primask_save"
    assert not any(isinstance(event, tuple) and event[0] == "write" for event in core.events)


@pytest.mark.parametrize("problem", ["core-changed", "core-running"])
def test_entry_rejects_mismatched_core_or_active_cpu_before_writing(problem):
    target, core = setup_core(0)
    if problem == "core-changed":
        target.selected_core = Core(0)
    else:
        core.state = core.State.RUNNING
    with pytest.raises(FlashError):
        with mask_flash_interrupts(target, core):
            pytest.fail("FLM admitted on a different or running core")
    assert not any(isinstance(event, tuple) and event[0] == "write" for event in core.events)


@pytest.mark.parametrize("problem", ["state-read-failed", "running", "core-changed", "ap-changed"])
def test_uncertain_stop_leaves_primask_and_preserves_operation_error(problem):
    target, core = setup_core(0)
    run = Mock(side_effect=OSError("No ACK after ProgramPage dispatch"))
    with pytest.raises(FlashError) as caught:
        with mask_flash_interrupts(target, core):
            if problem == "state-read-failed":
                core.get_state = Mock(side_effect=OSError("No ACK reading state"))
            elif problem == "running":
                core.state = core.State.RUNNING
            elif problem == "core-changed":
                target.selected_core = Core(0)
            else:
                core.ap = SimpleNamespace(address=SimpleNamespace(apsel=7))
            run()
    run.assert_called_once_with()
    assert core.primask == 1 and ("write", 0) not in core.events
    assert caught.value.details["reason"] == "primask_restore"
    assert caught.value.details["saved_primask"] == 0
    assert "No ACK after ProgramPage dispatch" in str(caught.value.details["operation_error"])


def test_restore_no_ack_is_reported_without_second_write_or_algorithm_launch():
    target, core = setup_core(0)
    run = Mock()
    original_write = core.write_core_register

    def apply_write_then_drop_response(name, value):
        original_write(name, value)
        if not value:
            raise OSError("No ACK restoring PRIMASK")

    core.write_core_register = apply_write_then_drop_response
    with pytest.raises(FlashError) as caught:
        with mask_flash_interrupts(target, core):
            run()
    run.assert_called_once_with()
    assert core.events.count(("write", 0)) == 1
    assert caught.value.details["reason"] == "primask_restore"
    assert caught.value.details["saved_primask"] == 0

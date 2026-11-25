from enum import Enum, auto
from itertools import repeat
from unittest.mock import Mock

import pytest

from mklink.cmsis_dap import flash_thread
from mklink.cmsis_dap.errors import FlashError


class State(Enum):
    HALTED = auto()
    RUNNING = auto()
    SLEEPING = auto()


def fake_core(initial, samples):
    core = Mock()
    core.get_state.side_effect = lambda: core.state
    core.halt.side_effect = lambda: setattr(core, "state", State.HALTED)
    core.resume.side_effect = lambda: setattr(core, "state", State.RUNNING)
    core.read_core_registers_raw.side_effect = samples
    core.state = initial
    return core


@pytest.mark.parametrize("initial,observed", [(State.RUNNING, False), (State.HALTED, True)])
def test_waits_for_normal_irq_return_before_programming(monkeypatch, initial, observed):
    monkeypatch.setattr(flash_thread.time, "sleep", lambda _: None)
    core = fake_core(initial, [(0x21000070, 0), (0x61000000, 4)])
    result = flash_thread.acquire_flash_thread(core, State, allow_resume=observed)
    assert result["attempts"] == 1 and result["ipsr"] == 0 and result["control"] == 4
    assert core.state == State.HALTED
    core.resume.assert_called_once_with()
    core.write_core_registers_raw.assert_not_called()


@pytest.mark.parametrize("xpsr,control,observed", [
    (0x21000070, 0, False), (0x21000003, 0, True), (0x21000000, 2, True),
    (0xffffffff, 0xffffffff, True), (0x21000000, 0x80000000, True),
])
def test_respects_independently_halted_or_unsafe_context(xpsr, control, observed):
    core = fake_core(State.HALTED, [(xpsr, control)])
    with pytest.raises(FlashError) as exc:
        flash_thread.acquire_flash_thread(core, State, allow_resume=observed)
    assert exc.value.details["xpsr"] == xpsr
    core.resume.assert_not_called()


def test_persistent_interrupt_is_bounded_and_stays_halted(monkeypatch):
    monkeypatch.setattr(flash_thread.time, "sleep", lambda _: None)
    core = fake_core(State.RUNNING, repeat((0x21000070, 0)))
    with pytest.raises(FlashError) as exc:
        flash_thread.acquire_flash_thread(core, State, allow_resume=False)
    assert exc.value.details["attempts"] == core.resume.call_count == 8
    assert core.state == State.HALTED


def test_uncertain_resume_is_not_issued_again():
    core = fake_core(State.HALTED, [(0x21000070, 0)])
    core.resume.side_effect = OSError("No ACK")
    with pytest.raises(OSError, match="No ACK"):
        flash_thread.acquire_flash_thread(core, State, allow_resume=True)
    core.resume.assert_called_once_with()
    core.halt.assert_not_called()

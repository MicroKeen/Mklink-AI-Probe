"""Final online reset with a software probe; the old AP cannot be used after reset."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pyocd.core.target import Target
from pyocd.coresight.cortex_m import CortexM
from pyocd.utility.sequencer import CallSequence

from mklink.cmsis_dap.backend import PyOcdBackend
from mklink.cmsis_dap.errors import FlashError, FlashErrorCode
from mklink.cmsis_dap.jobs import OnlineFlashJobManager
from mklink.cmsis_dap.models import JobRequest, JobState
from mklink.cmsis_dap.target_attach import ProfileAttachDelegate
from mklink.remote.online_flash_api import OnlineFlashServices, create_online_flash_router
from mklink.remote.resource_manager import ResourceManager


AP6_IDR = 0x060000FC
AP6_CTL = 0x06000004
EXPECTED_IDR = 0x001C0030
# Keil.S32K3xx_DFP 1.0.1, ResetSystem -> FunctionalReset.
FUNCTIONAL_RESET = (0x00400B00, 0x00400B20, 0x00400B00, 0x00400000)


def reset_transfers(step_count):
    expected = [call.read_ap(AP6_IDR)]
    for value in FUNCTIONAL_RESET[:step_count]:
        expected.extend((call.write_ap(AP6_CTL, value), call.flush()))
    return expected


@pytest.fixture
def rig(monkeypatch):
    probe = Mock(spec=["unique_id", "flush", "reset", "disconnect", "close"])
    probe.unique_id = "fixture-probe"
    sessions = []
    bindings = []
    def bind(delegate, dp):
        bindings.append(dp)
        delegate.bound = True
    monkeypatch.setattr(ProfileAttachDelegate, "_bind", bind)

    def open_session(selected_probe, options):
        assert selected_probe is probe
        order = []
        core = SimpleNamespace(ap=SimpleNamespace(address=SimpleNamespace(apsel=4)),
                               core_registers=SimpleNamespace(by_name={"xpsr": object()}),
                               debug_sequence_delegate=None, node_name="Cortex-M7_0",
                               get_state=Mock(side_effect=lambda: order.append("observe") or Target.State.RUNNING),
                               halt=Mock(side_effect=lambda: order.append("halt")), resume=Mock(),
                               write32=Mock(), has_debug_sequence=Mock(return_value=True))
        dp = Mock(spec=["read_ap", "write_ap", "flush"])
        dp.read_ap.return_value = EXPECTED_IDR
        target = SimpleNamespace(dp=dp, selected_core=core,
                                 get_state=Mock(return_value=Target.State.RUNNING))
        session = SimpleNamespace(target=target, probe=probe, options=options,
                                  delegate=None, close=Mock(), order=order)
        def open_target():
            seq = CallSequence(("dp_init", lambda: order.append("dp")),
                               ("discovery", lambda: order.append("discover")),
                               ("halt_on_connect", lambda: core.halt() if options["connect_mode"] == "halt" else None))
            session.delegate.will_init_target(target, seq)
            seq.invoke()
        session.open = open_target
        sessions.append(session)
        return session

    power = Mock()
    backend = PyOcdBackend(session_factory=open_session, probe_provider=lambda: [probe], power_cycle=power)
    backend.connect(probe, "S32K314", 1_000_000)
    return SimpleNamespace(backend=backend, probe=probe, sessions=sessions, power=power, bindings=bindings)


@pytest.mark.parametrize("mode", ["default", "software", "system", "hardware", "core", "power-cycle"])
def test_final_reset_rebinds_same_probe_before_status_and_leaves_old_core_alone(rig, mode):
    old = rig.sessions[0]
    if mode == "power-cycle":
        rig.backend._reset_voltage_mv = 3300
    rig.backend.reset_run(mode)
    rig.backend.disconnect()
    old.target.get_state.assert_not_called()
    old.close.assert_not_called()
    assert len(rig.sessions) == 2 and rig.bindings == [s.target.dp for s in rig.sessions]
    fresh = rig.sessions[1]
    assert fresh.options["connect_mode"] == "attach"
    assert old.order == ["dp", "discover", "observe", "halt"]
    assert fresh.order == ["dp", "discover"]
    fresh.target.get_state.assert_called_once_with()
    fresh.close.assert_not_called()
    assert rig.probe.disconnect.call_count == rig.probe.close.call_count == 2
    if mode == "hardware":
        rig.probe.reset.assert_called_once_with()
    elif mode == "power-cycle":
        rig.power.assert_called_once_with("fixture-probe", 3300)
    elif mode == "core":
        old.target.selected_core.write32.assert_called_once_with(
            CortexM.NVIC_AIRCR, CortexM.NVIC_AIRCR_VECTKEY | CortexM.NVIC_AIRCR_VECTRESET)
    else:
        assert old.target.dp.mock_calls == reset_transfers(4)
        old.target.selected_core.write32.assert_not_called()
    if mode in {"hardware", "power-cycle", "core"}:
        assert not old.target.dp.mock_calls


@pytest.mark.parametrize(("mode", "expected"), [("system", "ResetSystem"), ("software", "VendorReset"),
                                              ("default", "VendorReset"), ("hardware", "ResetHardware"),
                                              ("core", "ResetProcessor")])
def test_active_pack_reset_sequence_runs_once_on_the_bound_processor(rig, mode, expected):
    core = rig.sessions[0].target.selected_core
    delegate = Mock(spec=["run_sequence", "default_reset_sequence"])
    delegate.default_reset_sequence.return_value = "VendorReset"
    core.debug_sequence_delegate = delegate
    rig.backend.reset_run(mode)
    delegate.run_sequence.assert_called_once_with(expected, pname="Cortex-M7_0")
    core.write32.assert_not_called()
    assert not rig.sessions[0].target.dp.mock_calls
    rig.probe.reset.assert_not_called()


@pytest.mark.parametrize("failure", ["write", "ack", "release", "pack", "reattach", "halted"])
def test_final_reset_failure_preserves_evidence_and_never_reissues(rig, failure):
    old = rig.sessions[0]
    core = old.target.selected_core
    if failure == "write":
        old.target.dp.write_ap.side_effect = OSError("lost transfer")
    elif failure == "ack":
        rig.probe.flush.side_effect = [None, OSError("lost ACK")]
    elif failure == "release":
        rig.probe.disconnect.side_effect = OSError("could not release")
    elif failure == "pack":
        core.debug_sequence_delegate = Mock()
        core.debug_sequence_delegate.run_sequence.side_effect = OSError("partial sequence")
    else:
        original = rig.backend._session_factory
        def reconnect(probe, options):
            session = original(probe, options)
            if failure == "reattach":
                session.open = Mock(side_effect=FlashError(FlashErrorCode.CONNECT_FAIL, "AP signature", {"step": 7}))
            else:
                session.target.get_state.return_value = Target.State.HALTED
            return session
        rig.backend._session_factory = reconnect
    with pytest.raises(FlashError) as failed:
        rig.backend.reset_run("system")
    assert failed.value.code is FlashErrorCode.RESET_FAIL
    evidence = failed.value.details
    assert (evidence["profile"], evidence["mem_ap"]) == ("S32K314", 4)
    assert evidence["reset_outcome"] == ("unknown" if failure in {"ack", "write", "pack"} else "acknowledged")
    assert evidence["run_state"] == ("HALTED" if failure == "halted" else "unconfirmed")
    assert len(rig.sessions) == (2 if failure in {"reattach", "halted"} else 1)
    if failure == "reattach":
        assert evidence["cause"] == {"step": 7}
    if failure == "pack":
        core.debug_sequence_delegate.run_sequence.assert_called_once_with("ResetSystem", pname=core.node_name)
        assert not old.target.dp.mock_calls
    elif failure == "write":
        assert old.target.dp.mock_calls == [call.read_ap(AP6_IDR), call.write_ap(AP6_CTL, FUNCTIONAL_RESET[0])]
        assert evidence["step"] == 1 and evidence["acknowledged_steps"] == 0
    else:
        assert old.target.dp.mock_calls == reset_transfers(4)
        assert evidence["step"] == evidence["acknowledged_steps"] == 4
    core.write32.assert_not_called()
    old.target.get_state.assert_not_called()
    old.close.assert_not_called()
    rig.backend.disconnect()
    assert rig.probe.close.call_args_list[0] == call()


@pytest.mark.parametrize("step", [1, 2, 3, 4])
def test_lost_per_step_ack_stops_at_the_dispatched_prefix(rig, step):
    old = rig.sessions[0]
    dp = old.target.dp
    dp.flush.side_effect = [None] * (step-1) + [OSError(f"lost MDM-AP ACK at step {step}")]
    with pytest.raises(FlashError) as caught:
        rig.backend.reset_run("software")
    assert caught.value.code is FlashErrorCode.RESET_FAIL
    evidence = caught.value.details
    assert evidence["command"] == "S32K314.FunctionalReset"
    assert evidence["ap6_idr"] == EXPECTED_IDR
    assert evidence["step"] == step and evidence["acknowledged_steps"] == step-1
    assert evidence["reset_outcome"] == "unknown" and evidence["run_state"] == "unconfirmed"
    assert dp.mock_calls == reset_transfers(step)
    assert len(rig.sessions) == 1
    assert rig.backend._session is None
    old.target.selected_core.write32.assert_not_called()
    old.target.get_state.assert_not_called()
    rig.probe.reset.assert_not_called()


@pytest.mark.parametrize("actual", [0x24770011, None])
def test_unconfirmed_mdm_ap_identity_rejects_before_any_reset_dispatch(rig, actual):
    old = rig.sessions[0]
    if actual is None:
        old.target.dp.read_ap.side_effect = OSError("No ACK reading AP6 IDR")
    else:
        old.target.dp.read_ap.return_value = actual
    with pytest.raises(FlashError) as caught:
        rig.backend.reset_run("system")
    assert caught.value.code is FlashErrorCode.RESET_FAIL
    evidence = caught.value.details
    assert evidence["reset_outcome"] == "not_issued" and evidence["ap6_idr"] == actual
    assert evidence["acknowledged_steps"] == 0
    assert old.target.dp.mock_calls == [call.read_ap(AP6_IDR)]
    assert len(rig.sessions) == 1
    assert rig.backend._session is None
    rig.probe.disconnect.assert_called_once_with()
    rig.probe.close.assert_called_once_with()
    old.close.assert_not_called()
    old.target.get_state.assert_not_called()
    old.target.selected_core.write32.assert_not_called()
    rig.probe.reset.assert_not_called()


def test_job_api_retains_uncertain_reset_receipt_in_snapshot_and_error_event(rig):
    manager = OnlineFlashJobManager(lambda: rig.backend, ResourceManager())
    rig.probe.flush.side_effect = [None, OSError("lost reset ACK")]
    services = OnlineFlashServices(catalog=None, pack_manager=None, image_inspector=None, job_manager=manager,
                                   probe_provider=lambda: [rig.probe], target_memory_provider=lambda _: [], paths=None)
    app = FastAPI()
    app.include_router(create_online_flash_router(services))
    try:
        job = manager.start(JobRequest(actions=("connect", "reset", "disconnect"),
                                       target_part="S32K314", probe_id=rig.probe.unique_id, reset_mode="software"))
        assert manager.wait(job, timeout=2).state is JobState.FAILED
        with TestClient(app) as client:
            result = client.get(f"/api/online-flash/jobs/{job}").json()
            assert result["error_code"] == "RESET_FAIL"
            assert result["error_details"] == {"profile": "S32K314", "mem_ap": 4, "mode": "software",
                                               "reset_outcome": "unknown", "run_state": "unconfirmed",
                                               "command": "S32K314.FunctionalReset", "ap6_idr": EXPECTED_IDR,
                                               "acknowledged_steps": 4, "step": 4}
            stream = client.get(f"/api/online-flash/jobs/{job}/events").text
            events = [json.loads(line[6:]) for line in stream.splitlines() if line.startswith("data: ")]
            assert [e["error_details"] for e in events if e["event"] == "error"] == [result["error_details"]]
            assert all("error_details" not in e for e in events if e["event"] != "error")
    finally:
        manager.shutdown()

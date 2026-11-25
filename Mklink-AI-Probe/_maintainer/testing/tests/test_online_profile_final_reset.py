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
        target = SimpleNamespace(dp=object(), selected_core=core,
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
    else:
        mask = CortexM.NVIC_AIRCR_VECTRESET if mode == "core" else CortexM.NVIC_AIRCR_SYSRESETREQ
        old.target.selected_core.write32.assert_called_once_with(
            CortexM.NVIC_AIRCR, CortexM.NVIC_AIRCR_VECTKEY | mask)


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
    rig.probe.reset.assert_not_called()


@pytest.mark.parametrize("failure", ["write", "ack", "release", "pack", "reattach", "halted"])
def test_final_reset_failure_preserves_evidence_and_never_reissues(rig, failure):
    old = rig.sessions[0]
    core = old.target.selected_core
    if failure == "write":
        core.write32.side_effect = OSError("lost transfer")
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
        core.write32.assert_not_called()
    else:
        assert core.write32.call_count == 1
    old.target.get_state.assert_not_called()
    old.close.assert_not_called()
    rig.backend.disconnect()
    assert rig.probe.close.call_args_list[0] == call()


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
                                               "command": "SYSRESETREQ"}
            stream = client.get(f"/api/online-flash/jobs/{job}/events").text
            events = [json.loads(line[6:]) for line in stream.splitlines() if line.startswith("data: ")]
            assert [e["error_details"] for e in events if e["event"] == "error"] == [result["error_details"]]
            assert all("error_details" not in e for e in events if e["event"] != "error")
    finally:
        manager.shutdown()

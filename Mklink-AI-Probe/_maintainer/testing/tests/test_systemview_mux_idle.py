"""A quiet target is not a dead MUX transport (real framing/session/parser)."""
import struct
import time

import pytest

from mklink.mux import packet
from mklink.remote.dashboards import SystemViewStreamManager
from mklink.systemview import SystemViewSession
from test_mux_rtt_shared import rig


class MuxDevice:
    def __init__(self, bridge, info, mcu_name):
        self._bridge = bridge
        self.mcu_name = mcu_name
        self.session = SystemViewSession(bridge, info=info)
        self.start_calls = self.stop_calls = 0

    def systemview_start(self, addr, **options):
        self.start_calls += 1
        assert options.pop("channel") == 1  # bound in SystemViewSession's constructor
        return self.session.start(addr, **options)

    def systemview_read_bytes(self, **options):
        return self.session.read_bytes(**options)

    def systemview_stop(self):
        self.stop_calls += 1
        self.session.stop()


def wait_until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.005)
    assert predicate(), "worker did not reach the expected state"


@pytest.fixture
def capture():
    managers = []

    def start(mcu="STM32H743", duration=30):
        transport, calls, _, emit, info, bridge = rig()
        bridge._mux = transport
        device = MuxDevice(bridge, info, mcu)
        manager = SystemViewStreamManager()
        manager._startup_no_data_timeout_s = .03
        managers.append(manager)
        manager.start(device, addr="0x20000000", duration=duration)
        wait_until(lambda: transport.rtt_mask == 2)
        return manager, device, transport, calls, emit

    yield start
    for manager in managers:
        manager.stop()


@pytest.mark.parametrize("mcu", ["STM32H743", "HPM5301"])
def test_quiet_capture_keeps_partial_packet_history_and_session_until_resume(capture, mcu):
    manager, device, transport, calls, emit = capture(mcu)
    emit(1, b"\x11\x01\x11\x81")  # idle(dt=1), incomplete idle(dt=129)
    wait_until(lambda: manager.get_status()["stats"]["events"] == 1)
    parser = manager._parser
    cursor = manager.read_history()
    wait_until(lambda: manager.get_status()["progress_state"] == "waiting")
    assert manager.running and manager.get_status()["progress_error"] == ""
    assert manager.get_status()["stats"] == {"events": 1, "bytes": 4}
    # Real heartbeat ACKs are independent of event traffic. No DHCSR reads,
    # target resume, recorder replay, or extra device enumeration is needed.
    transport._last_command -= 2
    transport.tick()
    assert calls[-1] == (2, b"") and transport._pending is None
    emit(1, b"\x01")  # complete the packet across the long idle interval
    wait_until(lambda: manager.get_status()["stats"]["events"] == 2)
    assert manager.get_status()["progress_state"] == "streaming"
    page = manager.read_history(cursor["session"], cursor["next_seq"])
    assert [event["t_ticks"] for event in page["points"]] == [130]
    assert page["dropped"] == 0
    assert manager._parser is parser and device.start_calls == 1
    assert device.stop_calls == 0 and manager.get_status()["auto_retry_count"] == 0
    assert all(op in (0x20, 0x21, 2) for op, _ in calls)
    assert sum(op == 0x21 and data == b"\x01\x01" for op, data in calls) == 1


def test_waiting_before_first_event_is_explicit_and_duration_still_ends(capture):
    manager, device, _, _, _ = capture(duration=.2)
    wait_until(lambda: manager.get_status()["progress_state"] == "waiting")
    assert manager.running and manager.get_status()["stats"] == {"events": 0, "bytes": 0}
    wait_until(lambda: not manager.running)
    assert manager.get_status()["progress_state"] == "stopped"
    assert manager.get_status()["progress_error"] == ""
    assert (device.start_calls, device.stop_calls) == (1, 1)


@pytest.mark.parametrize("status,reason", [(5, "target read failed"),
                                         (7, "DAP changed"), (8, "reset recovery timed out")])
def test_target_failure_during_idle_remains_terminal_without_replay(capture, status, reason):
    manager, device, _, _, emit = capture()
    wait_until(lambda: manager.get_status()["progress_state"] == "waiting")
    emit(1, b"", status=status)
    wait_until(lambda: not manager.running)
    assert manager.get_status()["progress_state"] == "error"
    assert reason in manager.get_status()["progress_error"]
    assert (device.start_calls, device.stop_calls) == (1, 1)


@pytest.mark.parametrize("failure", ["heartbeat", "crc"])
def test_transport_failure_during_idle_remains_terminal(capture, failure):
    manager, device, transport, _, _ = capture()
    wait_until(lambda: manager.get_status()["progress_state"] == "waiting")
    if failure == "heartbeat":
        # Exercise the actual reader tick -> expiry -> session read failure.
        with transport._condition:
            transport._pending = (2, 123, time.monotonic() - .01, True)
        transport.tick()
        expected = "heartbeat=True"
    else:
        wire = bytearray(packet(0x40, 17, 1, struct.pack('<BBI', 1, 0, 1)))
        wire[-1] ^= 1
        transport.feed(wire)
        expected = "CRC"
    wait_until(lambda: not manager.running)
    assert manager.get_status()["progress_state"] == "error"
    assert expected in manager.get_status()["progress_error"]
    assert (device.start_calls, device.stop_calls) == (1, 1)


def test_undecodable_bytes_across_idle_are_not_hidden(capture):
    manager, device, _, _, emit = capture()
    manager._startup_progress_timeout_s = .02
    manager._startup_progress_min_bytes = 64
    emit(1, b"\xff" * 64)
    wait_until(lambda: manager.get_status()["progress_state"] == "waiting")
    emit(1, b"\xff" * 64)
    wait_until(lambda: not manager.running)
    assert "no decodable events" in manager.get_status()["progress_error"]
    assert manager.get_status()["raw_bytes_without_events"] == 128
    assert (device.start_calls, device.stop_calls) == (1, 1)


def test_failed_start_does_not_become_a_waiting_capture():
    class InvalidDevice:
        def systemview_start(self, *args, **options):
            raise RuntimeError("invalid RTT descriptor")

        def systemview_stop(self):
            pass

    manager = SystemViewStreamManager()
    manager.start(InvalidDevice())
    wait_until(lambda: not manager.running)
    manager.stop()
    assert manager.get_status()["progress_state"] == "error"
    assert manager.get_status()["progress_error"] == "invalid RTT descriptor"

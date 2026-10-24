"""Fault injection for ownership cleanup, using only isolated test locks."""
import os
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace

import pytest
import serial

from mklink import bridge as bridge_module
from mklink._isolated_serial import IsolatedSerial
from mklink.bridge import MKLinkSerialBridge
from mklink.device import Device
from mklink.hil_lock import HilFileLock
from mklink.local_resources import (
    _PortLock, local_resource_status, release_serial_resources, serial_lock_path,
)


@pytest.fixture(autouse=True)
def isolated_locks(tmp_path, monkeypatch):
    monkeypatch.setenv('MKLINK_LOCK_DIR', str(tmp_path / 'locks'))


def test_pid_zero_file_is_reusable_but_pid_zero_held_lock_is_not():
    first, second = _PortLock('TEST_CLEANUP'), _PortLock('TEST_CLEANUP')
    assert first.acquire()
    try:
        first._write_owner(0)
        assert not second.acquire()
        assert second.last_error is None
        result = release_serial_resources(port='TEST_CLEANUP')
        assert result['serial_locks'][0]['action'] == 'locked_or_unavailable'
        assert not second.acquire()
    finally:
        first.release()
    assert local_resource_status('TEST_CLEANUP')['serial_locks'][0]['owner_pid'] == 0
    try:
        assert second.acquire()
    finally:
        second.release()


def test_release_metadata_failure_still_releases_os_lock(monkeypatch):
    first, second = _PortLock('TEST_CLEANUP'), _PortLock('TEST_CLEANUP')
    assert first.acquire()
    def broken_metadata(_pid):
        raise OSError('injected metadata failure')
    monkeypatch.setattr(first, '_write_owner', broken_metadata)
    first.release()
    assert not first._locked
    try:
        assert second.acquire()
    finally:
        second.release()


def test_lock_io_failure_is_not_misreported_as_live_owner():
    Path(serial_lock_path('TEST_CLEANUP')).mkdir(parents=True)
    bridge = MKLinkSerialBridge('TEST_CLEANUP')
    assert not bridge.connect()
    assert 'Cannot access command-port lock' in bridge.last_connect_error
    result = release_serial_resources(port='TEST_CLEANUP')['serial_locks'][0]
    assert result['action'] == 'lock_error' and result['error']


@pytest.mark.parametrize('stage', ['reset_input_buffer', 'reset_output_buffer', 'start', 'write'])
@pytest.mark.parametrize('failure_type', [OSError, KeyboardInterrupt])
def test_direct_connect_exception_releases_ownership(monkeypatch, stage, failure_type):
    def fail():
        raise failure_type('injected handshake failure')
    class Port:
        is_open = True
        def reset_input_buffer(self):
            if stage == 'reset_input_buffer': fail()
        def reset_output_buffer(self):
            if stage == 'reset_output_buffer': fail()
        def write(self, _data):
            if stage == 'write': fail()
        def close(self): self.is_open = False
    class Reader:
        def __init__(self, **kw): pass
        def start(self):
            if stage == 'start': fail()
        def is_alive(self): return False
    port = Port()
    monkeypatch.setattr('mklink.probes.require_runtime_port', lambda _port: None)
    monkeypatch.setattr(bridge_module.serial, 'Serial', lambda *a, **kw: port)
    monkeypatch.setattr(bridge_module.threading, 'Thread', Reader)
    bridge, contender = MKLinkSerialBridge('TEST_CLEANUP'), _PortLock('TEST_CLEANUP')
    try:
        with pytest.raises(failure_type, match='injected'):
            bridge.connect()
        assert not port.is_open and not bridge._running
        assert contender.acquire()
    finally:
        bridge.close()
        contender.release()


class Worker:
    def __init__(self, *, alive=False, broken_pipe=False):
        self.alive = alive
        self.closed = []
        self.stdin, self.stdout, self.stderr = [self.pipe(name, broken_pipe) for name in ('in', 'out', 'err')]
    def pipe(self, name, broken):
        def close():
            self.closed.append(name)
            if broken and name == 'in': raise BrokenPipeError('injected pipe failure')
        return SimpleNamespace(close=close)
    def poll(self): return None if self.alive else 0
    def terminate(self): pass
    def kill(self): pass
    def wait(self, **kw):
        if self.alive: raise subprocess.TimeoutExpired('test-worker', 2)
        return 0


def transport(worker):
    port = IsolatedSerial.__new__(IsolatedSerial)
    port.is_open = True
    port._process = worker
    port._dispose_lock = threading.Lock()
    def failed_command(*a, **kw): raise serial.SerialException('worker unavailable')
    port._command = failed_command
    return port


def device_with_locks(tmp_path, port):
    bridge = MKLinkSerialBridge('TEST_CLEANUP')
    assert bridge._port_lock.acquire()
    bridge._serial = port
    device = Device(port='TEST_CLEANUP')
    device._bridge = bridge
    device._connected = True
    hil = HilFileLock('cleanup-test', root=tmp_path / 'hil').acquire()
    device._hil_lock = hil
    return device, bridge, hil


def test_exited_worker_pipe_error_does_not_strand_serial_or_hil_lock(tmp_path):
    worker = Worker(broken_pipe=True)
    port = transport(worker)
    device, bridge, hil = device_with_locks(tmp_path, port)
    device.close()
    assert worker.closed == ['in', 'out', 'err']
    assert not port.is_open and not hil.held and not bridge._port_lock._locked
    contender = _PortLock('TEST_CLEANUP')
    try:
        assert contender.acquire()
    finally:
        contender.release()


def test_unreaped_worker_retains_both_locks_until_confirmed_exit(tmp_path):
    worker = Worker(alive=True)
    port = transport(worker)
    device, bridge, hil = device_with_locks(tmp_path, port)
    contender = _PortLock('TEST_CLEANUP')
    try:
        with pytest.raises(subprocess.TimeoutExpired): device.close()
        assert port.is_open and hil.held and bridge._port_lock._locked
        assert not contender.acquire()
        assert worker.closed == []
        worker.alive = False
        device.close()
        assert not port.is_open and not hil.held
        assert contender.acquire()
    finally:
        worker.alive = False
        device.close()
        contender.release()


@pytest.mark.skipif(os.name != 'nt', reason='Windows bridge uses the isolated worker')
def test_failed_constructor_retains_worker_and_cannot_overwrite_it_on_retry(monkeypatch):
    worker = Worker(alive=True)
    starts = []
    def popen(*a, **kw):
        starts.append(True)
        return worker
    def failed_ready(self): raise serial.SerialException('injected ready failure')
    monkeypatch.setattr('mklink._isolated_serial.subprocess.Popen', popen)
    monkeypatch.setattr(IsolatedSerial, '_reply', failed_ready)
    monkeypatch.setattr(IsolatedSerial, '_command', lambda *a, **kw: None)
    monkeypatch.setattr('mklink.probes.require_runtime_port', lambda _port: None)
    bridge, contender = MKLinkSerialBridge('TEST_CLEANUP'), _PortLock('TEST_CLEANUP')
    try:
        with pytest.raises(subprocess.TimeoutExpired): bridge.connect()
        pending = bridge._serial
        assert isinstance(pending, IsolatedSerial) and pending.is_open
        assert not contender.acquire()
        with pytest.raises(subprocess.TimeoutExpired): bridge.connect()
        assert len(starts) == 1 and bridge._serial is pending
        worker.alive = False
        bridge.close()
        assert contender.acquire()
    finally:
        worker.alive = False
        bridge.close()
        contender.release()


def test_terminate_race_with_worker_exit_still_finishes_cleanup():
    worker = Worker(alive=True)
    def terminate():
        worker.alive = False
        raise ProcessLookupError('exited just before terminate')
    worker.terminate = terminate
    port = transport(worker)
    port._dispose()
    assert not port.is_open and worker.closed == ['in', 'out', 'err']

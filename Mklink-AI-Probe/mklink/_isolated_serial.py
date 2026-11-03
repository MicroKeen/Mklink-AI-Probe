"""Keep Windows USB CDC reception independent of application Python pauses.

The worker drains USB while the application collects garbage or parses ELF.
Transport buffers are finite; this is pause tolerance, not unlimited recording.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
import struct
import subprocess
import sys
import threading
import time

import serial


class _ControlFailure(serial.SerialException):
    """A missing/malformed reply makes subsequent command replies ambiguous."""


class SerialCleanupPending(serial.SerialException):
    """Keep an unreaped constructor's transport reachable for safe cleanup."""

    def __init__(self, transport):
        super().__init__('Serial worker exit is unconfirmed; ownership retained')
        self.transport = transport


def _worker_command(port, baudrate):
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--internal-serial-worker', port, str(baudrate)]
    return [sys.executable, str(Path(__file__).with_name('_serial_worker.py')), port, str(baudrate)]


class _PipeInbox:
    """Blocking pipe reader with bounded storage and notification on arrival.

    Separate control/data readers keep acknowledgements independent of RX
    backpressure. Only the consumer interprets framing and reset generations.
    """

    def __init__(self, pipe, capacity, name):
        self._pipe, self._capacity = pipe, capacity
        self._condition = threading.Condition()
        self._buffer = bytearray()
        self._ended = self._stopped = False
        self._error = None
        self._thread = threading.Thread(target=self._receive, name=name, daemon=True)
        self._thread.start()

    def _receive(self):
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._stopped or len(self._buffer) < self._capacity)
                    if self._stopped:
                        return
                    size = min(65536, self._capacity - len(self._buffer))
                # Popen uses unbuffered FileIO: return available bytes without
                # waiting to fill size. A worker exit releases the blocked read.
                data = self._pipe.read(size)
                if not data:
                    return
                with self._condition:
                    self._buffer.extend(data)
                    self._condition.notify_all()
        except (OSError, ValueError) as exc:
            self._error = exc
        finally:
            with self._condition:
                self._ended = True
                self._condition.notify_all()

    def wait(self, timeout):
        with self._condition:
            self._condition.wait_for(lambda: self._buffer or self._ended or self._stopped, timeout)

    def read(self, size, timeout=0):
        with self._condition:
            self._condition.wait_for(lambda: self._buffer or self._ended or self._stopped, timeout)
            if self._buffer:
                data = bytes(self._buffer[:size])
                del self._buffer[:size]
                self._condition.notify_all()
                return data
            if self._ended or self._stopped:
                raise serial.SerialException('Serial worker pipe closed') from self._error
            return b''

    def stop(self):
        with self._condition:
            self._stopped = True
            self._condition.notify_all()
        # Called only after the worker is reaped: the pipe can no longer block.
        self._thread.join(timeout=2)


class IsolatedSerial:
    def __init__(self, port: str, baudrate: int, timeout: float = .01):
        self.port, self.baudrate, self.timeout = port, baudrate, timeout
        self.is_open = False
        self._wire = bytearray()
        self._rx = bytearray()
        self._control = bytearray()
        self._epoch = 0
        self._control_operation = 'open'
        self._rx_lock = threading.Lock()
        self._command_lock = threading.Lock()
        self._dispose_lock = threading.Lock()
        try:
            self._process = subprocess.Popen(
                _worker_command(port, baudrate),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=0, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
        except OSError as exc:
            raise serial.SerialException('Cannot start serial receive worker') from exc
        self.is_open = True  # The worker may own IO before its ready reply.
        try:
            self._data_inbox = _PipeInbox(self._process.stdout, 1048576, 'serial-worker-data')
            self._control_inbox = _PipeInbox(self._process.stderr, 65536, 'serial-worker-control')
            if not self._reply().get('ready'):
                raise serial.SerialException('Serial worker did not open the port')
            self.is_open = True
        except BaseException:
            try:
                self._dispose()
            except Exception as cleanup_error:
                raise SerialCleanupPending(self) from cleanup_error
            raise

    def _reply(self):
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            if b'\n' in self._control:
                line, _, rest = self._control.partition(b'\n')
                self._control = bytearray(rest)
                try:
                    response = json.loads(line)
                except (ValueError, UnicodeError) as exc:
                    raise _ControlFailure('Invalid serial worker response') from exc
                if not isinstance(response, dict):
                    raise _ControlFailure('Invalid serial worker response')
                if 'error' in response:
                    raise serial.SerialException(response['error'])
                return response
            try:
                data = self._control_inbox.read(65536, max(0, deadline - time.monotonic()))
            except serial.SerialException as exc:
                raise _ControlFailure(f'Serial worker control pipe closed during {self._control_operation}') from exc
            if data:
                self._control.extend(data)
                if len(self._control) > 65536:
                    raise _ControlFailure('Oversized serial worker response')
        raise _ControlFailure(f'Serial worker control connection failed during {self._control_operation} (reply deadline 7s)')

    def _command(self, op, **kwargs):
        with self._command_lock:
            if not self.is_open:
                raise serial.SerialException('Serial port is closed')
            try:
                self._control_operation = op
                data = memoryview((json.dumps({'op': op, **kwargs})+'\n').encode())
                while data:
                    count = self._process.stdin.write(data)
                    if not count:
                        raise _ControlFailure('Serial worker input closed')
                    data = data[count:]
                return self._reply()
            except _ControlFailure:
                self._dispose()  # Do not accept a late reply as the next command.
                raise
            except serial.SerialException:
                # Worker errors already identify the failed transport operation.
                # SerialException is also an OSError; do not hide a USB timeout
                # or a closed control pipe behind an unrelated write error.
                raise
            except (OSError, ValueError) as exc:
                self._dispose()
                raise serial.SerialException(f'Serial worker write failed: {exc}') from exc

    def _drain(self):
        if not self.is_open:
            raise serial.SerialException('Serial port is closed')
        # Leave excess bytes in the bounded worker/pipe instead of growing
        # memory when a caller repeatedly checks in_waiting without reading.
        data = self._data_inbox.read(65536) if len(self._rx) < 1048576 else b''
        if data:
            self._wire.extend(data)
        elif self._process.poll() is not None:
            raise serial.SerialException('Serial worker exited')
        offset = 0
        while len(self._wire)-offset >= 9:
            kind, epoch, size = struct.unpack_from('<cII', self._wire, offset)
            if size > 65536 or kind not in (b'D', b'E'):
                raise serial.SerialException('Invalid serial worker packet')
            if len(self._wire)-offset < size+9: break
            data = self._wire[offset+9:offset+9+size]
            offset += size+9
            if kind == b'E':
                raise serial.SerialException(data.decode('utf-8', errors='replace'))
            if epoch >= self._epoch:
                self._rx.extend(data)
        if offset: del self._wire[:offset]

    @property
    def in_waiting(self):
        with self._rx_lock:
            self._drain()
            return len(self._rx)

    def read(self, size=1):
        if size <= 0: return b''
        deadline = time.monotonic()+self.timeout
        while True:
            with self._rx_lock:
                self._drain()
                if self._rx:
                    data = bytes(self._rx[:size])
                    del self._rx[:size]
                    return data
            remaining = deadline - time.monotonic()
            if remaining <= 0: return b''
            self._data_inbox.wait(remaining)

    def write(self, data):
        return self._command('write', data=base64.b64encode(data).decode('ascii'))['result']

    def flush(self):
        self._command('flush')

    def reset_input_buffer(self):
        with self._rx_lock:
            self._epoch = self._command('reset_input_buffer')['epoch']
            self._rx.clear()
            # Retain partial framing; old generations are discarded by _drain.

    def reset_output_buffer(self):
        self._command('reset_output_buffer')

    def _dispose(self):
        with self._dispose_lock:
            if self._process.poll() is None:
                try:
                    self._process.terminate()
                except OSError:
                    if self._process.poll() is None:
                        raise
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2)
            # Bridge.close skips serial.close when is_open is false. Publish
            # that state only after the worker has exited, so another thread
            # cannot release the application port lock while it still owns IO.
            self.is_open = False
            for name in ('_data_inbox', '_control_inbox'):
                inbox = getattr(self, name, None)
                if inbox is not None:
                    inbox.stop()
            for pipe in (self._process.stdin, self._process.stdout, self._process.stderr):
                try:
                    pipe.close()
                except (OSError, ValueError):
                    # IO ownership is gone. One broken pipe must not strand
                    # the other pipes or the parent application's locks.
                    logging.getLogger(__name__).warning('Failed to close exited serial worker pipe', exc_info=True)

    def close(self):
        try:
            if self.is_open and self._process.poll() is None:
                self._command('close')
        except serial.SerialException:
            # The read/write that discovered the failure reports it. Cleanup
            # must still release the port lock and reap an already-dead worker.
            pass
        finally:
            self._dispose()

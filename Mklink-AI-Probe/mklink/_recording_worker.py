"""Private, bounded disk-recording process; never opens hardware."""
from array import array
import json
from pathlib import Path
import queue
import struct
import subprocess
import sys
import threading
import time

# Filename launch must use this checkout, even without PYTHONPATH. Replacing
# the script directory also prevents mklink/serial from shadowing pyserial.
if __package__ in (None, ''):
    sys.path[0] = str(Path(__file__).resolve().parent.parent)

HEADER = struct.Struct('<III')
MAX_BATCH = 32 * 1024 * 1024
REPLY_TIMEOUT = 10


class RecordingWorker:
    def __init__(self, directory, max_values):
        command = ([sys.executable, '--internal-recording-worker'] if getattr(sys, 'frozen', False)
                   else [sys.executable, str(Path(__file__))])
        self.process = subprocess.Popen(
            [*command, str(directory), str(max_values)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self._buffer = bytearray()
        try:
            from mklink._isolated_serial import _PipeInbox
            self._inbox = _PipeInbox(self.process.stdout, 65536, 'recording-worker-status')
            self.status = self._reply()
            self._outgoing = queue.Queue(maxsize=1)
            self._writer = threading.Thread(target=self._write, name='recording-worker-input', daemon=True)
            self._writer.start()
        except BaseException:
            self.close()
            raise

    def _reply(self):
        deadline = time.monotonic() + REPLY_TIMEOUT
        while b'\n' not in self._buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Recording worker response timed out; recording is incomplete')
            try:
                self._buffer.extend(self._inbox.read(65536, remaining))
            except Exception as exc:
                raise RuntimeError('Recording worker exited; recording is incomplete') from exc
            if len(self._buffer) > 65536:
                raise RuntimeError('Invalid recording worker response')
        line, _, rest = self._buffer.partition(b'\n')
        self._buffer = bytearray(rest)
        result = json.loads(line)
        if not isinstance(result, dict) or 'state' not in result:
            raise RuntimeError(result.get('error', 'Invalid recording worker response')
                               if isinstance(result, dict) else 'Invalid recording worker response')
        return result

    def _send(self, data):
        # Waiting for ACK also bounds a blocked pipe write if the disk child
        # stops consuming input. Never block the forwarding thread in write().
        self._outgoing.put_nowait(data)

    def _write(self):
        try:
            while (data := self._outgoing.get()) is not None:
                view = memoryview(data)
                while view:
                    written = self.process.stdin.write(view)
                    if not written:
                        return
                    view = view[written:]
        except (OSError, ValueError):
            # EOF or the bounded ACK timeout reports failure to the caller.
            pass

    def append(self, values, times, names, boundaries):
        metadata = json.dumps([names, list(boundaries.items())], ensure_ascii=False).encode('utf-8')
        values, times = array('f', values).tobytes(), array('d', times).tobytes()
        if len(metadata) > 1048576 or len(values) + len(times) > MAX_BATCH:
            raise ValueError('Recording batch exceeds worker limit')
        self._send(HEADER.pack(len(metadata), len(values), len(times)) + metadata + values + times)
        return self._reply()

    def finish(self):
        self._send(HEADER.pack(0, 0, 0))
        result = self._reply()
        self.process.wait(timeout=10)
        return result

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        inbox = getattr(self, '_inbox', None)
        if inbox is not None:
            inbox.stop()
        writer = getattr(self, '_writer', None)
        if writer is not None:
            try:
                self._outgoing.put_nowait(None)
            except queue.Full:
                pass
            writer.join(timeout=2)
        self.process.stdin.close()
        self.process.stdout.close()


def main(arguments=None):
    from mklink.superwatch_recording import SuperWatchRecorder
    recorder = None
    def reply(value):
        sys.stdout.write(json.dumps(value) + '\n')
        sys.stdout.flush()
    def read_exact(size):
        data = bytearray()
        while len(data) < size:
            chunk = sys.stdin.buffer.read(size - len(data))
            if not chunk:
                raise EOFError('Recording input ended before finalization')
            data.extend(chunk)
        return data
    try:
        args = sys.argv[1:] if arguments is None else arguments
        if len(args) != 2:
            raise ValueError('Recording worker requires directory and part size')
        recorder = SuperWatchRecorder(args[0], max_values=int(args[1]), _local=True)
        reply(recorder.status())
        while True:
            metadata_size, value_size, time_size = HEADER.unpack(read_exact(HEADER.size))
            if (metadata_size > 1048576 or value_size + time_size > MAX_BATCH
                    or value_size % 4 or time_size % 8):
                raise ValueError('Invalid recording batch header')
            if not metadata_size:
                if value_size or time_size:
                    raise ValueError('Invalid recording finalization')
                reply(recorder.stop())
                return 0
            names, boundaries = json.loads(read_exact(metadata_size))
            values, times = array('f'), array('d')
            values.frombytes(read_exact(value_size))
            times.frombytes(read_exact(time_size))
            recorder.append(values, times, [{'name': name} for name in names], boundaries=boundaries)
            # At most one batch is in flight beyond the parent's bounded queue.
            with recorder._condition:
                recorder._condition.wait_for(lambda: not recorder._queued_bytes or not recorder._status['active'])
            result = recorder.status()
            reply(result)
            if result['state'] == 'failed':
                return 1
    except Exception as exc:
        reply({'error': str(exc) or type(exc).__name__})
        return 1
    finally:
        if recorder is not None:
            recorder.stop()


if __name__ == '__main__':
    raise SystemExit(main())

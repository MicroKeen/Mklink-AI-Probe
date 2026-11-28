"""Continuous disk sink for acquisition batches, independent of viewer history."""
from __future__ import annotations

from collections import deque
from datetime import datetime
import json
import math
from pathlib import Path
import threading
import time
import uuid


class SuperWatchRecorder:
    def __init__(self, directory, *, max_values=1_000_000, queue_bytes=32 * 1024 * 1024, _local=False):
        directory = Path(directory).expanduser()
        if not directory.is_absolute() or not directory.is_dir():
            raise ValueError('Choose an existing absolute directory on the backend computer')
        from mklink.work_files import capture_directory
        directory = capture_directory(directory)
        self._base = directory / ('superwatch-' + datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8])
        self._queue_limit = queue_bytes
        self._queue = deque()
        self._queued_bytes = 0
        self._condition = threading.Condition()
        self._closing = False
        self._status = dict(state='recording', active=True, directory=str(directory), path='',
                            parts=0, samples=0, bytes=0, error='', started_at=time.time())
        self._export = None
        if _local:
            from mklink.recording_file import RecordingFile
            path = self._base.with_suffix('.mklog')
            self._capture = RecordingFile(path, 'superwatch', block_rows=min(2048, max_values))
            self._status.update(path=str(path), parts=1)
        else:
            from mklink._recording_worker import RecordingWorker
            self._worker = RecordingWorker(directory, max_values)
            self._status = self._worker.status
            from mklink.recording_text import ManualExport
            self._export = ManualExport('superwatch')
        self._thread = threading.Thread(target=self._run if _local else self._forward,
                                        name='superwatch-recording', daemon=True)
        self._thread.start()

    def status(self):
        with self._condition:
            result = dict(self._status)
        if self._export:
            result.update(self._export.status())
        return result

    def export(self):
        if self._export is None:
            raise ValueError('This recording does not support conversion')
        self._export.start(self.status())
        return self.status()

    def append(self, values, times, channels, *, boundaries=()):
        size = len(values) * 4 + len(times) * 8 + len(boundaries) * 8
        with self._condition:
            if self._closing or self._status['state'] != 'recording':
                return
            if self._queued_bytes + size > self._queue_limit:
                self._status.update(state='failed', error='Disk recording queue overflow; recording is incomplete')
                self._closing = True
            else:
                # Manager transfers these arrays and never modifies them again.
                self._queue.append((values, times, tuple(channel['name'] for channel in channels), size, dict(boundaries)))
                self._queued_bytes += size
            self._condition.notify()

    def request_stop(self):
        with self._condition:
            self._closing = True
            if self._status['state'] == 'recording':
                self._status['state'] = 'stopping'
            self._condition.notify()

    def stop(self, timeout=10):
        self.request_stop()
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise TimeoutError('Recording is still draining; check status before starting another recording')
        return self.status()

    def _forward(self):
        """Keep JSON encoding off the acquisition process's Python lock."""
        error = ''
        try:
            while True:
                with self._condition:
                    while not self._queue and not self._closing:
                        self._condition.wait()
                    if not self._queue:
                        break
                    values, times, names, size, boundaries = self._queue.popleft()
                result = self._worker.append(values, times, names, boundaries)
                with self._condition:
                    for key in ('path', 'parts', 'samples', 'bytes'):
                        self._status[key] = result[key]
                    self._queued_bytes -= size
                if result['state'] == 'failed':
                    raise RuntimeError(result['error'])
            result = self._worker.finish(self._status['error'])
            with self._condition:
                for key in ('path', 'parts', 'samples', 'bytes'):
                    self._status[key] = result[key]
            if result['state'] != 'completed':
                raise RuntimeError(result['error'] or 'Recording did not complete')
        except Exception as exc:
            error = str(exc) or type(exc).__name__
        finally:
            try:
                self._worker.close()
            except Exception as exc:
                error = error or str(exc)
            with self._condition:
                error = error or self._status['error']
                self._queue.clear()
                self._status.update(active=False, state='failed' if error else 'completed',
                                    error=error, stopped_at=time.time())

    def _run(self):
        previous_names = None
        error = ''
        # Reuse the encoder across samples; TextIO already buffers file writes.
        encode = json.JSONEncoder(ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._queue or self._closing,
                                             timeout=2 if self._capture.count else None)
                    if not self._queue and self._closing:
                        break
                    batch = self._queue.popleft() if self._queue else None
                if batch is None:
                    self._capture.flush_block()
                    continue
                values, times, names, size, boundaries = batch
                width = len(names)
                batch_bytes = 0
                if not width or len(values) != len(times) * width:
                    raise ValueError('Recording batch layout mismatch')
                for row, timestamp in enumerate(times):
                    point = {name: float(values[row * width + i]) for i, name in enumerate(names)
                             if math.isfinite(values[row * width + i])}
                    if not point or not math.isfinite(timestamp):
                        raise ValueError('Recording contains an invalid sample')
                    point['_t'] = timestamp / 1000
                    line = encode(point) + '\n'
                    if row in boundaries:
                        # Separate metadata cannot overwrite a target variable
                        # with a reserved-looking name such as _break_before.
                        line = json.dumps({'event': 'discontinuity', 'reason': boundaries[row]},
                                          separators=(',', ':')) + '\n' + line
                    data = line.encode('utf-8')
                    self._capture.append(data, point['_t'], values=point, gap=boundaries.get(row, 0),
                                         new_layout=previous_names != names)
                    batch_bytes += len(data)
                    previous_names = names
                with self._condition:
                    self._queued_bytes -= size
                    self._status['samples'] += len(times)
                    self._status['bytes'] += batch_bytes
                    self._condition.notify_all()
        except Exception as exc:
            error = str(exc) or type(exc).__name__
        finally:
            try:
                self._capture.finish(error or self._status['error'])
            except Exception as exc:
                error = error or str(exc)
            with self._condition:
                error = error or self._status['error']
                self._queue.clear()
                self._status.update(active=False, state='failed' if error else 'completed',
                                    error=error, stopped_at=time.time())
                self._condition.notify_all()

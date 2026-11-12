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
    # Each part stays within the offline player's memory limits. A slow disk
    # fails explicitly instead of silently discarding the oldest samples.
    def __init__(self, directory, *, max_values=1_000_000, queue_bytes=32 * 1024 * 1024, _local=False):
        directory = Path(directory).expanduser()
        if not directory.is_absolute() or not directory.is_dir():
            raise ValueError('Choose an existing absolute directory on the backend computer')
        self._base = directory / ('superwatch-' + datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8])
        self._max_values = max_values
        self._queue_limit = queue_bytes
        self._queue = deque()
        self._queued_bytes = 0
        self._condition = threading.Condition()
        self._closing = False
        self._status = dict(state='recording', active=True, directory=str(directory), path='',
                            parts=0, samples=0, bytes=0, error='', started_at=time.time())
        self._file = None
        self._text_export = None
        if _local:
            self._open_part()
        else:
            from mklink._recording_worker import RecordingWorker
            self._worker = RecordingWorker(directory, max_values)
            self._status = self._worker.status
            from mklink.recording_text import TextExport
            self._text_export = TextExport('superwatch')
        self._thread = threading.Thread(target=self._run if _local else self._forward,
                                        name='superwatch-recording', daemon=True)
        self._thread.start()

    def _open_part(self):
        path = str(self._base) + f'-{self._status["parts"] + 1:04d}.jsonl'
        self._file = open(path, 'x', encoding='utf-8', newline='\n')
        self._status.update(path=path, parts=self._status['parts'] + 1)

    def status(self):
        with self._condition:
            result = dict(self._status)
        if self._text_export:
            result.update(self._text_export.status())
        return result

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
            result = self._worker.finish()
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
            self._text_export.start(self._status)

    def _run(self):
        part_values = 0
        part_bytes = 0
        previous_names = None
        error = ''
        # Reuse the encoder across samples; TextIO already buffers file writes.
        encode = json.JSONEncoder(ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode
        try:
            while True:
                with self._condition:
                    while not self._queue and not self._closing:
                        self._condition.wait()
                    if not self._queue:
                        break
                    values, times, names, size, boundaries = self._queue.popleft()
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
                    length = len(line.encode('utf-8'))
                    batch_bytes += length
                    if part_values and (part_values + width > self._max_values or
                                        part_bytes + length > 32 * 1024 * 1024 or previous_names != names):
                        self._file.close()
                        with self._condition:
                            self._open_part()
                        part_values = part_bytes = 0
                    self._file.write(line)
                    part_values += width
                    part_bytes += length
                    previous_names = names
                self._file.flush()
                with self._condition:
                    self._queued_bytes -= size
                    self._status['samples'] += len(times)
                    self._status['bytes'] += batch_bytes
                    self._condition.notify_all()
        except Exception as exc:
            error = str(exc) or type(exc).__name__
        finally:
            try:
                self._file.close()
            except Exception as exc:
                error = error or str(exc)
            with self._condition:
                error = error or self._status['error']
                self._queue.clear()
                self._status.update(active=False, state='failed' if error else 'completed',
                                    error=error, stopped_at=time.time())
                self._condition.notify_all()

"""Bounded, loss-reporting raw RX/TX recording, independent of GUI consumers."""
from collections import deque
from datetime import datetime
import json
from pathlib import Path
import threading
import time
import uuid


class TrafficRecorder:
    def __init__(self, directory, kind, *, part_bytes=4 * 1024 * 1024,
                 queue_bytes=8 * 1024 * 1024, part_events=20000):
        directory = Path(directory).expanduser()
        if not directory.is_absolute() or not directory.is_dir():
            raise ValueError('Choose an existing absolute directory on the backend computer')
        self._base = directory / (kind + '-' + datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:12])
        self._kind, self._part_bytes, self._part_events = kind, part_bytes, part_events
        self._queue_limit, self._queued_bytes = queue_bytes, 0
        self._condition = threading.Condition()
        self._queue = deque()
        self._closing = False
        self._export = None
        if kind == 'rtt':
            from mklink.recording_text import ManualExport
            self._export = ManualExport(kind)
        self._status = dict(state='recording', active=True, path='', directory=str(directory),
                            samples=0, bytes=0, parts=0, error='', started_at=time.time())
        self._open_part()
        self._thread = threading.Thread(target=self._run, name=kind + '-traffic-recording', daemon=True)
        self._thread.start()

    def _open_part(self):
        path = str(self._base) + f'-{self._status["parts"] + 1:04d}.jsonl'
        self._file = open(path, 'x', encoding='utf-8', newline='\n')
        try:
            self._file.write(json.dumps(dict(type='mklink-traffic', version=1, kind=self._kind)) + '\n')
            self._file.flush()
        except BaseException:
            self._file.close()
            raise
        with self._condition:
            self._status.update(path=path, parts=self._status['parts'] + 1)

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

    def append(self, source, data, direction, session, timestamp=None, lost_bytes=0):
        if not data:
            return
        # Bounded chunks keep both the queue and individual JSON lines bounded.
        for offset in range(0, len(data), 16384):
            chunk = bytes(data[offset:offset + 16384])
            with self._condition:
                if self._closing:
                    return
                size = len(chunk) + 256
                if self._queued_bytes + size > self._queue_limit:
                    self._status.update(state='failed', error='Disk recording queue overflow; recording is incomplete')
                    self._closing = True
                else:
                    self._queue.append((dict(type='data', source=str(source), direction=direction,
                        session=session or '', time=time.time() if timestamp is None else timestamp,
                        lost_bytes=lost_bytes), chunk, size))
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
            raise TimeoutError('Recording is still draining; check status before restarting')
        return self.status()

    def _finish_part(self, error=''):
        self._file.write(json.dumps(dict(type='end', complete=not bool(error), error=error)) + '\n')
        self._file.close()

    def _run(self):
        count = size = 0
        error = ''
        try:
            while True:
                with self._condition:
                    while not self._queue and not self._closing:
                        self._condition.wait()
                    if not self._queue:
                        break
                    row, chunk, weight = self._queue.popleft()
                row['hex'] = chunk.hex()
                line = json.dumps(row, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'
                length = len(line.encode('utf-8'))
                if count and (size + length > self._part_bytes or count >= self._part_events):
                    self._finish_part()
                    self._open_part()
                    size = count = 0
                self._file.write(line)
                self._file.flush()
                count += 1
                size += length
                with self._condition:
                    self._queued_bytes -= weight
                    self._status['samples'] += 1
                    self._status['bytes'] += len(chunk)
        except Exception as exc:
            error = str(exc) or type(exc).__name__
        finally:
            with self._condition:
                error = error or self._status['error']
            try:
                self._finish_part(error)
            except Exception as exc:
                error = error or str(exc)
            finally:
                try:
                    self._file.close()
                except Exception as exc:
                    error = error or str(exc)
            with self._condition:
                self._closing = True
                self._queue.clear()
                self._queued_bytes = 0
                self._status.update(active=False, state='failed' if error else 'completed',
                                    error=error, stopped_at=time.time())

class TrafficRecordings:
    """RTT records per channel; serial records all configured ports together."""
    def __init__(self, kind):
        self.kind = kind
        self._lock = threading.RLock()
        self._recorders = {}

    def _key(self, channel):
        if self.kind == 'rtt' and (type(channel) is not int or not 0 <= channel <= 7):
            raise ValueError('RTT channel must be 0..7')
        return channel if self.kind == 'rtt' else 0

    def status(self, channel=0):
        with self._lock:
            recorder = self._recorders.get(self._key(channel))
            return recorder.status() if recorder else dict(state='idle', active=False)

    def start(self, directory, channel=0):
        with self._lock:
            key = self._key(channel)
            if self.status(channel)['active']:
                raise RuntimeError('Recording is already active; stop it first')
            recorder = TrafficRecorder(directory, self.kind)
            self._recorders[key] = recorder
            return recorder.status()

    def append(self, source, data, direction, session, timestamp=None, lost_bytes=0):
        with self._lock:
            recorder = self._recorders.get(source if self.kind == 'rtt' else 0)
        if recorder:
            recorder.append(source, data, direction, session, timestamp, lost_bytes)

    def stop(self, channel=0):
        with self._lock:
            recorder = self._recorders.get(self._key(channel))
        return recorder.stop() if recorder else self.status(channel)

    def export(self, path, channel=0):
        with self._lock:
            recorder = self._recorders.get(self._key(channel))
            if recorder is None or recorder.status()['path'] != path:
                raise RuntimeError('Recording changed; refresh its status before converting')
            return recorder.export()

    def request_stop_all(self):
        with self._lock:
            recorders = list(self._recorders.values())
        for recorder in recorders:
            recorder.request_stop()

    def stop_all(self):
        with self._lock:
            recorders = list(self._recorders.values())
        for recorder in recorders:
            recorder.stop()

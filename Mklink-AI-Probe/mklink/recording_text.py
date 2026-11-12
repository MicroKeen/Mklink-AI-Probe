"""Manual human-readable companions for closed recordings; never opens hardware."""
from __future__ import annotations

import codecs
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid

if __package__ in (None, ''):
    sys.path[0] = str(Path(__file__).resolve().parent.parent)

MAX_LINE = 1024 * 1024
TEXT_LINE = 16384


def _date(timestamp):
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(sep=' ', timespec='microseconds')


def _safe(text):
    """Keep terminal controls and arbitrary bytes visible rather than executable."""
    return ''.join(f'\\x{ord(c) - 0xdc00:02x}' if 0xdc80 <= ord(c) <= 0xdcff
                   else f'\\x{ord(c):02x}' if ord(c) < 32 or ord(c) == 127
                   else '\\\\' if c == '\\' else c for c in str(text))


def _rows(path):
    with path.open('r', encoding='utf-8') as stream:
        while line := stream.readline(MAX_LINE + 1):
            if len(line) > MAX_LINE:
                raise ValueError(f'Recording line exceeds TXT conversion limit: {path.name}')
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f'Invalid recording row: {path.name}')
            yield row


class _RttText:
    def __init__(self):
        self.streams = {}

    def _flush(self, output, state, *, final=False):
        if final:
            state['text'] += state['decoder'].decode(b'', final=True)
        if state['text']:
            self._line(output, state, state['text'], ' [partial line]')
            state['text'] = ''

    def _line(self, output, state, text, suffix=''):
        output.write(f"[{_date(state['time'])}] channel={_safe(state['source'])} "
                     f"{_safe(state['direction'])} session={_safe(state['session'])} "
                     f"{_safe(text)}{suffix}\n")

    def row(self, output, row):
        if row.get('type') != 'data':
            if row.get('type') == 'end' and not row.get('complete', True):
                output.write(f"# INCOMPLETE: {_safe(row.get('error', ''))}\n")
            return
        key = (str(row['source']), row['direction'])
        if key not in self.streams and len(self.streams) >= 16:
            raise ValueError('Too many RTT channel/direction streams')
        state = self.streams.get(key)
        if state and state['session'] != row['session']:
            self._flush(output, state, final=True)
            state = None
        if state is None:
            state = dict(decoder=codecs.getincrementaldecoder('utf-8')('surrogateescape'),
                         text='', time=row['time'], source=key[0], direction=key[1],
                         session=row['session'], lost_bytes=0)
            self.streams[key] = state
        if not state['text'] and not state['decoder'].getstate()[0]:
            state['time'] = row['time']
        lost = row.get('lost_bytes', 0)
        if lost != state['lost_bytes']:
            # A missing byte range must not splice two fragments into a
            # seemingly intact UTF-8 character or application log line.
            self._flush(output, state, final=True)
            state['decoder'] = codecs.getincrementaldecoder('utf-8')('surrogateescape')
            state['time'] = row['time']
            output.write(f"# [{_date(row['time'])}] channel={_safe(key[0])} "
                         f"{_safe(key[1])} lost_bytes={lost}\n")
            state['lost_bytes'] = lost
        state['text'] += state['decoder'].decode(bytes.fromhex(row['hex']))
        while state['text']:
            newline = state['text'].find('\n')
            if 0 <= newline <= TEXT_LINE:
                self._line(output, state, state['text'][:newline].removesuffix('\r'))
                state['text'] = state['text'][newline + 1:]
                state['time'] = row['time']
            elif len(state['text']) > TEXT_LINE:
                self._line(output, state, state['text'][:TEXT_LINE], ' [continued]')
                state['text'] = state['text'][TEXT_LINE:]
            else:
                break

    def finish(self, output):
        for state in self.streams.values():
            self._flush(output, state, final=True)


def _save_status(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def export_text(manifest_path):
    """Stream closed JSONL parts; results/errors are separate from capture status."""
    manifest_path = Path(manifest_path)
    job = json.loads(manifest_path.read_text(encoding='utf-8'))
    try:
        traffic = _RttText() if job['kind'] == 'rtt' else None
        for index in range(1, job['parts'] + 1):
            source = Path(job['base'] + f'-{index:04d}.jsonl')
            target = source.with_suffix('.txt')
            with target.open('x', encoding='utf-8', newline='\n', buffering=65536) as output:
                output.write(f"# MKLink {job['kind']} readable log — {source.name}\n"
                             f"# Recording started: {_date(job['started_at'])}\n"
                             f"# Source: {'complete' if job['complete'] else 'INCOMPLETE: ' + _safe(job['source_error'])}\n")
                if traffic:
                    output.write('# Timestamps: host RX/TX time, local timezone; fragmented lines use first chunk time.\n'
                                 '# A line spanning parts appears where it finishes; read numbered parts in order.\n')
                else:
                    output.write('# t: acquisition-relative seconds (JSONL _t), not host wall-clock time.\n')
                for row in _rows(source):
                    if traffic:
                        traffic.row(output, row)
                    elif row.get('event') == 'discontinuity':
                        output.write(f"# DISCONTINUITY reason={_safe(row.get('reason'))}\n")
                    else:
                        timestamp = row.get('_t')
                        if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
                            raise ValueError('Invalid SuperWatch sample timestamp')
                        fields = '  '.join(f'{_safe(key)}={value}' for key, value in row.items() if key != '_t')
                        output.write(f'[t={timestamp:.9f} s] {fields}\n')
                if traffic and index == job['parts']:
                    traffic.finish(output)
                output.write('# TXT part complete; use JSONL for lossless replay.\n')
            job.update(export_parts=index, export_path=str(target))
            _save_status(manifest_path, job)
        job.update(export_state='completed')
    except Exception as exc:
        job.update(export_state='failed', export_error=str(exc) or type(exc).__name__)
    _save_status(manifest_path, job)
    return 0 if job['export_state'] == 'completed' else 1


class ManualExport:
    """Only an explicit user request launches conversion after the source closes."""
    def __init__(self, kind):
        self.kind = kind
        self._lock = threading.Lock()
        self._status = dict(export_state='pending', export_path='', export_parts=0, export_error='',
                            export_format='xlsx' if kind == 'superwatch' else 'txt')
        self._started = False
        self._manifest = None

    def status(self):
        with self._lock:
            if self._manifest is not None and self._status['export_state'] == 'generating':
                try:
                    job = json.loads(self._manifest.read_text(encoding='utf-8'))
                    self._status.update({key: value for key, value in job.items() if key.startswith('export_')})
                except (OSError, ValueError):
                    pass
            return dict(self._status)

    def start(self, recording):
        if recording.get('active') or recording.get('state') not in ('completed', 'failed'):
            raise RuntimeError('Stop recording and wait for it to finish before converting')
        with self._lock:
            if self._started:
                return
            self._started = True
            self._status['export_state'] = 'generating'
        manifest = job = None
        created = False
        try:
            path = Path(recording['path'])
            base = re.sub(r'-\d{4,}\.jsonl$', '', str(path))
            if base == str(path) or not recording['parts']:
                raise ValueError('No closed recording parts available for conversion')
            manifest = Path(base + '-export.json')
            job = dict(self._status, kind=self.kind, base=base, parts=recording['parts'],
                       started_at=recording['started_at'], complete=recording['state'] == 'completed',
                       source_error=recording.get('error', ''))
            with manifest.open('x', encoding='utf-8') as stream:
                json.dump(job, stream, ensure_ascii=False)
            created = True
            with self._lock:
                self._manifest = manifest
            command = ([sys.executable, '--internal-recording-export'] if getattr(sys, 'frozen', False)
                       else [sys.executable, str(Path(__file__).resolve())])
            environment = dict(os.environ)
            options = dict(cwd=str(path.parent), env=environment)
            if getattr(sys, 'frozen', False):
                # This process may outlive the backend's onefile extraction.
                environment.update(PYINSTALLER_RESET_ENVIRONMENT='1', TEMP=str(path.parent),
                                   TMP=str(path.parent), TMPDIR=str(path.parent))
            if os.name == 'nt':
                options['creationflags'] = (subprocess.CREATE_NO_WINDOW
                                            | subprocess.BELOW_NORMAL_PRIORITY_CLASS
                                            | subprocess.CREATE_NEW_PROCESS_GROUP)
                if environment.get('MKLINK_PARENT_JOB_BREAKAWAY_OK') == '1':
                    options['creationflags'] |= subprocess.CREATE_BREAKAWAY_FROM_JOB
            else:
                options['start_new_session'] = True
            process = subprocess.Popen([*command, str(manifest)], stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       **options)
            threading.Thread(target=self._wait, args=(process, manifest, job),
                             name='recording-export-result', daemon=True).start()
        except Exception as exc:
            self._failed(exc, manifest if created else None, job)

    def _failed(self, exc, manifest, job):
        with self._lock:
            if job:
                self._status.update({key: job[key] for key in self._status if key in job})
            self._status.update(export_state='failed', export_error=str(exc) or type(exc).__name__)
            result = dict(self._status)
        if manifest is not None and job:
            try:
                _save_status(manifest, {**job, **result})
            except OSError:
                # The in-memory status still reports the error if the disk is unavailable.
                pass

    def _wait(self, process, manifest, job):
        try:
            code = process.wait()
            job = json.loads(manifest.read_text(encoding='utf-8'))
            if code != 0 or job['export_state'] != 'completed':
                raise RuntimeError(job.get('export_error') or f'Recording export worker exited ({code})')
            with self._lock:
                self._status.update({key: value for key, value in job.items() if key.startswith('export_')})
        except Exception as exc:
            self._failed(exc, manifest, job)


def main(arguments=None):
    args = sys.argv[1:] if arguments is None else list(arguments)
    if len(args) != 1:
        return 2
    if os.name != 'nt':
        os.nice(10)
    job = json.loads(Path(args[0]).read_text(encoding='utf-8'))
    if job.get('export_format') == 'xlsx':
        from mklink.recording_excel import export_excel
        return export_excel(args[0])
    return export_text(args[0])


if __name__ == '__main__':
    raise SystemExit(main())

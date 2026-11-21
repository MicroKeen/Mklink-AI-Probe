"""Read a selected local recording for the existing browser replay Worker."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import stat

from .frontend_contract import keys, require

REPLAY_EXTENSIONS = {'.csv', '.txt', '.log', '.jsonl', '.ndjson'}
MAX_BYTES = 256 * 1024 * 1024  # superwatch_replay_data.js REPLAY_LIMITS.bytes
MAX_LINE = 1024 * 1024
TIME_COLUMNS = {'timestamp', '_t', 'timestamp_s', 'time', 'time(s)', 'timestamp_ms', 'timestamp_us'}


def recording_file(body):
    keys(body, {'path'})
    raw = body['path']
    require(isinstance(raw, str) and 1 <= len(raw) <= 4096 and not any(ord(char) < 32 for char in raw), message='Choose a local recording path')
    candidate = Path(raw).expanduser()
    require(candidate.is_absolute() and not str(candidate).startswith(('\\\\', '//')),
            message='Choose an absolute local path on the backend computer')
    require(candidate.suffix.lower() in REPLAY_EXTENSIONS, 'UNSUPPORTED_FORMAT', 'Choose a CSV, TXT, LOG, JSONL or NDJSON recording')
    try:
        # Check the unresolved chain too: resolve() alone hides a redirect.
        for part in [*reversed(candidate.parents), candidate]:
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode)
                    and not getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0),
                    'INVALID_PATH', 'Recording paths must not traverse a link or junction')
        resolved = candidate.resolve(strict=True)
        info = resolved.stat()
        require(stat.S_ISREG(info.st_mode), 'INVALID_PATH', 'Choose a regular recording file')
        require(0 < info.st_size <= MAX_BYTES, 'FILE_LIMIT', 'Recording must contain 1 byte to 256 MiB', 413)
        with resolved.open('rb') as source:
            # Only inspect the first effective line. The existing Worker owns
            # full parsing, continuity markers, numeric limits and diagnostics.
            remaining = MAX_LINE + 1
            first = ''
            while remaining:
                line = source.readline(remaining)
                remaining -= len(line)
                if not line:
                    break
                first = line.decode('utf-8-sig').strip()
                if first:
                    break
        require(bool(first) and len(first.encode('utf-8')) <= MAX_LINE and '\x00' not in first,
                'UNSUPPORTED_FORMAT', 'Recording has no supported UTF-8 header within 1 MiB')
        if first.startswith('{'):
            value = json.loads(first)
            valid = isinstance(value, dict) and (
                ('_t' in value or 'timestamp_us' in value)
                or value.get('event') in ('discontinuity', 'write'))
        elif first.startswith('['):
            valid = bool(re.match(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\]\s+[^=]+=.+', first))
        else:
            valid = False
            for delimiter in (',', ';', '\t'):
                try:
                    header = [cell.strip() for cell in next(csv.reader([first], delimiter=delimiter, strict=True))]
                except csv.Error:
                    continue
                if (2 <= len(header) <= 65 and all(header) and len(set(header)) == len(header)
                        and any(cell.lower() in TIME_COLUMNS for cell in header)):
                    valid = True
                    break
        require(valid, 'UNSUPPORTED_FORMAT', 'File does not begin with a supported SuperWatch recording header')
        return resolved, info
    except FileNotFoundError as exc:
        from fastapi import HTTPException
        raise HTTPException(404, {'code': 'NOT_FOUND', 'message': 'Recording file not found'}) from exc
    except (OSError, UnicodeError, ValueError) as exc:
        from fastapi import HTTPException
        raise HTTPException(422, {'code': 'INVALID_RECORDING', 'message': 'Recording cannot be read as a supported local UTF-8 file'}) from exc

"""Stream a closed SuperWatch recording into a readable Excel workbook."""
from __future__ import annotations

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

import xlsxwriter

from mklink.recording_text import _date, _rows, _safe, _save_status

MAX_ROWS = 1_048_576  # Includes the header row.
MAX_COLUMNS = 16_384


def export_excel(manifest_path):
    manifest_path = Path(manifest_path)
    job = json.loads(manifest_path.read_text(encoding='utf-8'))
    target = Path(job['base'] + '.xlsx')
    created = False
    try:
        # Exclusive creation never overwrites a user's workbook. Temporary XML
        # lives beside the output, not in the user's system TEMP directory.
        with TemporaryDirectory(prefix='.mklink-xlsx-', dir=target.parent) as temporary, target.open('xb') as output:
            created = True
            with xlsxwriter.Workbook(output, {'constant_memory': True, 'tmpdir': temporary,
                                             'strings_to_formulas': False, 'strings_to_urls': False,
                                             'use_zip64': True}) as book:
                heading = book.add_format({'bold': True, 'bg_color': '#203850', 'font_color': '#FFFFFF'})
                time_format = book.add_format({'num_format': '0.000000000'})
                info = book.add_worksheet('Info')
                info.set_column(0, 0, 24); info.set_column(1, 1, 100)
                metadata = [
                    ('MKLink SuperWatch', 'Excel export'),
                    ('Recording started', _date(job['started_at'])),
                    ('Source', 'Complete' if job['complete'] else 'INCOMPLETE: ' + _safe(job['source_error'])),
                    ('Time (s)', 'Acquisition-relative seconds from JSONL _t; not host wall-clock time.'),
                    ('Values', 'Numeric cells for analysis; Excel supports about 15 significant digits. Use JSONL for lossless replay.'),
                    ('Sheets', 'Numbered sheets continue in order. Blank values mean unavailable; Event marks discontinuities.'),
                    ('JSONL parts', str(job['parts'])),
                ]
                for row, fields in enumerate(metadata):
                    info.write_string(row, 0, fields[0], heading if row == 0 else None)
                    info.write_string(row, 1, fields[1], heading if row == 0 else None)
                sheet = None; names = []; row_index = 0; sheets = 0; samples = 0

                def finish_sheet():
                    if sheet is not None:
                        sheet.autofilter(0, 0, row_index - 1, len(names) + 1)

                def new_sheet(columns):
                    nonlocal sheet, names, row_index, sheets
                    finish_sheet()
                    if len(columns) + 2 > MAX_COLUMNS:
                        raise ValueError('Too many variables for an Excel worksheet')
                    names = columns; sheets += 1
                    sheet = book.add_worksheet(f'Data {sheets:03d}')
                    sheet.freeze_panes(1, 1)
                    sheet.set_column(0, 0, 19)
                    for column, name in enumerate(['Time (s)', *names, 'Event']):
                        sheet.write_string(0, column, _safe(name), heading)
                        if column: sheet.set_column(column, column, min(42, max(18, len(name) + 2)))
                    row_index = 1

                for part in range(1, job['parts'] + 1):
                    for point in _rows(Path(job['base'] + f'-{part:04d}.jsonl')):
                        boundary = point.get('event') == 'discontinuity'
                        columns = [name for name in point if name != '_t'] if not boundary else names
                        if sheet is None or row_index >= MAX_ROWS or set(columns) - set(names):
                            new_sheet(columns)
                        if boundary:
                            sheet.write_string(row_index, len(names) + 1, 'DISCONTINUITY reason=' + _safe(point.get('reason')))
                        else:
                            stamp = point.get('_t')
                            if not isinstance(stamp, (float, int)) or not math.isfinite(stamp):
                                raise ValueError('Invalid SuperWatch sample timestamp')
                            sheet.write_number(row_index, 0, stamp, time_format)
                            for column, name in enumerate(names, 1):
                                value = point.get(name)
                                if value is None: continue
                                if not isinstance(value, (int, float)) or not math.isfinite(value):
                                    raise ValueError('Invalid SuperWatch sample value')
                                sheet.write_number(row_index, column, value)
                            samples += 1
                        row_index += 1
                    job.update(export_parts=part, export_rows=samples)
                    _save_status(manifest_path, job)
                finish_sheet()
                info.write_number(len(metadata), 1, samples)
                info.write_string(len(metadata), 0, 'Samples')
        job.update(export_state='completed', export_path=str(target), export_sheets=sheets)
    except Exception as exc:
        job.update(export_state='failed', export_error=str(exc) or type(exc).__name__)
        if created:
            try:
                target.unlink()
            except OSError:
                pass  # The failed status remains visible; never touch the JSONL.
    _save_status(manifest_path, job)
    return 0 if job['export_state'] == 'completed' else 1

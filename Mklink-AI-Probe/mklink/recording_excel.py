"""Stream SuperWatch rows into XLSX without named intermediate XML files."""
from __future__ import annotations

import io
import json
import math
import re
import shutil
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryFile
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

from mklink.recording_text import _date, _rows, _safe, _save_status
from mklink.work_files import file_error

MAX_ROWS = 1_048_576  # Includes the header row.
MAX_COLUMNS = 16_384
_SHEET_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def _text_cell(ref, text, style=0):
    text = _safe(text)[:32767]
    text = re.sub(r'_(?=x[0-9a-fA-F]{4}_)', '_x005F_', text)
    text = re.sub('[\ufffe\uffff\ud800-\udfff]', '\ufffd', text)
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'


def _number_cell(ref, value, style=0):
    if not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f'采样单元格 {ref} 需要有限数值，实际为 {value!r}')
    return f'<c r="{ref}" s="{style}"><v>{value:.16G}</v></c>'


class _DataSheet:
    def __init__(self, names, rows, heading):
        if len(names) + 2 > MAX_COLUMNS:
            raise ValueError('采样变量超过 Excel 每页的 16384 列限制')
        self.names = names
        self.known_names = set(names)
        self.rows = rows
        self.count = 1
        self.columns = [xl_col_to_name(i) for i in range(len(names) + 2)]
        self.labels = ['Time (s)', *names, 'Event']
        self._row([_text_cell(col + '1', label, heading)
                   for col, label in zip(self.columns, self.labels)])

    def _row(self, cells):
        self.rows.write(f'<row r="{self.count}">{"".join(cells)}</row>'.encode('utf-8'))

    def append(self, point, boundary, time_style):
        self.count += 1
        row = str(self.count)
        if boundary:
            self._row([_text_cell(self.columns[-1] + row, 'DISCONTINUITY reason=' + str(point.get('reason')))])
            return
        cells = [_number_cell('A' + row, point.get('_t'), time_style)]
        for col, name in zip(self.columns[1:], self.names):
            value = point.get(name)
            if value is not None:
                cells.append(_number_cell(col + row, value))
        self._row(cells)

    def finish(self, archive, index):
        extent = f'A1:{self.columns[-1]}{self.count}'
        widths = [19, *(min(42, max(18, len(label) + 2)) for label in self.labels[1:])]
        cols = ''.join(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>'
                       for i, width in enumerate(widths, 1))
        prefix = (f'<worksheet xmlns="{_SHEET_NS}"><dimension ref="{extent}"/>'
                  '<sheetViews><sheetView workbookViewId="0"><pane xSplit="1" ySplit="1" '
                  'topLeftCell="B2" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>'
                  f'<cols>{cols}</cols><sheetData>')
        self.rows.seek(0)
        with archive.open(f'xl/worksheets/sheet{index + 1}.xml', 'w', force_zip64=True) as dest:
            dest.write(prefix.encode())
            shutil.copyfileobj(self.rows, dest)
            dest.write(f'</sheetData><autoFilter ref="{extent}"/></worksheet>'.encode())
        self.rows.seek(0)
        self.rows.truncate()


def _write_book(job, manifest, target, output):
    # Only workbook metadata and the Info sheet use XlsxWriter's memory mode.
    # Sample XML uses one anonymous handle, closed by the OS even on Windows.
    with ExitStack() as stack:
        archive = stack.enter_context(ZipFile(output, 'w', ZIP_DEFLATED))
        rows = stack.enter_context(TemporaryFile(dir=target.parent))
        metadata = io.BytesIO()
        book = xlsxwriter.Workbook(metadata, {'in_memory': True})
        info = book.add_worksheet('Info')
        heading = book.add_format({'bold': True, 'bg_color': '#203850', 'font_color': '#FFFFFF'})
        time_format = book.add_format({'num_format': '0.000000000'})
        heading_id, time_id = heading._get_xf_index(), time_format._get_xf_index()
        info.set_column(0, 0, 24)
        info.set_column(1, 1, 100)
        fields = [('MKLink SuperWatch', 'Excel export'), ('Recording started', _date(job['started_at'])),
                  ('Source', 'Complete' if job['complete'] else 'INCOMPLETE: ' + _safe(job['source_error'])),
                  ('Time (s)', 'Acquisition-relative seconds from JSONL _t.'),
                  ('Values', 'Excel supports about 15 significant digits. Use JSONL for lossless replay.'),
                  ('Sheets', 'Numbered sheets continue in order. Blank values mean unavailable; Event marks discontinuities.'),
                  ('JSONL parts', str(job['parts']))]
        for row, (label, value) in enumerate(fields):
            info.write_string(row, 0, label, heading if row == 0 else None)
            info.write_string(row, 1, value, heading if row == 0 else None)
        sheet = None
        sheets = samples = 0
        for part in range(1, job['parts'] + 1):
            for point in _rows(Path(job['base'] + f'-{part:04d}.jsonl')):
                boundary = point.get('event') == 'discontinuity'
                if sheet is None or sheet.count >= MAX_ROWS or (
                        not boundary and any(name != '_t' and name not in sheet.known_names for name in point)):
                    names = [name for name in point if name != '_t']
                    if boundary:
                        names = sheet.names if sheet else []
                    if sheet:
                        sheet.finish(archive, sheets)
                    sheets += 1
                    book.add_worksheet(f'Data {sheets:03d}')
                    sheet = _DataSheet(names, rows, heading_id)
                sheet.append(point, boundary, time_id)
                if not boundary:
                    samples += 1
            job.update(export_parts=part, export_rows=samples)
            _save_status(manifest, job)
        if sheet:
            sheet.finish(archive, sheets)
        info.write_string(len(fields), 0, 'Samples')
        info.write_number(len(fields), 1, samples)
        book.close()
        with ZipFile(metadata) as shell:
            for name in shell.namelist():
                if name.startswith('xl/worksheets/sheet') and name != 'xl/worksheets/sheet1.xml':
                    continue
                archive.writestr(name, shell.read(name))
        return sheets


def export_excel(manifest_path):
    manifest = Path(manifest_path)
    job = json.loads(manifest.read_text(encoding='utf-8'))
    target = Path(job.get('output_base', job['base']) + '.xlsx')
    created = False
    try:
        with target.open('xb') as output:
            created = True
            sheets = _write_book(job, manifest, target, output)
        job.update(export_state='completed', export_path=str(target), export_sheets=sheets)
    except Exception as exc:
        job.update(export_state='failed', export_error=file_error('转换 Excel', exc, target))
        if created:
            try:
                target.unlink()
            except OSError as cleanup:
                job['export_error'] += ' ' + file_error('移除未完成的工作簿', cleanup, target)
    _save_status(manifest, job)
    return 0 if job['export_state'] == 'completed' else 1

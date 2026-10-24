import io
import json
import zipfile
from datetime import datetime
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from mklink.connection_diagnostics import connection_log, event, export_bundle, error_detail
from mklink.mux import MuxTransport


def rows(directory):
    return [json.loads(line) for line in (directory / 'connection.jsonl').read_text(encoding='utf-8').splitlines()]


def test_first_mux_timeout_retains_request_and_ages_without_payload(tmp_path):
    transport = MuxTransport(lambda data: len(data), diagnostic_context={'port': 'TEST'})
    transport._pending = (2, 97, 0, True)
    transport._last_receive = transport._last_reply = 0
    with connection_log(tmp_path):
        transport.tick()
        transport.tick()
        transport.fail('secondary teardown failure')
    failed = [row for row in rows(tmp_path) if row['event'] == 'mux.failed']
    assert len(failed) == 1
    failure = failed[0]
    assert datetime.fromisoformat(failure['time']).tzinfo is not None
    assert failure['pending'] == {'opcode': '0x02', 'request': 97, 'heartbeat': True}
    assert failure['timeout']['last_receive_age_ms'] > 0
    assert 'secondary' not in json.dumps(failure)
    assert 'nonce' not in failure


def test_reader_records_first_error_with_os_cause(tmp_path):
    from mklink.bridge import MKLinkSerialBridge
    bridge = MKLinkSerialBridge('TEST')
    cause = OSError(22, 'device unavailable')
    cause.winerror = 433
    error = ConnectionError('serial worker failed')
    error.__cause__ = cause
    with connection_log(tmp_path):
        bridge._record_transport_error(error, 'serial_reader')
        bridge._record_transport_error(OSError('cleanup'), 'serial_reader')
    failures = [r for r in rows(tmp_path) if r['event'] == 'transport.failed']
    assert len(failures) == 1
    assert failures[0]['error'][1]['winerror'] == 433
    assert failures[0]['source'] == 'serial_reader'


def test_export_only_structured_allowlisted_logs_and_redacts_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv('MKLINK_RUNTIME_DIR', str(tmp_path))
    (tmp_path / 'endpoint.json').write_text('{"token":"ENDPOINT_SECRET"}')
    (tmp_path / 'runtime.log').write_text('RTT_TARGET_DATA')
    with connection_log(tmp_path):
        event('transport.failed', token='TOKEN_VALUE', error=error_detail(ValueError('Authorization=Bearer SECRET token=URL_SECRET')))
    with zipfile.ZipFile(io.BytesIO(export_bundle())) as archive:
        assert set(archive.namelist()) == {'manifest.json', 'connection-0.jsonl'}
        contents = ''.join(archive.read(n).decode() for n in archive.namelist())
        for secret in ('ENDPOINT_SECRET', 'RTT_TARGET_DATA', 'TOKEN_VALUE', 'URL_SECRET', 'Bearer SECRET'):
            assert secret not in contents
        assert '[redacted]' in contents and 'transport.failed' in contents


def test_partial_records_do_not_invalidate_export(tmp_path, monkeypatch):
    monkeypatch.setenv('MKLINK_RUNTIME_DIR', str(tmp_path))
    (tmp_path / 'connection.jsonl').write_text('{"event":"complete"}\n{"unfinished":')
    with zipfile.ZipFile(io.BytesIO(export_bundle())) as archive:
        assert archive.read('connection-0.jsonl') == b'{"event": "complete"}\n'


def test_desktop_export_survives_backend_failure_and_rejects_foreign_origin(tmp_path, monkeypatch):
    from mklink.runtime_proxy import create_proxy
    monkeypatch.setenv('MKLINK_RUNTIME_DIR', str(tmp_path))
    def unavailable(request):
        raise httpx.ConnectError('backend down')
    app = create_proxy({'port': 12345, 'token': 'PRIVATE_TOKEN'}, port=8765,
                       instance_id='fixture', transport=httpx.MockTransport(unavailable))
    with connection_log(tmp_path), TestClient(app, base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/health').status_code == 503
        assert client.post('/api/runtime/diagnostics/events', json={'events': [
            {'event': 'status_failed', 'time': '2026-10-24T10:00:00Z', 'message': 'HTTP 503'}]}).status_code == 200
        result = client.get('/api/diagnostics/export')
        assert result.status_code == 200 and result.headers['content-type'] == 'application/zip'
        assert client.get('/api/diagnostics/export', headers={'Origin': 'https://untrusted.example'}).status_code == 403
        assert client.post('/api/runtime/diagnostics/events', json={'events': [{'event': 'arbitrary', 'time': ''}]}).status_code == 422
    with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
        text = archive.read('connection-0.jsonl').decode()
        assert 'gui.status_failed' in text and 'PRIVATE_TOKEN' not in text


def test_diagnostics_failure_cannot_break_transport(tmp_path, monkeypatch):
    from mklink import connection_diagnostics as diagnostics
    def broken(*args):
        raise OSError('disk failure')
    monkeypatch.setattr(diagnostics, '_sink', SimpleNamespace(handle=broken))
    transport = MuxTransport(lambda wire: len(wire))
    transport.fail('original error')
    assert str(transport._error) == 'original error'


def test_diagnostics_open_failure_does_not_prevent_backend_start(tmp_path, monkeypatch):
    from mklink import connection_diagnostics as diagnostics
    def denied(*args, **kwargs):
        raise PermissionError('no diagnostic file permission')
    monkeypatch.setattr(diagnostics, 'RotatingFileHandler', denied)
    with connection_log(tmp_path):
        event('still.working')


def test_export_installed_after_web_spa_fallback_returns_zip(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    from mklink.connection_diagnostics import install_export
    monkeypatch.setenv('MKLINK_RUNTIME_DIR', str(tmp_path))
    app = FastAPI()
    @app.get('/{full_path:path}')
    def spa(full_path: str):
        return HTMLResponse('<html>app</html>')
    install_export(app)
    with TestClient(app) as client:
        result = client.get('/api/diagnostics/export')
        assert result.headers['content-type'] == 'application/zip'
        assert zipfile.is_zipfile(io.BytesIO(result.content))
        assert client.get('/dashboard').headers['content-type'].startswith('text/html')


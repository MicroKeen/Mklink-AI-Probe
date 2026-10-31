"""Reused loopback ports must not abort discovery or replay a command."""
from http.client import HTTPException
import json
import socketserver
import threading

import pytest

from mklink import runtime


# An HTTP/2 SETTINGS frame is not an HTTP/1 status line.
HTTP2_SETTINGS = b'\x00\x00\x06\x04\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x64'
INVALID_RESPONSES = [
    pytest.param(HTTP2_SETTINGS, id='http2-settings'),
    pytest.param(b'not-http\r\n', id='bad-status-line'),
    pytest.param(b'HTTP/1.1 200 OK\r\nContent-Length: 12\r\n\r\n{', id='truncated-body'),
    pytest.param(b'HTTP/1.1 200 OK\r\nX-Long: ' + b'x' * 65537 + b'\r\n\r\n', id='long-header'),
]


def json_response(body):
    data = json.dumps(body).encode('utf-8')
    return b'HTTP/1.1 200 OK\r\nContent-Length: ' + str(len(data)).encode() + b'\r\n\r\n' + data


@pytest.fixture
def endpoints(monkeypatch, tmp_path):
    monkeypatch.setenv('MKLINK_RUNTIME_DIR', str(tmp_path / 'registry'))
    monkeypatch.setattr(runtime, '_local_http', threading.local())

    def forbidden(*args, **kwargs):
        pytest.fail('Endpoint validation must not enumerate/open hardware or spawn a backend')

    monkeypatch.setattr('serial.Serial', forbidden)
    monkeypatch.setattr('serial.tools.list_ports.comports', forbidden)
    monkeypatch.setattr(runtime.subprocess, 'Popen', forbidden)
    servers = []

    def create(response):
        calls = []

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(3)
                request_line = self.rfile.readline()
                headers = {}
                while (line := self.rfile.readline()) not in (b'\r\n', b''):
                    name, value = line.split(b':', 1)
                    headers[name.lower()] = value.strip()
                body = self.rfile.read(int(headers.get(b'content-length', b'0')))
                calls.append((request_line, body))
                self.wfile.write(response)

        server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
        worker.start()
        servers.append((server, worker))
        return {'port': server.server_address[1], 'token': 'fixture-only'}, calls

    try:
        yield create
    finally:
        for server, worker in servers:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)
            assert not worker.is_alive()


def save_endpoint(info, digit):
    probe_id = 'local-' + digit * 24
    path = runtime.runtime_dir(probe_id) / 'endpoint.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(info), encoding='utf-8')
    return probe_id, path


@pytest.mark.parametrize('response', INVALID_RESPONSES)
def test_protocol_failure_is_reported_without_replaying_post(endpoints, response):
    info, calls = endpoints(response)
    with pytest.raises(runtime.RuntimeErrorResponse, match='no direct CDC fallback') as error:
        runtime.request(info, 'POST', '/_runtime/call', {'operation': 'fixture'}, timeout=3)
    assert isinstance(error.value.__cause__, HTTPException)
    assert calls == [(b'POST /_runtime/call HTTP/1.1\r\n', b'{"operation": "fixture"}')]


@pytest.mark.parametrize('entrypoint', ['running_runtimes', 'selected_runtime', 'control_runtime'])
@pytest.mark.parametrize('response', INVALID_RESPONSES[:3])
def test_stale_port_does_not_hide_live_runtime(endpoints, response, entrypoint):
    stale, stale_calls = endpoints(response)
    _, stale_path = save_endpoint({**stale, 'instance_id': 'retired'}, '0')
    stale_bytes = stale_path.read_bytes()
    health = dict(instance_id='live', probe_id='lobby', protocol=runtime.PROTOCOL,
                  version=runtime.VERSION, status='ready')
    live, live_calls = endpoints(json_response(health))
    live = {**live, 'instance_id': 'live', 'probe_id': 'lobby', 'runtime_id': 'local-' + '1' * 24}
    save_endpoint(live, '1')

    result = getattr(runtime, entrypoint)()
    assert result == ([live] if entrypoint == 'running_runtimes'
                      else health if entrypoint == 'control_runtime' else live)
    assert len(stale_calls) == 1
    assert len(live_calls) == (2 if entrypoint == 'control_runtime' else 1)
    assert stale_path.read_bytes() == stale_bytes


@pytest.mark.parametrize('mismatch', ['instance', 'version', 'protocol'])
def test_live_identity_and_version_guards_are_preserved(endpoints, mismatch):
    health = dict(instance_id='live', probe_id='lobby', protocol=runtime.PROTOCOL,
                  version=runtime.VERSION)
    health[{'instance': 'instance_id', 'version': 'version', 'protocol': 'protocol'}[mismatch]] = 'different'
    info, calls = endpoints(json_response(health))
    probe_id, _ = save_endpoint({**info, 'instance_id': 'live'}, '1')
    if mismatch == 'instance':
        assert runtime.discover(probe_id) is None
    else:
        with pytest.raises(runtime.RuntimeErrorResponse, match='stop the old runtime explicitly'):
            runtime.discover(probe_id)
    assert len(calls) == 1


@pytest.mark.parametrize('status', [401, 409])
def test_http_rejection_keeps_status_and_structured_detail(endpoints, status):
    detail = {'code': 'fixture-rejected', 'message': 'Explicit rejection'}
    response = json_response({'detail': detail}).replace(b'200 OK', f'{status} Rejected'.encode(), 1)
    info, calls = endpoints(response)
    with pytest.raises(runtime.RuntimeErrorResponse) as error:
        runtime.request(info, 'POST', '/_runtime/call', {}, timeout=3)
    assert error.value.status_code == status
    assert error.value.detail == detail
    assert len(calls) == 1

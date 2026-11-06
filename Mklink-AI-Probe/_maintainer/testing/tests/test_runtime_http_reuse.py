"""Real loopback reuse, lifecycle isolation and no replay after a lost reply."""
import json
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from mklink import runtime


@pytest.fixture
def endpoint(monkeypatch):
    monkeypatch.setattr(runtime, '_local_http', threading.local())
    monkeypatch.setenv('HTTP_PROXY', 'http://invalid.invalid:9999')
    monkeypatch.setenv('ALL_PROXY', 'http://invalid.invalid:9999')
    calls = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            calls.append((self.client_address, dict(self.headers), body))
            if self.path == '/lost':
                self.connection.shutdown(socket.SHUT_RDWR)
                self.close_connection = True
                return
            payload = json.dumps({'ok': True}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
    worker.start()
    info = {'port': server.server_port, 'token': 'fixture', 'instance_id': 'first', 'probe_id': 'one'}
    try:
        yield info, calls
    finally:
        connection = getattr(runtime._local_http, 'connection', None)
        if connection:
            connection.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
        assert not worker.is_alive()


def test_reuses_socket_and_preserves_body_headers_and_new_timeout(endpoint):
    info, calls = endpoint
    for index in range(3):
        assert runtime.request(info, 'POST', '/call', {'index': index}, timeout=2+index) == {'ok': True}
        assert runtime._local_http.connection.sock.gettimeout() == 2+index
    assert len({address for address, _, _ in calls}) == 1
    for index, (_, headers, body) in enumerate(calls):
        assert headers['X-Auth-Token'] == 'fixture'
        assert headers['X-MKLink-Probe'] == 'one'
        assert json.loads(body) == {'index': index}


@pytest.mark.parametrize('key,value', [('instance_id','next'),('probe_id','two'),('token','new-token')])
def test_changed_backend_target_or_credentials_retires_connection(endpoint, key, value):
    info, calls = endpoint
    runtime.request(info,'POST','/call',{})
    runtime.request({**info,key:value},'POST','/call',{})
    assert calls[0][0] != calls[1][0]
    assert calls[1][1]['X-Auth-Token'] == (value if key == 'token' else 'fixture')
    assert calls[1][1]['X-MKLink-Probe'] == (value if key == 'probe_id' else 'one')


def test_idle_connection_retires_before_next_submission(endpoint, monkeypatch):
    info, calls = endpoint
    runtime.request(info,'POST','/call',{})
    monkeypatch.setattr(runtime, '_HTTP_IDLE_SECONDS', 0)
    runtime.request(info,'POST','/call',{})
    assert calls[0][0] != calls[1][0]


def test_threads_do_not_share_connections(endpoint):
    info, calls = endpoint
    barrier = threading.Barrier(2)
    def client(index):
        barrier.wait(timeout=3)
        try:
            for _ in range(2):
                runtime.request(info,'POST','/call',{'client':index})
        finally:
            runtime._local_http.connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(client,(0,1)))
    assert len(calls) == 4
    peers = [{address for address,_,body in calls if json.loads(body)['client']==index} for index in (0,1)]
    assert len(peers[0]) == len(peers[1]) == 1
    assert peers[0].isdisjoint(peers[1])


def test_lost_reply_is_not_replayed_and_next_explicit_call_uses_new_socket(endpoint):
    info, calls = endpoint
    runtime.request(info,'POST','/call',{})
    with pytest.raises(runtime.RuntimeErrorResponse,match='no direct CDC fallback'):
        runtime.request(info,'POST','/lost',{'write':'once'},timeout=2)
    assert len(calls) == 2
    assert json.loads(calls[-1][2]) == {'write':'once'}
    runtime.request(info,'POST','/call',{})
    assert calls[0][0] != calls[2][0]
    assert len(calls) == 3


def test_invalid_endpoint_rejected_before_network(endpoint):
    info,calls=endpoint
    with pytest.raises(runtime.RuntimeErrorResponse,match='Invalid runtime endpoint'):
        runtime.request({**info,'port':True},'POST','/call',{})
    assert not calls

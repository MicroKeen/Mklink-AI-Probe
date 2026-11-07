import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from mklink.s3_rpc import Endpoint
from mklink.s3_transport import WirelessLink


@pytest.fixture
def gateway():
    requests = []
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass

        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.client_address, value['method']))
            mode = value['method']
            if mode == 'disconnect':
                self.close_connection = True
                return
            data = dict(v=1, id=value['id'], ok=True, data={'answer': 42})
            if mode == 'identity':
                data['id'] = 'wrong'
            payload = json.dumps(data).encode()
            if mode == 'oversized':
                payload = b'x' * 65537
            self.send_response(302 if mode == 'redirect' else 200)
            self.send_header('Location', '/credential-sink')
            self.send_header('Content-Length', str(len(payload) + (10 if mode == 'truncated' else 0)))
            if mode in ('identity', 'oversized', 'truncated', 'redirect'):
                self.send_header('Connection', 'close')
                self.close_connection = True
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
            if mode == 'truncated':
                self.close_connection = True

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = Endpoint(dict(transport='http', address=f'http://127.0.0.1:{server.server_port}', token='private'))
    try:
        yield endpoint, requests
    finally:
        endpoint.close()
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_http_reuses_connection_and_retires_it_before_idle_submission(gateway):
    endpoint, requests = gateway
    assert endpoint.rpc('first', {}) == endpoint.rpc('second', {}) == {'answer': 42}
    assert requests[0][0] == requests[1][0]
    endpoint.http_last_use -= 2
    assert endpoint.rpc('after_idle', {}) == {'answer': 42}
    assert requests[2][0] != requests[1][0]


@pytest.mark.parametrize('failure', ['disconnect', 'identity', 'oversized', 'truncated', 'redirect'])
def test_http_failure_is_not_replayed_and_connection_is_retired(gateway, failure):
    endpoint, requests = gateway
    with pytest.raises(ConnectionError, match='no replay') as error:
        endpoint.rpc(failure, {})
    assert 'private' not in str(error.value)
    assert [method for _, method in requests] == [failure]
    assert endpoint.http is None
    if failure == 'redirect':
        assert 'HTTP 302' in str(error.value)


@pytest.mark.parametrize('capability', [False, True])
def test_only_advertised_successful_stream_activity_renews_lease(monkeypatch, capability):
    calls = []
    now = [100.0]
    monkeypatch.setattr('mklink.s3_transport.time.monotonic', lambda: now[0])
    def rpc(method, params):
        calls.append(method)
        if method == 'probe.stream.write':
            now[0] += 2
        return {}
    link = WirelessLink(rpc, '0123456789ab')
    link.lease = 'lease'
    link.renewed = 100
    link.stream_renews_lease = capability
    now[0] = 102
    link.call('probe.stream.write')
    # Count from submission, not arrival: an old reply cannot grant a new lease.
    assert link.renewed == (102 if capability else 100)
    link.renew_if_due()
    assert ('control.renew' in calls) is not capability
    now[0] = 108
    link.renew_if_due()
    assert calls[-1] == 'control.renew'


def test_pull_releases_control_lane_but_keeps_single_reader():
    import time
    from concurrent.futures import ThreadPoolExecutor
    entered, release = threading.Event(), threading.Event()
    calls = []
    def rpc(method, params):
        calls.append(method)
        return dict(generation=1, reply_base64='', accepted_bytes=4)
    def pull(method, params):
        assert method == 'probe.stream.pull'
        assert params['open_sequence'] == 9 and params['sequence'] == 1
        entered.set()
        assert release.wait(3)
        return dict(generation=1, reply_base64='dGVzdA==')
    link = WirelessLink(rpc, '0123456789ab', pull_rpc=pull)
    link.duplex = link.opened = True
    link.lease, link.generation, link.sequence = 'lease', 1, 10
    link.open_sequence, link.renewed = 9, time.monotonic()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(link.stream, 'read')
        try:
            assert entered.wait(2)
            link.stream('write', b'ping')
            assert calls == ['probe.stream.write']
            with pytest.raises(ConnectionError, match='one healthy stream reader'):
                link.stream('read')
            with pytest.raises(ConnectionError, match='reader still owns IO'):
                link.stream('close')
        finally:
            release.set()
        assert future.result(2) == b'test'
    assert not link.pulling and not link.poisoned


@pytest.mark.parametrize('capability', [None, False, 'true', True])
def test_independent_reader_is_negotiated_and_bound_to_stream_open(capability):
    from unittest.mock import Mock
    state = dict(binary_streaming=True, stream_active=False, state='ready', generation=3,
                 next_sequence=12, independent_read_sequence=capability)
    rpc = Mock(side_effect=[{'device': {'id': '0123456789ab'}, 'probe': {'ready': True}},
                           {'lease_token': 'lease'}, state,
                           {'generation': 3, 'reply_base64': ''}])
    link = WirelessLink(rpc, '0123456789ab', pull_rpc=Mock())
    link.acquire()
    link.stream('open')
    assert link.duplex is (capability is True)
    assert link.open_sequence == 12 and link.pull_sequence == 0


@pytest.mark.parametrize('reply', [{'generation': 2, 'reply_base64': ''},
                                   {'generation': 1, 'reply_base64': '!'},
                                   {'generation': 1, 'reply_base64': 'YWI='}])
def test_invalid_pull_quarantines_without_retry(reply):
    import time
    from unittest.mock import Mock
    pull = Mock(return_value=reply)
    link = WirelessLink(Mock(), '0123456789ab', pull_rpc=pull)
    link.duplex = link.opened = True
    link.lease, link.generation, link.open_sequence = 'lease', 1, 1
    link.renewed = time.monotonic()
    link.read_max = 1
    with pytest.raises(ConnectionError, match='no replay'):
        link.stream('read')
    with pytest.raises(ConnectionError):
        link.stream('read')
    assert pull.call_count == 1 and link.poisoned and not link.pulling

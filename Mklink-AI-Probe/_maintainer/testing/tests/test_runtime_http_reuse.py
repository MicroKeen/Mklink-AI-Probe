"""Local HTTP reuse must retain proxy isolation and per-request credentials."""
import io
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from mklink import runtime


def test_opener_reused_per_thread_with_fresh_request_headers(monkeypatch):
    monkeypatch.setattr(runtime, '_local_http', threading.local())
    constructed = []
    requests = []

    def build(proxy):
        assert proxy.proxies == {}
        constructed.append(threading.get_ident())
        def open_request(req, timeout):
            requests.append((threading.get_ident(), req.full_url, dict(req.header_items()), req.data, timeout))
            return io.BytesIO(b'{"ok":true}')
        return Mock(open=open_request)

    monkeypatch.setattr(runtime, 'build_opener', build)
    monkeypatch.setenv('HTTP_PROXY', 'http://invalid.invalid:9999')
    barrier = threading.Barrier(2)
    def client(index):
        barrier.wait(timeout=5)
        for number in range(2):
            assert runtime.request({'port': 8765 + index, 'token': f'{index}-{number}'},
                                   'POST', '/_runtime/call', {'n': number}, timeout=12) == {'ok': True}
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(client, (0, 1)))
    assert len(constructed) == len(set(constructed)) == 2
    assert len(requests) == 4
    for _, url, headers, body, timeout in requests:
        index, number = headers['X-auth-token'].split('-')
        assert url == f'http://127.0.0.1:{8765 + int(index)}/_runtime/call'
        assert body == ('{"n": ' + number + '}').encode()
        assert timeout == 12


def test_failed_request_is_once_and_reuse_keeps_endpoint_validation(monkeypatch):
    opener = Mock()
    opener.open.side_effect = TimeoutError('lost reply')
    monkeypatch.setattr(runtime, '_local_http', threading.local())
    build = Mock(return_value=opener)
    monkeypatch.setattr(runtime, 'build_opener', build)
    with pytest.raises(runtime.RuntimeErrorResponse, match='no direct CDC fallback'):
        runtime.request({'port': 8765, 'token': 'test'}, 'POST', '/_runtime/call', {})
    opener.open.assert_called_once()
    with pytest.raises(runtime.RuntimeErrorResponse, match='Invalid runtime endpoint'):
        runtime.request({'port': True, 'token': 'test'}, 'POST', '/', {})
    opener.open.assert_called_once()
    build.assert_called_once()

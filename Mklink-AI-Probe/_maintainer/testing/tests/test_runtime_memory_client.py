"""Transport negotiation, failure boundaries and lifecycle for SDK reads."""
from unittest.mock import Mock

import pytest

from mklink import runtime


@pytest.fixture
def client(monkeypatch):
    client = runtime.RuntimeClient(info={'port': 8765, 'token': 'fixture', 'instance_id': 'fixture'})
    client.session_id = 'session'
    http = Mock(return_value={'data_hex': '01020304'})
    monkeypatch.setattr(runtime, 'request', http)
    channel = Mock()
    factory = Mock(return_value=channel)
    monkeypatch.setattr('mklink.runtime_memory_client.MemoryChannel', factory)
    return client, http, factory, channel


def test_unadvertised_runtime_uses_existing_http(client):
    client, http, factory, _ = client
    assert client.call('read_memory', {'address': '0', 'size': 4}) == http.return_value
    factory.assert_not_called()
    assert http.call_args.args[2] == '/_runtime/call'


def test_advertised_channel_reuses_one_connection_and_leaves_other_calls_on_http(client):
    client, http, factory, channel = client
    client._memory_transport = True
    for _ in range(3):
        assert client.call('read_memory', {'address': '0', 'size': 4}) == channel.read.return_value
    factory.assert_called_once_with(client.info, 'session')
    http.assert_not_called()
    assert client.call('device_status') == http.return_value
    client.close()
    channel.close.assert_called_once()
    assert client.session_id is None and client._memory_channel is None


@pytest.mark.parametrize('phase', ['connect', 'read'])
def test_channel_failure_never_falls_back_or_replays(client, phase):
    client, http, factory, channel = client
    client._memory_transport = True
    (factory if phase == 'connect' else channel.read).side_effect = TimeoutError('lost response')
    with pytest.raises(runtime.RuntimeErrorResponse, match='not retried'):
        client.call('read_memory', {'address': '0', 'size': 4})
    factory.assert_called_once()
    http.assert_not_called()
    assert client._memory_channel is None
    if phase == 'read':
        channel.read.assert_called_once()
        channel.close.assert_called_once()


def test_channel_server_error_preserves_detail(client):
    client, http, _, channel = client
    client._memory_transport = True
    error = runtime.RuntimeErrorResponse('busy', status_code=409, detail={'detail': 'busy'})
    channel.read.side_effect = error
    with pytest.raises(runtime.RuntimeErrorResponse) as caught:
        client.call('read_memory', {'address': '0', 'size': 4})
    assert caught.value is error
    http.assert_not_called()
    assert client._memory_channel is None


def test_disconnect_closes_channel_before_releasing_target(client):
    client, http, _, channel = client
    client._memory_channel = channel
    http.side_effect = lambda *args, **kwargs: (channel.close.assert_called_once() or {})
    client.disconnect()
    assert client.session_id is None and client._memory_channel is None


def test_channel_socket_idle_timeout_and_backend_binding(monkeypatch):
    from mklink.runtime_memory_client import MemoryChannel
    raw = Mock()
    connect = Mock()
    monkeypatch.setattr('socket.create_connection', Mock(return_value=raw))
    monkeypatch.setattr('websockets.sync.client.connect', connect)
    channel = MemoryChannel({'port': 8765, 'token': 'test', 'instance_id': 'instance',
                             'probe_id': 'probe'}, 'session')
    raw.settimeout.assert_called_once_with(None)
    assert connect.call_args.kwargs['sock'] is raw
    assert connect.call_args.kwargs['additional_headers'] == {
        'Authorization': 'Bearer test', 'X-MKLink-Session': 'session',
        'X-MKLink-Probe': 'probe', 'X-MKLink-Instance': 'instance'}
    channel.close()
    connect.return_value.close.assert_called_once()

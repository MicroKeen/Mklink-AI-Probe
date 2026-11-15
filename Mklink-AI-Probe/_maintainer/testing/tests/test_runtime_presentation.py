import asyncio
import threading
import pytest
from test_shared_runtime import runtime, attach, call


def test_selection_and_validation(runtime):
    client, control, calls, managers, _ = runtime
    session = attach(client)
    assert call(client, session, 'gui_windows').json() == {'windows': []}
    assert call(client, session, 'gui_present').status_code == 409
    for tab in ['https://evil', [], None, 'serial']:
        assert call(client, session, 'gui_present', {'tab': tab}).status_code == 422
    with client.websocket_connect('ws://127.0.0.1:8765/api/runtime/control/view/old') as old:
        old.receive_json()
        assert call(client, session, 'gui_windows').json() == {'windows': []}
    assert calls == []


def test_targeted_ack_during_capture(runtime):
    client, control, calls, managers, _ = runtime
    session = attach(client)
    managers['rtt'].running = True
    managers['superwatch'].running = True
    with client.websocket_connect('ws://127.0.0.1:8765/api/runtime/control/view/a?presentation=1') as a, client.websocket_connect('ws://127.0.0.1:8765/api/runtime/control/view/b?presentation=1') as b:
        a.receive_json(); b.receive_json()
        assert len(call(client, session, 'gui_windows').json()['windows']) == 2
        assert call(client, session, 'gui_present').status_code == 409
        result = []
        worker = threading.Thread(target=lambda: result.append(call(client, session, 'gui_present', {'window_id': 'a'})))
        worker.start()
        msg = a.receive_json()
        assert msg['tab'] == 'superwatch'
        assert call(client, session, 'gui_present', {'window_id': 'a'}).status_code == 409
        a.send_json({'type': 'present_result', 'request_id': msg['request_id'], 'ok': True})
        worker.join(5)
        assert not worker.is_alive()
        assert result[0].json()['status'] == 'displayed'
        assert not control.views['b'].get('pending')
        assert calls == []
        assert managers['rtt'].running and managers['superwatch'].running
    assert call(client, session, 'gui_windows').json() == {'windows': []}


def test_socket_loss_is_not_success(runtime):
    client, control, calls, _, _ = runtime
    session = attach(client)
    result = []
    with client.websocket_connect('ws://127.0.0.1:8765/api/runtime/control/view/a?presentation=1') as a:
        a.receive_json()
        worker = threading.Thread(target=lambda: result.append(call(client, session, 'gui_present')))
        worker.start(); a.receive_json()
    worker.join(5)
    assert result[0].json()['status'] == 'disconnected'
    assert calls == []



def test_unacknowledged_request_expires_without_replay(runtime):
    client, control, calls, _, _ = runtime
    session = attach(client)
    result = []
    with client.websocket_connect('ws://127.0.0.1:8765/api/runtime/control/view/a?presentation=1') as a:
        a.receive_json()
        worker = threading.Thread(target=lambda: result.append(call(client, session, 'gui_present')))
        worker.start(); message = a.receive_json()
        a.send_json({'type': 'present_result', 'request_id': 'wrong', 'ok': True})
        worker.join(5)
        assert not worker.is_alive()
        assert result[0].json()['status'] == 'unconfirmed'
        assert 'pending' not in control.views['a']
        a.send_json({'type': 'present_result', 'request_id': message['request_id'], 'ok': True})
    assert calls == []


def test_gui_actions_require_new_window_and_do_not_touch_capture(runtime):
    client, control, calls, managers, _ = runtime
    session = attach(client)
    managers['systemview'].running = True
    with client.websocket_connect('ws://127.0.0.1:8765/api/runtime/control/view/a?presentation=1') as socket:
        socket.receive_json()
        assert call(client, session, 'gui_snapshot', {'window_id': 'a'}).status_code == 409
        socket.send_json({'type': 'gui_hello', 'protocol': 2, 'kind': 'desktop'})
        # Synchronize on the same socket before the following HTTP request.
        result = []
        worker = threading.Thread(target=lambda: result.append(call(client, session, 'gui_action',
            {'window_id': 'a', 'action': 'navigate', 'page': 'dashboard', 'tab': 'serial'})))
        worker.start()
        msg = socket.receive_json()
        assert msg['command']['tab'] == 'serial'
        socket.send_json({'type': 'present_result', 'request_id': msg['request_id'], 'ok': True})
        assert control.views['a']['pending_kind'] == 'gui_result'
        socket.send_json({'type': 'gui_result', 'request_id': msg['request_id'], 'ok': True,
                         'state': {'page': 'dashboard', 'tab': 'serial'}})
        worker.join(5)
        assert result[0].json()['status'] == 'applied'
        assert result[0].json()['state']['tab'] == 'serial'
        window = call(client, session, 'gui_windows').json()['windows'][0]
        assert window['gui_protocol'] == 2 and window['kind'] == 'desktop'
        assert calls == [] and managers['systemview'].running


@pytest.mark.parametrize('body', [
    {'action': 'eval', 'code': 'anything'}, {'action': 'navigate', 'page': 'https://bad'},
    {'action': 'navigate', 'page': 'config', 'tab': 'systemview'},
    {'action': 'navigate', 'page': 'dashboard', 'section': 'firmware'},
    {'action': 'systemview.window', 'seconds': True}, {'action': 'systemview.window', 'seconds': 0},
    {'action': 'systemview.pause', 'confirm': True}, {'action': 'snapshot', 'window_id': []},
])
def test_gui_action_rejects_unsupported_payloads(runtime, body):
    client, _, calls, _, _ = runtime
    assert call(client, attach(client), 'gui_action', body).status_code == 422
    assert calls == []


def test_gui_action_socket_loss_is_not_success(runtime):
    client, control, calls, _, _ = runtime
    session = attach(client)
    result = []
    with client.websocket_connect('ws://127.0.0.1:8765/api/runtime/control/view/a?presentation=1') as socket:
        socket.receive_json()
        control.views['a']['gui_protocol'] = 2
        worker = threading.Thread(target=lambda: result.append(call(client, session, 'gui_snapshot', {'window_id': 'a'})))
        worker.start(); socket.receive_json()
    worker.join(5)
    assert result[0].json()['status'] == 'disconnected'
    assert calls == []

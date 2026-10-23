"""Read-only RTT discovery uses the shared admission/capability path."""
from types import SimpleNamespace
from unittest.mock import Mock
import struct

import pytest
from fastapi.testclient import TestClient
from mklink.remote.api import create_app
from mklink.runtime_api import install_runtime
from mklink.runtime_capabilities import CAPABILITIES, validate_arguments


def discovery_device(tmp_path, *, mux, jtag=False, read_status=0):
    """Real bridge/framing and Device parser, with bounded target RAM replies."""
    from mklink._types import DeviceState
    from mklink.bridge import MKLinkSerialBridge
    from mklink.device import Device
    from mklink.mux import packet

    base = 0x880DC if jtag else 0x20000100
    ram = b'SEGGER RTT'.ljust(16, b'\0') + struct.pack('<II', 1, 1)
    ram += struct.pack('<6I', 0, base + 128, 64, 4, 0, 0) * 2
    bridge = MKLinkSerialBridge('TEST_RTT_DISCOVERY')
    bridge._ctx.state = DeviceState.READY
    bridge._ctx.idcode = 0x1000563D if jtag else 0x1BA01477
    bridge._mux_marker = tmp_path / 'mux'
    commands = []

    def text(command, **kwargs):
        commands.append(command)
        if command == 'cmd.get_version()':
            return 'MUX_TARGET=1' if mux else 'legacy firmware'
        # A MUX-capable fresh HPM connection must not take the old read path.
        assert not mux, command
        assert command.startswith('cmd.read_ram('), command
        address, size = (int(part.strip(), 0) for part in command[13:-1].split(','))
        data = ram[address-base:address-base+size]
        return '\n'.join(f'{address+i:08x} ' + data[i:i+16].hex(' ')
                         for i in range(0, len(data), 16))

    def write(wire):
        if wire == b'~MKLINK-MUX1\n':
            commands.append('enter-mux')
            return len(wire)
        _, _, op, size, epoch, seq = struct.unpack_from('<4sBBHII', wire)
        commands.append(op)
        payload = wire[16:16+size]
        if 0x10 <= op < 0x40:
            assert payload[:8] == bridge._mux.nonce
            payload = payload[8:]
        answer = {1: struct.pack('<IHH', 15, 256, 1), 4: payload,
                  0x10: bytes(15) + bytes([2 if jtag else 1])}.get(op, b'')
        if op == 0x11:
            address, length = struct.unpack('<IH', payload)
            answer = ram[address-base:address-base+length]
        status = read_status if op == 0x11 else 0
        bridge._mux.feed(packet(op | 0x80, 17, seq, bytes([status]) + answer))
        return len(wire)

    bridge.send_command = Mock(side_effect=text)
    bridge._serial = SimpleNamespace(write=write)
    device = Device(project_root=str(tmp_path))
    device._connected, device._bridge = True, bridge
    device._target_writable_ram_ranges = lambda: ((base, base + 4096),)
    return device, base, commands


@pytest.mark.parametrize('model,mux,jtag', [
    ('V2 ARM legacy', False, False), ('V3 ARM legacy', False, False),
    ('V4 ARM legacy', False, False), ('V3 ARM MUX', True, False),
    ('V4 ARM MUX', True, False), ('V4 HPM JTAG MUX', True, True),
])
def test_fresh_connection_inspect_reads_channels_without_capture(tmp_path, model, mux, jtag):
    device, base, commands = discovery_device(tmp_path, mux=mux, jtag=jtag)
    info = device.rtt_inspect(base)
    assert info['channels'] == [0]
    assert info['up_buffers'][0]['size'] == 64
    assert info['down_buffers'][0]['active']
    assert device._rtt_session is None
    assert 0x20 not in commands and 0x32 not in commands  # No capture start.
    assert 0x12 not in commands and 0x14 not in commands  # No write/reset.
    assert ('enter-mux' in commands) is mux
    assert (0x13 in commands) is (mux and not jtag)  # SWD attach only on ARM.


@pytest.mark.parametrize('jtag', [False, True])
@pytest.mark.parametrize('first', ['rtt', 'superwatch'])
def test_inspect_during_both_start_orders_preserves_streams(tmp_path, jtag, first):
    from mklink.mux import packet
    from mklink.mux_watch import MuxWatchSession
    device, base, commands = discovery_device(tmp_path, mux=True, jtag=jtag)
    device.rtt_inspect(base)  # Search immediately after connecting.
    transport = device._bridge._mux
    watch = MuxWatchSession(transport, [(base + 128, 4)], .01)
    starts = {'rtt': lambda: device.rtt_start(base, mode=1), 'superwatch': watch.start}
    starts[first]()
    device.rtt_inspect(base)  # Search while only the first capture is active.
    starts['superwatch' if first == 'rtt' else 'rtt']()
    transport.feed(packet(0x40, 17, 1, struct.pack('<BBI', 0, 0, 10) + b'boot\n'))
    transport.feed(packet(0x41, 17, 2, struct.pack('<BBI', 0, 0, 10) + b'abcd'))
    before = list(commands)
    device.rtt_inspect(base)
    assert all(op == 0x11 for op in commands[len(before):])
    assert transport.rtt_mask == 1 and transport.watch_running
    assert device._rtt_session.read_channels(0) == {0: b'boot\n'}
    assert watch.read_frames()[0]['regions'] == [(0, b'abcd')]
    assert commands.count('enter-mux') == 1
    assert commands.count('cmd.get_version()') == 1
    watch.stop()
    device.rtt_stop()


def test_inspect_mux_read_failure_does_not_fallback_or_start_capture(tmp_path):
    from mklink.mux import MuxTargetError
    device, base, commands = discovery_device(tmp_path, mux=True, jtag=True, read_status=5)
    with pytest.raises(MuxTargetError):
        device.rtt_inspect(base)
    assert commands.count(0x11) == 1
    assert device._rtt_session is None
    assert not any(isinstance(op, str) and op.startswith('cmd.read_ram') for op in commands)


@pytest.mark.parametrize('address', ['0x20000001', '-4', '0x100000000', 'bad'])
def test_inspect_rejects_invalid_addresses(address):
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        validate_arguments('rtt_inspect', {'address': address})


@pytest.mark.parametrize('idcode', [0, 0x1ba01477])
def test_http_inspect_requires_identity_without_starting_capture(tmp_path, monkeypatch, idcode):
    app = create_app(auth_token=None, project_root=str(tmp_path))
    result = {'channels': [0, 1], 'control_block_addr': '0x20000000'}
    inspect = Mock(return_value=result)
    device = SimpleNamespace(connected=True, port='COM9', idcode=idcode, rtt_inspect=inspect)
    monkeypatch.setattr('mklink.probes.inventory', lambda: [dict(probe_id='usb-test', port='COM9', serial_number='test')])
    install_runtime(app, dict(port=8765, token='test', instance_id='fixture', probe_id='usb-test'))
    with TestClient(app, base_url='http://127.0.0.1:8765', headers={'X-Auth-Token': 'test'}) as client:
        app.state.mklink_state['device'] = device
        try:
            method, path = CAPABILITIES['rtt_inspect']
            response = client.request(method, path, json={'address': '0x20000000'})
            assert response.status_code == (200 if idcode else 400), response.text
            if idcode:
                assert response.json() == result
                inspect.assert_called_once_with(0x20000000)
            else:
                inspect.assert_not_called()
        finally:
            app.state.mklink_state['device'] = None

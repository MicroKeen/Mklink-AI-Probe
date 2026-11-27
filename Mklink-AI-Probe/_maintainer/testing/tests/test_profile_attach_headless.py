"""Real stdio MCP and loopback runtime with an in-memory serial peer."""
import asyncio
import json
import queue
import socket
import struct
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import uvicorn
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from mklink import probes
from mklink._types import MKLINK_IDENTITY_COMMAND, MKLINK_IDENTITY_TOKEN
from mklink.mux import packet
from mklink.remote.api import create_app
from mklink.runtime_api import install_runtime


class ProfileSerial:
    """The fixture implements the serial boundary; the production reader owns decoding."""
    def __init__(self, peer):
        self.peer = peer
        self.rx = queue.Queue()
        self.is_open = True
        self.bound = False
        self.nonce = None

    @property
    def in_waiting(self):
        return self.rx.qsize()

    def read(self, size):
        try:
            first = self.rx.get(timeout=.01)
        except queue.Empty:
            return b''
        return bytes([first] + [self.rx.get_nowait() for _ in range(min(size - 1, self.in_waiting))])

    def reset_input_buffer(self):
        while not self.rx.empty():
            self.rx.get_nowait()

    def reset_output_buffer(self):
        pass

    def close(self):
        self.is_open = False

    def write(self, frame):
        if frame.startswith(b'MLX1'):
            _, _, op, length, epoch, req = struct.unpack_from('<4sBBHII', frame)
            payload = frame[16:16 + length]
            assert frame == packet(op, epoch, req, payload)
            self.peer.ops.append(op)
            if op >= 0x10:
                assert payload[:8] == self.nonce
            reply = self.command(op, payload)
            data = packet(op | 0x80, 17, req, reply)
        elif frame == b'~MKLINK-MUX1\n':
            data = b''
        else:
            self.peer.text.append(frame)
            data = {b'\n': b'>>>', (MKLINK_IDENTITY_COMMAND + '\n').encode(): MKLINK_IDENTITY_TOKEN.encode() + b'\n>>>',
                    b'cmd.get_version()\n': b'MUX_TARGET=1\n>>>'}[frame]
        for value in data:
            self.rx.put_nowait(value)
        return len(frame)

    def command(self, op, payload):
        if op == 1:
            return b'\0' + struct.pack('<IHH', 0x2003 if self.peer.mode == 'old' else 0x6003, 256, 1)
        if op == 4:
            self.nonce = payload
            return b'\0' + payload
        if op in (2, 3):
            return b'\0'
        if op == 0x10:
            return bytes(16) + b'\x01'
        if op == 0x19:
            assert payload == self.nonce
            return b'\0' + struct.pack('<II', 0x6ba02477, 0x0995c01d)
        if op == 0x18:
            assert payload[8:12] == bytes([1, 4, 9, 0])
            assert struct.unpack_from('<BBHIII', payload, 12) == (5, 0, 0, 0, 0xffffffff, 0x0995c01d)
            assert struct.unpack_from('<BBHIII', payload, len(payload) - 16) == (
                4, 4, 0, 0x40290004, 0xffff0000, 0)
            self.bound = True
            actual = self.peer.reported_midr if self.peer.mode == 'wrong' else self.peer.midr
            return b'\0' + struct.pack('<BBBBI', 1, 4, 0xff, 0, actual)
        assert self.bound and op in (0x11, 0x12), f'unbound or unexpected command {op:#x}'
        address, = struct.unpack_from('<I', payload, 8)
        assert address == 0x20000000
        if op == 0x11:
            assert struct.unpack_from('<H', payload, 12) == (4,)
            return b'\0' + self.peer.memory
        self.peer.memory = payload[12:]
        return b'\x05' if self.peer.mode == 'lost' else b'\0'


@pytest.mark.parametrize('part,midr', [('S32K314', 0x2D3A0000), ('S32K344', 0x2D580000), ('S32K312', 0x2D380000)])
def test_headless_profile_stdio_shared_runtime(tmp_path, monkeypatch, part, midr):
    reported_midr = 0x2D580000 if part == 'S32K312' else 0x2D380000
    peer = SimpleNamespace(midr=midr, reported_midr=reported_midr, mode='old', memory=b'ABCD', ops=[], text=[])
    probe_id = 'usb-' + 'b' * 24
    port = 'TEST_HEADLESS_PROFILE'
    monkeypatch.setattr('serial.Serial', lambda name, *args, **kw: ProfileSerial(peer) if name == port else None)
    monkeypatch.setattr('serial.tools.list_ports.comports', lambda: [])
    monkeypatch.setattr(probes, '_bound_probe', probe_id)
    monkeypatch.setattr(probes, 'inventory', lambda: [dict(port=port, probe_id=probe_id, alias='', serial_number='test')])
    monkeypatch.setattr('mklink.remote.dashboards._managers', {})
    monkeypatch.setattr('mklink.hil_lock.LOCK_ROOT', tmp_path / 'hil')
    monkeypatch.setenv('HIL_CORE_LOCK_ROOT', str(tmp_path / 'hil'))
    monkeypatch.setenv('MKLINK_RUNTIME_DIR', str(tmp_path / 'runtime'))
    monkeypatch.setenv('MKLINK_LOCK_DIR', str(tmp_path / 'locks'))

    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(8)
    info = dict(port=listener.getsockname()[1], token='fixture', instance_id='profile-test', probe_id=probe_id)
    app = create_app(project_root=str(tmp_path), auth_token=info['token'])
    install_runtime(app, info)
    server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    thread.start()

    # Pin discovery in this child to our isolated listener. All MCP, HTTP and
    # websocket traffic thereafter uses the normal production transports.
    bootstrap = """
import json, sys
from mklink import runtime
from mklink.runtime_mcp import build_server
info = json.loads(sys.argv[1])
runtime.ensure_runtime = lambda **kwargs: info
build_server().run()
"""
    async def scenario():
        transport = StdioTransport(sys.executable, ['-B', '-c', bootstrap, json.dumps(info)],
                                   cwd=str(Path(__file__).resolve().parents[3]))
        async with Client(transport) as mcp:
            tools = {tool.name for tool in await mcp.list_tools()}
            assert {'list_target_profiles', 'connect', 'read_memory', 'write_memory', 'dump_memory'} <= tools
            catalog = (await mcp.call_tool('list_target_profiles', {})).data
            hooks = catalog['hook_support']
            assert hooks['supported'] == ['ConfigTargetSettings', 'InitTarget', 'SetupTarget']
            assert len(set(hooks['supported'] + hooks['reserved'])) == 44
            model, = (row for row in catalog['profiles'] if row['name'] == part)
            assert model['mem_ap'] == 4 and model['hooks'] == hooks['supported']
            if part == 'S32K314':
                assert model['aliases'] == ['S32K314HMS', 'NXPS32K314HMS']
            assert not peer.ops and not peer.text
            selection = dict(mcu=model['key'], project_root=str(tmp_path))
            for mode, expected in [('old', '0x4000'), ('wrong', f'SIUL2.MIDR1=0x{reported_midr:08X}')]:
                peer.mode = mode
                failure = await mcp.call_tool('connect', selection, raise_on_error=False)
                assert failure.is_error and expected.casefold() in str(failure.content).casefold()
                if mode == 'wrong' and part == 'S32K312':
                    assert '本次配置 S32K312，目标寄存器报告 S32K344' in failure.content[0].text
                    assert 'SIUL2.MIDR1' in failure.content[0].text
                assert app.state.mklink_state['device'] is None
                assert peer.ops.count(0x18) == int(mode == 'wrong')
            peer.mode = 'ok'
            del selection['mcu']
            if part == 'S32K344':
                from test_image_target import bind_file, image
                wrong_image = image(tmp_path, 'symbols-for-312.elf')
                bind_file(wrong_image, 'S32K312')
                selection['axf'] = str(wrong_image)
            result = (await mcp.call_tool('connect', selection)).data
            assert result['target_attach']['profile'] == part
            assert result['target_attach']['mem_ap'] == 4
            assert result['target_attach']['midr1'] == midr
            read = dict(address=0x20000000, size=4)
            write = dict(address=0x20000000, data_hex='1234abcd')
            data = (await mcp.call_tool('read_memory', read)).data
            assert data['data_hex'].lower() == b'ABCD'.hex()
            await mcp.call_tool('write_memory', write)
            captured = (await mcp.call_tool('dump_memory', {'regions': [read], 'sample_count': 2})).data
            assert [s['regions'][0]['data_hex'].lower() for s in captured['samples']] == ['1234abcd'] * 2
            peer.mode = 'lost'
            failure = await mcp.call_tool('write_memory', write, raise_on_error=False)
            assert failure.is_error
            assert (await mcp.call_tool('read_memory', read, raise_on_error=False)).is_error
            assert peer.ops.count(0x12) == 2 and peer.ops.count(0x18) == 2 and 0x13 not in peer.ops
            await mcp.call_tool('detach')
    try:
        deadline = time.monotonic() + 5
        while thread.is_alive() and not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        asyncio.run(scenario())
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        device = app.state.mklink_state.get('device')
        if device:
            device.close()
        assert not thread.is_alive()

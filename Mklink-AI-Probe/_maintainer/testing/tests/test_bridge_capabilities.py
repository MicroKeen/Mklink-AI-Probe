"""Capability queries cannot switch a running capture back to legacy REPL."""
import struct
from unittest.mock import Mock

import pytest

from mklink.bridge import MKLinkSerialBridge
from mklink.mux import MuxTransport
from mklink.mux_rtt import MuxRTTSession
from mklink.mux_watch import MuxWatchSession
from test_mux import packet


@pytest.mark.parametrize('first', ['rtt', 'watch'])
@pytest.mark.parametrize('hpm_write', [False, True])
def test_both_capture_orders_reuse_negotiated_capabilities(first, hpm_write):
    bridge = MKLinkSerialBridge('TEST_CAPABILITIES')
    def version(*args, **kwargs):
        bridge._leave_multiplex()  # Production guard rejects this during capture.
        return 'MUX_TARGET=1\nDUMP_WRITE=1\n' + ('DUMP_WRITE_HPM=1\n' if hpm_write else '')
    bridge.send_command = Mock(side_effect=version)
    if first == 'watch':
        assert bridge.supports_hpm_dump_write() is hpm_write
    assert bridge.supports_multiplex()
    transport = MuxTransport(Mock())
    transport.epoch = 17
    transport.capabilities = 63
    transport.request = Mock(side_effect=lambda op, *args: b'\x01\x00' if op == 0x20 else b'')
    bridge._mux = transport
    rtt = MuxRTTSession(transport, {'down_buffers': []}, channels=[0])
    watch = MuxWatchSession(transport, [(0x00085800, 4), (0x00080314, 4)], .01)
    def start_watch():
        assert bridge.supports_hpm_dump_write() is hpm_write
        watch.start()
    starters = {'rtt': lambda: rtt.start('0x000880dc'), 'watch': start_watch}
    for key in (first, 'watch' if first == 'rtt' else 'rtt'):
        starters[key]()
    assert bridge.supports_dump_write()
    assert bridge.supports_hpm_dump_write() is hpm_write
    bridge.send_command.assert_called_once_with('cmd.get_version()', timeout=3.0)
    assert [call.args[0] for call in transport.request.call_args_list] == (
        [0x20, 0x32] if first == 'rtt' else [0x32, 0x20])
    transport.feed(packet(0x40, 17, 1, struct.pack('<BBI', 0, 0, 1)+b'BOOT\n'))
    for i, value in enumerate((123, 0)):
        transport.feed(packet(0x41, 17, 2+i, struct.pack('<BBII', i, 0, 1, value)))
    assert rtt.read_channels(0) == {0: b'BOOT\n'}
    assert [struct.unpack('<I', data)[0] for _, data in watch.read_frames()[0]['regions']] == [123, 0]
    assert transport.rtt_mask == 1 and transport.watch_running


def test_reconnect_discards_all_firmware_capabilities():
    bridge = MKLinkSerialBridge('TEST_CAPABILITIES')
    bridge.send_command = Mock(return_value='MUX_TARGET=1\nDUMP_WRITE=1\nDUMP_WRITE_HPM=1')
    assert bridge.supports_multiplex() and bridge.supports_hpm_dump_write()
    # Fail before opening any physical port; even a failed new connection must
    # not retain knowledge about the previous probe/firmware.
    bridge._port_lock.acquire = Mock(return_value=False)
    assert not bridge.connect()
    bridge.send_command.return_value = 'old firmware\nDUMP_WRITE=1'
    assert not bridge.supports_multiplex()
    assert not bridge.supports_hpm_dump_write()
    assert bridge.supports_dump_write()
    assert bridge.send_command.call_count == 2


def test_failed_query_does_not_cache_missing_features():
    bridge = MKLinkSerialBridge('TEST_CAPABILITIES')
    bridge.send_command = Mock(side_effect=[TimeoutError('query failed'), 'MUX_TARGET=1\nDUMP_WRITE_HPM=1'])
    with pytest.raises(TimeoutError):
        bridge.supports_multiplex()
    assert bridge.supports_multiplex()
    assert bridge.supports_hpm_dump_write()
    assert bridge.send_command.call_count == 2

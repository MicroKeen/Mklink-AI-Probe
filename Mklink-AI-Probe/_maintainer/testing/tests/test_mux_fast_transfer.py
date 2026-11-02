import binascii
import struct

import pytest

from mklink.mux import MuxTransport, MuxError, MuxTargetError
from mklink.mux_rtt import MuxRTTSession


def frame(op, request, data, version=1):
    raw = struct.pack('<4sBBHII', b'MLX1', version, op, len(data), 17, request)+data
    return raw+struct.pack('<I', binascii.crc32(raw)&0xffffffff)


def peer(caps=511):
    wires, changes = [], {}
    def write(wire):
        wires.append(wire)
        _, _, op, size, _, req = struct.unpack_from('<4sBBHII', wire)
        raw = wire[16:16+size]
        data = raw[8:] if 0x10 <= op < 0x40 else raw
        answer = {1: struct.pack('<IHH', caps, 492, 1), 4: raw, 0x20: b'\x08\x08'}.get(op, b'')
        if op in (0x11, 0x16):
            address, count = struct.unpack('<IH', data)
            answer = bytes((address+i)%256 for i in range(count))
        if op in (0x21, 0x24):
            accepted = min(changes.get('accepted', 480), len(data)-1)
            answer = accepted.to_bytes(2 if op == 0x24 else 1, 'little')
        status = changes.get('status', 0) if op == 0x25 else 0
        t.feed(frame(op|128, req, bytes([status])+answer+changes.get('extra', b'')))
        return len(wire)
    t = MuxTransport(write)
    t.handshake()
    return t, wires, changes


@pytest.mark.parametrize('caps,quantum', [(255,128), (511,480)])
def test_default_compatibility_and_negotiated_packet_size(caps, quantum):
    t, wires, _ = peer(caps)
    assert t.transfer_quantum == quantum
    assert [w[5] for w in wires] == ([1,4,0x25] if quantum == 480 else [1,4])
    t.write_memory(0x20000000, bytes(1001))
    writes = [w for w in wires if w[5] == 0x12]
    assert all(len(w) <= 512 for w in writes)
    assert len(writes) == (1001+quantum-1)//quantum
    assert sum(len(w)-32 for w in writes) == 1001


@pytest.mark.parametrize('size', [1,127,128,129,479,480,481,960,1001])
def test_fast_memory_read_and_downlink_partial_acceptance(size):
    t, wires, changes = peer(511 & ~64)
    assert t.read_memory(0x20000000, size) == bytes(i%256 for i in range(size))
    assert all(len(w) <= 512 for w in wires)
    session = MuxRTTSession(t, {'down_buffers':[{'channel':0,'active':True}]})
    session.start('0x20000000')
    changes['accepted'] = 137
    payload = bytes(i%256 for i in range(size))
    session.send_input(payload)
    offset = 0
    for wire in (w for w in wires if w[5] == 0x24):
        assert len(wire) <= 509
        chunk = wire[25:-4]
        assert chunk == payload[offset:offset+480]
        offset += min(137, len(chunk))
    assert offset == size


@pytest.mark.parametrize('split', [0,15,16,17,480,501,505,506])
def test_quantum_ack_boundary_accepts_first_large_event_in_same_read(split):
    t, _, _ = peer(255)
    session = MuxRTTSession(t, {'down_buffers':[]})
    session.start('0x20000000')
    t.capabilities |= 256
    data = bytes(i%256 for i in range(480))
    def write(wire):
        request = struct.unpack_from('<I', wire, 12)[0]
        event = frame(0x40, 1, struct.pack('<BBI',0,0,1)+data)
        t.feed(frame(0xa5, request, b'\0')+event[:split])
        t.feed(event[split:])
        return len(wire)
    t._write = write
    t.set_transfer_quantum(480)
    assert session.read_output_bytes(0) == data


def test_failure_keeps_quantum_and_bad_ack_poisoned_without_replay():
    t, wires, changes = peer()
    changes['status'] = 6
    with pytest.raises(MuxTargetError):
        t.set_transfer_quantum(128)
    assert t.transfer_quantum == 480
    changes['status'] = 0
    changes['extra'] = b'junk'
    before = len(wires)
    with pytest.raises(MuxError, match='quantum ACK'):
        t.set_transfer_quantum(128)
    assert len(wires) == before+1


@pytest.mark.parametrize('op,size,version', [(0x40,486,1),(0x40,487,1),(0x91,482,1),(0x90,300,1),(0x40,486,2)])
def test_limits_are_opcode_and_negotiation_specific(op, size, version):
    t, _, _ = peer()
    if size == 486 and version == 1:
        t.transfer_quantum = 128  # Capability alone is insufficient.
    t.feed(frame(op, 1, bytes(size), version))
    assert isinstance(t._error, MuxError)


def test_existing_4096_read_contract_unchanged():
    t, wires, _ = peer()
    assert t.read_memory(0x20000000,4096) == bytes(range(256))*16
    assert wires[-1][5] == 0x16

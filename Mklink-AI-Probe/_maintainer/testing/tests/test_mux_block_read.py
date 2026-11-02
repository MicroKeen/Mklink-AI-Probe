import binascii
import struct

import pytest

from mklink.mux import MuxError, MuxTargetError, MuxTransport


def reply(op, epoch, req, data, version=1):
    raw = struct.pack('<4sBBHII', b'MLX1', version, op, len(data), epoch, req) + data
    return raw + struct.pack('<I', binascii.crc32(raw) & 0xffffffff)


def peer(caps=127, *, fragment=2048, failure=None):
    calls = []
    def write(wire):
        _, _, op, size, epoch, req = struct.unpack_from('<4sBBHII', wire)
        data = wire[16:16+size]
        if 0x10 <= op < 0x40:
            assert data[:8] == transport.nonce
            data = data[8:]
        calls.append((op, data))
        answer = {1: struct.pack('<IHH', caps, 256, 1), 4: data}.get(op, b'')
        if op in (0x11, 0x16):
            address, n = struct.unpack('<IH', data)
            answer = bytes((address + i) & 255 for i in range(n))
        response = reply(op | 0x80, 17, req, b'\0' + answer)
        if failure is not None and op in (0x11, 0x16):
            response = failure(op, req, answer)
        for off in range(0, len(response), fragment):
            transport.feed(response[off:off+fragment])
        return len(wire)
    transport = MuxTransport(write)
    transport.handshake()
    return transport, calls


@pytest.mark.parametrize('size', [1, 4, 128, 129, 255, 4095, 4096])
@pytest.mark.parametrize('fragment', [1, 15, 16, 2048, 4117])
def test_block_is_one_crc_reply_across_usb_fragments(size, fragment):
    transport, calls = peer(fragment=fragment)
    address = 0x20000000
    assert transport.read_memory(address, size) == bytes(i & 255 for i in range(size))
    assert calls[2:] == [(0x16, struct.pack('<IH', address, size))]


@pytest.mark.parametrize('caps,op,chunks', [(63, 0x11, 32), (127, 0x16, 1)])
def test_capability_selects_legacy_or_block_without_replay(caps, op, chunks):
    transport, calls = peer(caps)
    assert transport.read_memory(0xfffff000, 4096) == bytes(range(256)) * 16
    assert len(calls[2:]) == chunks
    assert {code for code, _ in calls[2:]} == {op}
    with pytest.raises(ValueError):
        transport.read_memory(0xfffff001, 4096)
    assert len(calls[2:]) == chunks


@pytest.mark.parametrize('caps,op,size,version', [(63, 0x96, 4097, 1), (127, 0x91, 4097, 1),
    (127, 0x96, 4098, 1), (127, 0x96, 4097, 2), (127, 0x41, 1025, 1)])
def test_larger_frame_is_restricted_to_advertised_crc_block_reply(caps, op, size, version):
    transport, _ = peer(caps)
    transport.feed(struct.pack('<4sBBHII', b'MLX1', version, op, size, 17, 3))
    with pytest.raises(MuxError, match='Malformed'):
        transport.request(0x11, b'')


@pytest.mark.parametrize('kind', ['crc', 'short', 'wrong_id', 'wrong_epoch'])
def test_bad_block_poisoned_without_old_opcode_fallback(kind):
    def failed(op, req, answer):
        wire = reply(op | 0x80, 18 if kind == 'wrong_epoch' else 17,
                     req + 1 if kind == 'wrong_id' else req,
                     b'\0' + (answer[:-1] if kind == 'short' else answer))
        return wire[:-1] + bytes([wire[-1] ^ 1]) if kind == 'crc' else wire
    transport, calls = peer(failure=failed)
    with pytest.raises(MuxError):
        transport.read_memory(0x20000000, 4096)
    with pytest.raises(MuxError):
        transport.read_memory(0x20000000, 4)
    assert [op for op, _ in calls] == [1, 4, 0x16]


def test_block_target_error_is_status_only_and_not_retried():
    transport, calls = peer(failure=lambda op, req, answer: reply(op | 0x80, 17, req, b'\x06'))
    with pytest.raises(MuxTargetError, match='busy'):
        transport.read_memory(0x20000000, 4096)
    assert [op for op, _ in calls] == [1, 4, 0x16]
    assert transport._error is None


def test_block_read_does_not_expand_write_size():
    transport, calls = peer()
    transport.write_memory(0x20000000, bytes(256))
    assert [(op, len(data)) for op, data in calls[2:]] == [(0x12, 132), (0x12, 132)]

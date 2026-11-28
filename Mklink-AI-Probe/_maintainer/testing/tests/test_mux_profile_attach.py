import struct
from dataclasses import replace
from types import SimpleNamespace

import pytest

from mklink._types import DeviceState
from mklink.bridge import MKLinkSerialBridge
from mklink.firmware_compatibility import FirmwareUpgradeRequired
from mklink.mux import MuxError, MuxProfileError, MuxTargetError, encode_attach_profile, packet
from mklink.profiles import MuxAttachProfile, MuxAttachStep, resolve_attach_profile


IDR = MuxAttachStep(1, 7, 0xfc, 0xffffffff, 0x001c0040)
UPDATE = MuxAttachStep(2, 7, 0x80, 0x300000f0, 0x300000f0)
MEM = MuxAttachStep(3, 4, 0xe000ed00, 0xff0ffff0, 0x410fc270)
PROFILE = MuxAttachProfile('test profile', 4, (IDR, UPDATE, MEM))
ACK = struct.pack('<BBBBI', 1, 4, 0xff, 0, 0)


@pytest.mark.parametrize('index,reason,actual', [
    (6, 8, 0x2D580000),  # CPUID comparison, even though the value resembles a valid MIDR1
    (7, 7, 0), (7, 8, 0x2D380123), (7, 8, 0x29580000), (7, 8, 0x2D590000),
])
def test_profile_diagnostic_only_names_a_distinct_documented_midr1(index, reason, actual):
    profile = resolve_attach_profile('S32K312')
    error = MuxProfileError(profile, 5, struct.pack('<BBBBI', 1, 4, index, reason, actual))
    assert 'model_mismatch' not in error.detail
    assert '目标寄存器报告' not in str(error)


def test_model_diagnostic_follows_the_compiled_step_not_its_position():
    profile = resolve_attach_profile('S32K312')
    diagnostic = struct.pack('<BBBBI', 1, 4, 0, 8, 0x2D581234)
    signature = profile.steps[-1]
    relocated = replace(profile, steps=(signature,))
    error = MuxProfileError(relocated, 5, diagnostic)
    assert error.detail['model_mismatch']['reported_model'] == 'S32K344'
    assert error.detail['actual'] == 0x2D581234
    for step in (replace(signature, address=0x40290008), replace(signature, mask=0xFFFFFFFF),
                 replace(signature, value=0x2D3A0000)):
        other = MuxProfileError(replace(profile, steps=(step,)), 5, diagnostic)
        assert 'model_mismatch' not in other.detail
    wrong_ap = MuxProfileError(replace(profile, mem_ap=1, steps=(replace(signature, ap=1),)), 5,
                               struct.pack('<BBBBI', 1, 1, 0, 8, 0x2D580000))
    assert 'model_mismatch' not in wrong_ap.detail


def profile_bridge(tmp_path, *, caps=0x2003, port=1, reply=None, profile=PROFILE):
    bridge = MKLinkSerialBridge('TEST_PROFILE')
    bridge.attach_profile = profile
    bridge._mux_supported = True
    bridge._ctx.state = DeviceState.READY
    bridge._mux_marker = tmp_path / 'mux'
    calls = []
    replies = {0x18: b'\0' + ACK, **(reply or {})}

    def write(frame):
        if frame == b'~MKLINK-MUX1\n':
            return len(frame)
        magic, ver, op, size, epoch, req = struct.unpack_from('<4sBBHII', frame)
        assert (magic, ver) == (b'MLX1', 1)
        payload = frame[16:16 + size]
        assert packet(op, epoch, req, payload) == frame
        calls.append((op, payload))
        answer = {1: b'\0' + struct.pack('<IHH', caps, 256, 1), 4: b'\0' + payload,
                  0x10: bytes(16) + bytes([port]), 0x11: b'\0ABCD', **replies}.get(op, b'\0')
        bridge._mux.feed(packet(op | 0x80, 17, req, answer))
        return len(frame)

    bridge._serial = SimpleNamespace(write=write)
    return bridge, calls


@pytest.mark.parametrize('part,target_id', [
    (310, 0x0996c01d), (311, 0x0996c01d), (312, 0x1996801d), (314, 0x0996001d),
    (322, 0x0996401d), (324, 0x0996001d), (328, 0x1995e01d), (338, 0x1995e01d),
    (341, 0x0996401d), (342, 0x0996401d), (344, 0x0995c01d), (348, 0x1995e01d),
    (356, 0x1995e01d), (358, 0x1995e01d), (364, 0x1995601d), (366, 0x1995601d),
    (374, 0x1995601d), (376, 0x1995601d), (388, 0x0995a01d), (389, 0x0996201d),
    (394, 0x1995601d), (396, 0x1995601d),
])
def test_hardware_identification_uses_captured_midr1(tmp_path, part, target_id):
    midr1 = 0x2c000a51 | (part << 16)
    bridge, calls = profile_bridge(tmp_path, caps=0x6003, profile=None, reply={
        0x19: b'\0' + struct.pack('<II', 0x6ba02477, target_id),
        0x18: b'\0' + struct.pack('<BBBBI', 1, 4, 255, 0, midr1),
    })
    assert bridge.identify_swd_target() == dict(profile=f'S32K{part}', mem_ap=4, source='SIUL2.MIDR1',
                                                midr1=midr1, target_id=target_id, dpidr=0x6ba02477)
    mux = bridge.enable_multiplex()
    assert mux.read_memory(0x20000000, 4) == b'ABCD'
    assert [op for op, _ in calls] == [1, 4, 0x19, 0x18, 0x11]
    assert calls[2][1] == mux.nonce
    steps = list(struct.iter_unpack('<BBHIII', calls[3][1][12:]))
    assert steps[0] == (5, 0, 0, 0, 0xffffffff, target_id)
    assert [s[1] for s in steps[1:4]] == [4, 6, 7]
    assert steps[-1] == (4, 4, 0, 0x40290004, 0xffff0000, 0)


@pytest.mark.parametrize('caps,identity', [
    (0x2003, b''), (0x6003, b'\x01'), (0x6003, b'\x05'), (0x6003, b'\x06'),
    (0x6003, b'\0short'), (0x6003, b'\0' + struct.pack('<II', 0x2ba01477, 0)),
    (0x6003, b'\0' + struct.pack('<II', 0x6ba02477, 0x0995801d)),
    (0x6003, b'\0' + struct.pack('<II', 0x6ba02477, 0x09968029)),
])
def test_other_targets_leave_read_only_claim_then_use_legacy_attach(tmp_path, caps, identity):
    bridge, calls = profile_bridge(tmp_path, caps=caps, profile=None, reply={0x19: identity})
    assert bridge.identify_swd_target() is None
    assert bridge._mux is None and bridge.attach_profile is None
    assert [op for op, _ in calls] == ([1, 4, 0x19, 3] if caps & 0x4000 else [1, 4, 3])
    bridge.enable_multiplex()
    assert [op for op, _ in calls[-4:]] == [1, 4, 0x10, 0x13]


@pytest.mark.parametrize('step,reason,safe', [(0, 12, True), (2, 3, True), (3, 4, True),
                                               (4, 4, False), (6, 5, False), (8, 7, False)])
def test_only_read_only_identity_failures_release_for_generic_attach(tmp_path, step, reason, safe):
    bridge, calls = profile_bridge(tmp_path, caps=0x6003, profile=None, reply={
        0x19: b'\0' + struct.pack('<II', 0x6ba02477, 0x0996801d),
        0x18: b'\x05' + struct.pack('<BBBBI', 1, 4, step, reason, 0),
    })
    if safe:
        assert bridge.identify_swd_target() is None
        assert bridge._mux is None
        assert calls[-1][0] == 3
    else:
        with pytest.raises(MuxProfileError):
            bridge.identify_swd_target()
        with pytest.raises(RuntimeError, match='unconfirmed'):
            bridge.enable_multiplex()
    assert [op for op, _ in calls].count(0x18) == 1
    assert all(op != 0x13 for op, _ in calls)


def test_profile_attach_max_frame_and_shared_binding(tmp_path):
    profile = replace(PROFILE, steps=(IDR,) * 14 + (UPDATE, MEM))
    bridge, calls = profile_bridge(tmp_path, profile=profile)
    mux = bridge.enable_multiplex()
    assert mux.attach_profile == profile
    assert bridge._ctx.clock_interface == 'SWD'
    assert calls == [
        (1, b''), (4, mux.nonce), (0x10, mux.nonce),
        (0x18, mux.nonce + b'\x01\x04\x10\x00'
         + bytes.fromhex('01 07 00 00 fc 00 00 00 ff ff ff ff 40 00 1c 00') * 14
         + bytes.fromhex('02 07 00 00 80 00 00 00 f0 00 00 30 f0 00 00 30')
         + bytes.fromhex('03 04 00 00 00 ed 00 e0 f0 ff 0f ff 70 c2 0f 41'))]
    assert len(calls[-1][1]) == 268
    assert bridge.enable_multiplex() is mux
    assert mux.read_memory(0x1000, 4) == b'ABCD'
    mux.write_memory(0x1000, b'ABCD')
    assert calls[-2:] == [(0x11, mux.nonce + struct.pack('<IH', 0x1000, 4)),
                          (0x12, mux.nonce + struct.pack('<I', 0x1000) + b'ABCD')]
    with pytest.raises(RuntimeError, match='text mode'):
        bridge.send_command('cmd.read_ram(0,4)')
    with pytest.raises(MuxError, match='explicit reconnect'):
        mux.request(0x13)
    bridge.attach_profile = None
    with pytest.raises(RuntimeError, match='reconnect'):
        bridge.enable_multiplex()
    mux.close()
    assert mux.attach_profile is None
    with pytest.raises(MuxError, match='reconnect'):
        mux.write_memory(0x1000, b'ABCD')
    assert [op for op, _ in calls] == [1, 4, 0x10, 0x18, 0x11, 0x12, 3]


@pytest.mark.parametrize('steps', [
    (), (MEM,) * 17, (IDR,), (UPDATE, MEM), (replace(IDR, mask=0xfffffffe), UPDATE, MEM),
    (replace(IDR, ap=6), UPDATE, MEM), (replace(IDR, address=0x100), MEM),
    (replace(IDR, address=0xfd), MEM), (replace(MEM, ap=7),),
    (replace(MEM, mask=0),), (replace(MEM, value=1),), (replace(MEM, address=1),),
    (replace(MEM, ap=True),), (replace(MEM, value=-1),), (IDR, replace(UPDATE, address=0xfc), MEM),
    (MEM, IDR, MEM), (IDR, MEM, UPDATE, MEM),
])
def test_invalid_recipe_precedes_target_traffic(steps, tmp_path):
    bridge, calls = profile_bridge(tmp_path, profile=replace(PROFILE, steps=steps))
    with pytest.raises(ValueError):
        bridge.enable_multiplex()
    assert [op for op, _ in calls] == [1, 4, 0x10]
    assert bridge._mux.attach_profile is None


@pytest.mark.parametrize('mem_ap', [-1, 256, False, '4'])
def test_profile_rejects_invalid_ap(mem_ap):
    with pytest.raises(ValueError, match='memory AP'):
        encode_attach_profile(replace(PROFILE, mem_ap=mem_ap))


def test_old_firmware_and_jtag_cannot_fall_back(tmp_path):
    bridge, calls = profile_bridge(tmp_path, caps=3)
    with pytest.raises(FirmwareUpgradeRequired, match='0x2000'):
        bridge.enable_multiplex()
    assert [op for op, _ in calls] == [1, 4, 0x10]
    bridge, calls = profile_bridge(tmp_path, port=2)
    with pytest.raises(RuntimeError, match='requires a SWD'):
        bridge.enable_multiplex()
    assert [op for op, _ in calls] == [1, 4, 0x10]
    bridge, calls = profile_bridge(tmp_path)
    bridge._mux_supported = False
    with pytest.raises(FirmwareUpgradeRequired, match='0x2000'):
        bridge.enable_multiplex()
    assert calls == []


@pytest.mark.parametrize('status,diagnostic,step,reason,actual', [
    (2, struct.pack('<BBBBI', 1, 4, 0xff, 1, 0), 0xff, 1, 0),
    (2, struct.pack('<BBBBI', 1, 0xff, 0xff, 1, 0), 0xff, 1, 0),
    (2, struct.pack('<BBBBI', 1, 4, 1, 1, 0), 1, 1, 0),
    (5, struct.pack('<BBBBI', 1, 4, 0xff, 2, 0), 0xff, 2, 0),
    (5, struct.pack('<BBBBI', 1, 4, 1, 3, 0), 1, 3, 0),
    (5, struct.pack('<BBBBI', 1, 4, 0, 4, 0x12345678), 0, 4, 0x12345678),
    (5, struct.pack('<BBBBI', 1, 4, 1, 5, 0x1234abcd), 1, 5, 0x1234abcd),
    (5, struct.pack('<BBBBI', 1, 4, 1, 6, 1), 1, 6, 1),
    (5, struct.pack('<BBBBI', 1, 4, 2, 7, 0), 2, 7, 0),
    (5, struct.pack('<BBBBI', 1, 4, 2, 8, 0x1234abcd), 2, 8, 0x1234abcd),
    (5, struct.pack('<BBBBI', 1, 4, 0xff, 9, 0), 0xff, 9, 0),
    (5, struct.pack('<BBBBI', 1, 4, 0xff, 10, 0), 0xff, 10, 0),
    (6, b'', None, None, None),
    (5, b'bad', None, None, None),
    (2, struct.pack('<BBBBI', 1, 4, 0xff, 2, 0), None, None, None),
    (5, struct.pack('<BBBBI', 1, 4, 0xff, 8, 1), None, None, None),
    (5, struct.pack('<BBBBI', 1, 4, 0xff, 10, 1), None, None, None),
    (5, struct.pack('<BBBBI', 1, 4, 1, 9, 0), None, None, None),
    (5, struct.pack('<BBBBI', 1, 4, 2, 5, 0), None, None, None),
    (5, struct.pack('<BBBBI', 1, 4, 2, 7, 1), None, None, None),
    (5, struct.pack('<BBBBI', 1, 0xff, 0xff, 10, 0), None, None, None),
    (6, struct.pack('<BBBBI', 1, 4, 0xff, 1, 0), None, None, None),
])
def test_profile_rejection_is_sticky_and_diagnostics_survive(tmp_path, status, diagnostic, step, reason, actual):
    bridge, calls = profile_bridge(tmp_path, reply={0x18: bytes([status]) + diagnostic})
    with pytest.raises(MuxProfileError) as caught:
        bridge.enable_multiplex()
    err = caught.value
    assert err.detail == dict(code='mux_profile_attach_failed', message=str(err), profile=PROFILE.name,
                              status=status, mem_ap=4, step=step, reason=reason, actual=actual,
                              response_hex=diagnostic.hex())
    assert err.response == diagnostic
    if reason == 5:
        assert 'write outcome unknown' in str(err)
    if status == 6:
        assert 'target busy' in str(err)
    with pytest.raises(RuntimeError, match='reconnect'):
        bridge.enable_multiplex()
    with pytest.raises(MuxError, match='reconnect'):
        bridge._mux.write_memory(0x1000, b'ABCD')
    bridge._mux.close()
    assert [op for op, _ in calls] == [1, 4, 0x10, 0x18, 3]


@pytest.mark.parametrize('ack', [b'', ACK[:-1], bytes(8), bytes([2]) + ACK[1:],
                                 ACK[:1] + bytes([7]) + ACK[2:], ACK[:2] + bytes(2) + ACK[4:],
                                 ACK[:3] + b'\x09' + ACK[4:], ACK[:4] + b'\x01\0\0\0'])
def test_unconfirmed_ack_stops_target_operations(tmp_path, ack):
    bridge, calls = profile_bridge(tmp_path, reply={0x18: b'\0' + ack})
    with pytest.raises(MuxError, match='unconfirmed'):
        bridge.enable_multiplex()
    with pytest.raises(MuxError):
        bridge._mux.read_memory(0x1000, 4)
    assert [op for op, _ in calls] == [1, 4, 0x10, 0x18]


def test_advertised_but_rejected_command_reports_firmware_support(tmp_path):
    bridge, calls = profile_bridge(tmp_path, reply={0x18: b'\x01'})
    with pytest.raises(MuxProfileError) as caught:
        bridge.enable_multiplex()
    assert caught.value.detail['code'] == 'firmware_upgrade_required'
    assert caught.value.detail['status'] == 1 and '0x18' in str(caught.value)
    assert caught.value.detail['response_hex'] == ''
    assert [op for op, _ in calls] == [1, 4, 0x10, 0x18]


@pytest.mark.parametrize('status', (3, 4))
def test_profile_claim_rejection_preserves_status_and_retires_transport(tmp_path, status):
    bridge, calls = profile_bridge(tmp_path, reply={0x18: bytes([status])})
    with pytest.raises(MuxProfileError) as caught:
        bridge.enable_multiplex()
    assert caught.value.detail['status'] == status and 'do not replay' in str(caught.value)
    assert not bridge._mux.ready
    with pytest.raises(MuxError):
        bridge.enable_multiplex()
    assert [op for op, _ in calls] == [1, 4, 0x10, 0x18]


def test_failed_bound_write_blocks_only_its_owner(tmp_path):
    bridge, calls = profile_bridge(tmp_path, reply={0x12: b'\x05'})
    other, other_calls = profile_bridge(tmp_path)
    mux = bridge.enable_multiplex()
    second = other.enable_multiplex()
    with pytest.raises(MuxTargetError, match='reconnect'):
        mux.write_memory(0x1000, b'ABCD')
    assert mux.attach_profile is None
    with pytest.raises(RuntimeError, match='reconnect'):
        bridge.enable_multiplex()
    with pytest.raises(MuxError, match='reconnect'):
        mux.read_memory(0x1000, 4)
    assert second.read_memory(0x1000, 4) == b'ABCD'
    assert [op for op, _ in calls] == [1, 4, 0x10, 0x18, 0x12]
    assert [op for op, _ in other_calls] == [1, 4, 0x10, 0x18, 0x11]

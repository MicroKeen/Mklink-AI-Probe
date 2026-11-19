"""Host profiles and transport for the HPMLink OTP ROM v1 single-word API."""
from dataclasses import dataclass
import hashlib
import json
import re
import secrets

from .hpm_config import HPM_ROM_TARGETS
from .hpm_otp_profiles import validate_change


@dataclass(frozen=True)
class RomProfile:
    chip_id: int
    otp_base: int
    driver_version: int
    ram_cpu: int
    ram_bus: int
    ldo_reg: int
    ldo_enable: int
    min_mv: int
    max_mv: int

    def encode(self):
        fields = (0x1000563D, self.chip_id, self.otp_base, 64, 0, 69, 79, 0xffffffff,
                  0x20000000, 0x20020000, 0x2001ff0c, self.driver_version,
                  self.ram_cpu, self.ram_bus, self.ldo_reg, self.ldo_enable,
                  self.min_mv, self.max_mv)
        return ''.join(f'{field:08x}' for field in fields)


# Identified HPM6E80 reference board, 3.3 V interface. SDK 1.13.0 hpm_misc.h
# gives hart 0 ILM's local and system aliases. Reserve the top 4 KiB for the
# reset-time ROM call. Never infer a write profile from a family/TAP match.
PROFILES = {
    'HPM6E80': RomProfile(0x10206141, 0xF3158000, 0x56010100, 0x0003F000,
                          0x011BF000, 0xF4104008, 0x10000, 3000, 3600),
}


def profile_for(part, model):
    name = part.strip().upper()
    if model == 'V4' and name in HPM_ROM_TARGETS:
        return PROFILES.get(name[:7])
    return None


def supported(bridge):
    reply = bridge.send_command('print("MKLINK_OTP_ROM",hpm.otp_rom_version())', timeout=5)
    return re.findall(r'(?m)^\s*MKLINK_OTP_ROM\s+(\d+)\s*$', reply) == ['1']


def profile_lines(profile):
    # The console has a bounded line buffer. Offline Pika accepts the same lines.
    encoded = profile.encode()
    return [f"mkotp='{encoded[:72]}'", f"mkotp=mkotp+'{encoded[72:]}'"]


def word_call(request_id, word, expected, desired, commit):
    return f'hpm.otp_rom_word(1,{request_id},mkotp,{word},{expected},{desired},{int(commit)})'


def _result(reply, request_id, profile, change, commit):
    lines = re.findall(r'(?m)^HPM_OTP_ROM (\{[^\r\n]+\})\r?$', reply)
    status = re.findall(r'(?m)^\s*(-?\d+)\s*$', reply)
    if len(lines) != 1 or len(status) != 1:
        raise ValueError('Missing OTP result; read again, do not retry programming')
    record = json.loads(lines[0])
    required = ('v','id','word','commit','rc','issued','valid','chip','mv','before','delta','after','rom_status')
    if (not isinstance(record, dict) or any(type(record.get(k)) is not int for k in required)
            or (record['v'], record['id'], record['word'], record['commit'], record['rc'])
            != (1, request_id, change['word'], int(commit), int(status[0]))):
        raise ValueError('Uncorrelated OTP result; read again, do not retry programming')
    if record['rc'] != 0:
        raise ValueError(f"OTP ROM rejected operation (rc={record['rc']}, issued={record['issued']}); read again before continuing")
    flags = 63 if commit else 15
    if (record['issued'] != int(commit) or record['valid'] & flags != flags
            or record['chip'] != profile.chip_id or record['before'] != change['expected']
            or record['delta'] != change['delta'] or not profile.min_mv <= record['mv'] <= profile.max_mv
            or (commit and (record['after'] != change['desired'] or record['rom_status'] != 0))):
        raise ValueError('Inconsistent OTP verification; read again, do not retry programming')
    return record


def run(device, part, model, word, expected, desired, *, commit=False, target_identity=None):
    from . import hpm_jtag_otp
    from .hpm_otp import _read

    profile = profile_for(part, model)
    if profile is None:
        raise ValueError('No qualified JTAG OTP write profile for the selected part and revision')
    change = validate_change(word, expected, desired)
    if not 69 <= change['word'] <= 79:
        raise ValueError('Only application OTP words 69..79 can be programmed')
    bridge = device._bridge
    if not supported(bridge):
        raise ValueError('此下载器固件缺少通用 JTAG OTP 写入接口。HPMLink OTP ROM API v1 required.')
    chip = hpm_jtag_otp.check_target(device, part.upper(), lambda a: _read(device, a), check_read_lock=True)
    if chip != profile.chip_id:
        raise ValueError('Connected CHIP_ID does not match the selected write profile')
    # SDK OTP_CHIP_UID_IDX_START..END. Keep the identifier inside the runtime.
    uid_lock = _read(device, profile.otp_base + 0x600)
    if any((uid_lock >> (2 * index)) & 3 == 3 for index in range(8, 12)):
        raise ValueError('Cannot bind a programming plan to this target UID')
    uid = device.read_memory(profile.otp_base + 0x420, 16)
    if len(uid) != 16 or uid in (bytes(16), b'\xff' * 16, bytes.fromhex('07041520') * 4):
        raise ValueError('Cannot bind a programming plan to this target UID')
    identity = hashlib.sha256(uid).hexdigest()
    if commit and target_identity != identity:
        raise ValueError('Target UID changed since preview; read again')
    for line in profile_lines(profile):
        bridge.send_command(line, timeout=5)
    echo = bridge.send_command('print("MKLINK_OTP_PROFILE",mkotp)', timeout=5)
    if re.findall(r'(?m)^\s*MKLINK_OTP_PROFILE\s+([0-9a-f]+)\s*$', echo) != [profile.encode()]:
        raise ValueError('Probe did not accept the complete OTP profile')
    nonce = secrets.randbelow(0x7fffffff) + 1
    command = word_call(nonce, change['word'], change['expected'], change['desired'], commit)
    reply = bridge.send_command(command, timeout=12)
    record = _result(reply, nonce, profile, change, commit)
    if commit and _read(device, profile.otp_base + 0x400 + change['word'] * 4) != change['desired']:
        raise ValueError('Independent physical fuse readback failed; do not retry programming')
    script = ['if hpm.otp_rom_version() != 1:', "    raise Exception('OTP ROM v1 required')",
              *profile_lines(profile)]
    for mode in (False, True):
        call = word_call(nonce, change['word'], change['expected'], change['desired'], mode)
        script.extend([f'if {call} != 0:', "    raise Exception('Stop; read back before retrying')"])
    return dict(change, target_identity=identity, verified=commit, after=record['after'] if commit else None,
                voltage_mv=record['mv'], irreversible=True, target_reset_required=True,
                script='\n'.join(script))

"""Family-aware ROM OTP transport. Legacy user-word APIs remain compatible."""
from datetime import datetime, timezone
import re
import uuid

from . import hpm_isp_otp as legacy
from .hpm_otp_profiles import family, ordered_changes, validate_change

CAPABILITY = 'print("MKLINK_HPM_ISP_OTP_PROFILE_API", hpm.isp_otp_profile_supported())'


def _supported(bridge):
    response = bridge.send_command(CAPABILITY, timeout=5, echo=False)
    return re.findall(r'(?m)^\s*MKLINK_HPM_ISP_OTP_PROFILE_API\s+(\d+)\s*$', response) == ['1']


def _profile_result(response, nonce, profile, operation):
    result = legacy._result(response, nonce, allow_rom_rejection=operation == 'read')
    if (result.get('api') != 'profile_v1' or result.get('profile') != profile
            or ('profile_verified' in result and result['profile_verified'] is not None and type(result['profile_verified']) is not bool)
            or result.get('operation') != operation
            or result.get('read_source') != 'rom_otp'
            or result.get('read_semantics') not in ('unknown', 'fuse', 'shadow')
            or legacy._u32(result.get('memory_id')) != 0x20000):
        raise ValueError('UART OTP result does not match the selected family profile')
    legacy._u32(result.get('chip_id'))
    for field in ('rom_version', 'soc_revision'):
        legacy._u32(result.get(field))
    legacy._u32(result.get('hard_lock'))
    legacy._u32(result.get('lifecycle'))
    return result


def read_snapshot(bridge, part_number):
    profile = family(part_number)
    if not _supported(bridge):
        if part_number in ('HPM5301', 'HPM5301XEGX'):
            return dict(legacy.read_snapshot(bridge, part_number), profile=profile, capability='legacy_user')
        raise ValueError('请升级 V4 下载器固件以读取此系列的 UART OTP')
    rows, identity = [], None
    # Bounded replies fit the probe's fixed output buffer. A denied word remains
    # unavailable rather than becoming a fabricated zero in a writable snapshot.
    for start in range(0, 128, 8):
        nonce = uuid.uuid4().hex
        response = bridge.send_command(
            f'hpm.isp_otp_profile_read("{nonce}","{profile}",{start},8,30000,1000)',
            timeout=90, echo=False)
        result = _profile_result(response, nonce, profile, 'read')
        current_identity = tuple(result[k] for k in ('chip_id', 'rom_version', 'soc_revision', 'hard_lock', 'lifecycle'))
        if identity is not None and identity != current_identity:
            raise ValueError('OTP target changed during reading; discard the snapshot')
        identity = current_identity
        values, statuses, codes = result.get('values'), result.get('statuses'), result.get('codes')
        if (type(result.get('start_word')) is not int or result['start_word'] != start
                or not isinstance(values, list) or len(values) != 8
                or not isinstance(statuses, list) or len(statuses) != 8
                or not isinstance(codes, list) or len(codes) != 8):
            raise ValueError('Incomplete UART OTP profile snapshot')
        for offset, (value, status, code) in enumerate(zip(values, statuses, codes)):
            status = legacy._u32(status)
            if type(code) is not int or not -12 <= code <= 0:
                raise ValueError('Invalid OTP read result code')
            if code not in (0, -7) or (code == 0) != (status == 0):
                raise ValueError('Incomplete or inconsistent OTP read status')
            if code == 0:
                value = legacy._u32(value)
            elif value is not None:
                raise ValueError('Unreadable OTP word must not contain a value')
            rows.append(dict(word=start + offset, current=value, shadow=None, locked=None, read_status=status, read_code=code))
    return dict(part_number=part_number, profile=profile, capability='profile_v1',
                chip_id=identity[0], rom_version=identity[1], soc_revision=identity[2], hard_lock=identity[3], lifecycle=identity[4],
                source='rom_otp', words=rows, read_at=datetime.now(timezone.utc).isoformat())


def _change(bridge, part_number, change, commit, target_identity=None):
    profile = family(part_number)
    if not _supported(bridge):
        if part_number in ('HPM5301', 'HPM5301XEGX') and 69 <= change['word'] <= 79:
            return legacy._user_change(bridge, part_number, change, commit=commit)
        raise ValueError('请升级 V4 下载器固件以配置此系列或区域的 UART OTP')
    if not isinstance(target_identity, dict) or set(target_identity) != {'chip_id', 'rom_version', 'soc_revision'}:
        raise ValueError('Refresh the target OTP identity before programming')
    identity = [legacy._u32(target_identity[key]) for key in ('chip_id', 'rom_version', 'soc_revision')]
    nonce = uuid.uuid4().hex
    response = bridge.send_command(
        f'hpm.isp_otp_profile_word("{nonce}","{profile}",{identity[0]},{identity[1]},{identity[2]},{change["word"]},'
        f'{change["expected"]},{change["desired"]},{int(commit)},30000,1000)', timeout=90, echo=False)
    result = _profile_result(response, nonce, profile, 'program' if commit else 'plan')
    if any(result[key] != value for key, value in target_identity.items()):
        raise ValueError('Target identity changed since the OTP snapshot')
    for field in ('word', 'expected', 'desired', 'delta'):
        if legacy._u32(result.get(field)) != change[field]:
            raise ValueError('OTP result differs from the reviewed change')
    for field in ('qualified', 'write_supported', 'write_attempted', 'verified'):
        if type(result.get(field)) is not bool:
            raise ValueError('Missing OTP operation status')
    if result['qualified'] != result['write_supported']:
        raise ValueError('Inconsistent OTP programming capability')
    before = result.get('before')
    if before is not None:
        before = legacy._u32(before)
    qualified = result['qualified']
    reason = result.get('reason')
    if qualified and (before != change['expected'] or (result.get('locked') is not None and result.get('locked') is not False)
                      or result['hard_lock'] & (1 << (change['word'] // 4))
                      or reason not in (None, 'ok')):
        raise ValueError('OTP preflight does not match the target or reviewed value')
    if not qualified and (not isinstance(reason, str) or not reason or len(reason) > 128):
        raise ValueError('Missing OTP rejection reason')
    if not commit:
        if result['write_attempted'] or result['verified'] or result.get('after') is not None or result.get('write_status') is not None:
            raise ValueError('OTP preflight unexpectedly attempted programming; do not retry')
        return dict(change, before=before, qualified=qualified, write_supported=qualified, reason=reason)
    if (not qualified or not result['write_attempted'] or not result['verified']
            or legacy._u32(result.get('after')) != change['desired']
            or legacy._u32(result.get('write_status')) != 0):
        raise ValueError('OTP programming outcome is unverified; read again, do not retry')
    return dict(change, after=result['after'], verified=True)


def plan_changes(bridge, part_number, changes, target_identity=None):
    family(part_number)
    fixed = ordered_changes([validate_change(item['word'], item['expected'], item['desired']) for item in changes])
    if len({item['word'] for item in fixed}) != len(fixed):
        raise ValueError('Duplicate OTP word')
    results = [_change(bridge, part_number, item, False, target_identity) for item in fixed]
    qualified = bool(results) and all(item['qualified'] for item in results)
    return dict(changes=results, qualified=qualified, write_supported=qualified, target_identity=target_identity)


def program_changes(bridge, part_number, changes, target_identity=None):
    preview = plan_changes(bridge, part_number, changes, target_identity)
    if not preview['qualified']:
        raise ValueError('OTP configuration is no longer writable; read again')
    fixed = [{key: item[key] for key in ('word', 'expected', 'desired', 'delta')} for item in preview['changes']]
    completed = []
    identity = dict(target_identity) if target_identity is not None else None
    for item in fixed:
        try:
            completed.append(_change(bridge, part_number, item, True, identity))
            if item['word'] == 64 and identity is not None:
                identity['chip_id'] = item['desired']
        except (ValueError, RuntimeError, OSError) as error:
            return dict(status='failed', completed=completed, failed_word=item['word'], error=str(error),
                        remaining=[later['word'] for later in fixed[len(completed) + 1:]])
    return dict(status='completed', completed=completed, failed_word=None, remaining=[])

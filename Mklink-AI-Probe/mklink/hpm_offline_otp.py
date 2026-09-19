"""Allowlisted user-OTP recipes; never accept arbitrary Pika code or security words."""
from dataclasses import dataclass
from .hpm_otp import _u32, _word


@dataclass(frozen=True)
class OfflineOtp:
    words: tuple[tuple[int, int, int], ...]
    locks: tuple[int, ...]
    hard_lock: int


def resolve(raw, part, model):
    if raw is None or raw == {}:
        return None
    if not isinstance(raw, dict) or set(raw) - {'words', 'locks', 'expected_hard_lock', 'confirm_irreversible'}:
        raise ValueError('Invalid offline OTP configuration')
    if part.upper() not in ('HPM5301', 'HPM5301XEGX') or model != 'V4':
        raise ValueError('Offline user OTP requires HPM5301 / V4 HPMLink')
    if raw.get('confirm_irreversible') is not True:
        raise ValueError('Confirm irreversible offline OTP programming')
    words, locks = raw.get('words', []), raw.get('locks', [])
    if not isinstance(words, list) or len(words) > 11 or not isinstance(locks, list) or len(locks) > 2:
        raise ValueError('Invalid OTP word/group list')
    parsed = []
    for row in words:
        if not isinstance(row, dict) or set(row) != {'word', 'expected', 'desired'}:
            raise ValueError('Each OTP word requires word, expected and desired')
        w, old, new = _word(row['word']), _u32(row['expected'], 'expected'), _u32(row['desired'], 'desired')
        if new & old != old or any(item[0] == w for item in parsed):
            raise ValueError('OTP cannot clear bits or repeat a word')
        parsed.append((w, old, new))
    groups = tuple(_u32(g, 'lock group') for g in locks)
    if any(g not in (18, 19) for g in groups) or len(set(groups)) != len(groups):
        raise ValueError('Only distinct user groups 18 and 19 may be locked')
    hard = _u32(raw.get('expected_hard_lock'), 'expected HARD_LOCK') if groups else 0
    if any(hard & (1 << g) for g in groups):
        raise ValueError('Requested OTP group is already locked')
    if not parsed and not groups:
        raise ValueError('Select OTP user words or lock groups')
    return OfflineOtp(tuple(parsed), groups, hard)


def script_lines(plan, *, commit, indent='    '):
    calls = [f'hpm.otp_user({w}, {old}, {new}, {int(commit)})' for w, old, new in plan.words]
    hard = plan.hard_lock
    for group in plan.locks:
        calls.append(f'hpm.otp_user_lock({group}, {hard}, {int(commit)})')
        # Dry runs do not change HARD_LOCK; commits do, so the next guard must advance.
        if commit:
            hard |= 1 << group
    lines = [f'{indent}# User OTP: data first, permanent locks last; never automatically retry.']
    for call in calls:
        lines.extend([f'{indent}if {call} != 0:',
                      f'{indent}    print("OTP failed; inspect readback before retrying")',
                      f'{indent}    abort = True', f'{indent}    break'])
    return lines

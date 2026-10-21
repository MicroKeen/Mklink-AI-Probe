"""HPM5301 UART user OTP client; unknown ROM protection remains read-only."""
from datetime import datetime, timezone
import json
import re
import uuid

from .hpm_otp import CHIP_ID, FIRST, LAST
from .hpm_otp import _u32 as parse_u32, _word
from .hpm_isp import ISP_ERROR_TEXT

CAPABILITY_COMMAND = 'print("MKLINK_HPM_ISP_OTP_API", hpm.isp_otp_supported())'
USER_CAPABILITY_COMMAND = 'print("MKLINK_HPM_ISP_OTP_USER_API", hpm.isp_otp_user_supported())'


def validate_change(word, expected, desired):
    word = _word(word)
    expected, desired = parse_u32(expected, 'expected'), parse_u32(desired, 'desired')
    if desired & expected != expected:
        raise ValueError('OTP bits cannot be cleared (1 to 0)')
    if desired == expected:
        raise ValueError('No new OTP bits selected')
    return dict(word=word, expected=expected, desired=desired, delta=desired & ~expected)


def _u32(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Invalid UART OTP value")
    return value


def _result(response: str, request_id: str) -> dict:
    results = []
    for line in response.splitlines():
        if not line.startswith("HPM_OTP "):
            continue
        try:
            item = json.loads(line[8:])
        except ValueError:
            continue
        if (isinstance(item, dict) and item.get("request_id") == request_id
                and item.get("event") == "result"):
            results.append(item)
    if len(results) != 1:
        raise ValueError("UART OTP returned no unique matching result; read again before any further operation")
    result = results[0]
    if type(result.get("schema")) is not int or result["schema"] != 1:
        raise ValueError("Unsupported UART OTP response version")
    code = result.get("code")
    if type(code) is not int:
        raise ValueError("Invalid UART OTP result status")
    if code:
        reason = "Unsupported OTP operation or profile" if code == -12 else ISP_ERROR_TEXT.get(code, "Operation failed")
        raise ValueError(f"UART OTP: {reason}")
    if _u32(result.get("rom_status")) != 0:
        raise ValueError("ROM rejected the OTP operation")
    return result


def parse_snapshot(response: str, request_id: str, part_number: str) -> dict:
    result = _result(response, request_id)
    if _u32(result.get("chip_id")) != CHIP_ID:
        raise ValueError("Target CHIP_ID does not match the qualified HPM5301 revision")
    if (result.get("part") != "HPM5301" or _u32(result.get("memory_id")) != 0x20000
            or type(result.get("start_word")) is not int or result["start_word"] != FIRST
            or result.get("read_source") != "rom_otp"
            or result.get("read_semantics") not in ("unknown", "fuse", "shadow")):
        raise ValueError("Invalid UART OTP memory profile")
    hard = _u32(result.get("hard_lock"))
    values = result.get("values")
    if not isinstance(values, list) or len(values) != LAST - FIRST + 1:
        raise ValueError("Incomplete UART OTP snapshot")
    # v1 does not establish fuse/shadow source or transient lock registers.
    # Keep lock status unknown even when a raw HARD_LOCK word is available.
    rows = [dict(word=word, current=_u32(value), shadow=None, locked=None)
            for word, value in zip(range(FIRST, LAST + 1), values)]
    return dict(part_number=part_number, chip_id=CHIP_ID, hard_lock=hard, words=rows,
                source="rom_otp", read_semantics=result["read_semantics"],
                read_at=datetime.now(timezone.utc).isoformat())


def read_snapshot(bridge, part_number: str) -> dict:
    if part_number not in ("HPM5301", "HPM5301XEGX"):
        raise ValueError("UART OTP reading requires HPM5301")
    response = bridge.send_command(CAPABILITY_COMMAND, timeout=5, echo=False)
    if not re.search(r"(?m)^\s*MKLINK_HPM_ISP_OTP_API\s+1\s*$", response):
        raise ValueError("Upgrade HPMLINK V4 firmware: UART OTP read API v1 required")
    request_id = uuid.uuid4().hex
    # One bounded operation owns the UART throughout handshake and snapshot.
    # No reset, voltage command, SD script, or arbitrary address is accepted.
    response = bridge.send_command(
        f'hpm.isp_otp_read("{request_id}",30000,1000)', timeout=90, echo=False)
    return parse_snapshot(response, request_id, part_number)


def _user_change(bridge, part_number, change, *, commit):
    if part_number not in ('HPM5301', 'HPM5301XEGX'):
        raise ValueError('UART OTP configuration requires HPM5301')
    response = bridge.send_command(USER_CAPABILITY_COMMAND, timeout=5, echo=False)
    if not re.search(r'(?m)^\s*MKLINK_HPM_ISP_OTP_USER_API\s+1\s*$', response):
        raise ValueError('Upgrade HPMLINK V4 firmware: UART OTP configuration API v1 required')
    request_id = uuid.uuid4().hex
    response = bridge.send_command(
        f'hpm.isp_otp_user("{request_id}",{change["word"]},{change["expected"]},'
        f'{change["desired"]},{int(commit)},30000,1000)', timeout=90, echo=False)
    return parse_change(response, request_id, change, commit=commit)


def parse_change(response, request_id, change, *, commit):
    result = _result(response, request_id)
    if (result.get('operation') != ('program' if commit else 'plan')
            or result.get('part') != 'HPM5301' or _u32(result.get('chip_id')) != CHIP_ID
            or result.get('read_source') != 'rom_otp'
            or result.get('read_semantics') not in ('unknown', 'fuse', 'shadow')):
        raise ValueError('Invalid UART OTP configuration profile')
    for key in ('word', 'expected', 'desired', 'delta'):
        if _u32(result.get(key)) != change[key]:
            raise ValueError('UART OTP result does not match the reviewed change')
    before = _u32(result.get('before'))
    hard = _u32(result.get('hard_lock'))
    for key in ('qualified', 'write_supported', 'write_attempted', 'verified'):
        if type(result.get(key)) is not bool:
            raise ValueError('Missing UART OTP write qualification')
    qualified = result['qualified'] and result['write_supported']
    if result['qualified'] != result['write_supported']:
        raise ValueError('Inconsistent UART OTP write qualification')
    reason = result.get('reason')
    if qualified:
        # A generic OTP read or a raw HARD_LOCK word alone cannot establish this.
        if (result.get('read_semantics') != 'fuse' or before != change['expected']
                or result.get('locked') is not False or hard & (1 << (change['word'] // 4))
                or _u32(result.get('fuse_lock')) != 0 or _u32(result.get('shadow_lock')) != 0
                or reason not in (None, 'ok')):
            raise ValueError('UART OTP fuse values and write protection were not verified')
    elif not isinstance(reason, str) or not reason or len(reason) > 128:
        raise ValueError('Missing UART OTP preflight rejection reason')
    if not commit:
        if result['write_attempted'] or result['verified'] or result.get('after') is not None:
            raise ValueError('OTP preflight returned an unexpected programming result; do not retry')
        return dict(change, before=before, qualified=qualified, write_supported=qualified, reason=reason)
    if (not qualified or not result['write_attempted'] or not result['verified']
            or _u32(result.get('after')) != change['desired']):
        raise ValueError('OTP outcome is unverified; read again, do not retry programming')
    return dict(change, after=result['after'], verified=True)


def plan_change(bridge, part_number, word, expected, desired, delta):
    change = validate_change(word, expected, desired)
    if change['delta'] != delta:
        raise ValueError('Invalid OTP bit change')
    return _user_change(bridge, part_number, change, commit=False)


def program_change(bridge, part_number, word, expected, desired, delta):
    # Recheck immediately before commit; firmware must also recheck atomically
    # inside commit. Neither the preview nor an old read grants write capability.
    planned = plan_change(bridge, part_number, word, expected, desired, delta)
    if not planned['qualified'] or not planned['write_supported']:
        raise ValueError('UART OTP programming is unavailable: ' + planned['reason'])
    fixed = {key: planned[key] for key in ('word', 'expected', 'desired', 'delta')}
    return _user_change(bridge, part_number, fixed, commit=True)

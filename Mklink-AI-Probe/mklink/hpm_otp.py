"""HPM5301 user words only; never expose security, boot or key programming."""
from __future__ import annotations

import re

FIRST, LAST = 69, 79
FUSE, SHADOW = 0xF3050400, 0xF3050000
CHIP_ID = 0x11705142  # Exact hardware qualification; other revisions fail closed.


def _u32(value, label):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{label} must be an unsigned 32-bit integer")
    value = int(value, 0) if isinstance(value, str) else value
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"{label} must be an unsigned 32-bit integer")
    return value


def _word(value):
    value = _u32(value, "word")
    if not FIRST <= value <= LAST:
        raise ValueError("Only HPM5301 application OTP words 69..79 are supported")
    return value


def _read(device, address):
    data = device.read_memory(address, 4)
    if len(data) != 4:
        raise RuntimeError("Incomplete OTP read")
    return int.from_bytes(data, "little")


def identity(device, part_number="HPM5301", model="V4"):
    if part_number.upper() not in ("HPM5301", "HPM5301XEGX") or model != "V4":
        raise ValueError("User OTP programming is qualified only for HPM5301 / V4 HPMLink")
    if device.idcode != 0x1000563D or _read(device, FUSE + 64 * 4) != CHIP_ID:
        raise ValueError("Target CHIP_ID does not match the qualified HPM5301 revision")


def snapshot(device, part_number="HPM5301", model="V4"):
    identity(device, part_number, model)
    hard = _read(device, FUSE)
    rows = []
    for word in range(FIRST, LAST + 1):
        fuse_lock = (_read(device, 0xF3050600 + word // 16 * 4) >> (word % 16 * 2)) & 3
        shadow_lock = (_read(device, 0xF3050200 + word // 16 * 4) >> (word % 16 * 2)) & 3
        rows.append(dict(word=word, current=_read(device, FUSE + word * 4),
                         shadow=_read(device, SHADOW + word * 4),
                         locked=bool(hard & (1 << (word // 4)) or fuse_lock & 1 or shadow_lock & 1)))
    return dict(part_number=part_number, model=model, words=rows, hard_lock=hard,
                irreversible=True, target_reset_required=True)


def _command(device, word, expected, desired, commit):
    response = device._bridge.send_command(
        f"hpm.otp_user({word},{expected},{desired},{int(commit)})", timeout=5)
    codes = re.findall(r"(?m)^\s*(-?\d+)\s*$", response)
    if not codes or int(codes[-1]) != 0 or "OTP_USER v=1 " not in response:
        raise RuntimeError(f"OTP command failed or unsupported; do not retry programming. {response}")
    return response


def plan(device, word, expected, desired, part_number="HPM5301", model="V4"):
    word, expected, desired = _word(word), _u32(expected, "expected"), _u32(desired, "desired")
    state = snapshot(device, part_number, model)
    row = next(row for row in state["words"] if row["word"] == word)
    if row["current"] != expected:
        raise ValueError("OTP snapshot changed; read again before preparing a new plan")
    if desired & expected != expected:
        raise ValueError("OTP bits cannot be cleared (1 to 0)")
    if row["locked"]:
        raise ValueError("OTP word is locked")
    _command(device, word, expected, desired, False)
    return dict(word=word, expected=expected, desired=desired, delta=desired & ~expected,
                irreversible=True, target_reset_required=True,
                script=("# HPM5301 user OTP: irreversible; resets the target.\n"
                        "# Stop on any error; never automatically retry.\n"
                        f"result = hpm.otp_user({word}, {expected}, {desired}, 1)\n"
                        "if result != 0:\n    raise Exception('OTP failed: inspect before retrying')\n"))


def program(device, word, expected, desired, confirm_irreversible=False,
            part_number="HPM5301", model="V4"):
    if confirm_irreversible is not True:
        raise ValueError("Explicit irreversible OTP confirmation is required")
    prepared = plan(device, word, expected, desired, part_number, model)
    response = _command(device, prepared["word"], prepared["expected"], prepared["desired"], True)
    # Programming may reset the target. Never retry if readback fails.
    after = _read(device, FUSE + prepared["word"] * 4)
    if after != prepared["desired"]:
        raise RuntimeError("OTP readback mismatch: unknown outcome, do not retry")
    return dict(**prepared, after=after, verified=True, response=response)


def lock_plan(device, group, expected, part_number="HPM5301", model="V4"):
    group, expected = _u32(group, "group"), _u32(expected, "expected")
    if group not in (18, 19):
        raise ValueError("Only complete user groups 18 (72..75) and 19 (76..79) can be permanently locked")
    state = snapshot(device, part_number, model)
    if state["hard_lock"] != expected:
        raise ValueError("HARD_LOCK snapshot changed; read again")
    if (state["hard_lock"] & 1 or _read(device, 0xF3050600) & 1
            or _read(device, 0xF3050200) & 1):
        raise ValueError("OTP HARD_LOCK is write-locked in the current boot state; no permanent-lock plan can be generated")
    response = device._bridge.send_command(f"hpm.otp_user_lock({group},{expected},0)", timeout=5)
    _lock_result(response)
    desired = expected | (1 << group)
    return dict(word=0, group=group, expected=expected, desired=desired, delta=desired & ~expected,
                affected_words=list(range(group*4, group*4+4)), irreversible=True,
                script=f"# Permanent user group lock; no automatic retry.\nresult = hpm.otp_user_lock({group}, {expected}, 1)\nif result != 0:\n    raise Exception('OTP lock failed: inspect before retrying')\n")


def _lock_result(response):
    codes = re.findall(r"(?m)^\s*(-?\d+)\s*$", response)
    if not codes or int(codes[-1]) != 0 or "OTP_USER v=1 word=0 " not in response:
        raise RuntimeError(f"OTP lock failed or unsupported; read state, do not retry. {response}")


def lock_program(device, group, expected, confirm_irreversible=False, part_number="HPM5301", model="V4"):
    if confirm_irreversible is not True:
        raise ValueError("Explicit permanent lock confirmation is required")
    prepared = lock_plan(device, group, expected, part_number, model)
    response = device._bridge.send_command(f"hpm.otp_user_lock({prepared['group']},{prepared['expected']},1)", timeout=5)
    _lock_result(response)
    after = _read(device, FUSE)
    if after != prepared["desired"]:
        raise RuntimeError("HARD_LOCK readback mismatch; do not retry")
    return dict(**prepared, after=after, verified=True, response=response)

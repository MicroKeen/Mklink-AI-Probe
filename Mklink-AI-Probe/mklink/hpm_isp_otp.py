"""HPM5301 ROM UART read-only OTP client. No write or JTAG fallback."""
from datetime import datetime, timezone
import json
import re
import uuid

from .hpm_otp import CHIP_ID, FIRST, LAST
from .hpm_isp import ISP_ERROR_TEXT

CAPABILITY_COMMAND = 'print("MKLINK_HPM_ISP_OTP_API", hpm.isp_otp_supported())'


def _u32(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Invalid UART OTP value")
    return value


def parse_snapshot(response: str, request_id: str, part_number: str) -> dict:
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
        raise ValueError("UART OTP read returned no unique matching result; read again")
    result = results[0]
    if type(result.get("schema")) is not int or result["schema"] != 1:
        raise ValueError("Unsupported UART OTP response version")
    code = result.get("code")
    if type(code) is not int:
        raise ValueError("Invalid UART OTP result status")
    if code:
        reason = "Unsupported OTP read profile" if code == -12 else ISP_ERROR_TEXT.get(code, "Read failed")
        raise ValueError(f"UART OTP: {reason}")
    if _u32(result.get("rom_status")) != 0:
        raise ValueError("ROM rejected the OTP read")
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

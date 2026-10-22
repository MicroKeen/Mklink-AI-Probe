"""Validated host configuration for firmware-owned HPM ROM USART ISP.

This module does not open a UART or perform target operations.
"""

from dataclasses import dataclass
from collections.abc import Mapping
import json
import re
import uuid

ISP_BAUD_RATES = (115200, 1000000, 2000000, 5000000, 10000000)


def integer(value: object, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{name} must be an integer")
    try:
        result = int(value, 0) if isinstance(value, str) else value
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


@dataclass(frozen=True)
class IspCompletion:
    beep: bool
    reset: str
    restore_voltage_mv: int | None
    power_off_ms: int
    beep_duration_ms: int | None = None


@dataclass(frozen=True)
class HpmIspConfig:
    baud_rate: int
    connect_timeout_ms: int
    command_timeout_ms: int
    memory_id: int
    config_address: int
    nor_options: tuple[int, ...]
    flash_base: int
    flash_size: int
    sector_size: int
    rearm_mode: str
    completion: IspCompletion


def parse_config(raw: object) -> HpmIspConfig:
    if not isinstance(raw, Mapping):
        raise ValueError("USART ISP configuration is required")
    # Host presets match V4 UART clock dividers. Firmware still accepts numeric
    # configuration and verifies clock/driver/ROM support at execution time.
    baud = integer(raw.get("baud_rate", 2000000), "ISP baud rate", 1, 0xFFFFFFFF)
    if baud not in ISP_BAUD_RATES:
        raise ValueError("ISP baud rate must match a supported V4 clock-divider preset")
    timeout = integer(raw.get("connect_timeout_ms", 10000), "ISP handshake timeout", 1000, 3600000)
    command_timeout = integer(raw.get("command_timeout_ms", 10000), "ISP command timeout", 1000, 120000)
    memory_id = integer(raw.get("memory_id", 0x10000), "ISP memory ID", 0, 0xFFFFFFFF)
    address = integer(raw.get("config_address", 0x200), "ISP configuration RAM address", 0, 0xFFFFFFFC)
    if address % 4:
        raise ValueError("ISP configuration RAM address must be word aligned")
    words = raw.get("nor_options", [0xFCF90002, 0x6, 0x1000])
    if not isinstance(words, (list, tuple)) or not 2 <= len(words) <= 4:
        raise ValueError("NOR options must contain a header and its declared option words")
    options = tuple(integer(word, "NOR option", 0, 0xFFFFFFFF) for word in words)
    if options[0] & 0xFFFFFF00 != 0xFCF90000 or (options[0] & 0xFF) != len(options) - 1:
        raise ValueError("NOR option header length does not match the supplied option words")
    flash_base = integer(raw.get("flash_base", 0x80000000), "ISP Flash base", 0, 0xFFFFFFFF)
    if "flash_size" in raw:
        flash_size_value = raw["flash_size"]
    else:
        # Retain the existing 2 MiB default when opening other HPM targets for
        # testing. This is not a measurement of the selected chip or board;
        # callers can supply flash_size for their board's external NOR.
        from mklink.profiles import load_mcu_profiles
        flash = next(region for region in load_mcu_profiles()["hpm5301"]["regions"]
                     if region["name"] == "flash")
        flash_size_value = flash["size"]
    flash_size = integer(flash_size_value, "ISP Flash size", 1, 0x10000000)
    sector_size = integer(raw.get("sector_size", 4096), "ISP erase sector size", 256, 65536)
    if sector_size & (sector_size - 1) or flash_size % sector_size or flash_base % sector_size:
        raise ValueError("Flash size/base must align to a power-of-two erase sector size")
    if flash_base + flash_size > 0x100000000:
        raise ValueError("ISP Flash range exceeds the 32-bit address space")
    if address != 0x200 or memory_id != 0x10000 or flash_base != 0x80000000:
        raise ValueError("HPM USART ISP profile requires RAM 0x200, memory ID 0x10000, Flash base 0x80000000")
    rearm = raw.get("rearm_mode", "isp_reconnect")
    if rearm != "isp_reconnect":
        raise ValueError("Unsupported ISP rearm mode")
    completion = raw.get("completion", {})
    if not isinstance(completion, Mapping):
        raise ValueError("ISP completion settings must be an object")
    beep = completion.get("beep", True)
    if not isinstance(beep, bool):
        raise ValueError("Completion beep must be a boolean")
    beep_ms = (integer(completion["beep_duration_ms"], "Beep duration (ms)", 1, 10000)
               if "beep_duration_ms" in completion else None)
    reset = completion.get("reset", "none")
    if reset not in ("none", "software", "power_cycle"):
        raise ValueError("Unsupported completion reset mode")
    voltage = completion.get("restore_voltage_mv")
    if reset == "power_cycle":
        voltage = integer(voltage, "Power-cycle restore voltage", 1201, 5499)
    elif voltage is not None:
        raise ValueError("Restore voltage is only valid for power-cycle reset")
    off_ms = integer(completion.get("power_off_ms", 200), "Reset duration", 10, 5000)
    return HpmIspConfig(baud, timeout, command_timeout, memory_id, address, options,
                        flash_base, flash_size, sector_size, rearm,
                        IspCompletion(beep, reset, voltage, off_ms, beep_ms))


def validate_images(config, paths) -> None:
    """Validate all images before any SD write; firmware repeats this preflight."""
    isp = config.hpm_isp
    previous_end = None
    for image in sorted(config.firmwares, key=lambda image: image.base_address):
        size = paths[image.id].stat().st_size
        start = image.base_address
        end = start + size
        if size <= 0 or start < isp.flash_base or end > isp.flash_base + isp.flash_size:
            raise ValueError(f"ISP BIN is empty or outside configured Flash: {image.file_name}")
        if previous_end is not None:
            if start < previous_end:
                raise ValueError("ISP BIN address ranges overlap")
            if start != previous_end and start // isp.sector_size == (previous_end - 1) // isp.sector_size:
                raise ValueError("Non-adjacent ISP BIN files share an erase sector; combine the image or use separate sectors")
        previous_end = end


SCRIPT_MARKER = "# MKLINK_HPM_ISP_V1 "
CAPABILITY_COMMAND = 'print("MKLINK_HPM_ISP_API", hpm.isp_supported())'
OTP_JOB_CAPABILITY_COMMAND = 'print("MKLINK_HPM_ISP_OTP_JOB_API", hpm.isp_otp_job_supported())'


def require_otp_job_capability(response: str) -> None:
    if re.findall(r'(?m)^\s*MKLINK_HPM_ISP_OTP_JOB_API\s+(\d+)\s*$', response) != ['1']:
        raise ValueError('Upgrade HPMLINK V4 firmware for combined image and OTP offline jobs')

# hpm_isp_wire.h return codes. Keep screen text short; machine result events
# retain the numeric code independently of the generated script's output.
ISP_ERROR_TEXT = {
    -1: "Invalid settings", -2: "UART I/O error", -3: "timeout",
    -4: "Invalid UART frame", -5: "CRC mismatch", -6: "ROM aborted transfer",
    -7: "ROM rejected command", -8: "Cancelled", -9: "Device busy",
    -10: "BIN file error", -11: "BIN address conflict", -12: "Baud not supported",
}


def require_capability(response: str) -> None:
    if not re.search(r"(?m)^\s*MKLINK_HPM_ISP_API\s+1\s*$", response):
        raise ValueError("Upgrade to HPMLINK V4 firmware with USART ISP API v1; JTAG fallback is disabled")


def generate_script(config) -> str:
    isp = config.hpm_isp
    # Each deployment gets a fresh identifier, even when replacing a BIN at
    # the same name/address. Trigger reads the identifier from the saved script.
    job_id = uuid.uuid4().hex
    args = [isp.baud_rate, isp.connect_timeout_ms, isp.command_timeout_ms,
            isp.config_address, isp.memory_id, isp.flash_base, isp.flash_size, isp.sector_size,
            *(list(isp.nor_options) + [0] * (4 - len(isp.nor_options)))]
    # Firmware action 2 is wired RST; keep power-cycle at action 3.
    reset = {"none": 0, "software": 1, "power_cycle": 3}[isp.completion.reset]
    program_args = [json.dumps(job_id), str(config.auto_download_count),
                    str(int(isp.completion.beep)), str(reset),
                    str(isp.completion.restore_voltage_mv or 0), str(isp.completion.power_off_ms)]
    path_lines = []
    for index, image in enumerate(sorted(config.firmwares, key=lambda image: image.base_address)):
        # The offline runner mounts SD as the current volume. FatFS 0: is USB
        # on V4, so root paths must not hard-code a drive number.
        path_lines.append(f'        path{index} = {json.dumps("/" + image.file_name)}')
        program_args.extend((f"path{index}", str(image.base_address)))
    # Emit simple branches supported by the embedded interpreter, without
    # requiring dict lookup or a new firmware helper for error reporting.
    error_lines = []
    for index, (code, message) in enumerate(ISP_ERROR_TEXT.items()):
        error_lines.extend([
            f"        {'if' if index == 0 else 'elif'} rc == {code}:",
            f"            print(isp_label, {json.dumps(message)})",
        ])
    otp = config.hpm_isp_otp
    timed_beep = isp.completion.beep and isp.completion.beep_duration_ms is not None
    capabilities = ['hpm.isp_supported() == 1']
    if otp is not None:
        capabilities.append('hpm.isp_otp_job_supported() == 1')
    if timed_beep:
        args.append(isp.completion.beep_duration_ms)
    otp_lines = []
    if otp is not None:
        otp_lines = [
            '    if rc == 0:',
            '        isp_label = "USART ISP OTP config:"',
            f'        rc = hpm.isp_otp_job_config({json.dumps(otp.profile)}, {otp.chip_id}, {otp.rom_version}, {otp.soc_revision})',
        ]
        for word, expected, desired in otp.words:
            otp_lines.extend(['    if rc == 0:', f'        rc = hpm.isp_otp_job_add({word}, {expected}, {desired})'])
    return "\n".join([
        SCRIPT_MARKER + json.dumps({"job_id": job_id, "total": config.auto_download_count, **({'otp': True, 'otp_words': len(otp.words)} if otp else {}), **({'beep_duration_ms': isp.completion.beep_duration_ms} if timed_beep else {})}, separators=(",", ":")),
        "import hpm",
        'if ' + ' and '.join(capabilities) + ':',
        '    isp_label = "USART ISP config:"',
        f"    rc = hpm.isp_config({', '.join(map(str, args))})",
        *(['    if rc == -1:',
           '        print("USART ISP config: Upgrade HPMLINK firmware for configurable beep duration")'] if timed_beep else []),
        *otp_lines,
        "    if rc == 0:",
        '        isp_label = "USART ISP"',
        *path_lines,
        f"        rc = hpm.isp_program({', '.join(program_args)})",
        *(['    hpm.isp_otp_job_clear()'] if otp else []),
        "    if rc != 0:",
        *error_lines,
        "        else:",
        '            print(isp_label, "Unknown ISP error")',
        "else:",
        '    print("Upgrade HPMLINK firmware: USART ISP API v1 required")',
        "",
    ])


def script_metadata(text: str) -> dict | None:
    first = text.splitlines()[0] if text else ""
    if not first.startswith(SCRIPT_MARKER):
        return None
    raw = json.loads(first[len(SCRIPT_MARKER):])
    if not isinstance(raw, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", str(raw.get("job_id", ""))):
        raise ValueError("Invalid ISP script job identifier")
    integer(raw.get("total"), "ISP script total", 1, 9999)
    if 'otp' in raw and type(raw['otp']) is not bool:
        raise ValueError('Invalid ISP OTP job metadata')
    if raw.get('otp'):
        integer(raw.get('otp_words'), 'ISP OTP word count', 1, 128)
    if 'beep_duration_ms' in raw:
        integer(raw['beep_duration_ms'], 'Beep duration (ms)', 1, 10000)
    return raw


def trigger_result(lines: list[str], expected: dict | None = None) -> dict:
    messages = []
    for line in lines:
        if not line.startswith("HPM_ISP "):
            continue
        try:
            message = json.loads(line[len("HPM_ISP "):])
        except (ValueError, TypeError):
            continue
        if isinstance(message, dict) and type(message.get("schema")) is int and message["schema"] == 1:
            messages.append(message)
    if expected is not None or messages:
        finals = [m for m in messages if m.get("event") == "result"
                  and (expected is None or m.get("job_id") == expected["job_id"])]
        if not finals:
            return {"status": "unknown", "lines": lines}
        result = finals[-1]
        code = result.get("code")
        success = (type(code) is int and code == 0
                   and type(result.get("total")) is int and result["total"] >= 1
                   and type(result.get("completed")) is int
                   and type(result.get("rom_status")) is int and result["rom_status"] == 0
                   and result.get("completed") == result["total"]
                   and (expected is None or result["total"] == expected["total"]))
        if expected is not None and expected.get('otp'):
            success = (success and type(result.get('otp_verified')) is int
                       and result['otp_verified'] == expected['otp_words']
                       and result.get('otp_reason') in (None, 'ok'))
        return {"status": "completed" if success else "failed", "lines": lines, "isp_result": result}
    text = "\n".join(lines).casefold()
    return {"status": "completed" if "finished" in text and "aborted" not in text else "failed", "lines": lines}

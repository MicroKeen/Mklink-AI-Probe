"""Read-only option-byte/OTP inspection shared by CLI, MCP and Web.

Writing remains owned by the existing validated offline security recipes.
Full HPM JTAG word snapshots require an explicit request.
"""

from __future__ import annotations
from datetime import datetime, timezone
from . import hpm_jtag_otp


def _profile(part: str, model: str):
    from .offline_security import offline_security_capability, _offline_profile

    part = part.strip().upper()
    if model not in ("V2", "V3", "V4"):
        raise ValueError("Select a V2/V3/V4 probe model")
    if hpm_jtag_otp.otp_base(part) is not None:
        if model != "V4":
            return dict(
                part_number=part, model=model, kind="otp", supported=False,
                read_supported=False, fields=[], source="", security=None,
                reason="HPM targets require V4 downloader firmware",
            ), None
        # SDK 1.11.0 HPM5301: hpm_otp_table.h and hpm_soc_ip.h.
        rows = [
            ("HARD_LOCK", "永久写保护位图", 0, 0, 32, "位为1表示对应组已永久禁止烧写。用户组18保护Word72–75，组19保护Word76–79。请在下方选择组，不要手工修改整个位图。"),
            ("LIFECYCLE_A", "安全生命周期 A", 1, 0, 4, "与B一起表示芯片安全状态：0x1普通开发，0x3安全启动，0x7返厂，0xB不可返厂。不是可自由切换的模式；安全启动前须准备匹配的签名镜像。此处只读。"),
            ("LIFECYCLE_B", "安全生命周期 B", 1, 28, 4, "应与A一起核对。A/B不一致时不要自行补写。返厂和不可返厂是不同的不可逆分支；当前GUI不执行生命周期转换。"),
            ("JTAG_DISABLE", "关闭 JTAG 接口", 1, 16, 1, "0：本位未禁用；1：永久禁用JTAG，可能无法再识别芯片或下载程序。0也不保证可调试，其他保护仍可能生效。仅显示，不能在此修改。"),
            ("DEBUG_DISABLE", "关闭调试访问", 1, 17, 1, "0：本位未禁用；1：永久限制调试访问。可能仍读到IDCODE但不能读写内存。普通开发请保持现状；此处只读。"),
            ("SW_VER", "启动版本限制", 3, 0, 32, "用于启动镜像版本检查，不是应用显示的版本号。改动可能使旧镜像无法启动；需要与签名/启动头配套验证。当前显示原始位图，不在此配置。"),
            ("USB_VID", "芯片 ROM USB 厂商标识", 68, 16, 16, "16位厂商标识，与PID配合使用。属于目标芯片ROM USB配置，不是修改MKLink下载器或应用USB描述符。当前只读。"),
            ("USB_PID", "芯片 ROM USB 产品标识", 68, 0, 16, "16位产品标识，与VID配合使用。不是串口号；修改不会直接改变应用程序自己定义的USB设备信息。当前只读。"),
        ]
        legacy = part in ("HPM5301", "HPM5301XEGX")
        from .hpm_jtag_otp_rom import profile_for
        try:
            write_api = "legacy" if legacy else "rom_v1" if profile_for(part, model) else None
            write_error = None
        except (OSError, ValueError) as exc:
            write_api, write_error = None, str(exc)
        if not legacy:
            rows = [
                ("HARD_LOCK", "永久写保护位图", 0, 0, 32, "每位对应四个 OTP Word。"),
                ("CHIP_ID", "芯片标识", 64, 0, 32, "读取所选系列的芯片标识。"),
            ]
        fields = [
            dict(
                id=id,
                label=label,
                word=word,
                bit_offset=shift,
                bit_width=width,
                description=desc,
                writable=False,
                current=None,
                shadow=None,
            )
            for id, label, word, shift, width, desc in rows
        ]
        return dict(
            part_number=part,
            model=model,
            kind="otp",
            supported=True,
            read_supported=True,
            fields=fields,
            source=f"HPM SDK / {part}",
            otp_word_count=128,
            jtag_otp_write_api=write_api, jtag_otp_write_error=write_error,
            reason="JTAG 可读取 Word 0–127，并分别显示熔丝值与影子值。",
            security=None,
        ), None
    if part.startswith('HPM'):
        return dict(part_number=part, model=model, kind='otp', supported=False,
                    read_supported=False, fields=[], source='', security=None,
                    reason='此型号尚无 JTAG OTP 寄存器映射。'), None
    capability = offline_security_capability(model, part)
    recipe = (
        _offline_profile(part, str(capability["family"]))
        if capability["supported"]
        else None
    )
    if recipe is None:
        return dict(
            part_number=part,
            model=model,
            kind="option_bytes",
            supported=False,
            read_supported=False,
            fields=[],
            source="",
            security=capability,
            reason=capability["reason"] or "该型号尚无配置读取描述",
        ), None
    cfg = dict(
        line.split("=", 1)
        for line in recipe.config_factory("lock", recipe.voltage_mv, part)
        .decode()
        .splitlines()
    )
    field = dict(
        id="RDP",
        label="读保护状态",
        writable=True,
        current=None,
        shadow=None,
        description="通过下方已验证的解锁/加锁选项生成脚本；其他选项字节保持不变。",
    )
    from .stm32f1_options import fields as option_fields

    extra = option_fields(part)
    return dict(
        part_number=part,
        model=model,
        kind="option_bytes",
        supported=True,
        read_supported=True,
        fields=[field, *extra],
        shadow_supported=bool(extra),
        option_write_supported=bool(extra),
        source="Validated offline security recipe",
        security=capability,
        reason=(
            "USER / DATA / 写保护可配置；空白表示保持。读保护使用下方加解锁流程。"
            if extra
            else "目前支持读保护配置；BOR、看门狗、启动及写保护字段尚未开放。"
        ),
    ), cfg


def describe_configuration(part_number: str, model: str = "V4") -> dict:
    return _profile(part_number, model)[0]


def read_configuration(device, part_number: str, model: str = "V4", otp_words: bool = False) -> dict:
    result, cfg = _profile(part_number, model)
    if not result["read_supported"]:
        raise ValueError(result["reason"])
    if otp_words and result["kind"] != "otp":
        raise ValueError("Full OTP word reads require an HPM target")

    def word(address):
        data = device.read_memory(address, 4)
        if len(data) != 4:
            raise RuntimeError(f"Configuration read incomplete at 0x{address:08X}")
        return int.from_bytes(data, "little")

    name = device.mcu_name.upper()
    if result["kind"] == "otp":
        part = result["part_number"]
        chip_id = hpm_jtag_otp.check_target(device, part, word, check_read_lock=otp_words)
        if otp_words:
            result.update(hpm_jtag_otp.read_words(device, part, chip_id))
            snapshots = {r["word"]: (r["current"], r["shadow"]) for r in result["words"]}
        else:
            base = hpm_jtag_otp.otp_base(part)
            snapshots = {i: (word(base + 0x400 + i * 4), word(base + i * 4))
                         for i in sorted({f["word"] for f in result["fields"]})}
        for field in result["fields"]:
            raw, shadow = snapshots[field["word"]]
            mask = (1 << field["bit_width"]) - 1
            field["current"] = None if raw is None else (raw >> field["bit_offset"]) & mask
            field["shadow"] = None if shadow is None else (shadow >> field["bit_offset"]) & mask
    else:
        if "HPM" in name:
            raise ValueError(
                "Connected HPM target cannot use an ARM option-byte description"
            )
        actual = word(int(cfg["id_address"], 0))
        if actual & int(cfg["id_mask"], 0) != int(cfg["id_expected"], 0):
            raise ValueError(
                "Connected target device ID does not match the selected recipe"
            )
        status = word(int(cfg["status_address"], 0))
        if status & int(cfg["status_error_mask"], 0):
            raise RuntimeError(
                "Option-byte status reports an error; snapshot is not valid"
            )
        protected_mask = int(cfg["status_protected_mask"], 0)
        if protected_mask:
            state = "protected" if status & protected_mask else "unprotected"
        else:
            raw = word(int(cfg["shadow_word0_address"], 0)) & 0xFF
            state = (
                "unprotected"
                if raw == int(cfg["unprotected_value"], 0)
                else "permanent"
                if raw == int(cfg["forbidden_value"], 0)
                else "protected"
            )
        result["fields"][0]["current"] = state
        if result.get("shadow_supported"):
            from .stm32f1_options import geometry

            if word(0x1FFFF7E0) & 0xFFFF != geometry(result["part_number"]).flash_kib:
                raise ValueError(
                    "Connected target Flash density does not match the selected part"
                )
            wrp = word(0x40022020)
            shadow = {
                2: (status >> 2) & 255,
                4: (status >> 10) & 255,
                6: (status >> 18) & 255,
                **{8 + i * 2: (wrp >> (8 * i)) & 255 for i in range(4)},
            }
            raw = None
            if state == "unprotected":
                raw = device.read_memory(0x1FFFF800, 16)
                if len(raw) != 16 or any(
                    raw[i] ^ raw[i + 1] != 255 for i in range(0, 16, 2)
                ):
                    raise RuntimeError(
                        "Option-byte storage length/complement validation failed"
                    )
                result["raw_options_hex"] = raw.hex()
            for field in result["fields"][1:]:
                offset, shift = field["byte_offset"], field["bit_offset"]
                mask = (1 << field["bit_width"]) - 1
                field["current"] = (
                    (raw[offset] >> shift) & mask if raw is not None else None
                )
                field["shadow"] = (shadow[offset] >> shift) & mask
    result["read_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result["snapshot_only"] = True
    return result


def configuration_script(part_number: str, changes: dict, model: str = "V4") -> dict:
    from .offline_download import parse_offline_config, generate_offline_script

    payload = dict(
        model=model,
        target_part=part_number,
        script_name="option-config.py",
        option_bytes=changes,
        algorithms=[],
        firmwares=[],
    )
    config = parse_offline_config(payload)
    return dict(
        config=payload,
        script_name=config.script_name,
        script=generate_offline_script(config),
        algorithm="STM32F10x_OPT.FLM",
    )


def run_offline_cli(args):
    import json

    if args.action == "describe":
        result = describe_configuration(args.chip, args.model)
    elif args.action == "generate":
        changes = {}
        for assignment in args.set:
            name, separator, value = assignment.partition("=")
            if not separator or name in changes:
                raise ValueError("Each --set must be a unique FIELD=VALUE")
            changes[name] = value
        result = configuration_script(args.chip, changes, args.model)
    else:
        raise ValueError('Offline configuration supports describe or generate only')
    print(json.dumps(result, ensure_ascii=False))

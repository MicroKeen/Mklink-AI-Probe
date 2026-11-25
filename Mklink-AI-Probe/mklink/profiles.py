"""
MKLink Serial Bridge — MCU 配置加载。

mcu_profiles.json 位于本包同目录下。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


def load_mcu_profiles(profile_path: str | None = None) -> dict:
    """加载 MCU 配置文件。"""
    if profile_path is None:
        profile_path = str(Path(__file__).parent / "mcu_profiles.json")

    with open(profile_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("mcus", {})


@dataclass(frozen=True)
class MuxAttachStep:
    kind: int
    ap: int
    address: int
    mask: int
    value: int


@dataclass(frozen=True)
class MuxAttachProfile:
    name: str
    mem_ap: int
    steps: tuple[MuxAttachStep, ...]
    requires_reset_released: bool = False


_ATTACH_HOOKS = ("ConfigTargetSettings", "InitTarget", "SetupTarget")
_RESERVED_HOOKS = (
    "ResetTarget", "InitEMU", "OnDisconnectTarget", "OnTraceStop", "OnTraceStart",
    "BeforeResetTarget", "AfterResetTarget", "AfterHalt", "BeforeGo",
    "SWO_EnableTarget", "SWO_GetSWOBaseClock", "HandleBeforeFlashProg", "HandleAfterFlashProg",
    "HandleBeforeMemAccessWrite", "HandleAfterMemAccessWrite",
    "HandleBeforeMemAccessRead", "HandleAfterMemAccessRead",
) + tuple(action + component for component in (
    "ETM", "TPIU", "TMC", "PTM", "TF", "ETB", "STM",
    "NTRACETE", "NTRACETF", "NTRACEPIB", "NTRACESRAM", "NTRACEATB",
) for action in ("Start", "Stop"))


class TargetProfileError(ValueError):
    def __init__(self, code: str, message: str, *, hook: str | None = None):
        super().__init__(f"{code}: {message}")
        self.detail = {"code": code, "message": str(self), "hook": hook}


def compile_attach_profile(name: str, recipe: dict) -> MuxAttachProfile:
    """Compile declarative lifecycle phases in connection order, before opening the probe."""
    from mklink.mux import encode_attach_profile

    if not isinstance(recipe, dict) or type(recipe.get("version")) is not int or recipe["version"] != 1:
        raise TargetProfileError("unsupported_profile_version", f"{name} requires target profile version 1")
    hooks = recipe.get("hooks")
    if set(recipe) != {"version", "hooks"} or not isinstance(hooks, dict):
        raise TargetProfileError("invalid_profile", f"{name} requires a version and hooks object")
    for hook, declaration in hooks.items():
        if hook not in _ATTACH_HOOKS and (hook not in _RESERVED_HOOKS or declaration != []):
            raise TargetProfileError("unsupported_hook", f"{name} cannot execute {hook}", hook=hook)
    settings = hooks.get("ConfigTargetSettings")
    if (not isinstance(settings, dict) or "mem_ap" not in settings
            or set(settings) - {"mem_ap", "requires_reset_released"}
            or type(settings.get("requires_reset_released", False)) is not bool):
        raise TargetProfileError("invalid_hook", "ConfigTargetSettings requires mem_ap and accepts a boolean requires_reset_released",
                                 hook="ConfigTargetSettings")
    steps = []
    for hook, kinds in (("InitTarget", {"ap_check": 1, "ap_update": 2}),
                        ("SetupTarget", {"mem32_check": 3})):
        operations = hooks.get(hook, [])
        if not isinstance(operations, list):
            raise TargetProfileError("invalid_hook", f"{hook} requires a list of operations", hook=hook)
        for index, step in enumerate(operations):
            try:
                if set(step) != {"kind", "ap", "address", "mask", "value"}:
                    raise ValueError("unexpected or missing fields")
                steps.append(MuxAttachStep(
                    kind=kinds[step["kind"]], ap=step["ap"], address=int(step["address"], 0),
                    mask=int(step["mask"], 0), value=int(step["value"], 0),
                ))
            except (KeyError, TypeError, ValueError) as exc:
                raise TargetProfileError("invalid_hook", f"{hook}[{index}] invalid operation: {exc}",
                                         hook=hook) from exc
    profile = MuxAttachProfile(name, settings["mem_ap"], tuple(steps), settings.get("requires_reset_released", False))
    try:
        encode_attach_profile(profile)
    except ValueError as exc:
        raise TargetProfileError("invalid_profile", f"{name}: {exc}") from exc
    return profile


def target_profile_catalog() -> dict:
    """Describe host hook support and selectable models without a probe or runtime."""
    profiles = []
    for key, entry in load_mcu_profiles().items():
        row = {"key": key, "name": entry["name"]}
        if "mux_attach" in entry:
            try:
                profile = compile_attach_profile(entry["name"], entry["mux_attach"])
                row.update(mem_ap=profile.mem_ap, hooks=list(entry["mux_attach"]["hooks"]))
            except TargetProfileError as exc:
                row["error"] = exc.detail
        profiles.append(row)
    return {"profiles": profiles, "hook_support": {"version": 1, "supported": list(_ATTACH_HOOKS),
                                                  "reserved": list(_RESERVED_HOOKS)}}


def resolve_attach_profile(mcu: str | None, *, project_root: str | None = None,
                           config: dict | None = None) -> MuxAttachProfile | None:
    """Resolve the selected model in the packaged catalog before any target I/O."""
    if not mcu and project_root:
        from mklink.project_config import load_config, load_project_info
        if config is None:
            config = load_config(project_root) or {}
        mcu = config.get("mcu_key")
        if not mcu:
            project = load_project_info(project_root) or {}
            mcu = project.get("device") or project.get("target_part")
    if not mcu:
        return None
    if not isinstance(mcu, str):
        raise TargetProfileError("invalid_profile", "The selected MCU model must be a string")
    entry = load_mcu_profiles().get(mcu.strip().casefold())
    if entry is None or "mux_attach" not in entry:
        return None
    return compile_attach_profile(entry["name"], entry["mux_attach"])


def match_mcu_by_idcode(idcode: int, profiles: dict) -> str | None:
    """仅返回唯一 IDCODE 匹配；同调试端口 ID 的多个器件不能按顺序猜测。"""
    idcode_str = f"0x{idcode:08X}"
    matches = [key for key, profile in profiles.items()
               if (profile.get("idcode_pattern") or "").upper() == idcode_str.upper()]
    # A debug-port IDCODE may describe multiple targets; order is not identity.
    return matches[0] if len(matches) == 1 else None


def match_mcu_by_device(device_name: str, profiles: dict) -> str | None:
    """按唯一最长设备名称前缀匹配 MCU 配置；同等具体的候选视为歧义。

    例如 "N32G435CB" 匹配 device_prefix "N32G43" → 返回 "n32g435"。
    """
    if not device_name:
        return None
    upper = device_name.upper()
    matches = []
    for key, profile in profiles.items():
        prefix = profile.get("device_prefix", "")
        if prefix and upper.startswith(prefix.upper()):
            matches.append((len(prefix), key))
    if not matches:
        return None
    longest = max(length for length, _ in matches)
    exact = [key for length, key in matches if length == longest]
    return exact[0] if len(exact) == 1 else None

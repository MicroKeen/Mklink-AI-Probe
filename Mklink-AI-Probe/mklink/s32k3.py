"""S32K3 application-core profiles from NXP S32K3XXRM rev 11 and S32K396RM rev 4."""

from copy import deepcopy


# MIDR1[25:16] is the numeric part number. The lists are the values enumerated
# by the manuals, not a wildcard covering every three-digit number.
PART_NUMBERS = (
    310, 311, 312, 314, 322, 324, 328, 338, 341, 342, 344, 348, 356, 358,
    364, 366, 374, 376, 388, 389, 394, 396,
)
MODELS = frozenset(f"S32K{number}" for number in PART_NUMBERS)
DFP_RESET_MODELS = frozenset({"S32K312", "S32K314", "S32K324", "S32K344"})
MIDR1_ADDRESS = 0x40290004
MIDR1_MODEL_MASK = 0xFFFF0000
# E_LETTER[31:26] = 0x0B (K), PART_NO[25:16] is the numeric part number.
MIDR1_MODELS = {(0x0B << 26) | (number << 16): f"S32K{number}" for number in PART_NUMBERS}


def midr1_model_mismatch(profile, step, actual):
    """Interpret a failed read comparison only for the catalog's AP4 identity check."""
    if (step.kind != 3 or step.ap != 4 or profile.mem_ap != 4
            or step.address != MIDR1_ADDRESS or step.mask != MIDR1_MODEL_MASK
            or MIDR1_MODELS.get(step.value) != profile.name):
        return None
    reported = MIDR1_MODELS.get(actual & step.mask)
    if reported is None or reported == profile.name:
        return None
    part_no = (actual >> 16) & 0x3FF
    return {
        "requested_model": profile.name, "reported_model": reported, "register": "SIUL2.MIDR1",
        "address": step.address, "mask": step.mask, "expected": step.value, "part_no": part_no,
        "message": (f"本次配置 {profile.name}，目标寄存器报告 {reported}。"
                    f"AP{step.ap} SIUL2.MIDR1 (0x{step.address:08X}) 的 PART_NO=0x{part_no:03X}，"
                    f"期望 0x{step.value:08X}，掩码 0x{step.mask:08X}。"),
    }


def flash_workspace(model):
    """First SRAM0 bank, limited by both the RM memory map and the host work area."""
    if model not in MODELS:
        return None
    size = {"S32K310": 0x4000, "S32K311": 0x8000}.get(model, 0x10000)
    return 0x20400000, size


def expand_profiles(common, models):
    """Materialize independent v1 recipes; the transport still compiles normal hooks."""
    for signature, name in MIDR1_MODELS.items():
        key = name.lower()
        if key in models:
            raise ValueError(f"Duplicate S32K3 model {key}")
        recipe = deepcopy(common)
        hooks = recipe["hooks"]
        settings = hooks["ConfigTargetSettings"]
        if name == "S32K314":
            settings["online_system_reset"] = "s32k314_functional"
        elif name in DFP_RESET_MODELS:
            settings["online_system_reset"] = "s32k3_dfp_functional"
        else:
            settings["online_system_reset"] = "s32k3_functional"
        hooks["SetupTarget"].append({
            "kind": "mem32_check", "ap": settings["mem_ap"], "address": hex(MIDR1_ADDRESS),
            "mask": hex(MIDR1_MODEL_MASK), "value": f"0x{signature:08x}",
        })
        entry = {"name": name, "mux_attach": recipe}
        if name == "S32K314":
            entry["aliases"] = ["S32K314HMS", "NXPS32K314HMS"]
        models[key] = entry

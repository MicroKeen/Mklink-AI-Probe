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


def flash_workspace(model):
    """First SRAM0 bank, limited by both the RM memory map and the host work area."""
    if model not in MODELS:
        return None
    size = {"S32K310": 0x4000, "S32K311": 0x8000}.get(model, 0x10000)
    return 0x20400000, size


def expand_profiles(common, models):
    """Materialize independent v1 recipes; the transport still compiles normal hooks."""
    for number in PART_NUMBERS:
        name = f"S32K{number}"
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
        # MIDR1[31:26] = 0x0B (product line K). Ignore package and mask revision.
        signature = (0x0B << 26) | (number << 16)
        hooks["SetupTarget"].append({
            "kind": "mem32_check", "ap": settings["mem_ap"], "address": "0x40290004",
            "mask": "0xffff0000", "value": f"0x{signature:08x}",
        })
        entry = {"name": name, "mux_attach": recipe}
        if name == "S32K314":
            entry["aliases"] = ["S32K314HMS", "NXPS32K314HMS"]
        models[key] = entry

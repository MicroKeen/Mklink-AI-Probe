"""S32K314 algorithm metadata confirmed against Keil.S32K3xx_DFP 1.0.1."""

from hashlib import sha256
from pathlib import Path


CODE_SHA256 = "ec68ecfee2740100df26150537e4e63ae4f3ce20f93bb4006b8f84e05c0ec1b7"
DATA_SHA256 = "05a67d4697187c87b42e72de41ef17cf38239d3b358ee683d24c87d57c1c6b80"
CODE_START = 0x00400000
CODE_END = 0x007E0000
DATA_START = 0x10000000
DATA_SIZE = 0x20000


def code_overlaps_data(part, digest, start, size):
    return (str(part).casefold() == "s32k314" and str(digest).casefold() == CODE_SHA256
            and start < DATA_START + DATA_SIZE and start + size > DATA_START)


def code_range(start, size):
    """Intersect the catalog range with this Code FLM's embedded FlashDevice."""
    begin = max(start, CODE_START)
    return begin, max(0, min(start + size, CODE_END) - begin)


def correct_algorithm(root, part, item):
    """Return one usable built-in row; keep original positions stable for algorithm IDs."""
    if str(part).casefold() != "s32k314":
        return item
    digest = str(item.get("sha256", "")).casefold()
    if digest not in (CODE_SHA256, DATA_SHA256):
        return item
    try:
        start, size = int(item["flash_start"]), int(item["flash_size"])
    except (KeyError, TypeError, ValueError):
        return None
    if start < 0 or size <= 0:
        return None
    if code_overlaps_data(part, digest, start, size) or digest == DATA_SHA256:
        if (start, size) != (DATA_START, DATA_SIZE):
            return None
        # The original full catalog already ships the DFP Data blob for other
        # parts. Verify it before advertising a replacement even in an old bundle.
        relative = f"blobs/{DATA_SHA256[:2]}/{DATA_SHA256}.flm"
        try:
            path = (Path(root) / relative).resolve()
            if not path.is_relative_to(Path(root).resolve()) or sha256(path.read_bytes()).hexdigest() != DATA_SHA256:
                return None
        except (OSError, RuntimeError):
            return None
        item = dict(item, blob=relative, sha256=DATA_SHA256, file_name="S32K3x4_Data.FLM",
                    page_size=0x2000, sector_sizes=[[0, 0x2000]])
    else:
        start, size = code_range(start, size)
        if not size:
            return None
        item = dict(item, flash_start=start, flash_size=size)
    return dict(item, ram_start=0x20400000, ram_size=0x10000)

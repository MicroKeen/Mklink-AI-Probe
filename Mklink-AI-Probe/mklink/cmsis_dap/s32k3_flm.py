"""S32K3 FlashDevice geometry from the identified Keil 1.0.1 algorithm files."""

from hashlib import sha256
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple


CODE_SHA256 = "ec68ecfee2740100df26150537e4e63ae4f3ce20f93bb4006b8f84e05c0ec1b7"
DATA_SHA256 = "05a67d4697187c87b42e72de41ef17cf38239d3b358ee683d24c87d57c1c6b80"
CODE_START = 0x00400000
CODE_END = 0x007E0000
X2_CODE_SHA256 = "1ccb035d72472ce0e9fc85ce4f243e540e574af0a543ca80c2a8b373feddd94f"
X2_DATA_SHA256 = "aba45a795ddd71f5896823d0c025fde77de39ab8a2f732143e54cc8442eb2e47"
DATA_START = 0x10000000
DATA_SIZE = 0x20000


class FlashLayout(NamedTuple):
    family: str
    code_sha: str
    data_sha: str
    code_end: int


def layout(part):
    model = str(part).upper()
    if model in {"S32K314", "S32K324", "S32K344"}:
        return FlashLayout("S32K3x4", CODE_SHA256, DATA_SHA256, CODE_END)
    if model in {"S32K312", "S32K322", "S32K342"}:
        return FlashLayout("S32K3x2", X2_CODE_SHA256, X2_DATA_SHA256, 0x005E0000)
    return None


def code_range(start, size, limit):
    """Intersect the catalog range with this Code FLM's embedded FlashDevice."""
    begin = max(start, CODE_START)
    return begin, max(0, min(start + size, limit) - begin)


def extend_builtin_catalog(records):
    """S32K322 and S32K342 implement the same x2 flash block geometry (RM table 102)."""
    if any(row.get("part_number") == "S32K322" for row in records):
        return
    for row in records:
        if row.get("part_number") != "S32K342":
            continue
        raw = row.get("algorithms")
        if not isinstance(raw, list):
            continue
        algorithms = [item for item in raw
                      if isinstance(item, Mapping) and item.get("sha256") in {X2_CODE_SHA256, X2_DATA_SHA256}]
        if {item["sha256"] for item in algorithms} == {X2_CODE_SHA256, X2_DATA_SHA256}:
            records.append(dict(part_number="S32K322", manufacturer="NXP", series="S32K3",
                                algorithms=algorithms, ram_start=0x20400000, ram_size=0x10000))
            return


def correct_algorithm(root, part, item):
    """Return one usable built-in row; keep original positions stable for algorithm IDs."""
    selected = layout(part)
    if selected is None:
        return item
    family, code_digest, data_digest, limit = selected
    digest = str(item.get("sha256", "")).casefold()
    if digest not in (code_digest, data_digest):
        return item
    try:
        start, size = int(item["flash_start"]), int(item["flash_size"])
    except (KeyError, TypeError, ValueError):
        return None
    if start < 0 or size <= 0:
        return None
    if digest == data_digest or (start < DATA_START + DATA_SIZE and start + size > DATA_START):
        if (start, size) != (DATA_START, DATA_SIZE):
            return None
        # The original full catalog already ships the DFP Data blob for other
        # parts. Verify it before advertising a replacement even in an old bundle.
        relative = f"blobs/{data_digest[:2]}/{data_digest}.flm"
        try:
            path = (Path(root) / relative).resolve()
            if not path.is_relative_to(Path(root).resolve()) or sha256(path.read_bytes()).hexdigest() != data_digest:
                return None
        except (OSError, RuntimeError):
            return None
        item = dict(item, blob=relative, sha256=data_digest, file_name=f"{family}_Data.FLM",
                    page_size=0x2000, sector_sizes=[[0, 0x2000]])
    else:
        start, size = code_range(start, size, limit)
        if not size:
            return None
        item = dict(item, flash_start=start, flash_size=size)
    return dict(item, ram_start=0x20400000, ram_size=0x10000)

"""Shared HPMicro board configuration."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Sequence


_HPM_BOARD = re.compile(r"^[A-Za-z0-9._-]+$")
_HPM_CFG_WORD = re.compile(r"^0[xX][0-9A-Fa-f]+[uU]?$")

_DEFAULTS = json.loads(Path(__file__).with_name("hpm_flash_defaults.json").read_text(encoding="utf-8"))
HPM_BOARD_FLASH_CFG: dict[str, tuple[str, str, str, str]] = {
    board: tuple(words) for board, words in _DEFAULTS["boards"].items()
}
HPM_TARGET_DEFAULT_BOARD: tuple[tuple[str, str], ...] = tuple(
    tuple(entry) for entry in _DEFAULTS["targets"]
)

HPM_ROM_TARGETS: tuple[str, ...] = (
    "HPM5300", "HPM5301", "HPM5301xEGx", "HPM5E00", "HPM6200",
    "HPM6300", "HPM6400", "HPM6700", "HPM6750", "HPM6800", "HPM6E00", "HPM6E80", "HPM6P00",
)


def is_hpm_target(
    part_number: object = None,
    *,
    vendor: object = None,
    board: object = None,
) -> bool:
    """Return whether the target uses the HPMicro device-side ROM API."""
    part = str(part_number or "").strip().casefold()
    board_name = str(board or "").strip().casefold()
    vendor_name = "".join(str(vendor or "").split()).casefold()
    return part.startswith("hpm") or board_name.startswith("hpm") or vendor_name == "hpmicro"


def default_hpm_board(part_number: object) -> str | None:
    normalized = str(part_number or "").strip().casefold()
    for prefix, board in HPM_TARGET_DEFAULT_BOARD:
        if normalized.startswith(prefix):
            return board
    return None


def normalize_hpm_board(value: object) -> str:
    board = str(value or "").strip().casefold()
    if not board or _HPM_BOARD.fullmatch(board) is None:
        raise ValueError("HPM board is invalid")
    return board


def normalize_hpm_flash_cfg(
    value: Sequence[object] | None,
) -> tuple[str, str, str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 4:
        raise ValueError("HPM flash config must contain four words")
    if not all(isinstance(word, str) for word in value):
        raise ValueError("HPM flash config words must be hexadecimal strings")
    words = tuple(word.strip() for word in value)
    if not all(_HPM_CFG_WORD.fullmatch(word) and int(word.rstrip("uU"), 16) <= 0xFFFFFFFF for word in words):
        raise ValueError("HPM flash config word is invalid")
    return words  # type: ignore[return-value]


def normalize_hpm_address(value: object) -> tuple[int, str]:
    if isinstance(value, bool):
        raise ValueError("HPM address must be an integer")
    try:
        address = int(value, 0) if isinstance(value, str) else int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("HPM address must be an integer") from error
    if address < 0 or address > 0xFFFFFFFF:
        raise ValueError("HPM address must be between 0x00000000 and 0xFFFFFFFF")
    return address, f"0x{address:08X}"


def normalize_hpm_configuration(
    part_number: object,
    *,
    board: object = None,
    flash_cfg: Sequence[object] | None = None,
) -> tuple[str | None, tuple[str, str, str, str] | None]:
    resolved_board = str(board or "").strip()
    normalized_board = normalize_hpm_board(resolved_board) if resolved_board else None
    normalized_cfg = normalize_hpm_flash_cfg(flash_cfg)
    if normalized_board is None and normalized_cfg is None:
        default_board = default_hpm_board(part_number)
        normalized_board = normalize_hpm_board(default_board) if default_board else None
    if normalized_board is None and normalized_cfg is None:
        raise ValueError("HPM target requires a board or flash configuration")
    if normalized_cfg is None and normalized_board in HPM_BOARD_FLASH_CFG:
        normalized_cfg = HPM_BOARD_FLASH_CFG[normalized_board]
    return normalized_board, normalized_cfg

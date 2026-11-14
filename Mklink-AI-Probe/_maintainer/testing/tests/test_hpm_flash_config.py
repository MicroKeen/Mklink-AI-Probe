"""HPM ROM configuration is explicit and independent of the image load address."""
import pytest

from mklink.hpm_config import HPM_BOARD_FLASH_CFG, normalize_hpm_configuration
from mklink.flash import FlashError, MKLinkFlash
from mklink.offline_download import generate_offline_script, parse_offline_config

CUSTOM = ("0xfcf90001", "0x00000007", "0x00000000", "0xf3040000")


@pytest.mark.parametrize("board", [None, "hpm5301evklite", "custom_board"])
def test_explicit_nor_configuration_wins_over_board_and_target(board):
    _, words = normalize_hpm_configuration("HPM5301", board=board, flash_cfg=CUSTOM)
    assert words == CUSTOM


def test_known_reference_board_resolves_to_four_words_but_unknown_board_is_preserved():
    assert normalize_hpm_configuration("HPM5301") == (
        "hpm5301evklite", HPM_BOARD_FLASH_CFG["hpm5301evklite"])
    assert normalize_hpm_configuration("HPM6400", board="custom_board") == ("custom_board", None)
    with pytest.raises(ValueError, match="requires"):
        normalize_hpm_configuration("HPM6400")
    assert normalize_hpm_configuration("HPM6400", flash_cfg=CUSTOM) == (None, CUSTOM)


@pytest.mark.parametrize("word", [0, True, "0x100000000", "-1", "0x1);evil()", "0x1\n0x2", ""])
def test_bad_config_rejected_before_copy_or_hardware(tmp_path, word):
    flash = MKLinkFlash(object())  # Any device access is a test failure.
    flash._copy_to_microkeen = lambda *_args, **_kwargs: pytest.fail("copied invalid configuration")
    path = tmp_path / "test.bin"
    path.write_bytes(b"test")
    with pytest.raises((ValueError, FlashError)):
        flash.burn_hpm_bin(str(path), addr="0x80000400", board="hpm5301evklite", flash_cfg=[word, *CUSTOM[1:]])


def test_failed_flash_configuration_does_not_start_programming(tmp_path):
    commands = []
    class Bridge:
        def send_command(self, command, **_kwargs):
            commands.append(command)
            return "-1\n"
    flash = MKLinkFlash(Bridge())
    flash._copy_to_microkeen = lambda *_args, **_kwargs: "test.bin"
    path = tmp_path / "test.bin"
    path.write_bytes(b"test")
    with pytest.raises(FlashError, match="configuration failed"):
        flash.burn_hpm_bin(str(path), addr="0x80000400", board="hpm5301evklite", flash_cfg=CUSTOM)
    assert commands == [f"hpm.flash_cfg({','.join(CUSTOM)})"]


@pytest.mark.parametrize("part,board", [("HPM5301", "hpm5301evklite"), ("HPM6400", None)])
def test_offline_uses_custom_config_and_keeps_image_address(part, board):
    config = parse_offline_config(dict(
        model="V4", script_name="test.py", target_part=part, board=board, hpm_flash_cfg=CUSTOM,
        algorithms=[], firmwares=[dict(id="app", file_name="app.bin", format="bin",
            base_address="0x80000400", algorithm_id="", upload_index=0)],
    ))
    script = generate_offline_script(config)
    assert f"hpm.flash_cfg({','.join(CUSTOM)})" in script
    assert 'hpm.program("app.bin", 0x80000400)' in script
    assert 'hpm.board(' not in script

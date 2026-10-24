"""Validated OTP recipe for a firmware-owned image + OTP UART job."""
from dataclasses import dataclass

from .hpm_isp import integer
from .hpm_otp_profiles import family, ordered_changes


@dataclass(frozen=True)
class IspOfflineOtp:
    profile: str
    chip_id: int
    rom_version: int
    soc_revision: int
    words: tuple[tuple[int, int, int], ...]


def resolve(raw, part, model, protocol):
    if raw is None:
        return None
    if model != 'V4' or protocol != 'hpm_rom_isp_uart':
        raise ValueError('UART offline OTP requires V4 and USART ISP')
    profile = family(part.upper())
    if not isinstance(raw, dict) or set(raw) != {'target_identity', 'words', 'confirm_irreversible'}:
        raise ValueError('Invalid UART offline OTP configuration')
    if raw['confirm_irreversible'] is not True:
        raise ValueError('Confirm irreversible offline OTP programming')
    identity = raw['target_identity']
    if not isinstance(identity, dict) or set(identity) != {'chip_id', 'rom_version', 'soc_revision'}:
        raise ValueError('UART offline OTP requires the freshly read target identity')
    ids = [integer(identity['chip_id'], 'chip_id', 0, 0xFFFFFFFF)]
    ids += [integer(identity[k], k, 0, 0xFFFFFFFF) for k in ('rom_version', 'soc_revision')]
    words = raw['words']
    if not isinstance(words, list) or not 1 <= len(words) <= 128:
        raise ValueError('Select 1..128 offline OTP words')
    parsed = []
    for item in words:
        if not isinstance(item, dict) or set(item) != {'word', 'expected', 'desired'}:
            raise ValueError('Each OTP word requires word, expected and desired')
        word = integer(item['word'], 'OTP word', 0, 127)
        expected = integer(item['expected'], 'Expected OTP value', 0, 0xFFFFFFFF)
        desired = integer(item['desired'], 'Desired OTP value', 0, 0xFFFFFFFF)
        if expected & desired != expected:
            raise ValueError('OTP bits cannot be cleared (1 to 0)')
        if any(row['word'] == word for row in parsed):
            raise ValueError('Duplicate OTP word')
        # Equal values remain in the recipe: firmware checks then skips them.
        parsed.append(dict(word=word, expected=expected, desired=desired))
    return IspOfflineOtp(profile, *ids, tuple((r['word'], r['expected'], r['desired']) for r in ordered_changes(parsed)))

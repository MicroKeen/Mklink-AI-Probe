"""HPM Manufacturing Tool v0.6.0 family selection and OTP word bounds.

The UI field maps describe configuration, not permission to program a target.
The firmware must match the ROM family before exposing an operation.
"""
import re
from .hpm_otp import _u32

FAMILIES = {
    'HPM53': 'HPM5300', 'HPM62': 'HPM6200', 'HPM63': 'HPM6300',
    'HPM64': 'HPM6700/HPM6400', 'HPM67': 'HPM6700/HPM6400',
    'HPM68': 'HPM6800', 'HPM6E': 'HPM6E00', 'HPM6P': 'HPM6P00',
    'HPM5E': 'HPM5E00',
}


def family(part):
    if not isinstance(part, str) or not re.fullmatch(r'HPM[0-9A-Z]{4,16}', part):
        raise ValueError('Invalid HPM part number')
    name = FAMILIES.get(part[:5])
    if name is None:
        raise ValueError('No official OTP profile for this HPM family')
    return name


def validate_change(word, expected, desired):
    word = _u32(word, 'word')
    if word > 127:
        raise ValueError('HPM OTP word must be 0..127')
    expected, desired = _u32(expected, 'expected'), _u32(desired, 'desired')
    if desired & expected != expected:
        raise ValueError('OTP bits cannot be cleared (1 to 0)')
    if desired == expected:
        raise ValueError('No new OTP bits selected')
    return dict(word=word, expected=expected, desired=desired, delta=desired & ~expected)


def ordered_changes(changes):
    """Data first, security and access restrictions next, HARD_LOCK last."""
    return sorted(changes, key=lambda item: (2 if item['word'] == 0 else 1 if item['word'] in (1, 2) else 0, item['word']))

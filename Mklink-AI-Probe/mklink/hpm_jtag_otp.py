"""Read HPM SDK OTP register arrays over the connected JTAG debug transport."""
import re
import struct

from .hpm_otp import CHIP_ID

# HPM SDK 1.13.0 soc/*/*/hpm_soc_ip.h and ip/hpm_otp_regs.h.
# HPM64 and HPM67 share the HPM6700 peripheral map.
BASES = {
    'HPM51': 0xF00EC000, 'HPM53': 0xF3050000, 'HPM5E': 0xF3158000,
    'HPM62': 0xF40C8000, 'HPM63': 0xF40C8000, 'HPM64': 0xF40C8000,
    'HPM67': 0xF40C8000, 'HPM68': 0xF3050000, 'HPM6E': 0xF3158000,
    'HPM6P': 0xF3158000,
}


def otp_base(part):
    # Installed Packs can supply additional package variants of a known family.
    if re.fullmatch(r'HPM[A-Z0-9]{4,8}', part):
        return BASES.get(part[:5])
    return None


def check_target(device, part, read_word, *, check_read_lock=False):
    # The common TAP ID identifies the architecture, not the selected SKU.
    name = device.mcu_name.strip().upper()
    detected = re.search(r'\bHPM[0-9][A-Z0-9]{3,}\b', name)
    # A selected series template also accepts a detected member of that series.
    match_length = 5 if part.endswith('00') else 7
    matches = detected and detected[0][:match_length] == part[:match_length]
    if device.idcode != 0x1000563D or (name and not matches):
        raise ValueError(f'Connected target does not match the {part} description')
    base = otp_base(part)
    # Word 64 occupies the low two bits of FUSE_LOCK[4].
    if check_read_lock and read_word(base + 0x610) & 3 == 3:
        raise ValueError('OTP CHIP_ID is read-locked; no valid snapshot')
    chip_id = read_word(base + 0x500)
    if (chip_id in (0, 0xffffffff, 0x20150407)
            or (part[:7] == 'HPM5301' and chip_id != CHIP_ID)):
        raise ValueError(f'{part} CHIP_ID is unreadable or does not match; debug access may be protected')
    return chip_id


def _words(device, address, count):
    data = device.read_memory(address, count * 4)
    if len(data) != count * 4:
        raise RuntimeError(f'JTAG OTP read incomplete at 0x{address:08X}')
    return struct.unpack(f'<{count}I', data)


def _bank(device, address):
    # SDK otp_disable_access (3) blocks this bank's word. Do not include
    # it in a wider transfer. An unexpected bus failure invalidates the read.
    packed = _words(device, address + 0x200, 8)
    locks = [(packed[i // 16] >> (2 * (i % 16))) & 3 for i in range(128)]
    values = [None] * 128
    start = 0
    while start < len(values):
        if locks[start] == 3:
            start += 1
            continue
        end = start + 1
        while end < len(values) and locks[end] != 3:
            end += 1
        values[start:end] = _words(device, address + 4 * start, end - start)
        start = end
    if _words(device, address + 0x200, 8) != packed:
        raise ValueError('OTP access locks changed during the read; discard the snapshot')
    return values, locks


def read_words(device, part, chip_id):
    base = otp_base(part)
    fuse, fuse_lock = _bank(device, base + 0x400)
    shadow, shadow_lock = _bank(device, base)
    if fuse[64] != chip_id or _words(device, base + 0x500, 1)[0] != chip_id:
        raise ValueError('OTP CHIP_ID changed or is inaccessible; discard the snapshot')
    hard = fuse[0]
    rows = []
    for i in range(128):
        locked = bool((fuse_lock[i] | shadow_lock[i]) & 1)
        if not locked:
            locked = None if hard is None else bool(hard & (1 << (i // 4)))
        rows.append(dict(word=i, current=fuse[i], shadow=shadow[i], locked=locked,
                         fuse_lock=fuse_lock[i], shadow_lock=shadow_lock[i]))
    return dict(words=rows, hard_lock=hard, chip_id=chip_id, source='jtag_otp')

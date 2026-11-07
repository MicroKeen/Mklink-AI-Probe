"""Historical offline control echoes and error-bearing memory text replies."""

import pytest

from mklink.dump_memory import DumpMemoryParser
from mklink.memory_access import parse_read_ram_response
from mklink.superwatch import parse_timestamped_read_ram_response
from test_dump_memory_session import _b1_frame

COMMAND = "cmd.dump_memory(0x20018BE0, 4096, 0.000001)"  # Recorded historical echo
ECHO = (COMMAND + '\n\r\n>>> ').encode('ascii')
BLOCKS = b''.join(_b1_frame(123, bytes(2048), block_index=i, block_count=2, total_size=4096) for i in range(2))


@pytest.mark.parametrize('split', [1, 7, 43, 49, 50, 51, 4096, 65536])
def test_exact_startup_echo_is_accounted_separately_across_usb_chunks(split):
    assert len(ECHO) == 50
    parser = DumpMemoryParser([4096], startup_command=COMMAND)
    frames = []
    wire = ECHO + BLOCKS
    for offset in range(0, len(wire), split):
        frames.extend(parser.feed(wire[offset:offset+split]))
    assert len(frames) == 2
    assert parser.startup_control_bytes == 50
    assert parser.dropped_bytes == parser.dropped_frames == parser.crc_errors == 0
    assert not parser.pending_bytes


@pytest.mark.parametrize('prefix', [b'garbage', b'Error: DAP busy\r\n', ECHO.replace(b'4096', b'4095')])
def test_unknown_startup_text_still_counts_as_damage(prefix):
    parser = DumpMemoryParser([4096], startup_command=COMMAND)
    assert len(parser.feed(prefix + BLOCKS)) == 2
    assert parser.dropped_bytes == len(prefix)
    assert not parser.startup_control_bytes


def test_later_echo_and_corrupt_frame_are_never_ignored():
    parser = DumpMemoryParser([4096], startup_command=COMMAND)
    assert len(parser.feed(BLOCKS)) == 2
    assert len(parser.feed(ECHO + BLOCKS)) == 2
    assert parser.dropped_bytes == 50
    damaged = bytearray(BLOCKS); damaged[40] ^= 1
    parser.feed(damaged)
    assert parser.crc_errors == parser.dropped_frames == 1


@pytest.mark.parametrize('prefix', ['', '20000000 aa bb cc dd\r\n'])
@pytest.mark.parametrize('failure', ['Error: DAP busy; use multiplex or disconnect debugger',
    'SBA unavailable: debug disabled, unauthenticated or unsupported', 'RuntimeError: read failed'])
def test_read_errors_are_preserved_even_after_partial_hex_rows(prefix, failure):
    response = 'cmd.read_ram(0x20000000, 4)\r\n' + prefix + failure + '\r\n>>> '
    for parser in (parse_read_ram_response, parse_timestamped_read_ram_response):
        with pytest.raises(RuntimeError, match=failure): parser(response)

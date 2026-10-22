"""Real pyOCD loader/builder/eraser with a recording target, no USB required."""
from types import SimpleNamespace

import pytest

from mklink.cmsis_dap.backend import PyOcdBackend
from mklink.cmsis_dap.errors import FlashError
from mklink.cmsis_dap.images import ImageInspector
from mklink.cmsis_dap.pyocd_runtime import import_pyocd_attr


def rig(double_buffer=False):
    FlashRegion = import_pyocd_attr("pyocd.core.memory_map", "FlashRegion")
    MemoryMap = import_pyocd_attr("pyocd.core.memory_map", "MemoryMap")
    Flash = import_pyocd_attr("pyocd.flash.flash", "Flash")
    FlashBuilder = import_pyocd_attr("pyocd.flash.builder", "FlashBuilder")
    events = []
    memory = {}
    target = SimpleNamespace(selected_core=SimpleNamespace(node_name=None))
    delegate = SimpleNamespace(
        has_sequence_with_name=lambda name: True,
        run_sequence=lambda name: events.append((name,)),
    )
    target.debug_sequence_delegate = delegate
    session = SimpleNamespace(
        target=target, board=SimpleNamespace(target=target),
        options={'hide_programming_progress': True, 'smart_flash': False,
                 'fast_program': False, 'keep_unwritten': False, 'flash.timeout.program': 1},
        notify=lambda event, source: events.append((event.name,)),
        close=lambda: events.append(('close',)),
    )
    target.session = session
    target.read_memory_block8 = lambda addr, size: [memory.get(i, 0xFF) for i in range(addr, addr + size)]

    class RecordingFlash:
        Operation = Flash.Operation
        is_erase_all_supported = True
        is_double_buffering_supported = double_buffer
        TIMEOUT_ERROR = -1
        fail = None

        def __init__(self, region):
            self.region = region
            self.target = target
            self.buffers = {}

        def get_flash_builder(self):
            return FlashBuilder(self)

        def get_sector_info(self, addr):
            return SimpleNamespace(base_addr=addr // 256 * 256, size=256, erase_weight=1)

        def get_page_info(self, addr):
            return SimpleNamespace(base_addr=addr // 64 * 64, size=64, program_weight=1)

        def get_flash_info(self):
            return SimpleNamespace(erase_weight=10)

        def init(self, op):
            events.append(('init', op.name))

        def uninit(self):
            events.append(('uninit',))
            if self.fail == 'uninit':
                raise RuntimeError('uninit failed')

        def cleanup(self):
            self.uninit()
            events.append(('cleanup',))

        def erase_sector(self, addr):
            events.append(('erase', addr))
            if self.fail == 'erase':
                raise RuntimeError('erase failed')
            for i in range(addr, addr + 256):
                memory[i] = 0xFF

        def erase_all(self):
            raise AssertionError('chip erase must never be selected')

        def program_page(self, addr, data):
            events.append(('write', addr))
            if self.fail == 'program':
                raise RuntimeError('page failed')
            memory.update({addr + i: value for i, value in enumerate(data)})

        def load_page_buffer(self, number, address, data):
            self.buffers[number] = bytes(data)

        def start_program_page_with_buffer(self, number, address):
            self.program_page(address, self.buffers[number])

        def wait_for_completion(self, timeout):
            return 0

    regions = [FlashRegion(start=addr, length=0x1000, blocksize=256,
                           name=f'mklink_custom_flm_{addr}') for addr in (0x08000000, 0x08010000)]
    for region in regions:
        region.flash = RecordingFlash(region)
    target.memory_map = MemoryMap(*regions)
    backend = PyOcdBackend()
    backend._session = session
    return backend, events, memory, regions


def bin_image(tmp_path):
    path = tmp_path / 'image.bin'
    path.write_bytes(bytes(range(192)))
    return ImageInspector(tmp_path / 'snapshots').inspect(
        path, (), base_address=0x08000000, require_flash_coverage=False)


@pytest.mark.parametrize('double_buffer', [False, True])
@pytest.mark.parametrize('explicit_erase', [False, True])
def test_sector_erased_once_and_progress_follows_real_pages(tmp_path, double_buffer, explicit_erase):
    backend, events, memory, _ = rig(double_buffer)
    image = bin_image(tmp_path)
    if explicit_erase:
        backend.erase_sectors([image.start])
    backend.program(image, lambda p: events.append(('progress', p)))
    assert [e for e in events if e[0] == 'erase'] == [('erase', image.start)]
    assert bytes(memory[i] for i in range(image.start, image.end)) == bytes(range(192))
    progress = [e[1] for e in events if e[0] == 'progress']
    assert progress == sorted(progress)
    assert progress.count(1.0) == 1
    assert any(0 < p < 1 for p in progress)
    first_progress = next(i for i, e in enumerate(events) if e[0] == 'progress' and e[1] > 0)
    assert any(e[0] == 'write' for e in events[:first_progress])
    assert events[-2:] == [('FlashProgramDone',), ('progress', 1.0)]
    backend.verify(image)
    assert backend._erased_ranges == ()
    # Reusing the backend for a second program must erase again.
    backend.program(image)
    assert sum(e[0] == 'erase' for e in events) == 2


def hex_record(address, kind, data=b''):
    raw = bytes((len(data), address >> 8, address & 255, kind)) + data
    return ':' + (raw + bytes((-sum(raw) & 255,))).hex().upper()


def test_sparse_two_bank_hex_preserves_gaps_and_aggregates_progress(tmp_path):
    backend, events, memory, _ = rig(True)
    path = tmp_path / 'banks.hex'
    path.write_text('\n'.join([
        hex_record(0, 4, b'\x08\x00'), hex_record(3, 0, b'abc'),
        hex_record(0x202, 0, b'def'), hex_record(0, 4, b'\x08\x01'),
        hex_record(1, 0, b'123456'), hex_record(0, 1),
    ]), encoding='ascii')
    memory[0x08000100] = 0x42
    inspector = ImageInspector(tmp_path / 'snapshots')
    image = inspector.inspect(path, (), require_flash_coverage=False)
    addresses = [0x08000000, 0x08000200, 0x08010000]
    backend.erase_sectors(addresses)
    progress = []
    backend.program(image, progress.append)
    backend.verify(image)
    assert [e[1] for e in events if e[0] == 'erase'] == addresses
    assert memory[0x08000100] == 0x42
    assert progress == sorted(progress)
    assert 0.25 in progress and 0.5 in progress
    assert progress.count(1.0) == 1
    assert sum(e[0] == 'FlashEraseDone' for e in events) == 1
    assert sum(e[0] == 'FlashProgramDone' for e in events) == 1


@pytest.mark.parametrize('failure', ['program', 'uninit'])
def test_program_or_cleanup_failure_never_reports_complete(tmp_path, failure):
    backend, events, _, regions = rig()
    image = bin_image(tmp_path)
    backend.erase_sectors([image.start])
    regions[0].flash.fail = failure
    progress = []
    with pytest.raises(FlashError):
        backend.program(image, progress.append)
    assert 1.0 not in progress
    assert ('FlashProgramDone',) not in events
    assert backend._session is None
    assert backend._erased_ranges == ()


def test_failed_erase_does_not_leave_previous_erase_credit(tmp_path):
    backend, _, _, regions = rig()
    image = bin_image(tmp_path)
    backend.erase_sectors([image.start])
    regions[0].flash.fail = 'erase'
    with pytest.raises(FlashError):
        backend.erase_sectors([image.start])
    assert backend._erased_ranges == ()


def test_partial_erase_coverage_cannot_skip_required_erase(tmp_path):
    backend, events, _, _ = rig()
    image = bin_image(tmp_path)
    backend.erase_sectors([image.start + 256])
    backend.program(image)
    assert ('erase', image.start) in events


def test_reset_and_disconnect_invalidate_erase_credit():
    backend, _, _, _ = rig()
    backend.erase_sectors([0x08000000])
    # Even a rejected reset must not leave reusable erase state.
    with pytest.raises(ValueError):
        backend.reset_run('invalid')
    assert backend._erased_ranges == ()
    backend.erase_sectors([0x08000000])
    backend.disconnect()
    assert backend._erased_ranges == ()


def test_whole_padded_page_must_be_erased():
    backend, _, _, regions = rig()
    regions[0].flash.get_page_info = lambda addr: SimpleNamespace(base_addr=0x08000000, size=512)
    assert not backend._image_pages_erased(backend._session.target,
        ((0x08000000, 0x08000100),), ((0x08000000, 0x08000010),))

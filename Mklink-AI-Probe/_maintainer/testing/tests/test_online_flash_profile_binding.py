"""Driver-level profile admission prior to online Flash reads, erases or writes."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink.cmsis_dap.backend import PyOcdBackend
from mklink.cmsis_dap.errors import FlashError, FlashErrorCode
from mklink.cmsis_dap.pyocd_runtime import import_pyocd_attr
from mklink.cmsis_dap.target_attach import ProfileAttachDelegate


class InitSequence:
    def __init__(self):
        self.after_dp_init = []
        self.before_create_flash = []

    def insert_after(self, task, item):
        assert task == 'dp_init'
        self.after_dp_init.append(item[1])

    def insert_before(self, task, item):
        assert task in ('create_flash', 'halt_on_connect')
        self.before_create_flash.append(item[1])


class FlashSession:
    """Run the production delegates at session.open, with a synthetic selected core."""
    def __init__(self, selected_ap, *, run_profile=True):
        self.events = []
        self.close = Mock()
        self.delegate = SimpleNamespace(will_init_target=lambda target, sequence: self.events.append('base-hook'))
        self.run_profile = run_profile
        core = None if selected_ap is None else SimpleNamespace(
            ap=SimpleNamespace(address=SimpleNamespace(apsel=selected_ap)),
            get_state=Mock(return_value=SimpleNamespace(name='RUNNING')),
            core_registers=SimpleNamespace(by_name={'xpsr': object()}))
        self.target = SimpleNamespace(session=self, dp=object(), selected_core=core,
                                      read_memory_block8=Mock(return_value=[0x1a, 0x2b]))

    def factory(self, probe, options):
        self.options = options
        self.events.append('factory')
        return self

    def open(self):
        self.events.append('open')
        sequence = InitSequence()
        self.delegate.will_init_target(self.target, sequence)
        if self.run_profile:
            for callback in sequence.after_dp_init:
                callback()
        for callback in sequence.before_create_flash:
            callback()


def install_profile_result(monkeypatch, session, *, error=None):
    def bind(delegate, dp):
        assert dp is session.target.dp
        assert delegate.profile.name == 'S32K314' and delegate.profile.mem_ap == 4
        session.events.append('profile')
        if error is not None:
            raise error
        delegate.bound = True
    monkeypatch.setattr(ProfileAttachDelegate, '_bind', bind)


def assert_no_programming_session(driver):
    for operation in (driver.erase_chip, lambda: driver.program(object())):
        with pytest.raises(FlashError) as blocked:
            operation()
        assert blocked.value.code is FlashErrorCode.CONNECT_FAIL


@pytest.mark.parametrize('connect_mode,with_pack,model', [
    ('attach', False, 'S32K314'), ('halt', True, 'S32K314'),
    ('attach', True, ' S32k314Hms '), ('halt', True, 'NXPS32K314HMS'),
])
def test_profile_composes_before_open_and_requires_selected_ap4(monkeypatch, tmp_path, connect_mode, with_pack, model):
    session = FlashSession(4)
    install_profile_result(monkeypatch, session)
    pack_options = {}
    if with_pack:
        pack = tmp_path / 'chip.pack'
        pack.write_bytes(b'fixture')
        pack_options['pack'] = str(pack)
        monkeypatch.setattr('mklink.cmsis_dap.backend._prepare_pack_flm_regions',
                            lambda target, regions: session.events.append('pack'))
    driver = PyOcdBackend(session_factory=session.factory)
    driver.connect(object(), model, 1_000_000, connect_mode=connect_mode, **pack_options)
    try:
        assert session.events == ['factory', 'open', 'base-hook', 'profile'] + (['pack'] if with_pack else [])
        assert session.options['target_override'] == ('S32K314' if with_pack else 'cortex_m')
        assert session.options['connect_mode'] == connect_mode
        assert session.options['auto_unlock'] is False and session.options['resume_on_disconnect'] is False
        assert driver.read_memory(0x20000000, 2) == b'\x1a\x2b'
        session.target.read_memory_block8.assert_called_once_with(0x20000000, 2)
    finally:
        driver.disconnect()
    session.close.assert_called_once_with()


@pytest.mark.parametrize('selected_ap,run_profile', [(0, True), (None, True), (4, False)])
def test_unconfirmed_core_binding_closes_and_blocks_erase_and_program(monkeypatch, selected_ap, run_profile):
    session = FlashSession(selected_ap, run_profile=run_profile)
    install_profile_result(monkeypatch, session)
    driver = PyOcdBackend(session_factory=session.factory)
    with pytest.raises(FlashError) as caught:
        driver.connect(object(), 'S32K314', 1_000_000, connect_mode='attach')
    assert caught.value.code is FlashErrorCode.CONNECT_FAIL
    assert caught.value.details == {'profile': 'S32K314', 'mem_ap': 4,
                                   'reason': 'bind_failed', 'selected_ap': selected_ap}
    assert session.events.count('open') == 1
    session.close.assert_called_once_with()
    assert_no_programming_session(driver)


def test_delegate_failure_keeps_step_diagnostic_and_never_enters_programming(monkeypatch):
    session = FlashSession(4)
    diagnostic = {'profile': 'S32K314', 'mem_ap': 4, 'step': 7,
                  'reason': 'memory_check', 'actual': 0x12345678}
    error = FlashError(FlashErrorCode.CONNECT_FAIL, 'fixture model check failed', diagnostic)
    install_profile_result(monkeypatch, session, error=error)
    driver = PyOcdBackend(session_factory=session.factory)
    with pytest.raises(FlashError) as caught:
        driver.connect(object(), 's32k314', 1_000_000, connect_mode='attach')
    assert caught.value.code is FlashErrorCode.CONNECT_FAIL
    assert caught.value.details == diagnostic
    assert session.events == ['factory', 'open', 'base-hook', 'profile']
    session.close.assert_called_once_with()
    assert_no_programming_session(driver)


def test_ordinary_target_and_rejected_profile_retarget_do_not_share_a_programming_session(monkeypatch):
    session = FlashSession(0)
    install_profile_result(monkeypatch, session)
    driver = PyOcdBackend(session_factory=session.factory)
    driver.connect(object(), 'STM32F103RC', 1_000_000, connect_mode='under-reset')
    assert session.events == ['factory', 'open', 'base-hook']
    assert session.options['target_override'] == 'STM32F103RC'
    assert session.options['connect_mode'] == 'under-reset'
    assert 'resume_on_disconnect' not in session.options
    resolve_new_probe = Mock(side_effect=AssertionError('Probe resolution before mode admission'))
    monkeypatch.setattr(driver, '_resolve_probe', resolve_new_probe)
    with pytest.raises(FlashError) as caught:
        driver.connect(object(), 'S32K314', 1_000_000, connect_mode='under-reset')
    assert caught.value.code is FlashErrorCode.CONNECT_FAIL
    assert caught.value.details['connect_mode'] == 'under-reset'
    resolve_new_probe.assert_not_called()
    session.close.assert_called_once_with()
    assert_no_programming_session(driver)


BASE = 0x602000


@pytest.fixture
def online_profile(monkeypatch):
    session = FlashSession(4)
    target = session.target
    core = target.selected_core
    core.node_name = 'CM7'
    core.has_cache = True
    state = import_pyocd_attr('pyocd.core.target', 'Target').State
    core.get_state = Mock(return_value=state.HALTED)
    core.read_core_registers_raw = Mock(return_value=[0x61000000, 4])
    core.primask = 1
    core.read_core_register = Mock(side_effect=lambda name: getattr(core, name))
    core.write_core_register = Mock(side_effect=lambda name, value: setattr(core, name, value))
    core.halt = Mock()
    core.resume = Mock(side_effect=AssertionError('Unexpected application resume'))
    core.flush = Mock()
    core.invalidate_instruction_cache = Mock()
    target.reset_and_halt = Mock(side_effect=AssertionError('Unexpected reset of profile AP grants'))
    target.halt = core.halt
    install_profile_result(monkeypatch, session)
    driver = PyOcdBackend(session_factory=session.factory, eraser_factory=Mock(), programmer_factory=Mock())
    driver.connect(object(), 'S32K314', 1_000_000, connect_mode='attach')
    FlashRegion = import_pyocd_attr('pyocd.core.memory_map', 'FlashRegion')
    MemoryMap = import_pyocd_attr('pyocd.core.memory_map', 'MemoryMap')
    regions = []
    # An overlapping region for another core comes first in the map.
    for pname, address in [('CM0', BASE), ('CM7', BASE), ('CM7', BASE+0x100), ('CM7', BASE+0x200)]:
        region = FlashRegion(name=f'{pname}_{address:x}', start=address, length=0x100,
                             sector_size=0x100, page_size=0x20, pname=pname)
        region.flash = SimpleNamespace(
            get_sector_info=lambda addr: SimpleNamespace(base_addr=addr & ~0xff, size=0x100))
        regions.append(region)
    target.memory_map = MemoryMap(*regions)
    # MPU, permissions and D/I-cache decoding are covered with real Pack layouts
    # in test_flash_workspace. Inspect the actual Flash instances routed here.
    checker = Mock()
    monkeypatch.setattr('mklink.cmsis_dap.backend.check_flash_workspace', checker)
    try:
        yield driver, target, regions[1:], checker
    finally:
        target.reset_and_halt.assert_not_called()
        driver.disconnect()


def test_profile_matches_only_selected_algorithms_for_sector_and_chip_erase(online_profile):
    driver, target, regions, checker = online_profile
    driver.erase_sectors([BASE, BASE])
    checker.assert_called_once_with(target, regions[0].flash, icache_sync=False)
    driver._eraser_factory.return_value.erase.assert_called_once_with([BASE])
    checker.reset_mock()
    driver.erase_chip()
    assert [call.args[1] for call in checker.call_args_list] == [region.flash for region in regions]


def test_profile_rejects_independently_halted_handler_with_evidence(online_profile):
    driver, target, _, checker = online_profile
    core = target.selected_core
    core.read_core_registers_raw.return_value = [0x61000070, 0]
    with pytest.raises(FlashError) as caught:
        driver.erase_sectors([BASE])
    assert caught.value.details['ipsr'] == 112 and caught.value.details['control'] == 0
    assert caught.value.details['mem_ap'] == 4 and caught.value.details['profile'] == 'S32K314'
    assert 'Thread' in caught.value.message and 'MSP' in caught.value.message
    core.resume.assert_not_called()
    checker.assert_not_called()
    driver._eraser_factory.assert_not_called()


def test_profile_stops_before_flash_if_actual_ap_changed(online_profile):
    driver, target, _, checker = online_profile
    target.selected_core.ap.address.apsel = 7
    with pytest.raises(FlashError) as caught:
        driver.erase_sectors([BASE])
    assert caught.value.details['selected_ap'] == 7
    target.selected_core.read_core_registers_raw.assert_not_called()
    checker.assert_not_called()
    driver._eraser_factory.assert_not_called()


def test_cross_region_program_requires_all_workspaces_before_first_write(online_profile, tmp_path):
    driver, target, regions, checker = online_profile
    path = tmp_path / 'cross.bin'
    path.write_bytes(bytes(0x30))
    image = SimpleNamespace(file_path=path, format='bin', base_address=BASE+0xf0)
    diagnostic = {'reason': 'mpu_xn', 'address': 0x20400000, 'workspace': 'code', 'region': 3}
    checker.side_effect = [None, FlashError(FlashErrorCode.CONNECT_FAIL, 'execute-never', diagnostic)]
    with pytest.raises(FlashError) as caught:
        driver.program(image)
    assert caught.value.details == diagnostic
    assert [call.args for call in checker.call_args_list] == [(target, region.flash) for region in regions[:2]]
    driver._programmer_factory.assert_not_called()


def test_profile_verify_admits_each_flm_and_keeps_memory_only_verify_readonly(online_profile, monkeypatch):
    driver, target, regions, checker = online_profile
    for region in regions[:2]:
        region.flash.verify_data = Mock(side_effect=lambda address, data: address + len(data))
    target.read_memory_block8 = Mock(return_value=[0])
    image = SimpleNamespace(payload_size=0x102)
    monkeypatch.setattr(driver, '_iter_image_chunks', lambda _: [(BASE+0xff, bytes(0x102))])
    driver.verify(image)
    assert [call.args[1] for call in checker.call_args_list] == [region.flash for region in regions[:2]]
    target.read_memory_block8.assert_called_once_with(BASE+0x200, 1)
    checker.reset_mock()
    target.selected_core.read_core_registers_raw.reset_mock()
    monkeypatch.setattr(driver, '_iter_image_chunks', lambda _: [(BASE+0x200, bytes(1))])
    driver.verify(image)
    checker.assert_not_called()
    target.selected_core.read_core_registers_raw.assert_not_called()


@pytest.mark.parametrize('stage', ['erase', 'program'])
def test_uncertain_flash_command_is_issued_once(online_profile, tmp_path, stage):
    driver, _, _, _ = online_profile
    if stage == 'erase':
        command = driver._eraser_factory.return_value.erase
        operation = lambda: driver.erase_sectors([BASE])
    else:
        path = tmp_path / 'payload.bin'
        path.write_bytes(b'\x01')
        image = SimpleNamespace(file_path=path, format='bin', base_address=BASE)
        command = driver._programmer_factory.return_value.program
        operation = lambda: driver.program(image)
    command.side_effect = OSError('No ACK after dispatch')
    with pytest.raises(FlashError):
        operation()
    assert command.call_count == 1
    assert driver._erased_ranges == ()


@pytest.mark.parametrize('sync_failure', [False, True])
def test_real_flash_upload_sync_and_launch_order(online_profile, sync_failure):
    driver, target, regions, checker = online_profile
    Flash = import_pyocd_attr('pyocd.flash.flash', 'Flash')
    load = 0x20400000
    algo = dict(load_address=load, instructions=[0]*8, static_base=load+24,
                pc_init=load+1, pc_erase_sector=load+3, pc_program_page=load+5, pc_unInit=load+7,
                begin_stack=load+0x200, page_buffers=[load+0x400], analyzer_supported=False)
    flash = Flash(target, algo)
    flash.region = regions[0]
    regions[0].flash = flash
    events = []
    target.write_memory_block32 = Mock(side_effect=lambda *_: events.append('upload'))
    core = target.selected_core
    core.primask = 0

    def observe_launch(pc, *_):
        assert core.primask == 1
        events.append(('launch', pc))
    original_launch = Mock(side_effect=observe_launch)
    flash._call_function = original_launch
    flash.wait_for_completion = Mock(return_value=0)
    core.flush.side_effect = lambda: events.append('flush')

    def invalidate():
        events.append('invalidate')
        if sync_failure:
            raise OSError('No ACK on cache maintenance')
    core.invalidate_instruction_cache.side_effect = invalidate

    def run_selected_flm(_addresses):
        flash.init(flash.Operation.ERASE)
        flash.erase_sector(BASE)
        flash.cleanup()
    driver._eraser_factory.return_value.erase.side_effect = run_selected_flm
    if sync_failure:
        with pytest.raises(FlashError) as caught:
            driver.erase_sectors([BASE])
        assert caught.value.details['reason'] == 'instruction_cache_sync'
        assert events == ['flush', 'upload', 'flush', 'invalidate', 'flush']
        original_launch.assert_not_called()
    else:
        driver.erase_sectors([BASE])
        driver.erase_sectors([BASE])
        assert events == ['flush', 'upload', 'flush', 'invalidate', 'flush',
                          ('launch', load+1), ('launch', load+3), ('launch', load+7), 'flush'] * 2
    assert core.primask == 0
    assert all(call.kwargs == {'icache_sync': True} for call in checker.call_args_list)
    driver.disconnect()
    assert flash._call_function is original_launch and 'prepare_target' not in vars(flash)


@pytest.mark.parametrize('stage', ['erase', 'program', 'verify'])
def test_running_application_interrupt_mask_restored_only_after_flm_returns(online_profile, tmp_path, stage):
    driver, target, regions, _ = online_profile
    core = target.selected_core
    core.primask = 0
    masks = []

    def run_flm(*args, **kwargs):
        masks.append(core.primask)
        if stage == 'verify':
            return args[0] + len(args[1])
    if stage == 'erase':
        driver._eraser_factory.return_value.erase.side_effect = run_flm
        driver.erase_sectors([BASE])
    elif stage == 'program':
        path = tmp_path / 'single.bin'
        path.write_bytes(b'p')
        driver._programmer_factory.return_value.program.side_effect = run_flm
        driver.program(SimpleNamespace(file_path=path, format='bin', base_address=BASE))
    else:
        driver._iter_image_chunks = lambda _: [(BASE, b'v'), (BASE+0x100, b'v')]
        regions[0].flash.verify_data = regions[1].flash.verify_data = run_flm
        driver.verify(SimpleNamespace(payload_size=2))
    assert masks and all(mask == 1 for mask in masks)
    assert core.primask == 0
    assert [call.args for call in core.write_core_register.call_args_list] == [('primask', 1), ('primask', 0)]

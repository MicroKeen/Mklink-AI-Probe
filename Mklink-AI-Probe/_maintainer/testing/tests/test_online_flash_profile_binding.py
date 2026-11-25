"""Driver-level profile admission prior to online Flash reads, erases or writes."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink.cmsis_dap.backend import PyOcdBackend
from mklink.cmsis_dap.errors import FlashError, FlashErrorCode
from mklink.cmsis_dap.target_attach import ProfileAttachDelegate


class InitSequence:
    def __init__(self):
        self.after_dp_init = []
        self.before_create_flash = []

    def insert_after(self, task, item):
        assert task == 'dp_init'
        self.after_dp_init.append(item[1])

    def insert_before(self, task, item):
        assert task == 'create_flash'
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


@pytest.mark.parametrize('connect_mode,with_pack', [('attach', False), ('halt', True)])
def test_profile_composes_before_open_and_requires_selected_ap4(monkeypatch, tmp_path, connect_mode, with_pack):
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
    driver.connect(object(), 'S32K314', 1_000_000, connect_mode=connect_mode, **pack_options)
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

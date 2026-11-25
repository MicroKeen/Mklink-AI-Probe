"""Exercise pyOCD 0.44's real init sequence at a simulated ADIv5 port."""
from pathlib import Path
from unittest.mock import Mock

import pytest
from pyocd.core.session import Session
from pyocd.core.soc_target import SoCTarget
from pyocd.core.target_delegate import DelegateHavingMixIn
from pyocd.coresight.ap import MEM_AP_CSW, MEM_AP_DRW, MEM_AP_TAR
from pyocd.coresight.coresight_target import CoreSightTarget
from pyocd.coresight.dap import ADIVersion, CDBGPWRUPACK, CSYSPWRUPACK, DP_CTRL_STAT
from pyocd.utility.sequencer import CallSequence

from mklink.cmsis_dap.backend import PyOcdBackend
from mklink.cmsis_dap.errors import FlashError, FlashErrorCode
from mklink.cmsis_dap.target_attach import ProfileAttachDelegate
from mklink.profiles import MuxAttachProfile, MuxAttachStep, resolve_attach_profile

MEM_AP = 4 << 24
ENABLE = (7 << 24) | 0x80


@pytest.mark.parametrize('target', ['S32K314', 'cortex_m'])
def test_real_session_project_file_discovery(monkeypatch, tmp_path, target):
    workspace = tmp_path / 'workspace'
    external = tmp_path / 'external'
    for directory in (workspace, external):
        directory.mkdir()
        (directory / 'pyocd_user.py').write_text(
            "from pathlib import Path\nPath('script-ran').touch()\n", encoding='utf-8')
        (directory / 'pyocd.yaml').write_text("persist: true\n", encoding='utf-8')
    monkeypatch.chdir(workspace)
    monkeypatch.setenv('PYOCD_PROJECT_DIR', str(external))

    def stop_before_probe_open(session):
        raise FlashError(FlashErrorCode.CONNECT_FAIL, "session constructed")

    monkeypatch.setattr(Session, 'open', stop_before_probe_open)
    probe = Mock(spec=['session', 'create_associated_board', 'unique_id'])
    with pytest.raises(FlashError, match='session constructed'):
        PyOcdBackend().connect(probe, target, 1_000_000, connect_mode='attach')

    uses_project = target == 'cortex_m'
    expected_cwd = external if uses_project else workspace
    assert Path(probe.session.project_dir) == Path.cwd() == expected_cwd
    assert probe.session.options.is_set('persist') is uses_project
    assert (external / 'script-ran').exists() is uses_project
    assert not (workspace / 'script-ran').exists()


class FakeDP:
    def __init__(self):
        self.adi_version = ADIVersion.ADIv5
        self.power = CDBGPWRUPACK | CSYSPWRUPACK
        self.regs = {MEM_AP | 0xfc: 0x84770001, 6 << 24 | 0xfc: 0x001c0030,
                     7 << 24 | 0xfc: 0x001c0040, 7 << 24: 0x40000000,
                     6 << 24: 0, ENABLE: 0x80000100, MEM_AP | MEM_AP_CSW: 0xa0000011}
        self.memory = {0xe000ed00: 0x410fc271, 0x40290004: 0x2d3a1234}
        self.valid_aps = None
        self.writes = []
        self.flushes = 0

    def read_dp(self, address):
        assert address == DP_CTRL_STAT
        return self.power

    def read_ap(self, address):
        if address == MEM_AP | MEM_AP_DRW:
            return self.memory[self.regs[MEM_AP | MEM_AP_TAR]]
        return self.regs[address]

    def write_ap(self, address, value):
        self.writes.append((address, value))
        self.regs[address] = value

    def flush(self):
        self.flushes += 1


class SequenceTarget(DelegateHavingMixIn):
    """Use the production pyOCD delegate and Pack unlock dispatch, without USB."""
    init = SoCTarget.init
    unlock_device = CoreSightTarget.unlock_device

    def __init__(self, profile=None):
        self.dp = FakeDP()
        self.events = []
        self.next_delegate = Mock(spec=['will_init_target', 'did_init_target', 'will_reset', 'unlock_device'])
        self.delegate = ProfileAttachDelegate(profile or resolve_attach_profile('s32k314'), self.next_delegate)

    def create_init_sequence(self):
        return CallSequence(('dp_init', lambda: self.events.append('dp')),
                            ('unlock_device', self.unlock_device),
                            ('discovery', lambda: self.events.append(('discover', self.dp.valid_aps))))

    def call_pre_discovery_debug_sequence(self, name):
        pytest.fail(f'Unexpected Pack debug sequence {name}')


@pytest.mark.parametrize('preconfigured', (False, True))
def test_profile_binds_before_discovery_and_replaces_pack_unlock(preconfigured):
    target = SequenceTarget()
    dp = target.dp
    if preconfigured:
        dp.regs[ENABLE] |= 0x300000f0
    target.init()
    assert target.delegate.bound
    assert target.events == ['dp', ('discover', [4])]
    assert [(addr, val) for addr, val in dp.writes if addr == ENABLE] == (
        [] if preconfigured else [(ENABLE, 0xb00001f0)])
    assert dp.flushes == int(not preconfigured)
    assert [(addr, val) for addr, val in dp.writes if addr >> 24 == 4] == [
        (MEM_AP | MEM_AP_CSW, 0xa3000002), (MEM_AP | MEM_AP_TAR, 0xe000ed00),
        (MEM_AP | MEM_AP_CSW, 0xa3000002), (MEM_AP | MEM_AP_TAR, 0x40290004)]
    target.next_delegate.will_init_target.assert_called_once()
    target.next_delegate.did_init_target.assert_called_once_with(target=target)
    target.next_delegate.unlock_device.assert_not_called()
    assert target.delegate.will_reset is target.next_delegate.will_reset


@pytest.mark.parametrize('case,step,reason,actual', [
    ('adiv6', None, 'adi_version', None),
    ('power', None, 'dp_power', 0xffffffff),
    ('missing_power_ack', None, 'dp_power', CSYSPWRUPACK),
    ('idr', 2, 'ap_check', 0xdeadbeef),
    ('auth', 3, 'ap_check', 0),
    ('functional_reset', 4, 'ap_check', 4),
    ('write_ack_lost', 5, 'ap_write', 0x80000100),
    ('readback', 5, 'ap_readback', 0x80000100),
    ('wrong_part', 7, 'memory_check', 0xbeef1234),
    ('unreadable', 7, 'memory_read', None),
])
def test_failed_attach_never_publishes_or_replays(case, step, reason, actual):
    target = SequenceTarget()
    dp = target.dp
    if case == 'adiv6':
        dp.adi_version = ADIVersion.ADIv6
    elif case in ('power', 'missing_power_ack'):
        dp.power = actual
    elif case == 'idr':
        dp.regs[7 << 24 | 0xfc] = actual
    elif case == 'auth':
        dp.regs[7 << 24] = actual
    elif case == 'functional_reset':
        dp.regs[6 << 24] = actual
    elif case == 'write_ack_lost':
        dp.flush = Mock(side_effect=OSError('lost transfer acknowledgement'))
    elif case == 'readback':
        dp.flush = lambda: dp.regs.update({ENABLE: actual})
    elif case == 'wrong_part':
        dp.memory[0x40290004] = actual
    else:
        dp.memory.pop(0x40290004)
    with pytest.raises(FlashError) as failed:
        target.init()
    assert failed.value.code == FlashErrorCode.CONNECT_FAIL
    assert failed.value.details == dict(profile='S32K314', mem_ap=4, step=step, reason=reason, actual=actual)
    assert not target.delegate.bound and dp.valid_aps is None and target.events == ['dp']
    assert len([addr for addr, _ in dp.writes if addr == ENABLE]) == int(step is not None and step >= 5)
    writes = list(dp.writes)
    with pytest.raises(FlashError, match='already attempted'):
        target.init()
    assert writes == dp.writes
    with pytest.raises(FlashError, match='before profile verification'):
        target.unlock_device()
    target.next_delegate.unlock_device.assert_not_called()


def test_profile_uses_compiled_ap_and_preserves_general_mask_semantics():
    profile = MuxAttachProfile('other', 11, (
        MuxAttachStep(1, 9, 0, 0x8, 0x8),
        MuxAttachStep(3, 11, 0x1000, 0xffff0000, 0xfedc0000),
    ))
    target = SequenceTarget(profile)
    dp = target.dp
    regs = {9 << 24: 0xffffffff, (11 << 24) | MEM_AP_CSW: 2, (11 << 24) | MEM_AP_DRW: 0xfedc1234}
    dp.read_ap = regs.__getitem__
    target.init()
    assert dp.valid_aps == [11]
    assert dp.writes == [((11 << 24) | MEM_AP_CSW, 0x03000002), ((11 << 24) | MEM_AP_TAR, 0x1000)]

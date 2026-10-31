"""A SWD setting echo must not certify an unsupported HPM JTAG frequency."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mklink._types import DeviceState
from mklink.debug_speed import apply_bridge_profile, validate_hpm_clock_hz
from mklink.flash import MKLinkFlash, FlashError


def bridge(identity, response):
    return SimpleNamespace(idcode=identity, state=DeviceState.READY,
        _ctx=SimpleNamespace(swd_clock_hz=10_000_000), send_command=Mock(return_value=response))


@pytest.mark.parametrize('hz', [1_000_000, 8_000_000, 12_000_000, True, '10000000', 10_000_000.0])
def test_hpm_accepts_only_named_integer_profiles(hz):
    with pytest.raises(ValueError, match='HPM JTAG'):
        validate_hpm_clock_hz(hz)


@pytest.mark.parametrize('hz', [4_000_000, 10_000_000, 20_000_000, 30_000_000])
def test_hpm_named_profiles(hz):
    assert validate_hpm_clock_hz(hz) == hz


def test_known_hpm_rejects_eight_mhz_before_changing_device():
    b = bridge(0x1000563D, 'set clock 8000000\nJTAG profile=0')
    with pytest.raises(FlashError, match='HPM JTAG'):
        MKLinkFlash(b).set_swd_clock(8_000_000)
    b.send_command.assert_not_called()
    assert b._ctx.swd_clock_hz == 10_000_000


@pytest.mark.parametrize('response', ['set clock 8000000\nJTAG profile=0',
                                     'set clock 8000000\nJTAG profile=10000000',
                                     'set clock 8000000\n-1'])
def test_deferred_identity_cannot_hide_jtag_profile_rejection(response):
    b = bridge(0, response)
    with pytest.raises(FlashError, match='debug clock/profile'):
        MKLinkFlash(b).set_swd_clock(8_000_000)
    assert b._ctx.swd_clock_hz == 0


def test_swd_keeps_arbitrary_eight_mhz_setting():
    b = bridge(0x1BA01477, 'set clock 8000000')
    MKLinkFlash(b).set_swd_clock(8_000_000)
    assert b._ctx.swd_clock_hz == 8_000_000


@pytest.mark.parametrize('fallback', ['set clock 4000000\nJTAG profile=0',
                                     'set clock 4000000',
                                     'set clock 4000000\nJTAG profile=4000000\n-1'])
def test_jtag_fallback_requires_matching_profile(fallback):
    b = bridge(0x1000563D, '')
    b.send_command.side_effect = ['set clock 30000000\nJTAG profile=0', fallback]
    with pytest.raises(ValueError, match='fallback clock'):
        apply_bridge_profile(b, 'ultra')
    assert b._ctx.swd_clock_hz == 0
    assert b.send_command.call_args.args == ('cmd.set_swd_clock(4000000)',)


def test_online_hpm_rejects_invalid_clock_before_opening_probe():
    from mklink.cmsis_dap.backend import HpmRomBackend
    factory, resolver = Mock(), Mock()
    backend = HpmRomBackend(device_factory=factory, port_resolver=resolver)
    with pytest.raises(ValueError, match='HPM JTAG'):
        backend.connect('chosen', 'HPM5301', 8_000_000, board='hpm5301evklite')
    factory.assert_not_called()
    resolver.assert_not_called()


def test_offline_hpm_rejects_eight_mhz_before_generating_script():
    from mklink.offline_download import OfflineDownloadError, parse_offline_config
    from test_hpm_jtag_offline_cycles import config
    body = config()
    body['swd_clock_hz'] = 8_000_000
    with pytest.raises(OfflineDownloadError, match='HPM JTAG'):
        parse_offline_config(body)


@pytest.mark.parametrize('split', [False, True])
def test_hpm_default_flash_clock_uses_supported_profile(tmp_path, monkeypatch, split):
    from mklink.device import Device
    if split:
        from mklink.project_config import save_config
        save_config(str(tmp_path), {'clock_interface':'SWD', 'swd_clock':'2000000', 'jtag_clock':'20000000'})
    image = tmp_path / 'app.bin'
    image.write_bytes(b'app')
    d = Device(project_root=str(tmp_path))
    d._connected = True
    d._bridge = SimpleNamespace(idcode=0x1000563D, current_mcu='HPMicro HPM5301')
    d._flash = Mock()
    d._flash.burn_hpm_bin.return_value = {'success': True}
    result = d.flash(str(image), target_part='HPM5301', board='hpm5301evklite',
                     base_address=0x80000400, verify=False)
    assert result['algorithm_source'] == 'hpm-rom-api'
    d._flash.set_swd_clock.assert_called_once_with(20_000_000 if split else 10_000_000)
    d._flash.load_flm.assert_not_called()


def test_explicit_hpm_clock_rejected_before_any_programming(tmp_path):
    from mklink.device import Device, DeviceError
    image = tmp_path / 'app.bin'
    image.write_bytes(b'app')
    d = Device(project_root=str(tmp_path))
    d._connected = True
    d._bridge = SimpleNamespace(idcode=0, current_mcu='')
    d._flash = Mock()
    with pytest.raises(DeviceError, match='HPM JTAG'):
        d.flash(str(image), target_part='HPM5301', board='hpm5301evklite',
                base_address=0x80000400, swd_clock=8_000_000)
    assert d._flash.mock_calls == []

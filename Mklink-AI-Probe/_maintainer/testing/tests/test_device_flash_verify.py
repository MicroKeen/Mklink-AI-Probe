from pathlib import Path

import pytest
from intelhex import IntelHex

from mklink.device import Device, DeviceError
from mklink.project_config import save_config, save_project_info


class _FlashStub:
    def __init__(self):
        self.loaded = []
        self.burned = []

    def set_swd_clock(self, _clock: int) -> None:
        pass

    def load_flm(self, path: str, flash_base: str, ram_base: str) -> bool:
        self.loaded.append((path, flash_base, ram_base))
        return True

    def burn_hex(self, _firmware: str, progress_callback=None) -> dict:
        self.burned.append(tuple(IntelHex(_firmware).segments()))
        return {"success": True}

    def burn_bin(self, _firmware: str, _address: str, progress_callback=None) -> dict:
        self.burned.append(("bin", Path(_firmware).name, _address))
        return {"success": True}

    def burn_hpm_bin(
        self,
        firmware: str,
        *,
        addr: str,
        board=None,
        flash_cfg=None,
        progress_callback=None,
    ) -> dict:
        self.burned.append(("hpm", Path(firmware).name, addr, board, tuple(flash_cfg or ())))
        return {"success": True}


class _BridgeStub:
    def __init__(self):
        self.calls = []

    def send_command(self, command: str, timeout: float):
        self.calls.append((command, timeout))
        return self.reply


def _device(read_memory):
    device = Device(mcu="custom", project_root="")
    device._connected = True
    device._bridge = object()
    device._flash = _FlashStub()
    device._get_mcu_profile = lambda: None
    device.read_memory = read_memory
    device.reset = lambda: None
    return device


def _write_hex(path: Path, data: bytes, address: int = 0x08000000) -> None:
    image = IntelHex()
    image.puts(address, data)
    image.write_hex_file(str(path))


def test_device_flash_verify_reads_back_hex_before_reset(tmp_path: Path):
    firmware = tmp_path / "firmware.hex"
    expected = bytes(range(32))
    _write_hex(firmware, expected)
    calls = []

    def read_memory(address: int, size: int) -> bytes:
        calls.append(("read", address, size))
        return expected[address - 0x08000000:address - 0x08000000 + size]

    device = _device(read_memory)
    device.reset = lambda: calls.append(("reset",))

    result = device.flash(str(firmware), verify=True, reset_after=True)

    assert result["verified"] is True
    assert calls[0][0] == "read"
    assert calls[-1] == ("reset",)


def test_normal_swd_flash_never_probes_sleep_or_writes_core_controls(tmp_path):
    from types import SimpleNamespace
    from mklink.capture_clock import V3_CLOCKS

    firmware = tmp_path / 'normal.hex'
    _write_hex(firmware, b'data')
    device = _device(lambda addr, n: b'data')
    device._bridge = SimpleNamespace(
        _ctx=SimpleNamespace(clock_interface='SWD', swd_clock_hz=10_000_000),
        _firmware_capabilities={'MUX_TARGET=1', 'SWD_CLOCK_ACK=1',
                                'SWD_CLOCKS=' + ','.join(map(str, V3_CLOCKS))},
        enable_multiplex=lambda: pytest.fail('Normal flash must not negotiate sleep access'),
    )
    assert device.flash(str(firmware), reset_after=False)['verified']


def test_normal_swd_reset_only_sends_one_checked_reset():
    from types import SimpleNamespace
    from mklink.capture_clock import V3_CLOCKS

    bridge = _BridgeStub()
    bridge._ctx = SimpleNamespace(clock_interface='SWD', swd_clock_hz=10_000_000)
    bridge._firmware_capabilities = {'MUX_TARGET=1', 'SWD_CLOCK_ACK=1',
                                     'SWD_CLOCKS=' + ','.join(map(str, V3_CLOCKS))}
    bridge.reply = 'MKLINK_RESET_RC=0'
    device = _device(None)
    device._bridge = bridge
    Device.reset(device)
    assert bridge.calls == [("print('MKLINK_RESET_RC=' + str(cmd.reset_target(1)))", 10.0)]


@pytest.mark.parametrize('mode,declared,timeout', [('SWD', True, 12), ('SWD', False, 10), ('JTAG', True, 10)])
def test_fresh_text_reset_keeps_clock_and_uses_only_advertised_budget(mode, declared, timeout):
    from types import SimpleNamespace
    bridge = _BridgeStub()
    bridge._ctx = SimpleNamespace(clock_interface=mode, swd_clock_hz=10_000_000,
                                  applied_clock_hz=10_000_000, clock_apply_state='applied')
    bridge._firmware_capabilities = {'MUX_ATOMIC_SLEEP=1'} if declared else set()
    bridge.reply = 'MKLINK_RESET_RC=-5'
    device = _device(None)
    device._bridge = bridge
    with pytest.raises(DeviceError, match='outcome unknown'):
        Device.reset(device)
    assert bridge.calls == [("print('MKLINK_RESET_RC=' + str(cmd.reset_target(1)))", timeout)]
    assert device.clock_hz == bridge._ctx.applied_clock_hz == 10_000_000


@pytest.mark.parametrize('cached,expected', [(0x1003, 12), (3, 10)])
def test_text_reset_reuses_actual_hello_for_the_current_connection(cached, expected):
    from types import SimpleNamespace
    bridge = _BridgeStub()
    bridge._ctx = SimpleNamespace(clock_interface='SWD', swd_clock_hz=10_000_000,
                                  applied_clock_hz=10_000_000, clock_apply_state='applied')
    bridge._firmware_capabilities = {'MUX_TARGET=1'}
    bridge._mux_capabilities = cached
    bridge.reply = 'MKLINK_RESET_RC=0'
    device = _device(None)
    device._bridge = bridge
    Device.reset(device)
    assert bridge.calls == [("print('MKLINK_RESET_RC=' + str(cmd.reset_target(1)))", expected)]


def test_atomic_flash_verifies_separate_hex_regions_and_requires_capability(tmp_path):
    from types import SimpleNamespace

    firmware = tmp_path / 'split.hex'
    image = IntelHex()
    regions = {0x08000000: b'first', 0x08001000: b'second'}
    for address, data in regions.items():
        image.puts(address, data)
    image.write_hex_file(str(firmware))
    device = _device(lambda *args: pytest.fail('Unconfirmed ordinary readback'))
    mux = SimpleNamespace(supports_atomic_sleep=True,
                          read_atomic_memory=lambda address, size: regions[address][:size])
    device._bridge = SimpleNamespace(
        _ctx=SimpleNamespace(clock_interface='SWD', swd_clock_hz=10_000_000),
        _sleep_debug_previous_clock=10_000_000, _sleep_debug_atomic=True,
        _firmware_capabilities={'MUX_TARGET=1'}, enable_multiplex=lambda: mux,
    )
    assert device.flash(str(firmware), reset_after=False)['verified']
    mux.supports_atomic_sleep = False
    with pytest.raises(DeviceError, match='Flash programmed; readback verification failed'):
        device.flash(str(firmware), reset_after=False)


def test_device_flash_verify_rejects_mismatched_hex(tmp_path: Path):
    firmware = tmp_path / "firmware.hex"
    _write_hex(firmware, b"expected")
    device = _device(lambda _address, size: b"X" * size)

    with pytest.raises(DeviceError, match="Flash verify failed"):
        device.flash(str(firmware), verify=True, reset_after=False)


@pytest.mark.parametrize('hpm', [False, True])
@pytest.mark.parametrize('outcome', ['success', 'mismatch', 'deferred'])
def test_online_copy_cleanup_follows_successful_readback(tmp_path, monkeypatch, hpm, outcome):
    firmware = tmp_path / 'demo.hex'
    base = 0x80000400 if hpm else 0x08000000
    _write_hex(firmware, b'image', base)
    events = []

    def read_memory(address, size):
        events.append('verify')
        return b'wrong' if outcome == 'mismatch' else b'image'

    def cleanup(flash, result):
        events.append('cleanup')
        return {'deleted': ['owned.hex'], 'retained': [], 'errors': []}

    monkeypatch.setattr('mklink.online_files.cleanup_firmware', cleanup)
    device = _device(read_memory)
    device.reset = lambda: events.append('reset')
    device._flash.burn_hpm_hex = lambda *args, **kwargs: {'success': True}
    options = {'target_part': 'HPM5301', 'board': 'hpm5301evklite'} if hpm else {}
    if outcome == 'mismatch':
        with pytest.raises(DeviceError, match='Flash verify failed'):
            device.flash(str(firmware), **options)
        assert events == ['verify']
    else:
        result = device.flash(str(firmware), _defer_probe_cleanup=outcome == 'deferred', **options)
        expected = ['verify'] + ([] if hpm else ['reset'])
        assert events == expected + (['cleanup'] if outcome == 'success' else [])
        assert ('temporary_files' in result) == (outcome == 'success')


def test_hpm_hex_uses_addressed_rom_route_without_generic_reset(tmp_path: Path):
    firmware = tmp_path / "hpm.hex"
    _write_hex(firmware, b"data", 0x80000030)
    calls = []
    device = _device(lambda address, size: b"data" if (address, size) == (0x80000030, 4) else b"")
    device._flash.burn_hpm_hex = lambda path, **options: calls.append((path, options)) or {"success": True}
    device.reset = lambda: pytest.fail("HPM must not use generic SWD reset")
    result = device.flash(str(firmware), target_part="HPM6E80", board="hpm6e00evk", verify=True)
    assert result["verified"] and result["reset_handled_by_rom_api"]
    assert "addr" not in calls[0][1]
    assert device._flash.loaded == []


def test_device_flash_can_skip_readback_when_verify_is_false(tmp_path: Path):
    firmware = tmp_path / "firmware.hex"
    _write_hex(firmware, b"expected")
    device = _device(
        lambda _address, _size: (_ for _ in ()).throw(
            AssertionError("readback must be skipped")
        )
    )

    result = device.flash(str(firmware), verify=False, reset_after=False)

    assert result["verified"] is False


@pytest.mark.parametrize("source_kind", ["builtin-pack", "daplink-builtin"])
def test_device_flash_uses_catalog_algorithm_for_external_flash(
    tmp_path: Path,
    monkeypatch,
    source_kind: str,
):
    from mklink.cmsis_dap.algorithm_catalog import FlashAlgorithm

    firmware = tmp_path / "external.hex"
    _write_hex(firmware, b"external", 0x90000000)
    algorithm = FlashAlgorithm(
        algorithm_id="a" * 64,
        target_part="DEVICE_A",
        file_name="External.FLM",
        flash_start=0x90000000,
        flash_size=0x800000,
        ram_start=0x20001000,
        ram_size=0x10000,
        default=False,
        source_kind=source_kind,
        source_name="Vendor.Pack@1",
        source_token="catalog:bundle:Vendor.Pack:1:DEVICE_A:0",
    )
    monkeypatch.setattr(
        "mklink.cmsis_dap.algorithm_catalog.discover_flash_algorithms",
        lambda part_number: [algorithm] if part_number == "DEVICE_A" else [],
    )
    monkeypatch.setattr(
        "mklink.cmsis_dap.algorithm_catalog.deploy_algorithm_to_probe",
        lambda selected: "/FLM/External_hash.flm",
    )
    device = _device(lambda _address, size: b"external"[:size])
    device._mcu_hint = None

    result = device.flash(
        str(firmware),
        target_part="DEVICE_A",
        verify=False,
        reset_after=False,
    )

    assert result["algorithm_source"] == source_kind
    assert device._flash.loaded == [
        ("/FLM/External_hash.flm", "0x90000000", "0x20001000"),
    ]


def test_device_flash_uses_verified_profile_when_catalog_deploy_fails(
    tmp_path: Path,
    monkeypatch,
):
    from mklink.cmsis_dap.algorithm_catalog import FlashAlgorithm

    firmware = tmp_path / "firmware.hex"
    _write_hex(firmware, b"fallback", 0x08020000)
    algorithm = FlashAlgorithm(
        algorithm_id="f" * 64,
        target_part="DEVICE_A",
        file_name="Catalog.FLM",
        flash_start=0x08000000,
        flash_size=0x100000,
        ram_start=0x20000000,
        ram_size=0x20000,
        default=True,
        source_kind="daplink-builtin",
        source_name="builtin",
        source_token="catalog:builtin:DEVICE_A:0",
    )
    monkeypatch.setattr(
        "mklink.cmsis_dap.algorithm_catalog.discover_flash_algorithms",
        lambda _part_number: [algorithm],
    )
    monkeypatch.setattr(
        "mklink.cmsis_dap.algorithm_catalog.deploy_algorithm_to_probe",
        lambda _selected: (_ for _ in ()).throw(OSError("volume unavailable")),
    )
    profile = {
        "name": "Verified MCU",
        "flm_path": "FLM/Verified.FLM",
        "flash_base": "0x08000000",
        "ram_base": "0x20000000",
    }
    monkeypatch.setattr("mklink.profiles.load_mcu_profiles", lambda: {"verified": profile})
    device = _device(lambda _address, size: b"fallback"[:size])
    device._mcu_hint = "verified"

    result = device.flash(
        str(firmware), target_part="DEVICE_A", verify=False, reset_after=False
    )

    assert result["algorithm_source"] == "legacy-profile-fallback"
    assert device._flash.loaded == [
        ("/FLM/Verified.FLM", "0x08000000", "0x20000000"),
    ]


def test_device_flash_uses_profile_for_packaged_catalog_import_failure_and_bin_offset(
    tmp_path: Path,
    monkeypatch,
):
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"fallback")
    monkeypatch.setattr(
        "mklink.cmsis_dap.algorithm_catalog.discover_flash_algorithms",
        lambda _part_number: (_ for _ in ()).throw(ImportError("not packaged")),
    )
    profile = {
        "name": "Verified MCU",
        "flm_path": "FLM/Verified.FLM",
        "flash_base": "0x08000000",
        "ram_base": "0x20000000",
    }
    monkeypatch.setattr("mklink.profiles.load_mcu_profiles", lambda: {"verified": profile})
    device = _device(lambda _address, size: b"fallback"[:size])
    device._mcu_hint = "verified"

    result = device.flash(
        str(firmware),
        target_part="DEVICE_A",
        base_address="0x08020000",
        verify=False,
        reset_after=False,
    )

    assert result["algorithm_source"] == "legacy-profile-fallback"
    assert device._flash.loaded == [
        ("/FLM/Verified.FLM", "0x08000000", "0x20000000"),
    ]
    assert device._flash.burned == [("bin", "firmware.bin", "0x08020000")]


def test_device_flash_splits_mixed_hex_across_catalog_algorithms(tmp_path: Path, monkeypatch):
    from mklink.cmsis_dap.algorithm_catalog import FlashAlgorithm

    firmware = tmp_path / "mixed.hex"
    image = IntelHex()
    image.puts(0x08000000, b"internal")
    image.puts(0x90000000, b"external")
    image.write_hex_file(str(firmware))

    def algorithm(name, start, size, default):
        return FlashAlgorithm(
            algorithm_id=name,
            target_part="DEVICE_A",
            file_name=f"{name}.FLM",
            flash_start=start,
            flash_size=size,
            ram_start=0x20001000,
            ram_size=0x10000,
            default=default,
            source_kind="builtin-pack",
            source_name="Vendor.Pack@1",
            source_token=f"catalog:bundle:Vendor.Pack:1:REVWSUNFX0E:{len(name)}",
        )

    algorithms = [
        algorithm("Internal", 0x08000000, 0x20000, True),
        algorithm("External", 0x90000000, 0x800000, False),
    ]
    monkeypatch.setattr(
        "mklink.cmsis_dap.algorithm_catalog.discover_flash_algorithms",
        lambda _part_number: algorithms,
    )
    monkeypatch.setattr(
        "mklink.cmsis_dap.algorithm_catalog.deploy_algorithm_to_probe",
        lambda selected: f"/FLM/{selected.file_name}",
    )
    device = _device(lambda _address, size: b"\x00" * size)

    result = device.flash(
        str(firmware),
        target_part="DEVICE_A",
        verify=False,
        reset_after=False,
    )

    assert result["success"] is True
    assert device._flash.burned == [
        ((0x08000000, 0x08000008),),
        ((0x90000000, 0x90000008),),
    ]
    assert [call[0] for call in device._flash.loaded] == [
        "/FLM/Internal.FLM",
        "/FLM/External.FLM",
    ]


def test_device_flash_routes_hpm_bin_to_rom_api_without_flm(tmp_path: Path, monkeypatch):
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"hpm")
    monkeypatch.setattr(
        "mklink.cmsis_dap.algorithm_catalog.discover_flash_algorithms",
        lambda _part_number: (_ for _ in ()).throw(
            AssertionError("HPM must not discover FLM algorithms")
        ),
    )
    device = _device(lambda _address, _size: b"")

    result = device.flash(
        str(firmware),
        target_part="HPM5301xEGx",
        base_address=0x80000400,
        board="hpm5301evklite",
        verify=False,
        reset_after=False,
    )

    assert result["algorithm_source"] == "hpm-rom-api"
    assert device._flash.loaded == []
    assert device._flash.burned == [
        ("hpm", "firmware.bin", "0x80000400", "hpm5301evklite", ()),
    ]


def test_device_flash_does_not_apply_generic_reset_after_hpm_rom_programming(
    tmp_path: Path,
):
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"hpm")
    device = _device(lambda _address, _size: b"")
    device.reset = lambda: (_ for _ in ()).throw(
        AssertionError("HPM must not use the generic SWD reset")
    )

    result = device.flash(
        str(firmware),
        target_part="HPM5301xEGx",
        base_address=0x80000400,
        board="hpm5301evklite",
        verify=False,
    )

    assert result["reset_handled_by_rom_api"] is True


def test_unknown_hpm_target_requires_board_or_flash_configuration(tmp_path: Path):
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"hpm")
    device = _device(lambda _address, _size: b"")

    with pytest.raises(DeviceError, match="board or flash configuration"):
        device.flash(
            str(firmware),
            target_part="HPM9999",
            base_address=0x80000400,
            verify=False,
            reset_after=False,
        )

    assert device._flash.burned == []


def test_device_flash_recognizes_hpm_project_without_target_part(tmp_path: Path):
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"hpm")
    save_config(str(tmp_path), {"mcu_key": None, "swd_clock": 4_000_000})
    save_project_info(str(tmp_path), {
        "vendor": "HPMicro",
        "board": "hpm5301evklite",
        "bin_base": "0x80000400",
        "bin_path": str(firmware),
    })
    device = Device(project_root=str(tmp_path))
    device._connected = True
    device._bridge = object()
    device._flash = _FlashStub()
    device._get_mcu_profile = lambda: None
    device.reset = lambda: None

    result = device.flash(
        str(firmware),
        verify=False,
        reset_after=False,
    )

    assert result["algorithm_source"] == "hpm-rom-api"
    assert device._flash.loaded == []
    assert device._flash.burned == [
        ("hpm", "firmware.bin", "0x80000400", "hpm5301evklite", ()),
    ]


def test_device_flash_preserves_bin_address_inside_algorithm_region(tmp_path: Path, monkeypatch):
    from mklink.cmsis_dap.algorithm_catalog import FlashAlgorithm

    firmware = tmp_path / "external.bin"
    firmware.write_bytes(b"external")
    algorithm = FlashAlgorithm(
        algorithm_id="b" * 64,
        target_part="DEVICE_A",
        file_name="External.FLM",
        flash_start=0x90000000,
        flash_size=0x800000,
        ram_start=0x20001000,
        ram_size=0x10000,
        default=False,
        source_kind="builtin-pack",
        source_name="Vendor.Pack@1",
        source_token="catalog:bundle:Vendor.Pack:1:DEVICE_A:0",
    )
    monkeypatch.setattr(
        "mklink.cmsis_dap.algorithm_catalog.discover_flash_algorithms",
        lambda _part_number: [algorithm],
    )
    monkeypatch.setattr(
        "mklink.cmsis_dap.algorithm_catalog.deploy_algorithm_to_probe",
        lambda _algorithm: "/FLM/External.flm",
    )
    device = _device(lambda _address, _size: b"")

    device.flash(
        str(firmware),
        target_part="DEVICE_A",
        base_address=0x90001000,
        verify=False,
        reset_after=False,
    )

    assert device._flash.loaded == [
        ("/FLM/External.flm", "0x90000000", "0x20001000"),
    ]
    assert device._flash.burned == [("bin", "external.bin", "0x90001000")]


def test_device_flash_rejects_exact_target_without_any_algorithm(tmp_path: Path, monkeypatch):
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"firmware")
    monkeypatch.setattr(
        "mklink.cmsis_dap.algorithm_catalog.discover_flash_algorithms",
        lambda _part_number: [],
    )
    device = _device(lambda _address, _size: b"")
    device._mcu_hint = None

    with pytest.raises(DeviceError, match="no usable Flash algorithm"):
        device.flash(
            str(firmware),
            target_part="MISSING_DEVICE",
            base_address=0x08000000,
            verify=False,
            reset_after=False,
        )

    assert device._flash.burned == []


def test_device_flash_verify_reads_multiple_hex_segments_and_chunk_tail(
    tmp_path: Path,
):
    firmware = tmp_path / "firmware.hex"
    first = bytes(index % 251 for index in range(1025))
    second = b"tail"
    image = IntelHex()
    image.puts(0x08000000, first)
    image.puts(0x08002000, second)
    image.write_hex_file(str(firmware))
    regions = {0x08000000: first, 0x08002000: second}
    calls = []

    def read_memory(address: int, size: int) -> bytes:
        calls.append((address, size))
        for start, data in regions.items():
            if start <= address < start + len(data):
                offset = address - start
                return data[offset:offset + size]
        raise AssertionError(f"unexpected address: {address:#x}")

    result = _device(read_memory).flash(
        str(firmware), verify=True, reset_after=False
    )

    assert result["verified"] is True
    assert calls == [
        (0x08000000, 1024),
        (0x08000400, 1),
        (0x08002000, 4),
    ]


def test_device_flash_verify_reads_bin_from_flash_base(tmp_path: Path):
    firmware = tmp_path / "firmware.bin"
    expected = bytes(index % 251 for index in range(1100))
    firmware.write_bytes(expected)
    calls = []

    def read_memory(address: int, size: int) -> bytes:
        calls.append((address, size))
        offset = address - 0x08000000
        return expected[offset:offset + size]

    result = _device(read_memory).flash(
        str(firmware), verify=True, reset_after=False
    )

    assert result["verified"] is True
    assert calls == [(0x08000000, 1024), (0x08000400, 76)]


@pytest.mark.parametrize('reply,confirmed', [
    ('MKLINK_RESET_RC=0\r\n>>>', True), ('>>>', False), ('0', False),
    ('MKLINK_RESET_RC=-4\r\n>>>', False), ('MKLINK_RESET_RC=0\nMKLINK_RESET_RC=-5', False),
])
def test_device_reset_requires_checked_target_receipt(reply, confirmed):
    device = Device()
    bridge = _BridgeStub()
    bridge.reply = reply
    device._connected = True
    device._bridge = bridge

    if confirmed:
        device.reset()
    else:
        with pytest.raises(DeviceError, match='outcome unknown'):
            device.reset()
    assert len(bridge.calls) == 1 and 'cmd.reset_target(1)' in bridge.calls[0][0]

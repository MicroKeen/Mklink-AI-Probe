"""Artifact identity and physical-claim transitions, without access to a probe."""
import hashlib
import json
import struct
from unittest.mock import Mock

import pytest

from mklink.device import Device
from mklink.image_target import image_binding, resolve_image_target
from mklink.profiles import TargetProfileError


def image(folder, name="demo.elf"):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    ident = b"\x7fELF\x01\x01\x01".ljust(16, b"\0")
    path.write_bytes(struct.pack("<16sHHIIIIIHHHHHH", ident, 2, 40, 1, 0, 0, 0, 0, 52, 0, 0, 40, 0, 0))
    return path


def bind_file(path, name, digest=None):
    data = {"schema_version": 1, "device": name, "sha256": digest or hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_name(path.name + ".mklink.json").write_text(json.dumps(data))


def test_digest_and_conflicting_signatures(tmp_path):
    target = image(tmp_path)
    bind_file(target, "S32K344")
    assert image_binding(target)[1].name == "S32K344"
    target.with_suffix(".map").write_text("LOAD build/startup_S32K314.o")
    assert resolve_image_target(target)["status"] == "conflict"
    with pytest.raises(TargetProfileError, match="image_target_conflict"):
        image_binding(target)
    assert image_binding(target, "S32K314")[1].name == "S32K314"
    target.with_suffix(".map").unlink()
    bind_file(target, "S32K344", "00" * 32)
    with pytest.raises(TargetProfileError, match="SHA-256"):
        image_binding(target)
    target.write_bytes(b"not ELF")
    assert resolve_image_target(target)["status"] == "unknown"


def test_matched_keil_outputs_only(tmp_path):
    target = image(tmp_path / "Objects", "Example.axf")
    def entry(model, output):
        return f"<Target><TargetOption><TargetCommonOption><Device>{model}</Device><OutputDirectory>.\\Objects\\</OutputDirectory><OutputName>{output}</OutputName></TargetCommonOption></TargetOption></Target>"
    project = tmp_path / "Project.uvprojx"
    same = entry("S32K344:Cortex-M7_0", "Example")
    project.write_text("<Project>" + same * 2 + entry("S32K314", "Other") + "</Project>")
    assert image_binding(target)[1].name == "S32K344"
    project.write_text("<Project>" + same + entry("S32K314", "Example") + "</Project>")
    assert resolve_image_target(target)["status"] == "conflict"
    project.write_text("<Project>" + entry("S32K344:Cortex-M7_1", "Example") + "</Project>")
    with pytest.raises(TargetProfileError, match="unsupported processor"):
        image_binding(target)
    assert resolve_image_target(image(tmp_path, "Example.axf"))["status"] == "unknown"


def test_cross_ide_outputs_and_core_only(tmp_path):
    target = image(tmp_path / "build" / "iar" / "Exe", "project.out")
    (tmp_path / "demo.ewp").write_text("""<project><configuration><settings><name>General</name><data>
<option><name>ExePath</name><state>build\\iar\\Exe</state></option>
<option><name>OGChipSelectEditMenu</name><state>STM32H743II ST STM32H743II</state></option></data></settings>
<settings><name>ILINK</name><data><option><name>IlinkOutputFile</name><state>project.out</state></option></data></settings></configuration></project>""")
    identity, profile = image_binding(target)
    assert identity["device"] == "STM32H743II" and profile is None
    other = image(tmp_path / "gcc", "firmware.elf")
    other.with_suffix(".map").write_text("LOAD startup_cortex-m7.o 0x40290004\n")
    assert resolve_image_target(other)["status"] == "unknown"
    run = tmp_path / "demo.cbuild-run.yml"
    run.write_text("cbuild-run:\n  device: NXP::S32K344\n  output:\n    - file: gcc/firmware.elf\n      type: elf\n")
    assert image_binding(other)[1].name == "S32K344"
    run.unlink()
    other.with_suffix(".map").write_text("LOAD obj/startup_S32K344.o\n")
    assert resolve_image_target(other)["device"] == "S32K344"


def test_switch_image_on_live_device_keeps_physical_claim(tmp_path, monkeypatch):
    first, second = image(tmp_path, "one.elf"), image(tmp_path, "two.elf")
    bind_file(first, "S32K314")
    bind_file(second, "S32K344")
    device = Device(port="mock", axf=str(first), mcu="S32K314")
    device._attach_profile = image_binding(first)[1]
    monkeypatch.setattr(Device, "connected", property(lambda self: self._connected))
    device._connected = True
    close = Mock(side_effect=lambda: setattr(device, "_connected", False))
    monkeypatch.setattr(device, "close", close)
    open_probe = Mock(side_effect=RuntimeError("physical signature mismatch"))
    monkeypatch.setattr(device, "_connect", open_probe)
    monkeypatch.setattr(device, "_prepare_axf_catalog", lambda *args: (str(second), "builtin", "builtin", object(), object()))
    device.reparse_axf_atomically(str(second))
    close.assert_not_called()
    open_probe.assert_not_called()
    assert device.connected and device.symbol_catalog is not None and device.axf_path == str(second)
    assert device._image_target['device'] == 'S32K344'
    assert device._attach_profile.name == 'S32K314'

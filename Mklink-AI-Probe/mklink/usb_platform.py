"""Passive OS USB metadata: exact device-node binding, never serial I/O."""
from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path


def macos_usb_device(node, parent=None):
    """Identify device boundaries, not properties copied onto interface drivers."""
    if 'idVendor' not in node or 'idProduct' not in node:
        return False
    kind = node.get('IOObjectClass') or node.get('IOClass') or ''
    if kind in ('IOUSBHostDevice', 'IOUSBDevice'):
        return True
    if 'bDeviceClass' in node and 'bInterfaceNumber' not in node:
        return True  # Device subclasses can have a vendor-specific IOObjectClass.
    if kind or any(key in node for key in ('bInterfaceNumber', 'bInterfaceClass',
                                           'IOCalloutDevice', 'IODialinDevice', 'BSD Name')):
        return False
    # Older registry snapshots may omit class metadata. Identical inherited
    # properties do not create a new device; a distinct identity is a boundary.
    return parent is None or macos_identity_conflicts(parent, node)


def macos_identity_conflicts(device, node):
    for key in ('idVendor', 'idProduct'):
        if key in node and node[key] != device.get(key):
            return True
    serial = str(node.get('USB Serial Number') or '').strip().casefold()
    expected = str(device.get('USB Serial Number') or '').strip().casefold()
    return bool(serial and serial != expected)


def _same_device(info, properties):
    if (properties.get("idVendor"), properties.get("idProduct")) != (getattr(info, "vid", None), getattr(info, "pid", None)):
        return False
    expected = str(getattr(info, "serial_number", "") or "").strip()
    actual = str(properties.get("USB Serial Number", "") or "").strip()
    return not expected or expected == actual


def _interface_nodes(device):
    """Do not cross into another USB device while collecting interfaces."""
    result = []
    def visit(node):
        if node is not device and (macos_usb_device(node, device) or macos_identity_conflicts(device, node)):
            return
        number = node.get("bInterfaceNumber")
        if type(number) is int and 0 <= number <= 255:
            result.append(node)
        for child in node.get("IORegistryEntryChildren", []):
            if isinstance(child, dict):
                visit(child)
    visit(device)
    return result


def macos_interface_from_registry(info, tree):
    """Bind IOSerialBSDClient to its actual USB interface ancestor.

    ACM serial clients can be below the data interface. For MKLink only,
    normalize it to the descriptor-confirmed control/data pair, not a suffix
    of the BSD device name. Ambiguous or conflicting metadata is rejected.
    """
    device_path = str(getattr(info, "device", ""))
    matches = []
    def visit(node, device=None, interface=None):
        if not isinstance(node, dict):
            return
        if macos_usb_device(node, device):
            device, interface = node, None
        elif device is not None and macos_identity_conflicts(device, node):
            return
        if "bInterfaceNumber" in node:
            interface = node
        if device_path in (node.get("IOCalloutDevice"), node.get("IODialinDevice")):
            if device is not None and interface is not None and _same_device(info, device):
                matches.append((device, interface))
        for child in node.get("IORegistryEntryChildren", []):
            visit(child, device, interface)
    for root in tree if isinstance(tree, list) else [tree]:
        visit(root)
    if len(matches) != 1:
        return None
    device, interface = matches[0]
    number = interface.get("bInterfaceNumber")
    if type(number) is not int or not 0 <= number <= 255:
        return None
    if (device.get("idVendor"), device.get("idProduct")) == (0x0D28, 0x0202) and interface.get("bInterfaceClass") == 0x0A:
        expected_names = {3: "MKLink USB to UART", 5: "MKLink Python Console", 7: "MKLink USB to RS485"}
        expected = expected_names.get(number)
        if not expected:
            return None
        controls = [entry for entry in _interface_nodes(device)
                    if entry.get("bInterfaceNumber") == number - 1
                    and entry.get("bInterfaceClass") == 2
                    and entry.get("bInterfaceSubClass") == 2
                    and (entry.get("USB Interface Name") or entry.get("IORegistryEntryName")) == expected]
        return number - 1 if len(controls) == 1 else None
    return number


def macos_registry():
    # IOService contains unrelated GPU/storage/network trees. -r keeps complete
    # descendants (serial clients and IOMedia) of the selected USB device roots.
    # Keep a fresh snapshot per enumeration and the legacy full-plane fallback.
    for selection, timeout in ((['-r', '-c', 'IOUSBHostDevice'], 2), ([], 5)):
        try:
            result = subprocess.run(['/usr/sbin/ioreg', '-a', '-l', '-p', 'IOService', *selection],
                                    capture_output=True, check=True, timeout=timeout)
            tree = plistlib.loads(result.stdout)
            if isinstance(tree, list) and tree and all(isinstance(node, dict) for node in tree):
                return tree
        except (OSError, ValueError, plistlib.InvalidFileException, subprocess.SubprocessError):
            pass
    return []


def macos_interface_number(info):
    return macos_interface_from_registry(info, macos_registry())


def linux_interface_number(info, *, sysfs_root=Path("/sys/class/tty")):
    """Use bInterfaceNumber from the selected tty's sysfs ancestry."""
    device_string = str(getattr(info, "device", ""))
    if not device_string.startswith("/dev/"):
        return None
    device = Path(device_string)
    try:
        node = (Path(sysfs_root) / device.resolve().name / "device").resolve(strict=True)
        number = None
        for parent in (node, *node.parents):
            if number is None and (parent / "bInterfaceNumber").is_file():
                number = int((parent / "bInterfaceNumber").read_text().strip(), 16)
            if (parent / "idVendor").is_file() and (parent / "idProduct").is_file():
                properties = {"idVendor": int((parent / "idVendor").read_text().strip(), 16),
                              "idProduct": int((parent / "idProduct").read_text().strip(), 16),
                              "USB Serial Number": (parent / "serial").read_text().strip() if (parent / "serial").is_file() else ""}
                return number if _same_device(info, properties) and number is not None and 0 <= number <= 255 else None
    except (OSError, ValueError, RuntimeError):
        return None
    return None

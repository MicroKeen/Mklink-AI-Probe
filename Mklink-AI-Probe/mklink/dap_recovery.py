"""Reconcile orphaned CMSIS-DAP ownership at a new Windows CDC connection.

USB handle closure is invisible to the probe. Never infer it from inactivity:
an exclusive OS handle must remain held through the HostStatus acknowledgement.
No Connect, Disconnect, reset, target memory or debug-port command is sent.
"""
from __future__ import annotations

import ctypes as c
from ctypes import wintypes as w
import sys
from uuid import UUID

from .usb_interfaces import (
    MKLINK_COMMAND_INTERFACE, MKLINK_USB_VID_PID, canonical_serial_port,
    is_mklink_usb_port, usb_interface_number,
)


def _port_identity(port):
    from serial.tools import list_ports
    matches = [p for p in list_ports.comports()
               if canonical_serial_port(p.device) == canonical_serial_port(port)]
    if len(matches) != 1:
        return None
    info = matches[0]
    serial = str(getattr(info, 'serial_number', '') or '').strip()
    if (not is_mklink_usb_port(info) or not serial
            or usb_interface_number(info) != MKLINK_COMMAND_INTERFACE):
        return None
    return (*MKLINK_USB_VID_PID, serial.casefold())


def reconcile_dap_owner(port):
    """Best effort; an active IDE or unverifiable interface is left untouched.

    Called only after owning the selected CDC port, before starting its reader.
    Failure never bypasses firmware arbitration or retries a target operation.
    """
    if sys.platform != 'win32':
        return 'unsupported'
    try:
        identity = _port_identity(port)
        if identity is None:
            return 'unverified'
        return _reconcile(identity, _WindowsDap())
    except (OSError, RuntimeError, ValueError) as exc:
        return f'unavailable: {exc}'


def _reconcile(identity, api):
    paths = [path for path, owner in api.interfaces() if owner == identity]
    if len(paths) != 1:
        return 'unverified'
    # Do not release this handle and reopen with pyUSB: that creates an
    # ownership race and pyUSB's shared open alone is not exclusivity proof.
    with api.exclusive(paths[0]) as channel:
        channel.drain()
        channel.write(b'\x01\x00\x00')  # DAP_HostStatus: DEBUGGER_CONNECTED=false
        response = channel.read()
        if len(response) < 2 or response[:2] != b'\x01\x00' or any(response[2:]):
            raise RuntimeError('CMSIS-DAP HostStatus acknowledgement was not confirmed')
    return 'reconciled'


class _InterfaceDescriptor(c.Structure):
    _fields_ = [(name, c.c_ubyte) for name in (
        'length', 'kind', 'number', 'alternate', 'endpoints',
        'interface_class', 'subclass', 'protocol', 'string')]


class _Pipe(c.Structure):
    _fields_ = [('kind', c.c_int), ('address', c.c_ubyte),
               ('maximum', c.c_ushort), ('interval', c.c_ubyte)]


class _WindowsDap:
    def __init__(self):
        from .windows_volumes import _WindowsInventory, _function
        self.os = _WindowsInventory()
        dll = c.WinDLL('winusb', use_last_error=True)
        ptr, handle, byte, ulong = c.c_void_p, w.HANDLE, c.c_ubyte, w.ULONG
        self.initialize = _function(dll, 'WinUsb_Initialize', w.BOOL, handle, ptr)
        self.free = _function(dll, 'WinUsb_Free', w.BOOL, handle)
        self.settings = _function(dll, 'WinUsb_QueryInterfaceSettings', w.BOOL, handle, byte, ptr)
        self.pipe = _function(dll, 'WinUsb_QueryPipe', w.BOOL, handle, byte, byte, ptr)
        self.policy = _function(dll, 'WinUsb_SetPipePolicy', w.BOOL, handle, byte, ulong, ulong, ptr)
        self.read_pipe = _function(dll, 'WinUsb_ReadPipe', w.BOOL, handle, byte, ptr, ulong, ptr, ptr)
        self.write_pipe = _function(dll, 'WinUsb_WritePipe', w.BOOL, handle, byte, ptr, ulong, ptr, ptr)

    def interfaces(self):
        from .windows_volumes import _Guid, _Interface, _DevInfo
        from .probe_volumes import usb_ancestor
        guid = _Guid.from_buffer_copy(UUID('cdb3b5ad-293b-4663-aa36-1aae46463776').bytes_le)
        api = self.os
        devices = api.class_devs(c.byref(guid), None, None, 0x12)
        if devices == api.invalid:
            raise c.WinError(c.get_last_error())
        try:
            index = 0
            while True:
                interface = _Interface(); interface.cbSize = c.sizeof(interface)
                if not api.enum(devices, None, c.byref(guid), index, c.byref(interface)):
                    if c.get_last_error() == 259:
                        break
                    raise c.WinError(c.get_last_error())
                index += 1
                size = w.DWORD()
                api.detail(devices, c.byref(interface), None, 0, c.byref(size), None)
                if c.get_last_error() != 122 or not 6 <= size.value <= 65536:
                    raise RuntimeError('Invalid CMSIS-DAP interface detail size')
                detail = c.create_string_buffer(size.value)
                c.cast(detail, c.POINTER(w.DWORD))[0] = 8 if c.sizeof(c.c_void_p) == 8 else 6
                dev = _DevInfo(); dev.cbSize = c.sizeof(dev)
                if not api.detail(devices, c.byref(interface), detail, size.value, None, c.byref(dev)):
                    raise c.WinError(c.get_last_error())
                instance = c.create_unicode_buffer(1024)
                if not api.instance(devices, c.byref(dev), instance, len(instance), None):
                    raise c.WinError(c.get_last_error())
                # Only interface zero of the identity-bound composite probe.
                if '&MI_00\\' in instance.value.upper():
                    yield c.wstring_at(c.addressof(detail) + 4), usb_ancestor(instance.value)
        finally:
            api.destroy(devices)

    def exclusive(self, path):
        return _Channel(self, path)


class _Channel:
    def __init__(self, api, path):
        self.api, self.path = api, path
        self.file = None
        self.usb = w.HANDLE()

    def __enter__(self):
        api = self.api
        # shareMode=0 is essential: an idle/paused IDE still owns its handle.
        self.file = api.os.open(self.path, 0xc0000000, 0, None, 3, 0x40000000, None)
        if self.file == api.os.invalid:
            self.file = None
            raise c.WinError(c.get_last_error())
        try:
            if not api.initialize(self.file, c.byref(self.usb)):
                raise c.WinError(c.get_last_error())
            descriptor = _InterfaceDescriptor()
            if not api.settings(self.usb, 0, c.byref(descriptor)):
                raise c.WinError(c.get_last_error())
            if (descriptor.number, descriptor.interface_class, descriptor.endpoints) != (0, 255, 2):
                raise RuntimeError('Unexpected CMSIS-DAP interface layout')
            pipes = []
            for index in range(2):
                pipe = _Pipe()
                if not api.pipe(self.usb, 0, index, c.byref(pipe)):
                    raise c.WinError(c.get_last_error())
                if pipe.kind != 2 or not 64 <= pipe.maximum <= 512:
                    raise RuntimeError('Unexpected CMSIS-DAP bulk pipe')
                pipes.append(pipe)
            incoming = [p for p in pipes if p.address & 0x80]
            outgoing = [p for p in pipes if not p.address & 0x80]
            if len(incoming) != 1 or len(outgoing) != 1:
                raise RuntimeError('Ambiguous CMSIS-DAP endpoints')
            self.in_ep, self.out_ep = incoming[0].address, outgoing[0].address
            self.size = incoming[0].maximum
            self.timeout(self.in_ep, 200)
            self.timeout(self.out_ep, 200)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.usb.value:
            self.api.free(self.usb)
            self.usb = w.HANDLE()
        if self.file is not None:
            self.api.os.close(self.file)
            self.file = None

    def timeout(self, endpoint, milliseconds):
        value = w.ULONG(milliseconds)
        if not self.api.policy(self.usb, endpoint, 3, c.sizeof(value), c.byref(value)):
            raise c.WinError(c.get_last_error())

    def read(self):
        data, count = c.create_string_buffer(self.size), w.ULONG()
        if not self.api.read_pipe(self.usb, self.in_ep, data, len(data), c.byref(count), None):
            raise c.WinError(c.get_last_error())
        return data.raw[:count.value]

    def write(self, data):
        count = w.ULONG()
        buffer = c.create_string_buffer(data)
        if not self.api.write_pipe(self.usb, self.out_ep, buffer, len(data), c.byref(count), None):
            raise c.WinError(c.get_last_error())
        if count.value != len(data):
            raise RuntimeError('Incomplete CMSIS-DAP HostStatus write')

    def drain(self):
        self.timeout(self.in_ep, 10)
        try:
            for _ in range(32):
                try:
                    self.read()
                except OSError as exc:
                    if exc.winerror == 121:  # ERROR_SEM_TIMEOUT: endpoint is drained.
                        return
                    raise
            raise RuntimeError('CMSIS-DAP response queue did not drain')
        finally:
            self.timeout(self.in_ep, 200)

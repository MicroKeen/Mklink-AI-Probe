"""Coordinate probe firmware transfers with the native desktop installer."""

from contextlib import contextmanager
import os
from pathlib import Path


class DesktopInstallInProgress(RuntimeError):
    """The desktop installer has exclusive access to the update lock."""


def _lock_shared(file):
    if os.name != 'nt':
        import fcntl
        try:
            fcntl.flock(file, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    import ctypes
    from ctypes import wintypes
    import msvcrt

    class Overlapped(ctypes.Structure):
        _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                    ('Offset', wintypes.DWORD), ('OffsetHigh', wintypes.DWORD),
                    ('hEvent', wintypes.HANDLE)]

    lock = ctypes.WinDLL('kernel32', use_last_error=True).LockFileEx
    lock.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                     wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
    lock.restype = wintypes.BOOL
    # LOCKFILE_FAIL_IMMEDIATELY, shared, first byte of the desktop's whole-file lock.
    if lock(msvcrt.get_osfhandle(file.fileno()), 1, 0, 1, 0, ctypes.byref(Overlapped())):
        return True
    error = ctypes.get_last_error()
    if error == 33:  # ERROR_LOCK_VIOLATION
        return False
    raise ctypes.WinError(error)


@contextmanager
def probe_firmware_transfer():
    path = Path.home() / '.mklink' / 'desktop-install.lock'
    path.parent.mkdir(mode=0o700, exist_ok=True)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_RDWR, 0o600), 'r+b') as lock:
        if not _lock_shared(lock):
            raise DesktopInstallInProgress('上位机正在安装更新，请在上位机重启后再升级下载器固件。')
        yield

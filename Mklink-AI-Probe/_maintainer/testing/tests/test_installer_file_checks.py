"""Run the actual NSIS file gate without installation/elevation or hardware."""
from contextlib import contextmanager
import ctypes
import os
from pathlib import Path
import subprocess
import threading
import time

import pytest

ROOT = Path(__file__).resolve().parents[3]
MAKENSIS = Path(os.environ.get('LOCALAPPDATA', '')) / 'tauri/NSIS/makensis.exe'
pytestmark = pytest.mark.skipif(os.name != 'nt' or not MAKENSIS.is_file(), reason='Windows NSIS is required')


@pytest.fixture(params=['install', 'uninstall'])
def installer(tmp_path, request):
    payload = tmp_path / 'payload'
    payload.mkdir()
    (payload / 'mklink-sidecar.exe').write_bytes(b'existing version')
    output = tmp_path / 'gate.exe'
    script = tmp_path / 'gate.nsi'
    gate = ROOT / 'gui/src-tauri/installer-file-check.nsh'
    # This suite exercises file locks only. The process helper has a separate
    # real-process suite with an isolated inventory; never close user apps here.
    prepare = tmp_path / 'prepare.ps1'
    prepare.write_text('''param([string]$InstallDir)
if (Test-Path "$InstallDir/hold-preparation") {
  Set-Content "$InstallDir/preparing" started
  for ($i = 0; $i -lt 200 -and (Test-Path "$InstallDir/hold-preparation"); $i++) {
    Start-Sleep -Milliseconds 100
  }
}
exit 0
''', encoding='utf-8')
    create_uninstaller = 'WriteUninstaller "$EXEDIR\\remove.exe"' if request.param == 'uninstall' else ''
    install_check = 'Call MklinkWaitForUpgradeFiles' if request.param == 'install' else ''
    script.write_text(f'''Unicode true
Name "MKLink file gate test"
OutFile "{output}"
RequestExecutionLevel user
SilentInstall silent
SilentUnInstall silent
!include "LogicLib.nsh"
!define MKLINK_PREPARE_SCRIPT "{prepare}"
!define MKLINK_INSTALL_LOCK_DIR "$EXEDIR\\.mklink"
!include "{gate}"
Section
  StrCpy $INSTDIR "$EXEDIR\\payload"
  {create_uninstaller}
  {install_check}
  {'Goto done' if request.param == 'uninstall' else ''}
  FileOpen $0 "$INSTDIR\\completed" w
  FileWrite $0 "ready"
  FileClose $0
  done:
SectionEnd
Section "Uninstall"
  StrCpy $INSTDIR "$EXEDIR\\payload"
  Call un.MklinkWaitForUpgradeFiles
  FileOpen $0 "$INSTDIR\\completed" w
  FileWrite $0 "ready"
  FileClose $0
SectionEnd
''', encoding='utf-8-sig')
    build = subprocess.run([str(MAKENSIS), str(script)], capture_output=True, timeout=30)
    assert build.returncode == 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace')
    if request.param == 'uninstall':
        assert run_gate(output).returncode == 0
        output = tmp_path / 'remove.exe'
    return output, payload


@contextmanager
def deny_writes(path):
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0, None)
    assert handle != ctypes.c_void_p(-1).value
    closed = False
    def release():
        nonlocal closed
        if not closed:
            kernel.CloseHandle(handle)
            closed = True
    try:
        yield release
    finally:
        release()


def run_gate(output):
    # Avoid NSIS copying the uninstaller to TEMP and detaching from this process.
    args = [str(output)]
    if output.name == 'remove.exe':
        args.append(f'_?={output.parent}')
    return subprocess.run(args, timeout=35, creationflags=subprocess.CREATE_NO_WINDOW)


def test_installer_proceeds_when_files_are_available(installer):
    output, payload = installer
    assert run_gate(output).returncode == 0
    assert (payload / 'completed').read_text() == 'ready'
    assert (payload / 'mklink-sidecar.exe').read_bytes() == b'existing version'


@pytest.mark.parametrize('installer', ['install'], indirect=True)
def test_installer_waits_for_firmware_and_protects_its_own_writes(tmp_path, monkeypatch, installer):
    from mklink.desktop_install import DesktopInstallInProgress, probe_firmware_transfer

    output, payload = installer
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    hold = payload / 'hold-preparation'
    hold.touch()
    with probe_firmware_transfer():
        process = subprocess.Popen([str(output)], creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            time.sleep(1)
            assert process.poll() is None and not (payload / 'preparing').exists()
        except BaseException:
            process.terminate()
            process.wait(timeout=10)
            raise
    try:
        deadline = time.monotonic() + 10
        while not (payload / 'preparing').exists():
            assert process.poll() is None and time.monotonic() < deadline
            time.sleep(0.05)
        with pytest.raises(DesktopInstallInProgress):
            with probe_firmware_transfer():
                pytest.fail('Firmware started during installation')
    finally:
        hold.unlink()
        process.wait(timeout=15)
    assert process.returncode == 0 and (payload / 'completed').exists()
    with probe_firmware_transfer():
        pass


def test_installer_waits_for_normal_backend_release(installer):
    output, payload = installer
    with deny_writes(payload / 'mklink-sidecar.exe') as release:
        timer = threading.Timer(1.0, release)
        timer.start()
        try:
            assert run_gate(output).returncode == 0
        finally:
            timer.cancel()
            timer.join()
    assert (payload / 'completed').exists()


def test_installer_blocks_before_any_payload_write_when_busy(installer):
    output, payload = installer
    with deny_writes(payload / 'mklink-sidecar.exe'):
        assert run_gate(output).returncode == 2
    assert not (payload / 'completed').exists()
    assert (payload / 'mklink-sidecar.exe').read_bytes() == b'existing version'

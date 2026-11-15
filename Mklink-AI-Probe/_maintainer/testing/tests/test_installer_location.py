"""Execute the shipping NSIS resolver with isolated registry namespaces.

Both fixture hives are mapped to distinct HKCU keys so these tests never need
elevation or alter a real installation. Production defaults remain HKCU/HKLM.
"""
import os
from pathlib import Path
import subprocess
import uuid

import pytest
from test_installer_file_checks import MAKENSIS, ROOT

pytestmark = pytest.mark.skipif(os.name != 'nt' or not MAKENSIS.is_file(), reason='Windows NSIS required')


@pytest.fixture
def migration(tmp_path):
    import winreg
    base = 'Software\\MKLinkInstallerTests\\' + uuid.uuid4().hex
    keys = [base + '\\' + name for name in ('User', 'UserUninstall', 'Machine', 'MachineUninstall')]
    output = tmp_path / 'resolve.exe'
    script = tmp_path / 'resolve.nsi'
    script.write_text(f'''Unicode true
Name "MKLink migration fixture"
OutFile "{output}"
RequestExecutionLevel user
SilentInstall silent
InstallDir "placeholder"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!define MKLINK_PRODUCT_KEY "{keys[0]}"
!define MKLINK_UNINSTALL_KEY "{keys[1]}"
!define MKLINK_MACHINE_HIVE HKCU
!define MKLINK_MACHINE_PRODUCT_KEY "{keys[2]}"
!define MKLINK_MACHINE_UNINSTALL_KEY "{keys[3]}"
!include "{ROOT / 'gui/src-tauri/installer-location.nsh'}"
Function .onInit
  SetRegView 64
  ${{If}} $INSTDIR == "placeholder"
    StrCpy $INSTDIR "$EXEDIR\\default"
  ${{EndIf}}
  Call MklinkResolveInstallLocation
FunctionEnd
Section
  ${{GetOptions}} $CMDLINE "/CHOOSE" $0
  ${{IfNot}} ${{Errors}}
    StrCpy $INSTDIR "$EXEDIR\\chosen in GUI"
  ${{EndIf}}
  Call MklinkResolveInstallLocation
  FileOpen $0 "$EXEDIR\\result.txt" w
  FileWriteUTF16LE $0 "$INSTDIR$\\r$\\n$MklinkPreviousUserDir$\\r$\\n$MklinkPreviousMachineDir"
  FileClose $0
SectionEnd
''', encoding='utf-8-sig')
    build = subprocess.run([str(MAKENSIS), str(script)], capture_output=True, timeout=30)
    assert build.returncode == 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace')

    def seed(scope, path, *, uninstall=False, stale=False):
        if not stale:
            path.mkdir(parents=True, exist_ok=True)
            (path / 'mklink-ai-probe.exe').write_bytes(b'fixture')
        index = (0 if scope == 'user' else 2) + int(uninstall)
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, keys[index], 0,
                               winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY) as key:
            winreg.SetValueEx(key, 'InstallLocation' if uninstall else '', 0, winreg.REG_SZ,
                             f'"{path}"' if uninstall else str(path))

    def run(*args, directory=None):
        # /D must be the last, unquoted NSIS argument, including paths with spaces.
        command = subprocess.list2cmdline([str(output), *args])
        if directory is not None:
            command += ' /D=' + str(directory)
        result = subprocess.run(command, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0
        return (tmp_path / 'result.txt').read_text(encoding='utf-16-le').splitlines()

    try:
        yield seed, run
    finally:
        for key in keys + [base]:
            try:
                winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, key, winreg.KEY_WOW64_64KEY)
            except FileNotFoundError:
                pass


def test_machine_only_upgrade_retains_original_nondefault_path(migration, tmp_path):
    seed, run = migration
    original = tmp_path / 'original drive' / '安装目录'
    seed('machine', original)
    assert run('/UPDATE', '/P')[0] == str(original)


def test_repairs_duplicate_user_install_by_updating_the_original_path(migration, tmp_path):
    seed, run = migration
    original, duplicate = tmp_path / 'original', tmp_path / 'accidental copy'
    seed('machine', original)
    seed('user', duplicate)
    assert run('/UPDATE') == [str(original), str(duplicate), str(original)]


def test_explicit_directory_and_gui_choice_are_not_overridden(migration, tmp_path):
    seed, run = migration
    seed('machine', tmp_path / 'original')
    explicit = tmp_path / 'explicit destination with spaces'
    assert run('/UPDATE', directory=explicit)[0] == str(explicit)
    assert run('/CHOOSE')[0] == str(tmp_path / 'chosen in GUI')


def test_user_install_and_quoted_uninstall_record(migration, tmp_path):
    seed, run = migration
    original = tmp_path / 'user install'
    seed('user', original, uninstall=True)
    assert run()[0] == str(original)


def test_stale_machine_registration_does_not_hide_valid_user_install(migration, tmp_path):
    seed, run = migration
    original = tmp_path / 'user install'
    seed('user', original)
    seed('machine', tmp_path / 'removed install', stale=True)
    assert run()[0] == str(original)


def test_fresh_install_keeps_current_user_default(migration, tmp_path):
    _, run = migration
    assert run()[0] == str(tmp_path / 'default')

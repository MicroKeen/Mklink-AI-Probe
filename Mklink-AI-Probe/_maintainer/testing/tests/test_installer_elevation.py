"""Execute NSIS relaunch/path/account/exit handling without requesting UAC.

The sole substitution is ShellExecute's verb (open rather than runas). Real
protected-directory/UAC acceptance is performed with the packaged installer.
"""
import ctypes
import os
import subprocess

import pytest

from test_installer_file_checks import MAKENSIS, ROOT

pytestmark = pytest.mark.skipif(os.name != 'nt' or not MAKENSIS.is_file(), reason='Windows NSIS required')


@pytest.fixture
def relaunch(tmp_path):
    if ctypes.windll.shell32.IsUserAnAdmin():
        pytest.skip('Relaunch is deliberately disabled for elevated callers')
    output = tmp_path / 'relaunch.exe'
    script = tmp_path / 'relaunch.nsi'
    script.write_text(f'''Unicode true
Name "MKLink relaunch qualification"
OutFile "{output}"
RequestExecutionLevel user
SilentInstall silent
!include "LogicLib.nsh"
!define MKLINK_ELEVATION_VERB "open"
!include "{ROOT / 'gui/src-tauri/installer-elevation.nsh'}"
Section
  Call MklinkCheckElevationUser
  ${{GetOptions}} $CMDLINE "/MKLINK-ORIGINAL-USER=" $0
  ${{IfNot}} ${{Errors}}
    FileOpen $0 "$EXEDIR\\child.txt" w
    FileWriteUTF16LE $0 "$INSTDIR$\\r$\\n$CMDLINE$\\r$\\n$MklinkElevationUser"
    FileClose $0
    ${{GetOptions}} $CMDLINE "/RESULT=" $0
    SetErrorLevel $0
    Quit
  ${{EndIf}}
  ; Bound fixture recursion even if a regression prevents marker parsing.
  IfFileExists "$EXEDIR\\started.txt" bad_relaunch
  FileOpen $0 "$EXEDIR\\started.txt" w
  FileClose $0
  ${{GetOptions}} $CMDLINE "/CHOOSE" $0
  ${{IfNot}} ${{Errors}}
    StrCpy $INSTDIR "$EXEDIR\\chosen 中文 directory"
  ${{EndIf}}
  Call MklinkTryElevatedInstall
  ; A successful launch never returns here, even if the child fails.
  FileOpen $0 "$EXEDIR\\unexpected-parent-write.txt" w
  FileClose $0
  SetErrorLevel 99
  Quit
  bad_relaunch:
  SetErrorLevel 98
SectionEnd
''', encoding='utf-8-sig')
    build = subprocess.run([str(MAKENSIS), str(script)], capture_output=True, timeout=30)
    assert build.returncode == 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace')

    def run(*args, directory=None):
        # NSIS uses its own /FLAG="value" syntax, not CommandLineToArgvW's
        # backslash-escaped nested quotation convention.
        command = subprocess.list2cmdline([str(output)]) + ' ' + ' '.join(args)
        if directory is not None:
            command += ' /D=' + str(directory)
        result = subprocess.run(command, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        child = tmp_path / 'child.txt'
        assert not (tmp_path / 'unexpected-parent-write.txt').exists()
        return result.returncode, child.read_text('utf-16-le').splitlines() if child.exists() else []
    return run


@pytest.mark.parametrize('exit_code', [0, 2, 1223])
def test_preserves_directory_flags_and_child_result(relaunch, tmp_path, exit_code):
    directory = tmp_path / "existing 中文 user's install with spaces"
    result, lines = relaunch('/S', '/UPDATE', '/P', '/NS', '/R', '/ARGS="space and apostrophe\'s"', f'/RESULT={exit_code}', directory=directory)
    assert result == exit_code
    assert lines[0] == str(directory)
    assert lines[2] and '\\' in lines[2]
    for flag in ['/S', '/UPDATE', '/P', '/NS', '/R']:
        assert flag in lines[1]


def test_uses_current_directory_page_selection(relaunch, tmp_path):
    result, lines = relaunch('/CHOOSE', '/RESULT=0', directory=tmp_path / 'original')
    assert result == 0
    assert lines[0] == str(tmp_path / 'chosen 中文 directory')


def test_rejects_a_different_account_before_payload_write(relaunch):
    result, lines = relaunch('/MKLINK-ORIGINAL-USER=other-account')
    assert result == 5
    assert lines == []

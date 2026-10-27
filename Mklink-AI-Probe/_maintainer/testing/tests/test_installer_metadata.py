"""Execute the shipping NSIS cleanup, including real Win32 locks and junctions."""
import os
from pathlib import Path
import subprocess

import pytest
from test_installer_file_checks import MAKENSIS, ROOT, deny_writes, run_gate

pytestmark = pytest.mark.skipif(os.name != 'nt' or not MAKENSIS.is_file(), reason='Windows NSIS required')


@pytest.fixture
def installer(tmp_path):
    output = tmp_path / 'cleanup.exe'
    script = tmp_path / 'cleanup.nsi'
    script.write_text(f'''Unicode true
Name "MKLink metadata cleanup test"
OutFile "{output}"
RequestExecutionLevel user
SilentInstall silent
!include "LogicLib.nsh"
!include "{ROOT / 'gui/src-tauri/installer-metadata.nsh'}"
Section
  StrCpy $INSTDIR "$EXEDIR\\payload"
  Call MklinkCleanDistributionMetadata
  CreateDirectory "$INSTDIR\\_internal\\mklink.egg-info"
  FileOpen $0 "$INSTDIR\\_internal\\mklink.egg-info\\PKG-INFO" w
  FileWrite $0 "Name: mklink$\\nVersion: 9.8.7$\\n"
  FileClose $0
  FileOpen $0 "$INSTDIR\\completed" w
  FileClose $0
SectionEnd
''', encoding='utf-8-sig')
    build = subprocess.run([str(MAKENSIS), str(script)], capture_output=True, timeout=30)
    assert build.returncode == 0, build.stdout.decode(errors='replace')
    return output, tmp_path / 'payload'


def seed(root, name, content=b'old'):
    target = root / '_internal' / name / 'METADATA'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def test_clean_install_and_repeat_upgrade(installer):
    output, root = installer
    for _ in range(2):
        assert run_gate(output).returncode == 0
        assert 'Version: 9.8.7' in (root / '_internal/mklink.egg-info/PKG-INFO').read_text()


def test_removes_old_versions_but_preserves_other_packages_and_user_data(installer):
    output, root = installer
    old = [seed(root, name) for name in ['mklink-0.3.6.dist-info', 'mklink-0.4.1.dist-info',
                                       'mklink.egg-info', 'mklink-0.1.0.egg-info']]
    kept = [seed(root, name) for name in ['mklink-helper-1.0.dist-info', 'fastmcp-2.0.dist-info',
                                        'mklink-backup', 'mklink']]
    user = root / 'user-settings.json'
    user.write_bytes(b'{"preserve":true}')
    assert run_gate(output).returncode == 0
    assert all(not path.exists() for path in old)
    assert all(path.read_bytes() == b'old' for path in kept)
    assert user.read_bytes() == b'{"preserve":true}'


@pytest.mark.parametrize('obstacle', ['locked', 'readonly', 'nested'])
def test_preflight_blocks_all_changes_when_metadata_is_unsafe(installer, obstacle):
    output, root = installer
    first = seed(root, 'mklink-0.1.dist-info')
    blocked = seed(root, 'mklink-0.3.6.dist-info')
    if obstacle == 'nested':
        (blocked.parent / 'unexpected').mkdir()
    if obstacle == 'readonly':
        blocked.chmod(0o444)
    try:
        if obstacle == 'locked':
            with deny_writes(blocked):
                assert run_gate(output).returncode == 3
        else:
            assert run_gate(output).returncode == 3
        assert first.read_bytes() == blocked.read_bytes() == b'old'
        assert not (root / 'completed').exists()
    finally:
        blocked.chmod(0o666)


@pytest.mark.parametrize('location', ['root', 'internal', 'metadata', 'child'])
def test_never_follows_junctions(installer, tmp_path, location):
    output, root = installer
    external = tmp_path / 'external'
    external.mkdir()
    sentinel = external / 'METADATA'
    sentinel.write_bytes(b'outside payload')
    junction = {'root': root, 'internal': root / '_internal',
                'metadata': root / '_internal/mklink-0.3.6.dist-info',
                'child': root / '_internal/mklink-0.3.6.dist-info/nested'}[location]
    junction.parent.mkdir(parents=True, exist_ok=True)
    # One shell creates one explicitly bounded test junction; os.rmdir removes
    # only the link in finally, never a recursive deletion of its destination.
    script = tmp_path / 'junction.ps1'
    script.write_text(f"New-Item -ItemType Junction -Path '{junction}' -Target '{external}' | Out-Null", encoding='utf-8')
    subprocess.run(['pwsh', '-NoProfile', '-File', str(script)], check=True, capture_output=True)
    try:
        assert run_gate(output).returncode == 3
        assert sentinel.read_bytes() == b'outside payload'
        assert not (root / 'completed').exists()
    finally:
        os.rmdir(junction)


def test_cleanup_is_after_file_gate_and_before_payload():
    hooks = (ROOT / 'gui/src-tauri/installer-hooks.nsh').read_text('utf-8')
    preinstall = hooks.split('!macro NSIS_HOOK_PREINSTALL', 1)[1].split('!macroend', 1)[0]
    assert preinstall.index('Call MklinkWaitForUpgradeFiles') < preinstall.index('Call MklinkCleanDistributionMetadata')

"""Run the shipping PowerShell helper against isolated legacy process fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
PS = Path(os.environ.get('SystemRoot', 'C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
HELPER = ROOT/'gui/src-tauri/installer-prepare.ps1'
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows installer')


def run_ps(tmp_path, code):
    script = tmp_path/'check.ps1'
    script.write_text(f". '{HELPER}' -InstallDir '{tmp_path}'\n"+code, encoding='utf-8-sig')
    result = subprocess.run([str(PS), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', str(script)], capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, (result.stdout, result.stderr)
    return result.stdout.decode('utf-8-sig').strip()


def test_process_entrypoint_matching_does_not_match_incidental_text(tmp_path):
    cases = [
        ('mklink-ai-probe.exe', '', True), ('mklink-sidecar.exe', '', True), ('mklink.exe', '', True),
        ('python.exe', 'python -m mklink mcp', True),
        ('pythonw.exe', '"C:/Program Files/Python/pythonw.exe" -u -m mklink runtime serve', True),
        ('python3.12.exe', 'python -X utf8 -m mklink.cli web', True),
        ('py.exe', 'py -m mklink.mcp_server', True),
        ('python.exe', 'python "C:/old skill/mklink/__main__.py" mcp', True),
        ('python.exe', r'python C:\skill\mklink\mcp_server.py', True),
        ('python.exe', 'python -m mklink_other', False),
        ('python.exe', 'python -m pytest mklink', False),
        ('python.exe', 'python unrelated.py -m mklink', False),
        ('python.exe', 'python -c "print(\' -m mklink \')"', False),
        ('codex.exe', 'codex exec python -m mklink', False),
        ('powershell.exe', 'powershell -File installer-prepare.ps1', False),
        ('python.exe', 'python "C:/unrelated/mklink/__main__.py.bak"', False),
        ('msedgewebview2.exe', '', False), ('mklink-user-tool.exe', '', False),
    ]
    data = [{'Name': name, 'CommandLine': command} for name, command, _ in cases]
    (tmp_path/'cases.json').write_text(json.dumps(data), encoding='utf-8')
    actual = json.loads(run_ps(tmp_path, f"@(foreach ($entry in (Get-Content -Raw '{tmp_path}/cases.json' | ConvertFrom-Json)) {{ Test-MklinkProcess $entry }}) | ConvertTo-Json"))
    assert actual == [expected for _, _, expected in cases]


@pytest.fixture
def processes(tmp_path):
    children = []
    def start(args, **kwargs):
        p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW, **kwargs)
        children.append(p)
        return p
    yield start
    for p in children:
        if p.poll() is None: p.terminate() # Only this test's fixture processes.
        p.wait(timeout=5)


def test_terminates_native_and_legacy_skill_without_backend_api(tmp_path, processes):
    native = []
    for name in ('mklink-ai-probe.exe', 'mklink-sidecar.exe', 'mklink.exe'):
        exe = tmp_path/name
        shutil.copyfile(Path(os.environ['SystemRoot'])/'System32/ping.exe', exe)
        native.append(processes([str(exe), '-t', '127.0.0.1']))
    module = tmp_path/'mklink'
    module.mkdir()
    (module/'__init__.py').write_text('', encoding='utf-8')
    (module/'__main__.py').write_text('import time; time.sleep(120)', encoding='utf-8')
    # No HTTP endpoints and no version reporting: mimic old Skill/MCP processes.
    skill = processes([sys.executable, '-m', 'mklink', 'mcp'], cwd=tmp_path,
                      env={**os.environ, 'PYTHONPATH': str(tmp_path)})
    unrelated = processes([sys.executable, '-c', 'import time; time.sleep(120)', '-m', 'mklink'])
    all_pids = [p.pid for p in native]+[skill.pid, unrelated.pid]
    inventory = ','.join(map(str, all_pids))
    # Constrain inventory to fixture PIDs. Selection, owner check, creation-time
    # check and termination are the actual production functions.
    run_ps(tmp_path, rf'''
function Get-CimInstance {{
    CimCmdlets\Get-CimInstance Win32_Process |
        Where-Object {{ $_.ProcessId -in @({inventory}) }}
}}
Stop-MklinkForInstall
''')
    for p in native+[skill]: assert p.wait(timeout=5) != 0
    assert unrelated.poll() is None


def test_reused_pid_is_not_terminated(tmp_path, processes):
    survivor = processes([sys.executable, '-c', 'import time; time.sleep(120)'])
    run_ps(tmp_path, f'''
$entry = Get-CimInstance Win32_Process -Filter 'ProcessId={survivor.pid}' | Select-Object ProcessId,CreationDate
$entry.CreationDate = $entry.CreationDate.AddMinutes(-1)
Stop-MklinkProcess $entry
''')
    assert survivor.poll() is None


def test_other_user_processes_are_excluded(tmp_path):
    output = run_ps(tmp_path, '''
function Get-CimInstance { [pscustomobject]@{Name='mklink.exe'; ProcessId=123; ParentProcessId=1; CreationDate=[datetime]::Now} }
function Invoke-CimMethod { [pscustomobject]@{Sid='S-1-5-21-unrelated-user'} }
@(Get-MklinkProcesses).Count
''')
    assert output == '0'

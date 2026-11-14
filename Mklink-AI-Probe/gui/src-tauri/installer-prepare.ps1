# Windows PowerShell 5.1 compatible; no installed Python/backend API required.
param([Parameter(Mandatory)][string]$InstallDir)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

function Test-MklinkProcess($Entry) {
    if ($Entry.Name -in @('mklink-ai-probe.exe', 'mklink-sidecar.exe', 'mklink.exe')) { return $true }
    if ($Entry.Name -notmatch '^(pythonw?|pythonw?3(?:\.\d+)?t?|py)\.exe$') { return $false }
    # Match the Python entry point, never a filename mentioned later in a
    # command, an arbitrary Python process, or the Codex/Claude parent process.
    $command = [string]$Entry.CommandLine
    $python = '^(?:"[^"]+"|\S+)\s+(?:(?:-[BEIsSux]+|-X\s+\S+|-W\s+\S+)\s+)*'
    return ($command -match ($python + '-m\s+"?mklink(?:\.(?:cli|mcp_server))?"?(?:\s|$)') -or
        $command -match ($python + '(?:"[^"\r\n]*[\\/]mklink[\\/](?:__main__|cli|mcp_server)\.py"|[^\s"]*[\\/]mklink[\\/](?:__main__|cli|mcp_server)\.py)(?:\s|$)'))
}

function Get-MklinkProcesses {
    $all = @(Get-CimInstance Win32_Process)
    $selected = @{}
    foreach ($entry in $all) {
        if (Test-MklinkProcess $entry) { $selected[[int]$entry.ProcessId] = $entry }
    }
    # WebView children can keep payload files open. Only include descendants
    # of identified MKLink processes, never an unrelated browser window.
    do {
        $added = $false
        foreach ($entry in $all) {
            $parent = $selected[[int]$entry.ParentProcessId]
            if ($entry.Name -eq 'msedgewebview2.exe' -and $parent -and
                $entry.CreationDate -ge $parent.CreationDate -and
                -not $selected.ContainsKey([int]$entry.ProcessId)) {
                $selected[[int]$entry.ProcessId] = $entry
                $added = $true
            }
        }
    } while ($added)
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    foreach ($entry in $selected.Values) {
        $owner = Invoke-CimMethod -InputObject $entry -MethodName GetOwnerSid -ErrorAction SilentlyContinue
        if ($owner.Sid -eq $sid) { $entry }
    }
}

function Stop-MklinkProcess($Entry) {
    $process = Get-Process -Id $Entry.ProcessId -ErrorAction SilentlyContinue
    if (-not $process) { return }
    try {
        # Verify creation time on the opened process handle before termination;
        # a reused PID is not evidence of MKLink ownership.
        $null = $process.Handle
        if ([Math]::Abs(($process.StartTime.ToUniversalTime() - $Entry.CreationDate.ToUniversalTime()).TotalMilliseconds) -ge 1) { return }
        $process.Kill()
        if (-not $process.WaitForExit(5000)) { throw 'MKLink did not exit in time.' }
    } catch {
        if (-not $process.HasExited) { throw }
    } finally { $process.Dispose() }
}

function Stop-MklinkForInstall {
    # Installing explicitly ends current MKLink work, regardless of version.
    # Repeat for launcher/child races; never terminate the AI host.
    for ($attempt = 0; $attempt -lt 3; $attempt++) {
        $entries = @(Get-MklinkProcesses)
        if (-not $entries.Count) { return }
        foreach ($entry in ($entries | Sort-Object CreationDate)) { Stop-MklinkProcess $entry }
    }
    if (@(Get-MklinkProcesses).Count) { throw 'An MKLink client keeps restarting its backend. Pause that client and Retry.' }
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        Stop-MklinkForInstall
        Write-Output 'Previous MKLink desktop and Skill/MCP processes were terminated for installation.'
        exit 0
    } catch {
        Write-Output ('Cannot close the previous MKLink process: ' + $_.Exception.Message)
        exit 2
    }
}

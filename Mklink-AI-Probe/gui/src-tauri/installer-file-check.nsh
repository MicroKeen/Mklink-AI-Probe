; Check the actual installation files before replacing or deleting any payload.
; Installation ends current-user MKLink work, including legacy Skill/MCP.
; Retain the file gate for permissions and unrelated processes holding files.
Var MklinkBlockedFile
Var MklinkFileError
Var MklinkPrepareMessage
!ifndef MKLINK_PREPARE_SCRIPT
  !define MKLINK_PREPARE_SCRIPT "${__FILEDIR__}\installer-prepare.ps1"
!endif

!macro MKLINK_INSPECT_FILE FILE
  ${If} ${FileExists} "$INSTDIR\${FILE}"
    ; GENERIC_WRITE, share all, OPEN_EXISTING: no truncation or data changes.
    System::Call 'kernel32::CreateFileW(w "$INSTDIR\${FILE}", i 0x40000000, i 7, p 0, i 3, i 0x80, p 0) p .r0 ?e'
    Pop $MklinkFileError
    ${If} $0 == -1
      StrCpy $MklinkBlockedFile "$INSTDIR\${FILE}"
      Goto inspected
    ${EndIf}
    System::Call 'kernel32::CloseHandle(p r0)'
  ${EndIf}
!macroend

!macro MKLINK_DEFINE_FILE_CHECK PREFIX
Function ${PREFIX}MklinkInspectUpgradeFiles
  Push $0
  StrCpy $MklinkBlockedFile ""
  !insertmacro MKLINK_INSPECT_FILE "mklink-ai-probe.exe"
  !insertmacro MKLINK_INSPECT_FILE "mklink-sidecar.exe"
  !insertmacro MKLINK_INSPECT_FILE "mklink-stcp.dll"
  inspected:
  Pop $0
FunctionEnd

Function ${PREFIX}MklinkWaitForUpgradeFiles
  Push $0
  retry:
  !if "${PREFIX}" == ""
    InitPluginsDir
    Push $OUTDIR
    SetOutPath "$PLUGINSDIR"
    File /oname=mklink-installer-prepare.ps1 "${MKLINK_PREPARE_SCRIPT}"
    Pop $0
    SetOutPath "$0"
    nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\mklink-installer-prepare.ps1" -InstallDir "$INSTDIR"'
    Pop $0
    Pop $MklinkPrepareMessage
    ${If} $0 != 0
      DetailPrint "$MklinkPrepareMessage"
      IfSilent blocked
      MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "无法结束旧 MKLink 进程。请检查进程权限或重启旧后台的客户端后重试。$\r$\n$\r$\nCould not terminate the old MKLink process. Check permissions or the client restarting it, then Retry.$\r$\n$\r$\n$MklinkPrepareMessage" /SD IDCANCEL IDRETRY retry
      Goto blocked
    ${EndIf}
  !endif
  StrCpy $0 0
  inspect:
  Call ${PREFIX}MklinkInspectUpgradeFiles
  ${If} $MklinkBlockedFile == ""
    Goto ready
  ${EndIf}
  ; Tolerate delayed DLL release and short antivirus scans after termination.
  ${If} $0 < 60
    IntOp $0 $0 + 1
    Sleep 250
    Goto inspect
  ${EndIf}
  DetailPrint "MKLink file is not writable: $MklinkBlockedFile (Windows error $MklinkFileError)"
  IfSilent blocked
  MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "MKLink files remain in use or inaccessible. Check the directory permissions or other software holding the file, then Retry.$\r$\n$\r$\n文件仍被占用或目录无法写入，请检查目录权限或其他占用文件的软件后重试。$\r$\n$\r$\n$MklinkBlockedFile$\r$\nWindows error: $MklinkFileError" /SD IDCANCEL IDRETRY retry
  blocked:
  SetErrorLevel 2
  Abort "MKLink files are still in use or inaccessible. No new payload was written."
  ready:
  Pop $0
FunctionEnd
!macroend

!insertmacro MKLINK_DEFINE_FILE_CHECK ""
!insertmacro MKLINK_DEFINE_FILE_CHECK "un."

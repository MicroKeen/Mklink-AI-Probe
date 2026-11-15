; Resolve upgrades across the former perMachine and currentUser scopes.
; Keep explicit /D and the directory-page choice. Never silently migrate a
; protected legacy installation to a second directory.
!ifndef MKLINK_PRODUCT_KEY
  !define MKLINK_PRODUCT_KEY "Software\microkeen\Mklink AI Probe"
!endif
!ifndef MKLINK_UNINSTALL_KEY
  !define MKLINK_UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Mklink AI Probe"
!endif
!ifndef MKLINK_MACHINE_HIVE
  !define MKLINK_MACHINE_HIVE HKLM
!endif
!ifndef MKLINK_MACHINE_PRODUCT_KEY
  !define MKLINK_MACHINE_PRODUCT_KEY "${MKLINK_PRODUCT_KEY}"
!endif
!ifndef MKLINK_MACHINE_UNINSTALL_KEY
  !define MKLINK_MACHINE_UNINSTALL_KEY "${MKLINK_UNINSTALL_KEY}"
!endif

Var MklinkInstallLocationResolved
Var MklinkPreviousUserDir
Var MklinkPreviousMachineDir

!macro MKLINK_READ_INSTALL_DIR OUT HIVE PRODUCT UNINSTALL
  ReadRegStr ${OUT} ${HIVE} "${PRODUCT}" ""
  ${IfNot} ${FileExists} "${OUT}\mklink-ai-probe.exe"
    ReadRegStr ${OUT} ${HIVE} "${UNINSTALL}" "InstallLocation"
  ${EndIf}
  ; Tauri's uninstall record quotes InstallLocation.
  StrCpy $0 ${OUT} 1
  ${If} $0 == '$\"'
    StrCpy ${OUT} ${OUT} -1 1
  ${EndIf}
  ${IfNot} ${FileExists} "${OUT}\mklink-ai-probe.exe"
    StrCpy ${OUT} ""
  ${EndIf}
!macroend

Function MklinkResolveInstallLocation
  ${If} $MklinkInstallLocationResolved == 1
    Return
  ${EndIf}
  StrCpy $MklinkInstallLocationResolved 1
  Push $0
  !insertmacro MKLINK_READ_INSTALL_DIR $MklinkPreviousUserDir HKCU "${MKLINK_PRODUCT_KEY}" "${MKLINK_UNINSTALL_KEY}"
  !insertmacro MKLINK_READ_INSTALL_DIR $MklinkPreviousMachineDir ${MKLINK_MACHINE_HIVE} "${MKLINK_MACHINE_PRODUCT_KEY}" "${MKLINK_MACHINE_UNINSTALL_KEY}"
  ; NSIS consumes /D before exposing $CMDLINE. Read the original command line
  ; solely to detect this explicit override; NSIS already parsed its path.
  System::Call 'kernel32::GetCommandLineW() w .r0'
  ClearErrors
  ${GetOptions} $0 "/D=" $0
  ${If} ${Errors}
    ; A surviving machine installation is the original launch location,
    ; including after an earlier updater accidentally created a user copy.
    ${If} $MklinkPreviousMachineDir != ""
      StrCpy $INSTDIR $MklinkPreviousMachineDir
    ${ElseIf} $MklinkPreviousUserDir != ""
      StrCpy $INSTDIR $MklinkPreviousUserDir
    ${EndIf}
  ${EndIf}
  ClearErrors
  Pop $0
FunctionEnd

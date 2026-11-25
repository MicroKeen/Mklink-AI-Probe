; Keep fresh/current-user installs unelevated. Relaunch this exact installer
; only after ERROR_ACCESS_DENIED, retaining NSIS flags and the selected path.
!include "FileFunc.nsh"
!ifndef MKLINK_ELEVATION_VERB
  !define MKLINK_ELEVATION_VERB "runas"
!endif
Var MklinkElevationArgs
Var MklinkElevationUser
Var MklinkElevationResult

Function MklinkGetElevationUser
  Push $0
  ; SAM-compatible DOMAIN\User, including local accounts; do not silently
  ; install HKCU settings/shortcuts under a different administrator account.
  System::Call 'secur32::GetUserNameExW(i 2, w .s, *i ${NSIS_MAX_STRLEN}) i .r0'
  Pop $MklinkElevationUser
  ${If} $0 == 0
    StrCpy $MklinkElevationUser ""
  ${EndIf}
  Pop $0
FunctionEnd

Function MklinkCheckElevationUser
  Push $0
  ${GetOptions} $CMDLINE "/MKLINK-ORIGINAL-USER=" $0
  ${IfNot} ${Errors}
    Call MklinkGetElevationUser
    ${If} $0 == ""
    ${OrIf} $0 != $MklinkElevationUser
      IfSilent +2
      MessageBox MB_OK|MB_ICONSTOP "请使用当前 Windows 用户确认管理员权限。使用其他账户会改变用户配置和快捷方式，本次安装已停止。$\r$\n$\r$\nConfirm elevation with the original Windows account. Installation stopped to preserve that user's settings and shortcuts."
      SetErrorLevel 5
      Quit
    ${EndIf}
  ${EndIf}
  ClearErrors
  Pop $0
FunctionEnd

Function MklinkTryElevatedInstall
  Push $0
  Push $1
  Push $2
  ${GetOptions} $CMDLINE "/MKLINK-ORIGINAL-USER=" $0
  ${IfNot} ${Errors}
    ; A relaunched installer never requests elevation again, even if Windows
    ; did not grant a full administrator token.
    Goto done
  ${EndIf}
  ClearErrors
  ; Already elevated: access denial is an ACL/read-only/security-product
  ; problem. Do not loop through UAC or change any directory permissions.
  System::Call 'shell32::IsUserAnAdmin() i .r0'
  ${If} $0 != 0
    Goto done
  ${EndIf}
  Call MklinkGetElevationUser
  ${If} $MklinkElevationUser == ""
    Goto done
  ${EndIf}
  ${GetParameters} $MklinkElevationArgs
  StrLen $0 $MklinkElevationArgs
  StrLen $1 $INSTDIR
  StrLen $2 $MklinkElevationUser
  IntOp $0 $0 + $1
  IntOp $0 $0 + $2
  IntOp $0 $0 + 40
  ${If} $0 >= ${NSIS_MAX_STRLEN}
    ; Never truncate the selected directory into a different valid path.
    Goto done
  ${EndIf}
  ; NSIS removes /D from CMDLINE/GetParameters. Always supply the resolved
  ; directory last, unquoted, as required by NSIS (also paths with spaces).
  StrCpy $MklinkElevationArgs '/MKLINK-ORIGINAL-USER="$MklinkElevationUser" $MklinkElevationArgs /D=$INSTDIR'
  !if ${NSIS_PTR_SIZE} > 4
    !define MKLINK_SHELLEXEC_SIZE 112
  !else
    !define MKLINK_SHELLEXEC_SIZE 60
  !endif
  ; SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC. Wait for the actual child and
  ; return its exit status; the outer installer must never write a second copy.
  StrCpy $1 $EXEPATH
  StrCpy $2 $MklinkElevationArgs
  System::Call '*(&i${MKLINK_SHELLEXEC_SIZE}) p .r0'
  ; Pass arguments through registers, not interpolated System syntax: command
  ; lines can contain both quote styles and must remain literal data.
  System::Call '*$0(i ${MKLINK_SHELLEXEC_SIZE}, i 0x140, p $HWNDPARENT, t "${MKLINK_ELEVATION_VERB}", t r1, t r2, p 0, i 1) p .r0'
  System::Call 'shell32::ShellExecuteExW(p r0) i .r1 ?e'
  Pop $MklinkElevationResult
  ${If} $1 == 0
    System::Free $0
    ; A cancelled UAC prompt is a cancellation, not successful installation.
    ${If} $MklinkElevationResult == 1223
      SetErrorLevel 1223
      Quit
    ${EndIf}
    Goto done
  ${EndIf}
  System::Call '*$0(i, i, p, p, p, p, p, i, p, p, p, p, i, p, p .r1)'
  !ifdef MKLINK_INSTALLER_HAS_UPDATE_LOCK
    ; The elevated child acquires its own lock; the parent only waits from here.
    Call MklinkReleaseInstallLock
  !endif
  System::Free $0
  ShowWindow $HWNDPARENT 0
  wait:
    System::Call 'kernel32::WaitForSingleObject(p r1, i 0) i .r2'
    ${If} $2 == 258
      Sleep 250
      Goto wait
    ${EndIf}
  StrCpy $MklinkElevationResult 2
  System::Call 'kernel32::GetExitCodeProcess(p r1, *i .r2) i .r0'
  ${If} $0 != 0
    StrCpy $MklinkElevationResult $2
  ${EndIf}
  System::Call 'kernel32::CloseHandle(p r1)'
  SetErrorLevel $MklinkElevationResult
  Quit
  done:
  Pop $2
  Pop $1
  Pop $0
FunctionEnd

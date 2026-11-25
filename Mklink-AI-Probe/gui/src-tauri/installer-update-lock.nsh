; The updater exits as soon as it launches NSIS. Acquire the same first byte
; before stopping processes, and hold it until the replacement is complete.
!define MKLINK_INSTALLER_HAS_UPDATE_LOCK
!ifndef MKLINK_INSTALL_LOCK_DIR
  !define MKLINK_INSTALL_LOCK_DIR "$PROFILE\.mklink"
!endif
Var MklinkInstallLock

Function MklinkAcquireInstallLock
  ${If} $MklinkInstallLock != ""
    Return
  ${EndIf}
  Push $0
  Push $1
  Push $2
  CreateDirectory "${MKLINK_INSTALL_LOCK_DIR}"
  System::Call 'kernel32::CreateFileW(w "${MKLINK_INSTALL_LOCK_DIR}\desktop-install.lock", i 0xC0000000, i 7, p 0, i 4, i 0x80, p 0) p .r0 ?e'
  Pop $2
  ${If} $0 != -1
    DetailPrint "正在等待下载器固件升级或其他安装完成 / Waiting for any firmware update or other installation"
    acquire:
    System::Call 'kernel32::LockFile(p r0, i 0, i 0, i 1, i 0) i .r1 ?e'
    Pop $2
    ${If} $1 != 0
      StrCpy $MklinkInstallLock $0
      Goto acquired
    ${EndIf}
    ${If} $2 == 33
      Sleep 250
      Goto acquire
    ${EndIf}
    System::Call 'kernel32::CloseHandle(p r0)'
  ${EndIf}
  DetailPrint "Cannot prepare update lock: ${MKLINK_INSTALL_LOCK_DIR}\desktop-install.lock (Windows error $2)"
  IfSilent +2
  MessageBox MB_OK|MB_ICONSTOP "无法准备安装，请检查下列文件的访问权限。 / Check access to the update lock.$\r$\n${MKLINK_INSTALL_LOCK_DIR}\desktop-install.lock$\r$\nWindows error: $2"
  SetErrorLevel 2
  Quit
  acquired:
  Pop $2
  Pop $1
  Pop $0
FunctionEnd

Function MklinkReleaseInstallLock
  ${If} $MklinkInstallLock != ""
    System::Call 'kernel32::CloseHandle(p $MklinkInstallLock)'
    StrCpy $MklinkInstallLock ""
  ${EndIf}
FunctionEnd

; /UPDATE overlays files, leaving older dist-info ahead of current egg-info in
; importlib.metadata. Remove only MKLink's flat distribution records BEFORE
; extraction. Never recursively remove _internal, dependencies or user data.
Var MklinkMetadataError
Var MklinkMetadataPass

Function MklinkCleanDistributionMetadata
  Push $0
  Push $1
  Push $2
  Push $3
  Push $4
  Push $5
  StrCpy $MklinkMetadataError "$INSTDIR"
  System::Call 'kernel32::GetFileAttributesW(w "$INSTDIR") i .r0'
  ${If} $0 == -1
    Goto metadata_ready
  ${EndIf}
  IntOp $0 $0 & 0x400
  ${If} $0 != 0
    Goto metadata_failed
  ${EndIf}
  StrCpy $MklinkMetadataError "$INSTDIR\_internal"
  System::Call 'kernel32::GetFileAttributesW(w "$INSTDIR\_internal") i .r0'
  ${If} $0 == -1
    Goto metadata_ready
  ${EndIf}
  IntOp $0 $0 & 0x400
  ${If} $0 != 0
    Goto metadata_failed
  ${EndIf}
  ; Preflight every candidate before deleting any metadata. A locked file,
  ; junction, nested directory or read-only record blocks the upgrade safely.
  StrCpy $MklinkMetadataPass 0
  metadata_scan:
  FindFirst $1 $2 "$INSTDIR\_internal\mklink*"
  metadata_next:
  ${If} $2 == ""
    Goto metadata_scan_done
  ${EndIf}
  ${If} $2 == "mklink.egg-info"
    Goto metadata_candidate
  ${EndIf}
  StrCpy $0 $2 7
  ${If} $0 != "mklink-"
    Goto metadata_skip
  ${EndIf}
  ; A version starts with a digit. Do not match mklink-helper or similar
  ; independent distributions that share the prefix.
  StrCpy $0 $2 1 7
  ${If} $0 != "0"
  ${AndIf} $0 != "1"
  ${AndIf} $0 != "2"
  ${AndIf} $0 != "3"
  ${AndIf} $0 != "4"
  ${AndIf} $0 != "5"
  ${AndIf} $0 != "6"
  ${AndIf} $0 != "7"
  ${AndIf} $0 != "8"
  ${AndIf} $0 != "9"
    Goto metadata_skip
  ${EndIf}
  StrCpy $0 $2 "" -10
  ${If} $0 != ".dist-info"
    StrCpy $0 $2 "" -9
    ${If} $0 != ".egg-info"
      Goto metadata_skip
    ${EndIf}
  ${EndIf}
  metadata_candidate:
  StrCpy $MklinkMetadataError "$INSTDIR\_internal\$2"
  System::Call 'kernel32::GetFileAttributesW(w "$MklinkMetadataError") i .r0'
  IntOp $0 $0 & 0x411 ; directory required; reparse/read-only forbidden
  ${If} $0 != 16
    Goto metadata_close_failed
  ${EndIf}
  FindFirst $3 $4 "$INSTDIR\_internal\$2\*"
  metadata_file:
  ${If} $4 == ""
    Goto metadata_files_done
  ${EndIf}
  ${If} $4 == "."
  ${OrIf} $4 == ".."
    Goto metadata_file_next
  ${EndIf}
  StrCpy $MklinkMetadataError "$INSTDIR\_internal\$2\$4"
  System::Call 'kernel32::GetFileAttributesW(w "$MklinkMetadataError") i .r0'
  IntOp $0 $0 & 0x411
  ${If} $0 != 0
    Goto metadata_file_failed
  ${EndIf}
  ; DELETE access, share all, OPEN_EXISTING: inspect without modifying bytes.
  System::Call 'kernel32::CreateFileW(w "$MklinkMetadataError", i 0x10000, i 7, p 0, i 3, i 0x80, p 0) p .r5'
  ${If} $5 == -1
    Goto metadata_file_failed
  ${EndIf}
  System::Call 'kernel32::CloseHandle(p r5)'
  ${If} $MklinkMetadataPass == 1
    ClearErrors
    Delete "$MklinkMetadataError"
    IfErrors metadata_file_failed
  ${EndIf}
  metadata_file_next:
  FindNext $3 $4
  Goto metadata_file
  metadata_files_done:
  FindClose $3
  ${If} $MklinkMetadataPass == 1
    StrCpy $MklinkMetadataError "$INSTDIR\_internal\$2"
    ClearErrors
    RMDir "$MklinkMetadataError"
    IfErrors metadata_close_failed
    DetailPrint "Removed obsolete MKLink metadata: $2"
  ${EndIf}
  metadata_skip:
  FindNext $1 $2
  Goto metadata_next
  metadata_scan_done:
  FindClose $1
  ${If} $MklinkMetadataPass == 0
    StrCpy $MklinkMetadataPass 1
    Goto metadata_scan
  ${EndIf}
  Goto metadata_ready
  metadata_file_failed:
  FindClose $3
  metadata_close_failed:
  FindClose $1
  metadata_failed:
  DetailPrint "Cannot safely remove old MKLink metadata: $MklinkMetadataError"
  IfSilent +2
  MessageBox MB_OK|MB_ICONSTOP "Cannot safely clean old MKLink version metadata. Close MKLink clients and check folder permissions before retrying.$\r$\n无法安全清理旧版元数据。请关闭 MKLink 客户端并检查目录权限后重新安装。$\r$\n$MklinkMetadataError"
  SetErrorLevel 3
  Abort "MKLink metadata cleanup failed; new payload was not written."
  metadata_ready:
  Pop $5
  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Pop $0
FunctionEnd

!include "${__FILEDIR__}\installer-file-check.nsh"
!include "${__FILEDIR__}\installer-metadata.nsh"
!include "${__FILEDIR__}\installer-location.nsh"

; .onInit has restored the installed directory before MUI initializes its UI.
; Check before Tauri's maintenance page can launch an OLD uninstaller, whose
; pre-uninstall hook did not yet protect a shared backend. PREINSTALL repeats
; the check for silent /UPDATE and the final directory selected by the user.
!define MUI_CUSTOMFUNCTION_GUIINIT MklinkCheckBeforeMaintenance
Function MklinkCheckBeforeMaintenance
  Call MklinkCheckElevationUser
  Call MklinkResolveInstallLocation
  Push $0
  ${If} ${FileExists} "$INSTDIR\mklink-ai-probe.exe"
    Call MklinkWaitForUpgradeFiles
  ${EndIf}
  Pop $0
FunctionEnd

; Fresh installs stay unelevated. Protected legacy upgrades can request UAC
; for the same user; device registry changes remain an explicit Settings action.
Var MklinkLegacyInstallDir
Var MklinkShortcutFindHandle
Var MklinkShortcutName

!macro NSIS_HOOK_PREINSTALL
  Call MklinkCheckElevationUser
  ; GUIINIT is not called in silent mode. Resolve before replacing any files,
  ; and refresh OUTDIR because Tauri set it before invoking this hook.
  Call MklinkResolveInstallLocation
  SetOutPath "$INSTDIR"
  Call MklinkWaitForUpgradeFiles
  Call MklinkCleanDistributionMetadata
  ; Tauri owns uninstall/reinstall. In /UPDATE mode it deliberately overwrites
  ; in place and preserves shortcuts. Launching another uninstaller here races
  ; file extraction and deletes shortcuts which /UPDATE will not recreate.
  ; Keep other legacy files/registration; only our distribution metadata is
  ; removed above, before the new payload restores its current metadata.
  StrCpy $MklinkLegacyInstallDir $MklinkPreviousUserDir
!macroend

!macro MKLINK_RETARGET_LEGACY_SHORTCUT SHORTCUT
  ; Only retarget an existing shortcut to this product's old executable.
  ; Do not recreate shortcuts the user intentionally deleted or touch others.
  !insertmacro IsShortcutTarget "${SHORTCUT}" "$MklinkLegacyInstallDir\${MAINBINARYNAME}.exe"
  Pop $0
  ${If} $0 = 1
    !insertmacro SetShortcutTarget "${SHORTCUT}" "$INSTDIR\${MAINBINARYNAME}.exe"
  ${EndIf}
!macroend

!macro NSIS_HOOK_POSTINSTALL
  ; The new frozen helper uses ordinary user permissions, never opens hardware,
  ; and archives invalid job journals only after acquiring runtime owner locks.
  ; Valid history and all project/user settings are retained.
  nsExec::ExecToStack '"$INSTDIR\mklink-sidecar.exe" --internal-install-history-maintenance'
  Pop $0
  Pop $1
  ${If} $0 != 0
    DetailPrint "MKLink: task history maintenance was skipped or incomplete. Close all MKLink/Skill backends and rerun setup. Original records were retained; see installation-history-report.json in the runtime directory."
  ${Else}
    DetailPrint "MKLink: task history checked; invalid records were backed up before initialization."
  ${EndIf}

  ; Preserve existing current-user shortcuts when repair changes the location.
  ; Only retarget shortcuts which still point to this product's previous path.
  ${If} $MklinkLegacyInstallDir != ""
  ${AndIf} $MklinkLegacyInstallDir != $INSTDIR
    SetShellVarContext current
    !insertmacro MKLINK_RETARGET_LEGACY_SHORTCUT "$DESKTOP\${PRODUCTNAME}.lnk"
    !insertmacro MKLINK_RETARGET_LEGACY_SHORTCUT "$SMPROGRAMS\${PRODUCTNAME}.lnk"
    ; Existing pins may still refer to the accidental per-user installation.
    ; Tauri's shortcut helpers overwrite $0-$3. Keep enumeration in named vars.
    FindFirst $MklinkShortcutFindHandle $MklinkShortcutName "$APPDATA\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\*.lnk"
    ${DoWhile} $MklinkShortcutName != ""
      !insertmacro MKLINK_RETARGET_LEGACY_SHORTCUT "$APPDATA\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\$MklinkShortcutName"
      FindNext $MklinkShortcutFindHandle $MklinkShortcutName
    ${Loop}
    FindClose $MklinkShortcutFindHandle
    !insertmacro SetContext
  ${EndIf}

  ; Keep the portable HTML launcher cross-platform: Windows still uses the
  ; Python Web handler, while macOS/Linux use their native Skill handlers. The
  ; friendly metadata prevents Chromium from presenting the Windows handler as
  ; merely "Python" without changing its actual command or requiring Tauri.
  ReadRegStr $0 HKCU "Software\Classes\mklink-ai-probe\shell\open\command" ""
  ${If} $0 != ""
    WriteRegStr HKCU "Software\Classes\mklink-ai-probe" "FriendlyTypeName" "MKLink Web GUI"
    WriteRegStr HKCU "Software\Classes\mklink-ai-probe" "ApplicationName" "MKLink Web GUI"
    WriteRegStr HKCU "Software\Classes\mklink-ai-probe\Application" "ApplicationName" "MKLink Web GUI"
    WriteRegStr HKCU "Software\Classes\mklink-ai-probe\Application" "ApplicationDescription" "MKLink AI Probe Web GUI Launcher"
  ${EndIf}

!macroend

!macro NSIS_HOOK_PREUNINSTALL
  Call un.MklinkWaitForUpgradeFiles
!macroend

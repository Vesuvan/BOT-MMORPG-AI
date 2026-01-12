; Custom NSIS template for Tauri (v1.4+).
; This file is used by tauri-cli to generate the final installer.
; Variables are injected by the bundler at build time.
; Adds driver installation step (Interception + vJoy) during install.

!include "MUI2.nsh"

Name "{{product_name}}"
OutFile "{{out_file}}"
InstallDir "{{install_dir}}"

; We need admin to install drivers reliably.
RequestExecutionLevel admin

; --- UI ---
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME

; License page is optional.
; If the bundler provides a license file path, it will be shown.
{{#if license_file}}
!insertmacro MUI_PAGE_LICENSE "{{license_file}}"
{{/if}}

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"

  ; --- App files packaged by Tauri ---
  {{#each resources}}
    File /r "{{this}}"
  {{/each}}

  ; --- Shortcuts ---
  CreateDirectory "$SMPROGRAMS\{{product_name}}"
  CreateShortCut "$SMPROGRAMS\{{product_name}}\{{product_name}}.lnk" "$INSTDIR\{{main_binary_name}}.exe"
  CreateShortCut "$DESKTOP\{{product_name}}.lnk" "$INSTDIR\{{main_binary_name}}.exe"

  ; --- Driver installers ---
  ; Interception
  IfFileExists "$INSTDIR\drivers\interception\install-interception.exe" 0 +4
    DetailPrint "Installing Interception driver..."
    ExecWait '"$INSTDIR\drivers\interception\install-interception.exe" /install'
    DetailPrint "Interception install step finished."

  ; vJoy
  IfFileExists "$INSTDIR\drivers\vjoy\vJoySetup.exe" 0 +4
    DetailPrint "Installing vJoy..."
    ExecWait '"$INSTDIR\drivers\vjoy\vJoySetup.exe" /S'
    DetailPrint "vJoy install step finished."

  ; --- Uninstaller ---
  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\{{product_name}}.lnk"
  Delete "$SMPROGRAMS\{{product_name}}\{{product_name}}.lnk"
  RMDir "$SMPROGRAMS\{{product_name}}"

  ; Remove installed files
  RMDir /r "$INSTDIR"
SectionEnd

<#
scripts/install_windows.ps1
Installs Windows-only driver prerequisites:
- Interception (keyboard/mouse driver)
- vJoy (virtual joystick)

Safety:
- Checks for Administrator
- Verifies files exist before executing
- Prints clear status/errors
#>

$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[ERR]  $msg" -ForegroundColor Red }

function Assert-Admin {
  $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
  ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

  if (-not $isAdmin) {
    Write-Err "Please run this script as Administrator."
    Write-Host "Right click PowerShell -> Run as Administrator, then run:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1" -ForegroundColor Yellow
    exit 1
  }
}

function Run-Exe($path, $args="") {
  if (-not (Test-Path $path)) {
    throw "Missing file: $path"
  }
  Write-Info "Running: $path $args"
  $p = Start-Process -FilePath $path -ArgumentList $args -Wait -PassThru
  if ($p.ExitCode -ne 0) {
    throw "Process failed (exit code $($p.ExitCode)): $path"
  }
}

function Run-Interception {
  # Try common locations in this repo
  $candidates = @(
    "frontend\input_record\install-interception.exe",
    "frontend\input_record\Interception\command line installer\install-interception.exe"
  )

  $exe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $exe) {
    Write-Warn "Interception installer not found in expected locations."
    Write-Warn "Expected one of:"
    $candidates | ForEach-Object { Write-Host "  - $_" }
    return
  }

  Write-Info "Installing Interception driver..."
  # Interception installer supports /install in some builds; if your exe differs, adjust here.
  try {
    Run-Exe $exe "/install"
  } catch {
    Write-Warn "Interception installer did not accept /install; trying without args..."
    Run-Exe $exe ""
  }
  Write-Ok "Interception step complete."
}

function Run-vJoy {
  $vj = "versions\0.01\pyvjoy\vJoySetup.exe"
  if (-not (Test-Path $vj)) {
    Write-Warn "vJoy installer not found at $vj"
    return
  }
  Write-Info "Installing vJoy..."
  # Common silent flags vary by vJoy version; start interactive if silent fails.
  try {
    Run-Exe $vj "/S"
  } catch {
    Write-Warn "Silent install failed; starting interactive installer..."
    Run-Exe $vj ""
  }
  Write-Ok "vJoy step complete."
}

# ---- Main ----
Assert-Admin
Write-Info "Windows prerequisites installer"

Run-Interception
Run-vJoy

Write-Ok "All done. Reboot may be required for drivers to fully load."

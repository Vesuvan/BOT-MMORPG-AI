$ErrorActionPreference = "Stop"

function Write-Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Write-Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err($m){ Write-Host "[ERR]  $m" -ForegroundColor Red }

function Assert-Admin {
  $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
  ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  if (-not $isAdmin) {
    Write-Err "Run as Administrator."
    exit 1
  }
}

function Run-Exe($path, $args="") {
  if (-not (Test-Path $path)) { throw "Missing file: $path" }
  Write-Info "Running: $path $args"
  $p = Start-Process -FilePath $path -ArgumentList $args -Wait -PassThru
  if ($p.ExitCode -ne 0) { throw "Failed (exit $($p.ExitCode)): $path" }
}

Assert-Admin

$root = Split-Path -Parent $PSScriptRoot

# Expect drivers shipped alongside installed app
$interception = Join-Path $root "drivers\interception\install-interception.exe"
$vjoy = Join-Path $root "drivers\vjoy\vJoySetup.exe"

if (Test-Path $interception) {
  try { Run-Exe $interception "/install" } catch { Run-Exe $interception "" }
  Write-Ok "Interception installed/attempted."
} else {
  Write-Warn "Interception installer not found: $interception"
}

if (Test-Path $vjoy) {
  try { Run-Exe $vjoy "/S" } catch { Run-Exe $vjoy "" }
  Write-Ok "vJoy installed/attempted."
} else {
  Write-Warn "vJoy installer not found: $vjoy"
}

Write-Ok "Driver install finished. A reboot may be required."

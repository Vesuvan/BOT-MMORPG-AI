param(
  [switch]$Download  # If set, download drivers from internet if missing
)

$ErrorActionPreference = "Stop"

function Write-Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Write-Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err($m){ Write-Host "[ERR]  $m" -ForegroundColor Red }

function Assert-Admin {
  $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
  ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  if (-not $isAdmin) {
    Write-Err "This script requires Administrator privileges to install drivers."
    Write-Info "Please right-click PowerShell and select 'Run as Administrator'"
    exit 1
  }
}

function Run-Exe($path, $args="") {
  if (-not (Test-Path $path)) { throw "Missing file: $path" }
  Write-Info "Running: $path $args"
  $p = Start-Process -FilePath $path -ArgumentList $args -Wait -PassThru
  if ($p.ExitCode -ne 0) { throw "Failed (exit $($p.ExitCode)): $path" }
}

function Download-Driver {
  param(
    [string]$Url,
    [string]$OutPath,
    [string]$Name
  )

  $outDir = Split-Path -Parent $OutPath
  if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
  }

  Write-Info "Downloading $Name from $Url..."
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $Url -OutFile $OutPath -UseBasicParsing
    Write-Ok "$Name downloaded to $OutPath"
    return $true
  } catch {
    Write-Err "Failed to download $Name: $_"
    return $false
  }
}

function Download-AndExtract-Driver {
  param(
    [string]$Url,
    [string]$OutDir,
    [string]$ExpectedExe,
    [string]$Name
  )

  if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
  }

  $zipPath = Join-Path $OutDir "temp_download.zip"

  Write-Info "Downloading $Name from $Url..."
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $Url -OutFile $zipPath -UseBasicParsing
    Write-Ok "$Name archive downloaded"

    Write-Info "Extracting $Name..."
    Expand-Archive -Path $zipPath -DestinationPath $OutDir -Force
    Remove-Item $zipPath -Force

    # Find the exe in extracted contents (may be in subdirectory)
    $found = Get-ChildItem -Path $OutDir -Recurse -Filter "*.exe" | Select-Object -First 1
    if ($found -and ($found.FullName -ne $ExpectedExe)) {
      Copy-Item $found.FullName -Destination $ExpectedExe -Force
    }

    Write-Ok "$Name extracted"
    return $true
  } catch {
    Write-Err "Failed to download/extract $Name: $_"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    return $false
  }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " BOT-MMORPG-AI Driver Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Assert-Admin

$root = Split-Path -Parent $PSScriptRoot

# Driver paths - check both src-tauri/drivers (development) and drivers/ (installed app)
$driversDir = Join-Path $root "src-tauri\drivers"
if (-not (Test-Path $driversDir)) {
  $driversDir = Join-Path $root "drivers"
}

$interceptionDir = Join-Path $driversDir "interception"
$vjoyDir = Join-Path $driversDir "vjoy"
$interception = Join-Path $interceptionDir "install-interception.exe"
$vjoy = Join-Path $vjoyDir "vJoySetup.exe"

# Download URLs (official sources)
$interceptionUrl = "https://github.com/oblitum/Interception/releases/download/v1.0.1/Interception.zip"
$vjoyUrl = "https://github.com/shauleiz/vJoy/releases/download/v2.1.9.1/vJoySetup.exe"

Write-Info "Checking driver availability..."

# Download Interception if missing (only if -Download flag is set)
if (-not (Test-Path $interception)) {
  if ($Download) {
    Write-Warn "Interception driver not found. Downloading from source..."
    if (Download-AndExtract-Driver -Url $interceptionUrl -OutDir $interceptionDir -ExpectedExe $interception -Name "Interception") {
      # The Interception zip contains command line installer
      $cmdInstaller = Get-ChildItem -Path $interceptionDir -Recurse -Filter "install-interception.exe" | Select-Object -First 1
      if ($cmdInstaller) {
        Copy-Item $cmdInstaller.FullName -Destination $interception -Force
      }
    }
  } else {
    Write-Warn "Interception driver not found: $interception"
    Write-Info "Use -Download flag to download from internet, or ensure drivers are in the repo"
  }
}

# Download vJoy if missing (only if -Download flag is set)
if (-not (Test-Path $vjoy)) {
  if ($Download) {
    Write-Warn "vJoy driver not found. Downloading from source..."
    Download-Driver -Url $vjoyUrl -OutPath $vjoy -Name "vJoy"
  } else {
    Write-Warn "vJoy driver not found: $vjoy"
    Write-Info "Use -Download flag to download from internet, or ensure drivers are in the repo"
  }
}

Write-Host ""
Write-Info "Installing drivers..."
Write-Host ""

# Install Interception
if (Test-Path $interception) {
  Write-Info "Installing Interception driver..."
  try {
    Run-Exe $interception "/install"
  } catch {
    # Try without arguments if /install fails
    try { Run-Exe $interception "" } catch { Write-Warn "Interception install may have failed: $_" }
  }
  Write-Ok "Interception driver installed/attempted."
} else {
  Write-Warn "Interception installer not found: $interception"
  Write-Info "Manual download: https://github.com/oblitum/Interception/releases"
}

Write-Host ""

# Install vJoy
if (Test-Path $vjoy) {
  Write-Info "Installing vJoy driver..."
  try {
    Run-Exe $vjoy "/S"
  } catch {
    # Try without silent flag if it fails
    try { Run-Exe $vjoy "" } catch { Write-Warn "vJoy install may have failed: $_" }
  }
  Write-Ok "vJoy driver installed/attempted."
} else {
  Write-Warn "vJoy installer not found: $vjoy"
  Write-Info "Manual download: https://github.com/shauleiz/vJoy/releases"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Ok "Driver installation complete!"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Warn "A system REBOOT is required for drivers to take effect."
Write-Host ""

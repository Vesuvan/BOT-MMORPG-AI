<#
Build pipeline (Windows):
1) Build Python backend sidecar with PyInstaller
2) Rename for Tauri sidecar requirements
3) Copy sidecar + driver installers into src-tauri/binaries and src-tauri/resources
4) Build Tauri app + NSIS installer

Requirements:
- Python 3.10+ (for PyInstaller)
- uv (Python package installer - faster than pip)
- Rust toolchain + cargo (install via rustup)
- Tauri CLI (cargo install tauri-cli)
- NSIS installed (Tauri bundler uses it)

Usage:
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_pipeline.ps1 [-SkipPython] [-SkipTauri] [-Clean] [-Verify] [-SkipRustInstall] [-SkipTauriCliInstall]
#>

param(
  [switch]$SkipPython,
  [switch]$SkipTauri,
  [switch]$Clean,
  [switch]$Verify,
  [switch]$SkipRustInstall,
  [switch]$SkipTauriCliInstall
)

$ErrorActionPreference = "Stop"

function Log-Ok([string]$msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Log-Info([string]$msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Log-Warn([string]$msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Log-Fail([string]$msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

function Log-Step([int]$step, [string]$msg) {
  Write-Host ""
  Write-Host "======================================"
  Write-Host (" STEP {0}: {1}" -f $step, $msg)
  Write-Host "======================================"
}

function Refresh-Path {
  # Reload path from registry
  $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $user    = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = "$machine;$user"

  # Explicitly add Rust default bin location if it exists (fixes session latency)
  $cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
  if (Test-Path $cargoBin) {
    if ($env:Path -notlike "*$cargoBin*") {
        $env:Path += ";$cargoBin"
    }
  }
}

function Test-Command-Runnable([string]$name) {
    # Actually tries to execute the command to ensure it's not a broken shim
    try {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            # Try running version flag (works for cargo, python, winget, uv, etc)
            $null = & $name --version 2>&1
            return ($LASTEXITCODE -eq 0)
        }
        return $false
    } catch {
        return $false
    }
}

function Ensure-Uv {
  Refresh-Path
  if (Test-Command-Runnable "uv") {
    $uvVersion = & uv --version 2>&1
    Log-Ok "uv found: $uvVersion"
    return $true
  }

  Log-Warn "uv not found. Installing uv (Python package installer)..."

  try {
    # Install uv via pip
    & python -m pip install --user uv --quiet
    if ($LASTEXITCODE -ne 0) {
      throw "uv installation failed with exit code $LASTEXITCODE"
    }

    Refresh-Path

    if (Test-Command-Runnable "uv") {
      $uvVersion = & uv --version 2>&1
      Log-Ok "uv installed: $uvVersion"
      return $true
    }

    Log-Warn "uv installed but not in PATH. May need terminal restart."
    return $false
  } catch {
    Log-Warn "Failed to install uv: $_"
    Log-Info "Falling back to pip"
    return $false
  }
}

function Ensure-Rust {
  Refresh-Path
  if (Test-Command-Runnable "cargo") { return $true }

  Log-Warn "Rust/Cargo not found (or not runnable) in PATH."

  if ($SkipRustInstall) {
    Log-Warn "SkipRustInstall enabled; not attempting Rust install."
    return $false
  }

  if (-not (Test-Command-Runnable "winget")) {
    Log-Warn "winget not available; cannot auto-install Rust."
    return $false
  }

  Log-Info "Attempting to install Rust via winget (Rustup)..."
  try {
    # Added --disable-interactivity to prevent hanging/weird exit codes
    & winget install -e --id Rustlang.Rustup --accept-package-agreements --accept-source-agreements --disable-interactivity

    if ($LASTEXITCODE -ne 0) {
      Log-Warn "winget Rust install failed: winget exited with code $LASTEXITCODE"
      return $false
    }

    Log-Ok "Rustup installed. Refreshing PATH..."
    Refresh-Path

    if (Test-Command-Runnable "cargo") {
      return $true
    }

    Log-Warn "Cargo installed but not executable in this session."
    return $false
  } catch {
    Log-Warn "winget Rust install exception: $_"
    return $false
  }
}

function Ensure-TauriCli {
  if (-not (Test-Command-Runnable "cargo")) { return $false }

  if ($SkipTauriCliInstall) {
    return (Test-Command-Runnable "cargo-tauri") # cargo-tauri is the actual executable
  }

  # First check using cargo tauri
  try {
    $v = & cargo tauri --version 2>&1
    if ($LASTEXITCODE -eq 0) {
      Log-Ok "Tauri CLI found: $v"
      return $true
    }
  } catch { }

  Log-Warn "Tauri CLI not found. Installing tauri-cli..."
  try {
    & cargo install tauri-cli --version "^1.0"
    if ($LASTEXITCODE -ne 0) {
      Log-Warn "cargo install tauri-cli failed with exit code $LASTEXITCODE"
      return $false
    }

    Refresh-Path

    # Verify again
    try {
        $v2 = & cargo tauri --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Log-Ok "Tauri CLI installed: $v2"
            return $true
        }
    } catch {}

    Log-Warn "tauri-cli installed but still not runnable."
    return $false
  } catch {
    Log-Warn "Tauri CLI check/install failed: $_"
    return $false
  }
}

# ---- Root directory ----
$scriptPath = $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($scriptPath)) { $scriptPath = $PSCommandPath }
$scriptDir = Split-Path -Parent $scriptPath
$root = (Resolve-Path (Join-Path $scriptDir "..")).Path

Log-Info "Root directory: $root"
Log-Info ("Build started at: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Write-Host ""

# ---- Prereqs ----

# ================================
# STEP 1: UI Smoke Tests (pre-build)
# ================================
$__hasLog = (Get-Command Log-Step -ErrorAction SilentlyContinue) -ne $null
if ($__hasLog) { Log-Step 1 "UI Smoke Tests (pre-build)" } else { Write-Host "[STEP 1] UI Smoke Tests (pre-build)" }

try {
  if ($__hasLog) { Log-Info "Running UI/installer smoke tests..." } else { Write-Host "[INFO] Running UI/installer smoke tests..." }

  # Bypass 'uv run' to avoid tensorflow dependency issues on Windows
  # Tests are standard library only.
  & python tests/test_tauri_ui_smoke.py
  if ($LASTEXITCODE -ne 0) { throw "UI smoke tests failed (exit code $LASTEXITCODE)" }

  if ($__hasLog) { Log-Ok "UI smoke tests passed" } else { Write-Host "[OK] UI smoke tests passed" }
} catch {
  if ($__hasLog) { Log-Fail "$_" } else { Write-Host "[FAIL] $($_.Exception.Message)" }
  exit 1
}
Log-Step 0 "Checking Prerequisites"

# Python
try {
  $pythonVersion = & python --version 2>&1
  Log-Ok "Python found: $pythonVersion"
} catch {
  Log-Fail "Python not found. Please install Python 3.10+"
  exit 1
}

# uv (Python package installer - faster than pip)
$useUv = Ensure-Uv

# Rust + Tauri only required if building Tauri
if (-not $SkipTauri) {
  $hasCargo = Ensure-Rust

  if (-not $hasCargo) {
    Log-Fail "Rust/Cargo is required to build the installer."
    Log-Info "Auto-install failed or PATH is not updated."
    Log-Info "MANUAL FIX:"
    Log-Info "  1. Download https://rustup.rs/ and install."
    Log-Info "  2. Restart your terminal."
    Log-Info "  3. Verify by running: cargo --version"
    exit 1
  }

  # Safe check for version
  try {
      $rustVersion = & cargo --version 2>&1
      Log-Ok "Rust found: $rustVersion"
  } catch {
      Log-Fail "Cargo command exists but failed to run. Please reinstall Rustup."
      exit 1
  }

  $hasTauri = Ensure-TauriCli
  if (-not $hasTauri) {
    Log-Fail "Tauri CLI is required."
    Log-Info "Run: cargo install tauri-cli"
    exit 1
  }
} else {
  Log-Warn "SkipTauri enabled; Rust/Cargo not required."
}

# ---- Clean ----
if ($Clean) {
  Log-Step 1 "Cleaning Build Artifacts"

  $cleanTargets = @(
    "dist",
    "build",
    ".venv",
    "src-tauri\target",
    "src-tauri\binaries",
    "src-tauri\drivers",
    "src-tauri\resources"
  )

  foreach ($rel in $cleanTargets) {
    $p = Join-Path $root $rel
    if (Test-Path $p) {
      Log-Info "Removing: $rel"
      Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue
    }
  }

  Get-ChildItem -Path $root -Filter "*.spec" -ErrorAction SilentlyContinue | ForEach-Object {
    Log-Info "Removing: $($_.Name)"
    Remove-Item -Force $_.FullName
  }

  Log-Ok "Clean completed"
}

# ---- Build Python backend ----
if (-not $SkipPython) {
  Log-Step 2 "Building Python Backend"

  $venv = Join-Path $root ".venv"
  $venvPython = Join-Path $venv "Scripts\python.exe"
  $venvPyInstaller = Join-Path $venv "Scripts\pyinstaller.exe"

  # Check if venv exists AND is functional
  $venvNeedsCreation = $false
  if (-not (Test-Path $venv)) {
    $venvNeedsCreation = $true
  } elseif (-not (Test-Path $venvPython)) {
    Log-Warn "Virtual environment exists but is broken (python.exe missing)"
    Log-Info "Removing broken virtual environment..."
    Remove-Item -Recurse -Force $venv -ErrorAction SilentlyContinue
    $venvNeedsCreation = $true
  } else {
    Log-Info "Using existing virtual environment"
  }

  if ($venvNeedsCreation) {
    Log-Info "Creating Python virtual environment with uv..."
    try {
      if ($useUv) {
        # Use uv to create venv (much faster)
        & uv venv $venv --python python
        if ($LASTEXITCODE -ne 0) {
          throw "uv venv creation failed with exit code $LASTEXITCODE"
        }
      } else {
        # Fallback to standard venv
        & python -m venv $venv
        if ($LASTEXITCODE -ne 0) {
          throw "venv creation failed with exit code $LASTEXITCODE"
        }
      }

      # Verify python.exe was created
      if (-not (Test-Path $venvPython)) {
        throw "venv created but python.exe not found at: $venvPython"
      }

      Log-Ok "Virtual environment created"
    } catch {
      Log-Fail "Failed to create virtual environment: $_"
      exit 1
    }
  }

  Log-Info "Installing Python dependencies..."
  try {
    if ($useUv) {
      # Use uv for faster installation
      Log-Info "Using uv for package installation (faster than pip)"
      & uv pip install --python $venvPython -e . --quiet
      if ($LASTEXITCODE -ne 0) { throw "uv pip install project failed" }

      & uv pip install --python $venvPython pyinstaller --quiet
      if ($LASTEXITCODE -ne 0) { throw "uv pip install pyinstaller failed" }

      Log-Ok "Dependencies installed with uv"
    } else {
      # Fallback to pip
      Log-Info "Using pip for package installation"
      $venvPip = Join-Path $venv "Scripts\pip.exe"

      & $venvPip install --quiet -e .
      if ($LASTEXITCODE -ne 0) { throw "pip install project failed" }

      & $venvPip install --quiet pyinstaller
      if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }

      Log-Ok "Dependencies installed with pip"
    }
  } catch {
    Log-Fail "Failed to install Python dependencies: $_"
    Log-Info "TIP: Try running with -Clean to recreate the virtual environment"
    exit 1
  }

  Log-Info "Building backend sidecar with PyInstaller..."
  $backend = Join-Path $root "backend\main_backend.py"
  if (-not (Test-Path $backend)) {
    Log-Fail "Backend source not found: $backend"
    exit 1
  }

  try {
    # Use venv's pyinstaller
    & $venvPyInstaller --noconfirm --clean --onefile --name main-backend $backend
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    Log-Ok "Backend built successfully"
  } catch {
    Log-Fail "PyInstaller build failed: $_"
    exit 1
  }

  $distExe = Join-Path $root "dist\main-backend.exe"
  if (-not (Test-Path $distExe)) {
    Log-Fail "PyInstaller output missing: $distExe"
    exit 1
  }

  $sizeMb = [math]::Round(((Get-Item $distExe).Length / 1MB), 2)
  Log-Ok "Backend executable created: $sizeMb MB"

  Log-Info "Preparing Tauri sidecar binary..."
  $target = "x86_64-pc-windows-msvc"
  $tauriSidecarDir = Join-Path $root "src-tauri\binaries"
  $tauriSidecar = Join-Path $tauriSidecarDir ("main-backend-{0}.exe" -f $target)

  New-Item -Force -ItemType Directory $tauriSidecarDir | Out-Null
  Copy-Item -Force $distExe $tauriSidecar
  Log-Ok "Sidecar copied: $(Split-Path -Leaf $tauriSidecar)"
} else {
  Log-Warn "Skipping Python backend build"
}

# ---- Copy driver installers ----
Log-Step 3 "Copying Driver Installers"

$drvInterDir = Join-Path $root "src-tauri\drivers\interception"
$drvVjoyDir  = Join-Path $root "src-tauri\drivers\vjoy"
$resScripts  = Join-Path $root "src-tauri\resources\scripts"

New-Item -Force -ItemType Directory $drvInterDir | Out-Null
New-Item -Force -ItemType Directory $drvVjoyDir  | Out-Null
New-Item -Force -ItemType Directory $resScripts  | Out-Null

$interceptionSrc = Join-Path $root "frontend\input_record\install-interception.exe"
$interceptionDst = Join-Path $drvInterDir "install-interception.exe"
if (Test-Path $interceptionSrc) {
  Copy-Item -Force $interceptionSrc $interceptionDst
  Log-Ok "Interception driver copied"
} else {
  Log-Warn "Interception installer not found: $interceptionSrc"
  Log-Warn "Creating placeholder (installer will not have driver support)"
  "Placeholder" | Set-Content -Path $interceptionDst -NoNewline
}

$vjoySrc = Join-Path $root "versions\0.01\pyvjoy\vJoySetup.exe"
$vjoyDst = Join-Path $drvVjoyDir "vJoySetup.exe"
if (Test-Path $vjoySrc) {
  Copy-Item -Force $vjoySrc $vjoyDst
  Log-Ok "vJoy driver copied"
} else {
  Log-Warn "vJoy installer not found: $vjoySrc"
  Log-Warn "Creating placeholder (installer will not have driver support)"
  "Placeholder" | Set-Content -Path $vjoyDst -NoNewline
}

$installScriptSrc = Join-Path $root "scripts\install_drivers.ps1"
$installScriptDst = Join-Path $resScripts "install_drivers.ps1"
if (Test-Path $installScriptSrc) {
  Copy-Item -Force $installScriptSrc $installScriptDst
  Log-Ok "Install drivers script copied"
} else {
  Log-Warn "Install drivers script not found: $installScriptSrc"
}

$modelsScriptSrc = Join-Path $root "scripts\download_models.ps1"
$modelsScriptDst = Join-Path $resScripts "download_models.ps1"
if (Test-Path $modelsScriptSrc) {
  Copy-Item -Force $modelsScriptSrc $modelsScriptDst
  Log-Ok "Download models script copied"
} else {
  Log-Warn "Download models script not found: $modelsScriptSrc"
}

# ---- Build Tauri ----
if (-not $SkipTauri) {
  Log-Step 4 "Building Tauri Application"

  Push-Location (Join-Path $root "src-tauri")
  try {
    Log-Info "Running cargo tauri build..."
    & cargo tauri build --verbose
    if ($LASTEXITCODE -ne 0) { throw "Tauri build failed with exit code $LASTEXITCODE" }
    Log-Ok "Tauri build completed successfully"
  } catch {
    Log-Fail "Tauri build failed: $_"
    Pop-Location
    exit 1
  } finally {
    Pop-Location
  }

  $installerDir = Join-Path $root "src-tauri\target\release\bundle\nsis"
  if (Test-Path $installerDir) {
    $installers = Get-ChildItem -Path $installerDir -Filter "*.exe" -ErrorAction SilentlyContinue
    if ($installers.Count -gt 0) {
      Write-Host ""
      Log-Ok "NSIS installer(s) created:"
      foreach ($inst in $installers) {
        $s = [math]::Round(($inst.Length / 1MB), 2)
        Write-Host ("  - {0} ({1} MB)" -f $inst.Name, $s)
      }
    } else {
      Log-Warn "No installer executables found in $installerDir"
    }
  } else {
    Log-Warn "Installer directory not found: $installerDir"
  }
} else {
  Log-Warn "Skipping Tauri build"
}

# ---- Verify ----
if ($Verify) {
  Log-Step 5 "Running Verification"

  $verifyScript = Join-Path $root "scripts\verify_installer.ps1"
  if (Test-Path $verifyScript) {
    & $verifyScript
    if ($LASTEXITCODE -ne 0) {
      Log-Fail "Verification failed"
      exit 1
    }
  } else {
    Log-Warn "Verification script not found: $verifyScript"
  }
}

# ---- Summary ----
Write-Host ""
Write-Host "======================================"
Write-Host " BUILD COMPLETED"
Write-Host "======================================"
Log-Ok ("Build finished at: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Write-Host ""
Log-Info "Installer location: src-tauri\target\release\bundle\nsis\"
Write-Host ""
Log-Info "Next steps:"
Write-Host "  1. Run tests:   .\scripts\test_installer.ps1"
Write-Host "  2. Verify:      .\scripts\verify_installer.ps1"
Write-Host "  3. Test install on a clean Windows machine"
Write-Host ""
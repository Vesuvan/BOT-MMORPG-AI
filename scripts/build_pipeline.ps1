<#
Build pipeline (Windows):
1) Build Python backend sidecar with PyInstaller (ONEDIR)
2) Copy sidecar folder into src-tauri/resources/sidecar/main-backend/
3) Copy driver installers + ps scripts into src-tauri/drivers and src-tauri/resources/scripts
4) Build Tauri app + NSIS installer

Requirements:
- Python 3.10+ (for PyInstaller)
- uv (optional, faster than pip)
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
  try {
    if (Get-Command $name -ErrorAction SilentlyContinue) {
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
    & winget install -e --id Rustlang.Rustup --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) {
      Log-Warn "winget Rust install failed: winget exited with code $LASTEXITCODE"
      return $false
    }

    Log-Ok "Rustup installed. Refreshing PATH..."
    Refresh-Path

    if (Test-Command-Runnable "cargo") { return $true }

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
    return (Test-Command-Runnable "cargo-tauri")
  }

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

# ---- Guard: ensure versions folder exists (better error than Tauri glob failure) ----
$versionsDir = Join-Path $root "versions"
if (-not (Test-Path $versionsDir)) {
  throw "Missing required folder: $versionsDir (expected versions/0.01 etc.)"
}


Log-Info "Root directory: $root"
Log-Info ("Build started at: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Write-Host ""

# ================================
# STEP 1: UI Smoke Tests (pre-build)
# ================================
Log-Step 1 "UI Smoke Tests (pre-build)"

try {
  Log-Info "Running UI/installer smoke tests..."
  & python tests/test_tauri_ui_smoke.py
  if ($LASTEXITCODE -ne 0) { throw "UI smoke tests failed (exit code $LASTEXITCODE)" }
  Log-Ok "UI smoke tests passed"
} catch {
  Log-Fail "$_"
  exit 1
}

# ================================
# STEP 0: Checking Prerequisites
# ================================
Log-Step 0 "Checking Prerequisites"

# Python
try {
  $pythonVersion = & python --version 2>&1
  Log-Ok "Python found: $pythonVersion"
} catch {
  Log-Fail "Python not found. Please install Python 3.10+"
  exit 1
}

# uv (optional)
$useUv = Ensure-Uv

# Rust + Tauri only required if building Tauri
if (-not $SkipTauri) {
  $hasCargo = Ensure-Rust
  if (-not $hasCargo) {
    Log-Fail "Rust/Cargo is required to build the installer."
    Log-Info "MANUAL FIX:"
    Log-Info "  1. Download https://rustup.rs/ and install."
    Log-Info "  2. Restart your terminal."
    Log-Info "  3. Verify by running: cargo --version"
    exit 1
  }

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

# ================================
# Optional Clean
# ================================
if ($Clean) {
  Log-Step 1 "Cleaning Build Artifacts"

  # IMPORTANT: do NOT delete src-tauri/resources entirely (it contains icons/config/etc).
  # Only delete generated subfolders.
  $cleanTargets = @(
    "dist",
    "build",
    ".venv",
    "src-tauri\target",
    "src-tauri\binaries",
    "src-tauri\drivers",
    "src-tauri\resources\scripts",
    "src-tauri\resources\sidecar"
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

# ================================
# STEP 2: Build Python backend
# ================================
if (-not $SkipPython) {
  Log-Step 2 "Building Python Backend (PyInstaller ONEDIR)"

  $venv       = Join-Path $root ".venv"
  $venvPython = Join-Path $venv "Scripts\python.exe"

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
    Log-Info "Creating Python virtual environment..."
    try {
      if ($useUv) {
        & uv venv $venv --python python
        if ($LASTEXITCODE -ne 0) { throw "uv venv creation failed with exit code $LASTEXITCODE" }
      } else {
        & python -m venv $venv
        if ($LASTEXITCODE -ne 0) { throw "venv creation failed with exit code $LASTEXITCODE" }
      }

      if (-not (Test-Path $venvPython)) { throw "venv created but python.exe not found at: $venvPython" }
      Log-Ok "Virtual environment created"
    } catch {
      Log-Fail "Failed to create virtual environment: $_"
      exit 1
    }
  }

  # --- ensure pip exists inside venv ---
  Log-Info "Ensuring pip exists in build venv..."
  try {
    & $venvPython -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) { throw "pip missing" }
    Log-Ok "pip already present"
  } catch {
    Log-Warn "pip not found in venv. Bootstrapping pip with ensurepip..."
    try {
      & $venvPython -m ensurepip --upgrade
      if ($LASTEXITCODE -ne 0) { throw "ensurepip failed (exit code $LASTEXITCODE)" }

      & $venvPython -m pip install --upgrade pip setuptools wheel --quiet
      if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed (exit code $LASTEXITCODE)" }

      Log-Ok "pip bootstrapped and upgraded"
    } catch {
      Log-Fail "Failed to bootstrap pip in venv: $_"
      exit 1
    }
  }

  # --- install project deps into venv (so PyInstaller sees everything) ---
  Log-Info "Installing Python dependencies..."
  try {
    if ($useUv) {
      Log-Info "Using uv for package installation (faster than pip)"
      & uv pip install --python $venvPython -e . --quiet
      if ($LASTEXITCODE -ne 0) { throw "uv pip install project failed" }
    } else {
      Log-Info "Using pip for package installation"
      & $venvPython -m pip install -e . --quiet
      if ($LASTEXITCODE -ne 0) { throw "pip install project failed" }
    }
    Log-Ok "Project dependencies installed"
  } catch {
    Log-Fail "Failed to install project dependencies: $_"
    exit 1
  }

  # --- ensure backend runtime deps exist in build venv ---
  Log-Info "Ensuring backend runtime deps (fastapi/uvicorn) are installed in build venv..."
  try {
    & $venvPython -c "import fastapi, uvicorn; print('backend deps OK')" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "missing" }
    Log-Ok "Backend runtime deps OK"
  } catch {
    try {
      if ($useUv) {
        & uv pip install --python $venvPython fastapi uvicorn --quiet
      } else {
        & $venvPython -m pip install fastapi uvicorn --quiet
      }
      if ($LASTEXITCODE -ne 0) { throw "install failed" }

      & $venvPython -c "import fastapi, uvicorn; print('backend deps OK')" 2>$null
      if ($LASTEXITCODE -ne 0) { throw "still missing after install" }

      Log-Ok "Backend runtime deps installed"
    } catch {
      Log-Fail "Failed to ensure fastapi/uvicorn in build venv: $_"
      exit 1
    }
  }

  # --- ensure PyInstaller exists ---
  Log-Info "Ensuring PyInstaller is installed in build venv..."
  try {
    & $venvPython -m pip show pyinstaller *> $null
    if ($LASTEXITCODE -ne 0) {
      if ($useUv) {
        & uv pip install --python $venvPython pyinstaller --quiet
      } else {
        & $venvPython -m pip install pyinstaller --quiet
      }
      if ($LASTEXITCODE -ne 0) { throw "install failed" }
    }
    Log-Ok "PyInstaller ready"
  } catch {
    Log-Fail "Failed to install PyInstaller: $_"
    exit 1
  }

  # --- build the sidecar with PyInstaller ONEDIR ---
  Log-Info "Building backend sidecar with PyInstaller (onedir)..."

  $backend = Join-Path $root "backend\entry_main.py"
  if (-not (Test-Path $backend)) {
    Log-Fail "Backend source not found: $backend"
    exit 1
  }

  try {
    # Clean previous dist/main-backend so we never ship stale _internal
    $distDir = Join-Path $root "dist\main-backend"
    if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir -ErrorAction SilentlyContinue }

    & $venvPython -m PyInstaller `
      --noconfirm `
      --clean `
      --onedir `
      --console `
      --name main-backend `
      $backend

    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    Log-Ok "Backend built successfully"
  } catch {
    Log-Fail "PyInstaller build failed: $_"
    exit 1
  }

  # --- validate output exists ---
  $distDir = Join-Path $root "dist\main-backend"
  $distExe = Join-Path $distDir "main-backend.exe"
  if (-not (Test-Path $distExe)) {
    Log-Fail "PyInstaller output missing: $distExe"
    exit 1
  }
  if (-not (Test-Path (Join-Path $distDir "_internal"))) {
    Log-Fail "PyInstaller _internal folder missing: dist\main-backend\_internal"
    exit 1
  }

  $sizeMb = [math]::Round(((Get-Item $distExe).Length / 1MB), 2)
  Log-Ok "Backend executable created: $sizeMb MB (onedir)"

  # --- bundle into Tauri resources ---
  Log-Info "Bundling sidecar into Tauri resources..."
  $tauriSidecarDir = Join-Path $root "src-tauri\resources\sidecar\main-backend"

  if (Test-Path $tauriSidecarDir) {
    Remove-Item -Recurse -Force $tauriSidecarDir -ErrorAction SilentlyContinue
  }
  New-Item -Force -ItemType Directory $tauriSidecarDir | Out-Null

# --- Robust sidecar copy (handles locked DLLs / Defender scanning) ---
$lockNames = @("main-backend", "main-backend.exe", "BOT-MMORPG-AI", "BOT-MMORPG-AI.exe")
foreach ($n in $lockNames) {
  try { Get-Process -Name $n -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue } catch {}
}

# Remove destination _internal to avoid update-in-place locks
try { Remove-Item -Recurse -Force (Join-Path $tauriSidecarDir "_internal") -ErrorAction SilentlyContinue } catch {}

$maxTries = 25
$delaySec = 1
$lastErr = $null
for ($i = 1; $i -le $maxTries; $i++) {
  try {
    Copy-Item -Recurse -Force (Join-Path $distDir "*") $tauriSidecarDir -ErrorAction Stop
    $lastErr = $null
    break
  } catch {
    $lastErr = $_
    Log-Warn ("Sidecar copy attempt {0}/{1} failed: {2}" -f $i, $maxTries, $_.Exception.Message)
    Start-Sleep -Seconds $delaySec
  }
}
if ($lastErr -ne $null) { throw $lastErr }
# --- End robust sidecar copy ---

  $bundledExe = Join-Path $tauriSidecarDir "main-backend.exe"
  if (-not (Test-Path $bundledExe)) {
    Log-Fail "Bundled sidecar exe missing after copy: $bundledExe"
    exit 1
  }

  Log-Ok "Sidecar bundled: $tauriSidecarDir"


  Log-Info "Killing any running main-backend.exe..."
  cmd /c "taskkill /IM main-backend.exe /F >nul 2>&1"
  Start-Sleep -Milliseconds 500

  # --- smoke test the bundled exe prints READY (must not hang) ---
  Log-Info "Smoke testing bundled sidecar (wait for READY, then stop)..."

  $timeoutSec = 15
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $bundledExe
  $psi.Arguments = "--port 0"
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.CreateNoWindow = $true

  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi

  $null = $p.Start()

  $readyLine = $null
  $sw = [System.Diagnostics.Stopwatch]::StartNew()

  try {
    while ($sw.Elapsed.TotalSeconds -lt $timeoutSec) {
      # ReadLine blocks only if no newline; use Peek to avoid hang
      while (-not $p.StandardOutput.EndOfStream -and $p.StandardOutput.Peek() -ge 0) {
        $line = $p.StandardOutput.ReadLine()
        if ($line) {
          if ($line -match "^READY url=http://127\.0\.0\.1:\d+ token=") {
            $readyLine = $line
            break
          }
        }
      }

      if ($readyLine) { break }
      if ($p.HasExited) { break }

      Start-Sleep -Milliseconds 100
    }

    if (-not $readyLine) {
      # Collect some stderr for debugging
      $err = ""
      try { $err = $p.StandardError.ReadToEnd() } catch {}
      throw "Sidecar did not print READY within ${timeoutSec}s. stderr: $err"
    }

    Log-Ok "Sidecar smoke test OK: $readyLine"
  }
  finally {
    # Always stop the process so the pipeline doesn't hang
    try {
      if (-not $p.HasExited) { $p.Kill($true) }
    } catch {}
    try { $p.WaitForExit(3000) | Out-Null } catch {}
  }



} else {
  Log-Warn "Skipping Python backend build"
}



# ================================
# STEP 3: Copy driver installers + scripts
# ================================
Log-Step 3 "Copying Driver Installers + Scripts"

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

# ================================
# STEP 4: Build Tauri
# ================================
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

# ================================
# STEP 5: Verify (optional)
# ================================
if ($Verify) {
  Log-Step 5 "Running Verification"

  $verifyScript = Join-Path $root "scripts\verify_installer.ps1"
  if (Test-Path $verifyScript) {
    & $verifyScript
    if ($LASTEXITCODE -ne 0) {
      Log-Fail "Verification failed"
      exit 1
    }
    Log-Ok "Verification completed"
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

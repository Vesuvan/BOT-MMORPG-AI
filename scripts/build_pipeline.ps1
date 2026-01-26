<#
Build pipeline (Windows):
1) (Optional) Build wheelhouse + lock for OFFLINE installs
2) Bundle embeddable Python into src-tauri/resources/python/
3) Pre-install ALL Python deps (including tensorflow) into src-tauri/resources/python/site-packages
4) Build Python backend sidecar with PyInstaller (ONEDIR)
5) Copy sidecar folder into src-tauri/resources/sidecar/main-backend/
6) Copy driver installers + ps scripts into src-tauri/drivers and src-tauri/resources/scripts
7) Build Tauri app + NSIS installer (Now Lean: No redundant wheelhouse)

Requirements:
- Host Python 3.10+ available as `python` (used only at BUILD time to run pip)
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
  $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $user    = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = "$machine;$user"

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
    if ($LASTEXITCODE -ne 0) { throw "uv installation failed with exit code $LASTEXITCODE" }

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
  } catch {}

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

function Find-PythonExe {
  param([string[]]$Roots)

  foreach ($r in $Roots) {
    if (-not (Test-Path $r)) { continue }

    $hit = Get-ChildItem -Path $r -Recurse -File -Filter "python.exe" -ErrorAction SilentlyContinue |
      Select-Object -First 1

    if ($hit) { return $hit.FullName }
  }
  return $null
}

function Write-PyRuntime-Manifest {
  param([string]$DstDir, [string]$PickedFrom)

  try {
    $mf = Join-Path $DstDir "py_runtime_manifest.txt"
    $lines = @()
    $lines += ("BuiltAt=" + (Get-Date).ToString("s"))
    $lines += ("Host=" + $env:COMPUTERNAME)
    $lines += ("PickedFrom=" + $PickedFrom)
    $lines += ("Root=" + $DstDir)

    $files = Get-ChildItem -Path $DstDir -Recurse -File -ErrorAction SilentlyContinue |
      Select-Object FullName, Length |
      Sort-Object FullName

    foreach ($f in $files) {
      $lines += ("FILE=" + $f.FullName + " SIZE=" + $f.Length)
    }
    Set-Content -Path $mf -Value $lines -Encoding UTF8
  } catch {
    Log-Warn ("Could not write py_runtime_manifest.txt: " + $_.Exception.Message)
  }
}

function Ensure-EmbeddedPythonDownloaded {
  param([string]$Root)

  $ver = "3.10.11"
  $arch = "amd64"
  $zipName = "python-$ver-embed-$arch.zip"
  $url = "https://www.python.org/ftp/python/$ver/$zipName"

  $dst = Join-Path $Root "third_party\python\python-$ver-embed-$arch"
  New-Item -ItemType Directory -Force -Path $dst | Out-Null

  if (Test-Path (Join-Path $dst "python.exe")) {
    return $dst
  }

  $zipPath = Join-Path $dst $zipName

  Log-Info ("Python runtime not found. Downloading embeddable Python: " + $url)
  try {
    Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing
    Expand-Archive -Path $zipPath -DestinationPath $dst -Force
    Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
    return $dst
  } catch {
    throw ("Auto-download failed. Please manually download: " + $url + " and extract it to: " + $dst + "  Error=" + $_.Exception.Message)
  }
}

function Patch-EmbeddedPythonPth {
  param(
    [string]$PyDir,          # src-tauri/resources/python
    [string]$SitePackagesRel # ".\site-packages"
  )

  $pth = Get-ChildItem -Path $PyDir -Filter "python*._pth" -File -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $pth) {
    Log-Warn "No python*._pth found under $PyDir. Embedded python may not see site-packages."
    return
  }

  $pthPath = $pth.FullName
  $lines = @()
  try { $lines = Get-Content $pthPath -ErrorAction SilentlyContinue } catch { $lines = @() }
  if (-not $lines) { $lines = @() }

  if ($lines -notcontains $SitePackagesRel) { $lines += $SitePackagesRel }
  if ($lines -notcontains "import site")    { $lines += "import site" }

  Set-Content -Path $pthPath -Value $lines -Encoding ASCII
  Log-Ok "Patched embedded _pth: $pthPath"
}

function Ensure-BundledSitePackages {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)]
    [string]$RootDir
  )

  Set-StrictMode -Version Latest
  $ErrorActionPreference = "Stop"

  function Invoke-Checked {
    param(
      [Parameter(Mandatory=$true)][string]$FilePath,
      [Parameter(Mandatory=$true)][string[]]$Arguments,
      [string]$ErrorMessage = "Command failed"
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "$ErrorMessage (exit=$LASTEXITCODE): $FilePath $($Arguments -join ' ')"
    }
  }

  function Ensure-PipAvailable {
    param(
      [Parameter(Mandatory=$true)][string]$PythonExe
    )

    # Try pip first
    try {
      & $PythonExe -m pip --version | Out-Null
      if ($LASTEXITCODE -eq 0) { return }
    } catch {}

    # Try ensurepip (works for many venvs; might not exist in some stripped envs)
    try {
      & $PythonExe -m ensurepip --upgrade | Out-Null
      if ($LASTEXITCODE -eq 0) { return }
    } catch {}

    # Final: explicit failure with actionable message
    throw "Host python has no pip and ensurepip failed. Fix your build venv by recreating it with pip (e.g. 'uv venv --seed' or 'py -3.10 -m venv .venv' then 'python -m ensurepip --upgrade'). Host python: $PythonExe"
  }

  # ---- Paths ----
  $pyRoot   = Join-Path $RootDir "src-tauri\resources\python"
  $pyExe    = Join-Path $pyRoot "python.exe"
  $sitePkgs = Join-Path $pyRoot "site-packages"

  if (-not (Test-Path $pyExe)) { throw "Bundled python.exe not found: $pyExe" }
  New-Item -ItemType Directory -Force -Path $sitePkgs | Out-Null

  # Where your wheelhouse lives (generated by prepare script)
  $wheelhouseTag = "win_amd64_cp310"
  $whRoot   = Join-Path $RootDir "third_party\wheelhouse\$wheelhouseTag"
  $whWheels = Join-Path $whRoot "wheels"
  if (-not (Test-Path $whWheels)) { throw "Wheelhouse wheels folder missing: $whWheels" }

  Log-Step 99 "Pre-bundling Python deps into installer (site-packages)"
  Log-Info "Target site-packages: $sitePkgs"
  Log-Info "Wheelhouse Source: $whWheels"

  # ---- Host Python (drives pip install into target) ----
  $hostPy = Join-Path $RootDir ".venv\Scripts\python.exe"
  if (-not (Test-Path $hostPy)) { throw "Build venv python not found: $hostPy" }

  # Validate host python is 3.10 and 64-bit (wheelhouse is cp310 win_amd64)
  $hostInfo = & $hostPy -c "import sys,platform; print(f'{sys.version_info.major}.{sys.version_info.minor}|{platform.architecture()[0]}|{sys.executable}')"
  if ($LASTEXITCODE -ne 0) { throw "Failed to query host python info: $hostPy" }

  $parts = $hostInfo.Trim().Split('|')
  $hostVer  = $parts[0]
  $hostArch = $parts[1]
  if ($hostVer -ne "3.10") { throw "Step 99 must run with Python 3.10 to match wheelhouse ($wheelhouseTag). Got: $hostVer ($hostPy)" }
  if ($hostArch -ne "64bit") { throw "Step 99 requires 64-bit host python for win_amd64 wheels. Got: $hostArch ($hostPy)" }

  # Ensure pip exists (fixes: No module named pip)
  Ensure-PipAvailable -PythonExe $hostPy

  # Upgrade core build tools (quiet but logged to file)
  $pipLog = Join-Path $RootDir "build_pip_step99.log"
  Log-Info "Pip log: $pipLog"

  Invoke-Checked -FilePath $hostPy -Arguments @(
    "-m","pip","install","--upgrade","pip","setuptools","wheel",
    "--disable-pip-version-check","--no-python-version-warning",
    "--log",$pipLog
  ) -ErrorMessage "Failed to upgrade host pip/setuptools/wheel"

  # ---- Deterministic clean target ----
  try {
    if (Test-Path $sitePkgs) {
      Get-ChildItem -Path $sitePkgs -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
  } catch {}

  New-Item -ItemType Directory -Force -Path $sitePkgs | Out-Null

  # ---- Correct install strategy ----
  # DO NOT install "all wheels" with --no-deps (causes duplicates like pycparser 2.23 + 3.0).
  # Instead, install your project spec using the wheelhouse as the only source and let pip resolve.
  #
  # IMPORTANT: keep it offline:
  #   --no-index + --find-links wheelhouse
  #
  # Choose the same spec you used when building wheelhouse. If you already have a wheel for your project in wheelhouse,
  # pip will pick it from --find-links.
  $projectSpec = "bot-mmorpg-ai[launcher,backend,ml]"

  Log-Info "Installing project spec into bundled site-packages (offline): $projectSpec"

  Invoke-Checked -FilePath $hostPy -Arguments @(
    "-m","pip","install",
    "--no-index",
    "--find-links",$whWheels,
    "--target",$sitePkgs,
    "--upgrade",
    "--force-reinstall",
    "--disable-pip-version-check",
    "--no-python-version-warning",
    "--log",$pipLog,
    $projectSpec
  ) -ErrorMessage "Failed to install project deps into bundled site-packages from wheelhouse"

  # ---- Patch python._pth so embedded python sees .\site-packages and imports site ----
  Patch-EmbeddedPythonPth -PyDir $pyRoot -SitePackagesRel ".\site-packages"

  # ---- Size/NSIS fix: do not copy wheelhouse ----
  Log-Info "Skipping wheelhouse copy (using installed site-packages only) to save space and prevent NSIS mmapping errors."

  # ---- Smoke tests (use embedded python, not host) ----
  Log-Info "Smoke test: embedded python can import from bundled site-packages..."
  Invoke-Checked -FilePath $pyExe -Arguments @(
    "-c","import sys; import numpy; print('numpy_ok'); print('python_ok', sys.version)"
  ) -ErrorMessage "Bundled python cannot import numpy from site-packages"

  # Optional: tensorflow import only if installed
  $tfMarker1 = Join-Path $sitePkgs "tensorflow"
  $tfMarker2 = Join-Path $sitePkgs "tensorflow-*.dist-info"
  $hasTf = (Test-Path $tfMarker1) -or ((Get-ChildItem -Path $sitePkgs -Filter "tensorflow-*.dist-info" -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0)

  if ($hasTf) {
    Log-Info "Smoke test: tensorflow import (may take time)..."
    Invoke-Checked -FilePath $pyExe -Arguments @(
      "-c","import tensorflow as tf; print('tf_ok', tf.__version__)"
    ) -ErrorMessage "Bundled python cannot import tensorflow"
  } else {
    Log-Info "TensorFlow not detected in bundled site-packages; skipping tf import test."
  }

  Log-Ok "Bundled site-packages ready (production-safe install strategy)."
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
# STEP 0: Checking Prerequisites
# ================================
Log-Step 0 "Checking Prerequisites"

try {
  $pythonVersion = & python --version 2>&1
  Log-Ok "Host Python found: $pythonVersion"
} catch {
  Log-Fail "Host Python not found. Please install Python 3.10+"
  exit 1
}

$useUv = Ensure-Uv

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

  $cleanTargets = @(
    "dist",
    "build",
    ".venv",
    "src-tauri\target",
    "src-tauri\binaries",
    "src-tauri\drivers",
    "src-tauri\resources\scripts",
    "src-tauri\resources\sidecar",
    "src-tauri\resources\python\site-packages",
    "src-tauri\resources\wheelhouse"
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

# ===================== BUNDLE_PY_RUNTIME_BEGIN =====================
# STEP 1: Build wheelhouse + lock for OFFLINE installs
# =====================
Log-Step 1 "Preparing wheelhouse (cp310 win_amd64)"

# Run the prepare script to populate wheels
& (Join-Path $root "scripts\prepare_python_from_pyproject_embed310_target.ps1") `
  -Extras @("launcher","backend","ml") `
  -TargetTag "win_amd64_cp310" `
  -RebuildTarget
if ($LASTEXITCODE -ne 0) { exit 1 }
# ===================== BUNDLE_PY_RUNTIME_END =====================

# ================================
# STEP 2: Bundle embeddable python into src-tauri/resources/python
# ================================
Log-Step 2 "Bundling embeddable Python runtime"

try {
  $pyDst = Join-Path $root "src-tauri\resources\python"
  New-Item -ItemType Directory -Force -Path $pyDst | Out-Null

  # Clean destination (keep README.txt if present)
  Get-ChildItem $pyDst -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne "README.txt" } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

  $searchRoots = @(
    (Join-Path $root "third_party\python"),
    (Join-Path $root "src-tauri\resources\python")
  )

  $pyExePath = Find-PythonExe -Roots $searchRoots

  if (-not $pyExePath) {
    $dlDir = Ensure-EmbeddedPythonDownloaded -Root $root
    $pyExePath = Find-PythonExe -Roots @($dlDir, (Join-Path $root "third_party\python"))
  }

  if (-not $pyExePath) {
    throw ("Python runtime not found. Expected python.exe somewhere under: " + ($searchRoots -join " OR "))
  }

  $pickedDir = Split-Path -Parent $pyExePath
  Copy-Item -Recurse -Force (Join-Path $pickedDir "*") $pyDst
  Log-Ok ("Bundled Python runtime from: " + $pickedDir)

  $pyExeRoot = Join-Path $pyDst "python.exe"
  if (-not (Test-Path $pyExeRoot)) {
    throw ("Python runtime copy succeeded but python.exe not at root: " + $pyExeRoot + " (pickedDir=" + $pickedDir + ")")
  }

  Write-PyRuntime-Manifest -DstDir $pyDst -PickedFrom $pickedDir
} catch {
  Log-Fail "$_"
  exit 1
}

# ================================
# STEP 3: Pre-bundle ALL python deps into site-packages (includes tensorflow)
# ================================
try {
  Ensure-BundledSitePackages -RootDir $root
} catch {
  Log-Fail "$_"
  exit 1
}

# ================================
# STEP 4: UI Smoke Tests (pre-build)
# ================================
Log-Step 4 "UI Smoke Tests (pre-build)"

try {
  Log-Info "Running UI/installer smoke tests..."
  if (Test-Path "tests/test_tauri_ui_smoke.py") {
      & python tests/test_tauri_ui_smoke.py
      if ($LASTEXITCODE -ne 0) { throw "UI smoke tests failed (exit code $LASTEXITCODE)" }
      Log-Ok "UI smoke tests passed"
  } else {
      Log-Warn "Smoke test file not found. Skipping."
  }
} catch {
  Log-Fail "$_"
  exit 1
}

# ================================
# STEP 5: Build Python backend (PyInstaller ONEDIR)
# ================================
if (-not $SkipPython) {
  Log-Step 5 "Building Python Backend (PyInstaller ONEDIR)"

  $venv       = Join-Path $root ".venv"
  $venvPython = Join-Path $venv "Scripts\python.exe"

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

  Log-Info "Installing Python dependencies (build venv for PyInstaller)..."
  try {
    if ($useUv) {
      Log-Info "Using uv for package installation (faster than pip)"
      & uv pip install --python $venvPython -e ".[backend,packaging]" --quiet
      if ($LASTEXITCODE -ne 0) { throw "uv pip install project failed" }
    } else {
      Log-Info "Using pip for package installation"
      & $venvPython -m pip install -e ".[backend,packaging]" --quiet
      if ($LASTEXITCODE -ne 0) { throw "pip install project failed" }
    }
    Log-Ok "Project dependencies installed"
  } catch {
    Log-Fail "Failed to install project dependencies: $_"
    exit 1
  }

  Log-Info "Ensuring backend runtime deps (fastapi/uvicorn) are installed in build venv..."
  try {
    & $venvPython -c "import fastapi, uvicorn; print('backend deps OK')" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "missing" }
    Log-Ok "Backend runtime deps OK"
  } catch {
    try {
      if ($useUv) { & uv pip install --python $venvPython fastapi uvicorn --quiet }
      else        { & $venvPython -m pip install fastapi uvicorn --quiet }
      if ($LASTEXITCODE -ne 0) { throw "install failed" }

      & $venvPython -c "import fastapi, uvicorn; print('backend deps OK')" 2>$null
      if ($LASTEXITCODE -ne 0) { throw "still missing after install" }

      Log-Ok "Backend runtime deps installed"
    } catch {
      Log-Fail "Failed to ensure fastapi/uvicorn in build venv: $_"
      exit 1
    }
  }

  Log-Info "Ensuring PyInstaller is installed in build venv..."
  try {
    & $venvPython -m pip show pyinstaller *> $null
    if ($LASTEXITCODE -ne 0) {
      if ($useUv) { & uv pip install --python $venvPython pyinstaller --quiet }
      else        { & $venvPython -m pip install pyinstaller --quiet }
      if ($LASTEXITCODE -ne 0) { throw "install failed" }
    }
    Log-Ok "PyInstaller ready"
  } catch {
    Log-Fail "Failed to install PyInstaller: $_"
    exit 1
  }

  Log-Info "Building backend sidecar with PyInstaller (onedir)..."

  $backend = Join-Path $root "backend\entry_main.py"
  if (-not (Test-Path $backend)) {
    Log-Fail "Backend source not found: $backend"
    exit 1
  }

  try {
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

  Log-Info "Bundling sidecar into Tauri resources..."
  $tauriSidecarDir = Join-Path $root "src-tauri\resources\sidecar\main-backend"

  if (Test-Path $tauriSidecarDir) {
    Remove-Item -Recurse -Force $tauriSidecarDir -ErrorAction SilentlyContinue
  }
  New-Item -Force -ItemType Directory $tauriSidecarDir | Out-Null

  $lockNames = @("main-backend", "main-backend.exe", "BOT-MMORPG-AI", "BOT-MMORPG-AI.exe")
  foreach ($n in $lockNames) {
    try { Get-Process -Name $n -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue } catch {}
  }

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

  $bundledExe = Join-Path $tauriSidecarDir "main-backend.exe"
  if (-not (Test-Path $bundledExe)) {
    Log-Fail "Bundled sidecar exe missing after copy: $bundledExe"
    exit 1
  }

  Log-Ok "Sidecar bundled: $tauriSidecarDir"

  Log-Info "Killing any running main-backend.exe..."
  cmd /c "taskkill /IM main-backend.exe /F >nul 2>&1"
  Start-Sleep -Milliseconds 500

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
      while (-not $p.StandardOutput.EndOfStream -and $p.StandardOutput.Peek() -ge 0) {
        $line = $p.StandardOutput.ReadLine()
        if ($line -and $line -match "^READY url=http://127\.0\.0\.1:\d+ token=") {
          $readyLine = $line
          break
        }
      }

      if ($readyLine) { break }
      if ($p.HasExited) { break }

      Start-Sleep -Milliseconds 100
    }

    if (-not $readyLine) {
      $err = ""
      try { $err = $p.StandardError.ReadToEnd() } catch {}
      throw "Sidecar did not print READY within ${timeoutSec}s. stderr: $err"
    }

    Log-Ok "Sidecar smoke test OK: $readyLine"
  }
  finally {
    try { if (-not $p.HasExited) { $p.Kill($true) } } catch {}
    try { $p.WaitForExit(3000) | Out-Null } catch {}
  }

} else {
  Log-Warn "Skipping Python backend build"
}

# ================================
# STEP 6: Copy driver installers + scripts
# ================================
Log-Step 6 "Copying Driver Installers + Scripts"

$drvInterDir = Join-Path $root "src-tauri\drivers\interception"
$drvVjoyDir  = Join-Path $root "src-tauri\drivers\vjoy"
$resScripts  = Join-Path $root "src-tauri\resources\scripts"

New-Item -Force -ItemType Directory $drvInterDir | Out-Null
New-Item -Force -ItemType Directory $drvVjoyDir  | Out-Null
New-Item -Force -ItemType Directory $resScripts  | Out-Null

$mlScriptSrc = Join-Path $root "scripts\install_ml_deps.ps1"
$mlScriptDst = Join-Path $resScripts "install_ml_deps.ps1"
if (Test-Path $mlScriptSrc) {
  Copy-Item -Force $mlScriptSrc $mlScriptDst
  Log-Ok "Install ML deps script copied"
} else {
  Log-Warn "Install ML deps script not found: $mlScriptSrc"
}

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


Log-Step 6.5 "Bundling versions into resources"

$srcVersions = Join-Path $root "versions"
$dstVersions = Join-Path $root "src-tauri\resources\versions"

if (-not (Test-Path $srcVersions)) { throw "Missing versions folder: $srcVersions" }

if (Test-Path $dstVersions) {
  Remove-Item $dstVersions -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $dstVersions | Out-Null

Copy-Item -Recurse -Force (Join-Path $srcVersions "*") $dstVersions
Log-Ok "Versions copied to: $dstVersions"



# ================================
# STEP 7: Build Tauri
# ================================
if (-not $SkipTauri) {
  Log-Step 7 "Building Tauri Application"

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
# STEP 8: Verify (optional)
# ================================
if ($Verify) {
  Log-Step 8 "Running Verification"

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
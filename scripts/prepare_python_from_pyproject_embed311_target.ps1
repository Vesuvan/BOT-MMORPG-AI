<#
prepare_python_from_pyproject_embed311_target.ps1

PRODUCTION-READY FIX

What this script does:
- Ensures Windows embeddable Python 3.11.9 (amd64) exists under:
    third_party/python/python-3.11.9-embed-amd64
  If missing, it auto-downloads and extracts it (CI-friendly).
- Patches python._pth to enable "import site" and optional "Lib" visibility.
- Ensures pip exists (bootstraps via get-pip.py if needed).
- Installs your project (+ extras) into a portable --target site-packages folder (no venv).
- Produces a lock file via pip freeze.
- Downloads wheels into a wheelhouse for offline use.

Outputs:
- third_party/wheelhouse/<TargetTag>/requirements.lock.txt
- third_party/wheelhouse/<TargetTag>/wheels/*.whl
- third_party/python/portable_site_packages/<TargetTag>/

Notes:
- Requires internet access in CI for:
  - Downloading embeddable Python zip (if missing)
  - Bootstrapping pip (if missing)
  - pip install / download wheels
- If some dependencies have no wheels for cp311/win_amd64, pip download may fail.
#>

param(
  [string[]]$Extras = @("backend","packaging"),
  [string]$TargetTag = "win_amd64_cp311",
  [switch]$RebuildTarget
)

$ErrorActionPreference = "Stop"

function Info($m) { Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[FAIL] $m" -ForegroundColor Red; exit 1 }

function Ensure-Tls12 {
  try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
}

function Ensure-EmbeddedPython311Downloaded {
  param(
    [Parameter(Mandatory=$true)][string]$Root
  )

  $ver  = "3.11.9"
  $arch = "amd64"
  $zipName = "python-$ver-embed-$arch.zip"
  $url = "https://www.python.org/ftp/python/$ver/$zipName"

  $dst = Join-Path $Root ("third_party\python\python-$ver-embed-$arch")
  $pyExe = Join-Path $dst "python.exe"

  New-Item -ItemType Directory -Force -Path $dst | Out-Null

  if (Test-Path $pyExe) {
    Ok "Embeddable Python already present: $pyExe"
    return $dst
  }

  Ensure-Tls12
  $zipPath = Join-Path $dst $zipName

  Info "Embeddable Python missing; downloading: $url"
  try {
    Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing
  } catch {
    Fail ("Failed to download embeddable Python from: $url`nError: " + $_.Exception.Message)
  }

  Info "Extracting embeddable Python to: $dst"
  try {
    Expand-Archive -Path $zipPath -DestinationPath $dst -Force
  } catch {
    Fail ("Failed to extract: $zipPath`nError: " + $_.Exception.Message)
  } finally {
    Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
  }

  if (-not (Test-Path $pyExe)) {
    Fail "python.exe still missing after extraction at: $pyExe"
  }

  Ok "Downloaded embeddable Python to: $dst"
  return $dst
}

function Patch-EmbeddablePth {
  param(
    [Parameter(Mandatory=$true)][string]$PyRuntimeDir
  )

  $pth = Get-ChildItem -Path $PyRuntimeDir -Filter "python*._pth" -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $pth) {
    Warn "No python._pth found in $PyRuntimeDir; skipping _pth patch."
    return
  }

  Info "Patching _pth: $($pth.Name)"
  $lines = Get-Content -Path $pth.FullName -ErrorAction Stop

  # Enable import site
  $hasImportSite = $false
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "import site") { $hasImportSite = $true }
    if ($lines[$i].Trim() -eq "#import site") {
      $lines[$i] = "import site"
      $hasImportSite = $true
    }
  }
  if (-not $hasImportSite) { $lines += "import site" }

  # Add Lib if it exists (helps stdlib visibility for some layouts)
  $libDir = Join-Path $PyRuntimeDir "Lib"
  $hasLib = $false
  foreach ($ln in $lines) {
    if ($ln.Trim() -eq "Lib") { $hasLib = $true; break }
  }

  if ((Test-Path $libDir) -and (-not $hasLib)) {
    $new = @()
    foreach ($ln in $lines) {
      $new += $ln
      if ($ln.Trim() -eq ".") { $new += "Lib" }
    }
    $lines = $new
    Info "Added 'Lib' to _pth."
  }

  # Embeddable python expects ASCII here
  Set-Content -Path $pth.FullName -Value $lines -Encoding ASCII
  Ok "Patched _pth."
}

function Ensure-Pip {
  param(
    [Parameter(Mandatory=$true)][string]$PyExe,
    [Parameter(Mandatory=$true)][string]$PyRuntimeDir
  )

  Info "Ensuring pip exists..."
  $pipOk = $false
  try {
    & $PyExe -m pip --version | Out-Null
    if ($LASTEXITCODE -eq 0) { $pipOk = $true }
  } catch {}

  if ($pipOk) {
    Ok "pip present."
    return
  }

  Warn "pip missing; bootstrapping via get-pip.py (internet required)..."
  Ensure-Tls12
  $getPip = Join-Path $PyRuntimeDir "get-pip.py"
  try {
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -UseBasicParsing
  } catch {
    Fail ("Failed to download get-pip.py`nError: " + $_.Exception.Message)
  }

  & $PyExe $getPip
  if ($LASTEXITCODE -ne 0) { Fail "get-pip.py execution failed" }

  Remove-Item -Force $getPip -ErrorAction SilentlyContinue

  & $PyExe -m pip --version | Out-Null
  if ($LASTEXITCODE -ne 0) { Fail "pip still missing after bootstrap" }

  Ok "pip bootstrapped."
}

# --- Paths / Inputs ---
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir "..")).Path

$pyproject = Join-Path $root "pyproject.toml"
if (-not (Test-Path $pyproject)) { Fail "pyproject.toml not found at: $pyproject" }

# Ensure embedded python exists (auto-download if missing)
$pyRuntimeDir = Ensure-EmbeddedPython311Downloaded -Root $root
$pyExe = Join-Path $pyRuntimeDir "python.exe"
if (-not (Test-Path $pyExe)) { Fail "Missing python.exe at: $pyExe" }

$wheelRoot = Join-Path $root ("third_party\wheelhouse\" + $TargetTag)
$wheelDir  = Join-Path $wheelRoot "wheels"
$lockFile  = Join-Path $wheelRoot "requirements.lock.txt"

# Target site-packages folder (portable env)
$targetRoot = Join-Path $root "third_party\python\portable_site_packages"
$targetDir  = Join-Path $targetRoot $TargetTag

Info "Repo root: $root"
Info "Embeddable python: $pyExe"
Info "Target site-packages: $targetDir"
Info "Wheelhouse: $wheelRoot"
Info ("Extras: " + ($Extras -join ","))

# 1) Patch python._pth to enable import site (and Lib if exists)
Patch-EmbeddablePth -PyRuntimeDir $pyRuntimeDir

# 2) Ensure pip exists (bootstrap if missing)
Ensure-Pip -PyExe $pyExe -PyRuntimeDir $pyRuntimeDir

# 3) Build the portable target site-packages by installing your project + extras
if ($RebuildTarget -and (Test-Path $targetDir)) {
  Info "RebuildTarget enabled; removing: $targetDir"
  Remove-Item -Recurse -Force $targetDir -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

Info "Upgrading pip tooling and build dependencies (hatchling, editables, pathspec)..."
& $pyExe -m pip install -U pip setuptools wheel hatchling editables pathspec
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade/build-tools installation failed" }

$extrasStr = ""
if ($Extras -and $Extras.Count -gt 0) { $extrasStr = "[" + ($Extras -join ",") + "]" }

Info ("Installing project into --target (no venv): -e .${extrasStr}")
Push-Location $root
try {
  # --no-build-isolation helps on embeddable Python where isolated builds may fail
  & $pyExe -m pip install --no-build-isolation --target $targetDir -e ".${extrasStr}"
  if ($LASTEXITCODE -ne 0) { throw "pip install --target failed" }
} finally {
  Pop-Location
}
Ok "Installed project into portable target."

# 4) Write lock file from portable target
Info "Generating lock file from portable target..."
New-Item -ItemType Directory -Force -Path $wheelRoot | Out-Null

$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $targetDir
try {
  & $pyExe -m pip freeze | Set-Content -Path $lockFile -Encoding UTF8
  if ($LASTEXITCODE -ne 0) { throw "pip freeze failed" }
} finally {
  if ($null -ne $oldPythonPath) { $env:PYTHONPATH = $oldPythonPath } else { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue }
}
Ok "Lock file written: $lockFile"

# 5) Download wheels into wheelhouse
New-Item -ItemType Directory -Force -Path $wheelDir | Out-Null
Info "Downloading wheels (binary only) into wheelhouse..."
& $pyExe -m pip download --only-binary=:all: --dest $wheelDir -r $lockFile
if ($LASTEXITCODE -ne 0) {
  Fail "pip download failed (some deps may lack wheels for cp311/win_amd64 or conflict)."
}

$wheelCount = (Get-ChildItem -Path $wheelDir -Filter "*.whl" -ErrorAction SilentlyContinue).Count
if ($wheelCount -lt 1) { Fail "No wheels downloaded. Check lock file." }

Ok "Wheelhouse ready: $wheelCount wheel(s)."
Ok "DONE."

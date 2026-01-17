<#
prepare_python_from_pyproject_embed311_target.ps1

Works with embeddable Python that has NO venv:
- Uses pip --target to create a portable site-packages folder
- Generates requirements.lock.txt via pip freeze from that target
- Downloads offline wheelhouse from the lock

Output:
- third_party/wheelhouse/<TargetTag>/requirements.lock.txt
- third_party/wheelhouse/<TargetTag>/wheels/*.whl
- third_party/python/portable_site_packages/ (optional build artifact)

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

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir "..")).Path

$pyproject = Join-Path $root "pyproject.toml"
if (-not (Test-Path $pyproject)) { Fail "pyproject.toml not found at: $pyproject" }

$pyRuntimeDir = Join-Path $root "third_party\python\python-3.11.9-embed-amd64"
$pyExe         = Join-Path $pyRuntimeDir "python.exe"
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
$pth = Get-ChildItem -Path $pyRuntimeDir -Filter "python*._pth" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pth) {
  Info "Patching _pth: $($pth.Name)"
  $lines = Get-Content -Path $pth.FullName -ErrorAction Stop

  # enable import site
  $hasImportSite = $false
  for ($i=0; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "import site") { $hasImportSite = $true }
    if ($lines[$i].Trim() -eq "#import site") {
      $lines[$i] = "import site"
      $hasImportSite = $true
    }
  }
  if (-not $hasImportSite) { $lines += "import site" }

  # add Lib if it exists (doesn't add venv, just helps stdlib visibility)
  $libDir = Join-Path $pyRuntimeDir "Lib"
  $hasLib = $lines | Where-Object { $_.Trim() -eq "Lib" }
  if ((Test-Path $libDir) -and (-not $hasLib)) {
    $new = @()
    foreach ($ln in $lines) {
      $new += $ln
      if ($ln.Trim() -eq ".") { $new += "Lib" }
    }
    $lines = $new
    Info "Added 'Lib' to _pth."
  }

  Set-Content -Path $pth.FullName -Value $lines -Encoding ASCII
  Ok "Patched _pth."
} else {
  Warn "No python._pth found; skipping."
}

# 2) Ensure pip exists (bootstrap if missing)
Info "Ensuring pip exists..."
$pipOk = $false
try { & $pyExe -m pip --version | Out-Null; if ($LASTEXITCODE -eq 0) { $pipOk = $true } } catch {}

if (-not $pipOk) {
  Warn "pip missing; bootstrapping via get-pip.py (internet required)..."
  $getPip = Join-Path $pyRuntimeDir "get-pip.py"
  Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -UseBasicParsing
  & $pyExe $getPip
  if ($LASTEXITCODE -ne 0) { Fail "get-pip.py failed" }
  Remove-Item -Force $getPip -ErrorAction SilentlyContinue

  & $pyExe -m pip --version | Out-Null
  if ($LASTEXITCODE -ne 0) { Fail "pip still missing after bootstrap" }
  Ok "pip bootstrapped."
} else {
  Ok "pip present."
}

# 3) Build the portable target site-packages by installing your project + extras
if ($RebuildTarget -and (Test-Path $targetDir)) {
  Info "RebuildTarget enabled; removing: $targetDir"
  Remove-Item -Recurse -Force $targetDir -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

Info "Upgrading pip tooling and build dependencies (hatchling, editables, pathspec)..."
# FIXED: Added editables and pathspec. 
# Hatchling needs 'editables' to handle editable (-e) installs.
& $pyExe -m pip install -U pip setuptools wheel hatchling editables pathspec
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade/build-tools installation failed" }

$extrasStr = ""
if ($Extras -and $Extras.Count -gt 0) { $extrasStr = "[" + ($Extras -join ",") + "]" }

# Install your project into target folder
Info ("Installing project into --target (no venv): -e .${extrasStr}")
Push-Location $root
try {
  # We use --no-build-isolation because the embeddable python environment 
  # often cannot create the temporary venvs needed for isolated builds.
  & $pyExe -m pip install --no-build-isolation --target $targetDir -e ".${extrasStr}"
  if ($LASTEXITCODE -ne 0) { throw "pip install --target failed" }
} finally { Pop-Location }
Ok "Installed project into portable target."

# 4) Write lock file
Info "Generating lock file from portable target..."
New-Item -ItemType Directory -Force -Path $wheelRoot | Out-Null

$env:PYTHONPATH = $targetDir
try {
  & $pyExe -m pip freeze | Set-Content -Path $lockFile -Encoding UTF8
  if ($LASTEXITCODE -ne 0) { throw "pip freeze failed" }
} finally {
  Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
}
Ok "Lock file written: $lockFile"

# 5) Download wheels
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
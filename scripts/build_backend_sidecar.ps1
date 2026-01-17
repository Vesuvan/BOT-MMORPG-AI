<#
Build ONLY the Python backend sidecar (PyInstaller ONEDIR)
Output:
  dist\main-backend\main-backend.exe
Usage:
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_backend_sidecar.ps1
#>

$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Fail($m){ Write-Host "[FAIL] $m" -ForegroundColor Red; exit 1 }

# Repo root = one folder above /scripts
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$venv = Join-Path $root ".venv"
$py   = Join-Path $venv "Scripts\python.exe"

Info "Repo root: $root"

# 1) Create venv if missing
if (-not (Test-Path $py)) {
  Info "Creating venv at: $venv"
  python -m venv $venv
  if (-not (Test-Path $py)) { Fail "venv creation failed: $py missing" }
  Ok "venv created"
} else {
  Info "Using existing venv: $venv"
}

# 2) Ensure pip exists (fixes: No module named pip)
Info "Ensuring pip is available in venv..."
& $py -m ensurepip --upgrade | Out-Null
& $py -m pip install --upgrade pip setuptools wheel | Out-Null
Ok "pip ready"

# 3) Install runtime deps + PyInstaller into venv
Info "Installing project + backend deps into venv..."
& $py -m pip install -e . | Out-Null
& $py -m pip install fastapi uvicorn pyinstaller | Out-Null
Ok "deps installed"

# 4) Choose entrypoint
$entry = Join-Path $root "backend\entry_main.py"
if (-not (Test-Path $entry)) { Fail "Missing entrypoint: $entry" }

# 5) Build ONEDIR (reliable)
Info "Building sidecar with PyInstaller (onedir)..."
& $py -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --console `
  --name "main-backend" `
  --hidden-import "uvicorn.logging" `
  --hidden-import "uvicorn.loops.auto" `
  --hidden-import "uvicorn.protocols.http.auto" `
  --hidden-import "uvicorn.protocols.websockets.auto" `
  --hidden-import "uvicorn.lifespan.on" `
  $entry

if ($LASTEXITCODE -ne 0) { Fail "PyInstaller failed (exit code $LASTEXITCODE)" }

$exe = Join-Path $root "dist\main-backend\main-backend.exe"
if (-not (Test-Path $exe)) { Fail "Build succeeded but exe not found: $exe" }

$sizeMb = [Math]::Round(((Get-Item $exe).Length / 1MB), 2)
Ok "Built: $exe ($sizeMb MB)"

Info "Test it with:"
Write-Host "  `"$exe`" --port 0" -ForegroundColor Yellow

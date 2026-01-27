$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir "..")).Path

$py = Join-Path $root "src-tauri\resources\python\python.exe"
if (-not (Test-Path $py)) { throw "Embedded python not found: $py" }

$targetDir = Join-Path $root "src-tauri\resources\python\site-packages"
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

& $py -m pip install --upgrade pip setuptools wheel
& $py -m pip install --target $targetDir "bot-mmorpg-ai[ml]"

Write-Host "[OK] Installed ML deps into: $targetDir"

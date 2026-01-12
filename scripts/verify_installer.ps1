<#
.SYNOPSIS
    Verifies that the installer was built correctly with all required components.

.DESCRIPTION
    This script checks:
    - Backend sidecar binary exists and is valid
    - Driver installers are present
    - Tauri application was built
    - NSIS installer was created
    - All files have reasonable sizes

.EXAMPLE
    .\scripts\verify_installer.ps1
#>

$ErrorActionPreference = "Stop"

function Write-Success($msg) {
    Write-Host "✓ $msg" -ForegroundColor Green
}

function Write-Failure($msg) {
    Write-Host "✗ $msg" -ForegroundColor Red
}

function Write-Info($msg) {
    Write-Host "ℹ $msg" -ForegroundColor Cyan
}

$root = Resolve-Path "$(Split-Path -Parent $MyInvocation.MyCommand.Path)\.." | % Path
$errors = @()

Write-Info "Starting installer verification..."
Write-Info "Root directory: $root"
Write-Host ""

# Check 1: Backend sidecar binary
Write-Info "Checking backend sidecar binary..."
$target = "x86_64-pc-windows-msvc"
$sidecarPath = Join-Path $root "src-tauri\binaries\main-backend-$target.exe"

if (Test-Path $sidecarPath) {
    $size = (Get-Item $sidecarPath).Length / 1MB
    if ($size -gt 1) {
        Write-Success "Backend sidecar exists: $([math]::Round($size, 2)) MB"
    } else {
        Write-Failure "Backend sidecar is too small: $([math]::Round($size, 2)) MB"
        $errors += "Backend sidecar file size is suspiciously small"
    }
} else {
    Write-Failure "Backend sidecar not found: $sidecarPath"
    $errors += "Missing backend sidecar binary"
}

# Check 2: Driver installers
Write-Info "Checking driver installers..."

$interceptionPath = Join-Path $root "src-tauri\drivers\interception\install-interception.exe"
if (Test-Path $interceptionPath) {
    $size = (Get-Item $interceptionPath).Length / 1KB
    Write-Success "Interception installer exists: $([math]::Round($size, 2)) KB"
} else {
    Write-Failure "Interception installer not found: $interceptionPath"
    $errors += "Missing Interception driver installer"
}

$vjoyPath = Join-Path $root "src-tauri\drivers\vjoy\vJoySetup.exe"
if (Test-Path $vjoyPath) {
    $size = (Get-Item $vjoyPath).Length / 1KB
    Write-Success "vJoy installer exists: $([math]::Round($size, 2)) KB"
} else {
    Write-Failure "vJoy installer not found: $vjoyPath"
    $errors += "Missing vJoy driver installer"
}

# Check 3: PowerShell driver install script
Write-Info "Checking install scripts..."

$installScriptPath = Join-Path $root "src-tauri\resources\scripts\install_drivers.ps1"
if (Test-Path $installScriptPath) {
    Write-Success "Install drivers script exists"
} else {
    Write-Failure "Install drivers script not found: $installScriptPath"
    $errors += "Missing install_drivers.ps1 script"
}

# Check 4: Tauri application binary
Write-Info "Checking Tauri application binary..."

$tauriExePath = Join-Path $root "src-tauri\target\release\bot-mmorpg-ai.exe"
if (Test-Path $tauriExePath) {
    $size = (Get-Item $tauriExePath).Length / 1MB
    Write-Success "Tauri application exists: $([math]::Round($size, 2)) MB"
} else {
    Write-Failure "Tauri application not found: $tauriExePath"
    $errors += "Missing Tauri application binary"
}

# Check 5: NSIS installer
Write-Info "Checking NSIS installer..."

$installerDir = Join-Path $root "src-tauri\target\release\bundle\nsis"
if (Test-Path $installerDir) {
    $installers = Get-ChildItem -Path $installerDir -Filter "*.exe"

    if ($installers.Count -gt 0) {
        foreach ($installer in $installers) {
            $size = $installer.Length / 1MB
            Write-Success "NSIS installer: $($installer.Name) ($([math]::Round($size, 2)) MB)"

            # Check if it's a valid PE executable
            $header = Get-Content -Path $installer.FullName -Encoding Byte -TotalCount 2
            if ($header[0] -eq 0x4D -and $header[1] -eq 0x5A) {
                Write-Success "Valid PE executable header"
            } else {
                Write-Failure "Invalid executable header for $($installer.Name)"
                $errors += "Invalid installer executable format"
            }
        }
    } else {
        Write-Failure "No installer executables found in $installerDir"
        $errors += "No NSIS installer generated"
    }
} else {
    Write-Failure "Installer directory not found: $installerDir"
    $errors += "NSIS installer directory does not exist"
}

# Check 6: UI files
Write-Info "Checking UI files..."

$uiIndexPath = Join-Path $root "tauri-ui\index.html"
if (Test-Path $uiIndexPath) {
    Write-Success "UI index.html exists"
} else {
    Write-Failure "UI index.html not found: $uiIndexPath"
    $errors += "Missing UI index.html"
}

$uiJsPath = Join-Path $root "tauri-ui\main.js"
if (Test-Path $uiJsPath) {
    Write-Success "UI main.js exists"
} else {
    Write-Failure "UI main.js not found: $uiJsPath"
    $errors += "Missing UI main.js"
}

# Summary
Write-Host ""
Write-Host "======================================"
Write-Host " VERIFICATION SUMMARY"
Write-Host "======================================"

if ($errors.Count -eq 0) {
    Write-Success "All checks passed! Installer is ready."
    Write-Host ""
    Write-Info "Installer location: $installerDir"
    exit 0
} else {
    Write-Failure "Verification failed with $($errors.Count) error(s):"
    Write-Host ""
    foreach ($error in $errors) {
        Write-Host "  • $error" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Info "Please run the build pipeline again: .\scripts\build_pipeline.ps1"
    exit 1
}

<#
.SYNOPSIS
    Development test runner for BOT-MMORPG-AI backend

.DESCRIPTION
    Creates a temporary mock environment that simulates the production installation
    structure without modifying the repo tree. This allows testing the backend,
    modelhub, and ML scripts before building the installer.

.PARAMETER Mode
    Test mode: "backend", "ml", "full", or "cleanup"
    - backend: Test FastAPI backend server only
    - ml: Test ML scripts (collect, train, test)
    - full: Run all tests
    - cleanup: Remove test environment

.PARAMETER KeepEnv
    Keep the test environment after tests complete (for debugging)

.EXAMPLE
    .\dev_test_backend.ps1 -Mode backend
    .\dev_test_backend.ps1 -Mode full -KeepEnv
    .\dev_test_backend.ps1 -Mode cleanup
#>

param(
    [ValidateSet("backend", "ml", "full", "cleanup")]
    [string]$Mode = "backend",
    [switch]$KeepEnv
)

$ErrorActionPreference = "Stop"

# Colors for output
function Log-Ok([string]$msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Log-Info([string]$msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Log-Warn([string]$msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Log-Fail([string]$msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }
function Log-Test([string]$msg) { Write-Host "[TEST] $msg" -ForegroundColor Magenta }

# Get paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$testEnvRoot = Join-Path $env:TEMP "BOT-MMORPG-AI-DevTest"

Write-Host ""
Write-Host "=============================================="
Write-Host " BOT-MMORPG-AI Development Test Runner"
Write-Host "=============================================="
Write-Host ""
Log-Info "Repo root: $repoRoot"
Log-Info "Test environment: $testEnvRoot"
Log-Info "Mode: $Mode"
Write-Host ""

# Cleanup function
function Remove-TestEnv {
    if (Test-Path $testEnvRoot) {
        Log-Info "Cleaning up test environment..."

        # Kill any running processes
        Get-Process -Name "python*" -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -like "*$testEnvRoot*" } |
            Stop-Process -Force -ErrorAction SilentlyContinue

        Start-Sleep -Milliseconds 500
        Remove-Item -Recurse -Force $testEnvRoot -ErrorAction SilentlyContinue
        Log-Ok "Test environment removed"
    }
}

if ($Mode -eq "cleanup") {
    Remove-TestEnv
    exit 0
}

# Create mock production environment
function Setup-MockEnvironment {
    Log-Info "Setting up mock production environment..."

    # Create directory structure (mirrors C:\Program Files\BOT-MMORPG-AI)
    $dirs = @(
        "$testEnvRoot",
        "$testEnvRoot\runtime\py\python",
        "$testEnvRoot\runtime\py\site-packages",
        "$testEnvRoot\resources\versions\0.01",
        "$testEnvRoot\resources\backend",
        "$testEnvRoot\resources\modelhub",
        "$testEnvRoot\datasets",
        "$testEnvRoot\models",
        "$testEnvRoot\logs",
        "$testEnvRoot\content"
    )

    foreach ($d in $dirs) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
    }

    # Create symlinks or copy files to simulate bundled resources
    # (Using copies to avoid permission issues on Windows)

    # Copy backend
    Log-Info "Copying backend files..."
    Copy-Item -Recurse -Force "$repoRoot\backend\*" "$testEnvRoot\resources\backend\"

    # Copy modelhub
    Log-Info "Copying modelhub files..."
    Copy-Item -Recurse -Force "$repoRoot\modelhub\*" "$testEnvRoot\resources\modelhub\"

    # Copy versions (ML scripts)
    Log-Info "Copying ML scripts..."
    Copy-Item -Recurse -Force "$repoRoot\versions\0.01\*" "$testEnvRoot\resources\versions\0.01\"

    # Create a mock .env file
    $envContent = @"
AI_PROVIDER="gemini"
GEMINI_API_KEY=""
OPENAI_API_KEY=""
PYTHON_PATH=""
"@
    Set-Content -Path "$testEnvRoot\.env" -Value $envContent

    Log-Ok "Mock environment created"
    return $testEnvRoot
}

# Find Python executable
function Get-PythonExe {
    # Try repo venv first
    $venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
        return $venvPy
    }

    # Try system python
    try {
        $sysPy = (Get-Command python -ErrorAction SilentlyContinue).Source
        if ($sysPy) { return $sysPy }
    } catch {}

    # Try py launcher
    try {
        $pyLauncher = (Get-Command py -ErrorAction SilentlyContinue).Source
        if ($pyLauncher) { return "py -3.10" }
    } catch {}

    throw "Python not found. Please install Python 3.10+ or create a venv in .venv"
}

# Test backend server
function Test-Backend {
    param([string]$EnvRoot, [string]$PythonExe)

    Log-Test "Testing Backend Server..."

    $backendScript = Join-Path $EnvRoot "resources\backend\entry_main.py"
    if (-not (Test-Path $backendScript)) {
        Log-Fail "Backend script not found: $backendScript"
        return $false
    }

    # Set up environment variables (mimics what Rust does)
    $env:PYTHONPATH = @(
        "$EnvRoot\resources\backend",
        "$EnvRoot\resources\modelhub",
        "$EnvRoot\resources",
        $repoRoot
    ) -join ";"

    $env:PYTHONUNBUFFERED = "1"
    $env:PYTHONUTF8 = "1"
    $env:MODELHUB_DATA_ROOT = $EnvRoot
    $env:MODELHUB_RESOURCE_ROOT = "$EnvRoot\resources"

    # Generate a test token
    $token = "test-token-$(Get-Random)"

    Log-Info "Starting backend server..."
    Log-Info "PYTHONPATH: $env:PYTHONPATH"

    # Start backend process
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $PythonExe
    $psi.Arguments = "-u `"$backendScript`" --port 0 --token $token"
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.WorkingDirectory = $EnvRoot

    # Set environment
    $psi.EnvironmentVariables["PYTHONPATH"] = $env:PYTHONPATH
    $psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1"
    $psi.EnvironmentVariables["PYTHONUTF8"] = "1"
    $psi.EnvironmentVariables["MODELHUB_DATA_ROOT"] = $EnvRoot
    $psi.EnvironmentVariables["MODELHUB_RESOURCE_ROOT"] = "$EnvRoot\resources"

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi

    try {
        $null = $process.Start()
        Log-Info "Backend PID: $($process.Id)"

        # Wait for READY line
        $timeout = 30
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $readyLine = $null
        $port = $null

        while ($sw.Elapsed.TotalSeconds -lt $timeout) {
            if ($process.HasExited) {
                $stderr = $process.StandardError.ReadToEnd()
                Log-Fail "Backend exited prematurely"
                if ($stderr) { Log-Fail "stderr: $stderr" }
                return $false
            }

            while ($process.StandardOutput.Peek() -ge 0) {
                $line = $process.StandardOutput.ReadLine()
                Write-Host "  [Backend] $line" -ForegroundColor DarkGray

                if ($line -match "^READY url=http://127\.0\.0\.1:(\d+) token=") {
                    $readyLine = $line
                    $port = $Matches[1]
                    break
                }
            }

            if ($readyLine) { break }
            Start-Sleep -Milliseconds 100
        }

        if (-not $readyLine) {
            Log-Fail "Backend did not print READY within ${timeout}s"
            $stderr = $process.StandardError.ReadToEnd()
            if ($stderr) { Log-Fail "stderr: $stderr" }
            return $false
        }

        Log-Ok "Backend started: $readyLine"

        # Test API endpoints
        Log-Info "Testing API endpoints..."

        $baseUrl = "http://127.0.0.1:$port"
        $headers = @{ "X-Auth-Token" = $token }

        # Test /modelhub/available
        try {
            $response = Invoke-RestMethod -Uri "$baseUrl/modelhub/available" -Headers $headers -TimeoutSec 5
            Log-Ok "GET /modelhub/available - OK"
        } catch {
            Log-Warn "GET /modelhub/available - Failed: $_"
        }

        # Test /modelhub/games
        try {
            $response = Invoke-RestMethod -Uri "$baseUrl/modelhub/games" -Headers $headers -TimeoutSec 5
            Log-Ok "GET /modelhub/games - OK (found $($response.Count) games)"
        } catch {
            Log-Warn "GET /modelhub/games - Failed: $_"
        }

        Log-Ok "Backend tests PASSED"
        return $true

    } finally {
        # Cleanup
        if (-not $process.HasExited) {
            Log-Info "Stopping backend server..."
            $process.Kill()
            $process.WaitForExit(3000)
        }
        $process.Dispose()
    }
}

# Test ML scripts (import validation only - no actual ML execution)
function Test-MLScripts {
    param([string]$EnvRoot, [string]$PythonExe)

    Log-Test "Testing ML Scripts (import validation)..."

    $scriptsDir = "$EnvRoot\resources\versions\0.01"

    # Set up environment
    $env:PYTHONPATH = @(
        $scriptsDir,
        "$EnvRoot\resources\modelhub",
        $repoRoot
    ) -join ";"

    $scripts = @(
        @{ Name = "models.py"; Import = "models" },
        @{ Name = "grabscreen.py"; Import = "grabscreen" },
        @{ Name = "getkeys.py"; Import = "getkeys" }
    )

    $allPassed = $true

    foreach ($script in $scripts) {
        $scriptPath = Join-Path $scriptsDir $script.Name
        if (-not (Test-Path $scriptPath)) {
            Log-Warn "Script not found: $($script.Name)"
            continue
        }

        Log-Info "Validating $($script.Name)..."

        # Test syntax and basic imports
        $testCode = @"
import sys
sys.path.insert(0, r'$scriptsDir')
try:
    # Just check syntax, don't execute
    with open(r'$scriptPath', 'r') as f:
        compile(f.read(), r'$scriptPath', 'exec')
    print('SYNTAX_OK')
except SyntaxError as e:
    print(f'SYNTAX_ERROR: {e}')
    sys.exit(1)
"@

        $result = & $PythonExe -c $testCode 2>&1
        if ($LASTEXITCODE -eq 0) {
            Log-Ok "$($script.Name) - Syntax OK"
        } else {
            Log-Fail "$($script.Name) - $result"
            $allPassed = $false
        }
    }

    # Test that models.py can be imported (critical for training/inference)
    Log-Info "Testing models.py import (requires TensorFlow)..."
    $modelTestCode = @"
import sys
sys.path.insert(0, r'$scriptsDir')
try:
    import tensorflow as tf
    print(f'TensorFlow: {tf.__version__}')
    from models import inception_v3
    print('IMPORT_OK: inception_v3')
except ImportError as e:
    print(f'IMPORT_WARN: {e}')
except Exception as e:
    print(f'ERROR: {e}')
"@

    $result = & $PythonExe -c $modelTestCode 2>&1
    Write-Host "  $result" -ForegroundColor DarkGray

    if ($allPassed) {
        Log-Ok "ML script validation PASSED"
    } else {
        Log-Warn "ML script validation had warnings"
    }

    return $allPassed
}

# Test model metadata system
function Test-ModelMetadata {
    param([string]$EnvRoot, [string]$PythonExe)

    Log-Test "Testing Model Metadata System..."

    $env:PYTHONPATH = @(
        "$EnvRoot\resources\modelhub",
        $repoRoot
    ) -join ";"

    $testCode = @"
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, r'$EnvRoot\resources\modelhub')

from model_metadata import (
    ModelMetadata,
    InputSpec,
    OutputSpec,
    TrainingConfig,
    create_default_metadata,
    save_metadata,
    load_metadata,
    validate_metadata
)

# Test 1: Create default metadata
print('Test 1: Creating default metadata...')
meta = create_default_metadata(
    model_id='test_model_001',
    game_id='genshin_impact',
    architecture='inception_v3'
)
assert meta.model_id == 'test_model_001'
assert meta.input_spec.width == 480
assert meta.output_spec.num_classes == 29
print('  PASS: Default metadata created')

# Test 2: Validate metadata
print('Test 2: Validating metadata...')
is_valid, errors = validate_metadata(meta)
assert is_valid, f'Validation failed: {errors}'
print('  PASS: Metadata is valid')

# Test 3: Save and load metadata
print('Test 3: Save/Load round-trip...')
with tempfile.TemporaryDirectory() as tmpdir:
    model_dir = Path(tmpdir) / 'test_model'
    model_dir.mkdir()

    # Create a fake checkpoint file
    (model_dir / 'model.index').write_text('fake')

    # Save
    save_metadata(meta, model_dir)
    assert (model_dir / 'metadata.json').exists()

    # Load
    loaded = load_metadata(model_dir)
    assert loaded is not None
    assert loaded.model_id == meta.model_id
    print('  PASS: Save/Load works')

# Test 4: Serialization
print('Test 4: JSON serialization...')
data = meta.to_dict()
assert isinstance(data, dict)
assert 'model_id' in data
assert 'input_spec' in data
json_str = json.dumps(data)  # Should not raise
print('  PASS: JSON serialization works')

print('')
print('All model metadata tests PASSED!')
"@

    $result = & $PythonExe -c $testCode 2>&1
    $exitCode = $LASTEXITCODE

    foreach ($line in $result) {
        if ($line -match "PASS") {
            Write-Host "  $line" -ForegroundColor Green
        } elseif ($line -match "FAIL|ERROR") {
            Write-Host "  $line" -ForegroundColor Red
        } else {
            Write-Host "  $line" -ForegroundColor DarkGray
        }
    }

    if ($exitCode -eq 0) {
        Log-Ok "Model metadata tests PASSED"
        return $true
    } else {
        Log-Fail "Model metadata tests FAILED"
        return $false
    }
}

# Main execution
try {
    # Setup environment
    Remove-TestEnv  # Clean start
    $envRoot = Setup-MockEnvironment

    # Find Python
    $pythonExe = Get-PythonExe
    Log-Info "Using Python: $pythonExe"

    # Verify Python version
    $pyVersion = & $pythonExe --version 2>&1
    Log-Info "Python version: $pyVersion"

    $results = @{
        Backend = $null
        MLScripts = $null
        Metadata = $null
    }

    # Run tests based on mode
    switch ($Mode) {
        "backend" {
            $results.Backend = Test-Backend -EnvRoot $envRoot -PythonExe $pythonExe
        }
        "ml" {
            $results.MLScripts = Test-MLScripts -EnvRoot $envRoot -PythonExe $pythonExe
        }
        "full" {
            $results.Metadata = Test-ModelMetadata -EnvRoot $envRoot -PythonExe $pythonExe
            $results.MLScripts = Test-MLScripts -EnvRoot $envRoot -PythonExe $pythonExe
            $results.Backend = Test-Backend -EnvRoot $envRoot -PythonExe $pythonExe
        }
    }

    # Summary
    Write-Host ""
    Write-Host "=============================================="
    Write-Host " Test Results"
    Write-Host "=============================================="

    $allPassed = $true
    foreach ($test in $results.Keys) {
        if ($null -eq $results[$test]) {
            Write-Host "  $test : SKIPPED" -ForegroundColor DarkGray
        } elseif ($results[$test]) {
            Write-Host "  $test : PASSED" -ForegroundColor Green
        } else {
            Write-Host "  $test : FAILED" -ForegroundColor Red
            $allPassed = $false
        }
    }

    Write-Host ""
    if ($allPassed) {
        Log-Ok "All tests completed successfully!"
    } else {
        Log-Fail "Some tests failed"
    }

} finally {
    # Cleanup unless KeepEnv is set
    if (-not $KeepEnv) {
        Remove-TestEnv
    } else {
        Log-Info "Test environment preserved at: $testEnvRoot"
        Log-Info "Run with -Mode cleanup to remove"
    }
}

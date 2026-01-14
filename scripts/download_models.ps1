# Download AI Models for BOT MMORPG AI
# This script downloads pre-trained AI models from the project repository

param(
    [string]$Dest = "$PSScriptRoot\..\models",
    [string]$ModelsRepo = "https://github.com/ruslanmv/BOT-MMORPG-AI",
    [string]$ModelsBranch = "models",
    [switch]$UseGit = $false
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BOT MMORPG AI - Models Downloader" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Models destination: $Dest" -ForegroundColor Yellow

# Create destination directory if it doesn't exist
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

# Method 1: Try to download from GitHub releases (fastest, no git required)
try {
    Write-Host "Checking for pre-packaged models in GitHub releases..." -ForegroundColor Cyan

    # Get the latest release info
    $releaseApiUrl = "https://api.github.com/repos/ruslanmv/BOT-MMORPG-AI/releases/latest"
    $release = Invoke-RestMethod -Uri $releaseApiUrl -Headers @{ "User-Agent" = "BOT-MMORPG-AI-Installer" }

    # Look for a models.zip asset
    $modelsAsset = $release.assets | Where-Object { $_.name -eq "models.zip" }

    if ($modelsAsset) {
        Write-Host "Found models package in release: $($release.tag_name)" -ForegroundColor Green
        $downloadUrl = $modelsAsset.browser_download_url
        $tempZip = Join-Path $env:TEMP "bot-mmorpg-ai-models.zip"

        Write-Host "Downloading models ($([math]::Round($modelsAsset.size / 1MB, 2)) MB)..." -ForegroundColor Cyan
        Write-Host "This may take a few minutes depending on your internet connection..." -ForegroundColor Yellow

        # Download with progress
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $downloadUrl -OutFile $tempZip -UseBasicParsing
        $ProgressPreference = 'Continue'

        Write-Host "Extracting models..." -ForegroundColor Cyan
        Expand-Archive -Path $tempZip -DestinationPath $Dest -Force

        Remove-Item $tempZip -Force
        Write-Host "Models downloaded and extracted successfully!" -ForegroundColor Green
        Write-Host ""
        return
    }
    else {
        Write-Host "No pre-packaged models found in releases." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "Could not download from releases: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "Trying alternative download methods..." -ForegroundColor Cyan
}

# Method 2: Try to use git sparse-checkout (if git is available and UseGit is specified)
if ($UseGit) {
    try {
        Write-Host "Checking for git installation..." -ForegroundColor Cyan
        $gitPath = Get-Command git -ErrorAction SilentlyContinue

        if ($gitPath) {
            Write-Host "Git found. Using sparse checkout to download models..." -ForegroundColor Cyan

            $tempRepo = Join-Path $env:TEMP "bot-mmorpg-ai-temp"

            # Clean up any existing temp repo
            if (Test-Path $tempRepo) {
                Remove-Item -Path $tempRepo -Recurse -Force
            }

            # Initialize sparse checkout
            git clone --depth 1 --filter=blob:none --sparse $ModelsRepo $tempRepo
            Push-Location $tempRepo

            try {
                git sparse-checkout set models

                # Copy models to destination
                if (Test-Path "models") {
                    Copy-Item -Path "models\*" -Destination $Dest -Recurse -Force
                    Write-Host "Models downloaded successfully using git!" -ForegroundColor Green
                    Write-Host ""
                    return
                }
            }
            finally {
                Pop-Location
                Remove-Item -Path $tempRepo -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
    catch {
        Write-Host "Git download failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# Method 3: Download individual model files from raw GitHub URLs
try {
    Write-Host "Attempting direct download of model files..." -ForegroundColor Cyan

    # List of common model files (adjust based on your actual models)
    $modelFiles = @(
        "yolov5s.pt",
        "character_detector.onnx",
        "game_state_model.pkl",
        "navigation_model.h5"
    )

    $successCount = 0
    foreach ($file in $modelFiles) {
        try {
            $url = "https://raw.githubusercontent.com/ruslanmv/BOT-MMORPG-AI/$ModelsBranch/models/$file"
            $destFile = Join-Path $Dest $file

            Write-Host "  Downloading $file..." -ForegroundColor Gray
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $url -OutFile $destFile -UseBasicParsing -ErrorAction Stop
            $ProgressPreference = 'Continue'
            $successCount++
        }
        catch {
            Write-Host "  Could not download $file (may not exist in repository)" -ForegroundColor DarkGray
        }
    }

    if ($successCount -gt 0) {
        Write-Host "Downloaded $successCount model file(s) successfully!" -ForegroundColor Green
        Write-Host ""
        return
    }
}
catch {
    Write-Host "Direct download failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

# If all methods failed
Write-Host ""
Write-Host "======================================" -ForegroundColor Yellow
Write-Host "  Models Download Information" -ForegroundColor Yellow
Write-Host "======================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "Could not automatically download models." -ForegroundColor Yellow
Write-Host ""
Write-Host "You can download models manually:" -ForegroundColor Cyan
Write-Host "  1. Visit: https://github.com/ruslanmv/BOT-MMORPG-AI" -ForegroundColor White
Write-Host "  2. Navigate to the 'models' branch or releases section" -ForegroundColor White
Write-Host "  3. Download the models and place them in: $Dest" -ForegroundColor White
Write-Host ""
Write-Host "Or, you can download models later from within the application." -ForegroundColor Cyan
Write-Host ""

# Create a placeholder README
$readmePath = Join-Path $Dest "README.txt"
$readmeContent = @"
BOT MMORPG AI - Models Folder
==============================

This folder is intended for AI model files.

To download models:
1. Visit https://github.com/ruslanmv/BOT-MMORPG-AI
2. Look for the models in the releases or models branch
3. Download and place them in this folder

Alternatively, you can download models from within the application.

Common model files:
- yolov5s.pt (object detection)
- character_detector.onnx (character recognition)
- game_state_model.pkl (game state analysis)
- navigation_model.h5 (pathfinding and navigation)

For more information, visit the project documentation.
"@

Set-Content -Path $readmePath -Value $readmeContent -Force

Write-Host "Created README in models folder with download instructions." -ForegroundColor Green
Write-Host ""

# Exit with a warning code (not an error, just incomplete)
exit 0

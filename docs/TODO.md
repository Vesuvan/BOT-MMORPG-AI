## 📦 Deployment Strategy (v2.0)

To avoid Windows Installer size limits (NSIS 2GB crash) and improve update speeds, this project uses a **"Downloader Stub"** architecture.

### How it works
1.  **The Installer (`.exe`)**: Is lightweight (~300MB). It contains the App, UI, Python Runtime, and basic libraries (NumPy, OpenCV). It **does not** contain TensorFlow.
2.  **The Engine (`ml-engine.zip`)**: A separate ~1GB archive containing TensorFlow and TFLearn.

### Build Process
1.  **Build the App:**
    ```powershell
    make build-installer
    # Output: src-tauri/target/release/bundle/nsis/setup.exe
    ```
2.  **Build the Engine Add-on:**
    ```powershell
    .\scripts\package_ml_addon.ps1
    # Output: dist/ml-engine.zip
    ```
3.  **Release:**
    * Upload `setup.exe` to users.
    * Upload `ml-engine.zip` to your hosting provider.
    * Update the `install_ml_engine` URL in `src-tauri/src/main.rs` if the link changes.
### Phase 1: Modify the Build Pipeline (The "Light" Installer)

We first instruct your existing build script to **ignore** the heavy ML libraries.

**Action:** Open `scripts/build_pipeline.ps1`.
Find **Step 1** (around line ~350) and remove `"ml"` from the `-Extras` list.

```powershell
# scripts/build_pipeline.ps1

# ... inside Step 1 ...
# CHANGE THIS LINE: Remove "ml"
& (Join-Path $root "scripts\prepare_python_from_pyproject_embed310_target.ps1") `
  -Extras @("launcher","backend") `  <-- "ml" IS GONE. Installer is now ~300MB.
  -TargetTag "win_amd64_cp310" `
  -RebuildTarget

```

**Result:** Running `make build-installer` will now produce a small, fast installer that has Python, OpenCV, and NumPy, but **no TensorFlow**.

---

### Phase 2: Create the "ML Asset Package" Script

We need a new script to build the "Add-on" zip file containing just the heavy stuff.

**Action:** Create a new file `scripts/package_ml_addon.ps1`.

```powershell
<# 
scripts/package_ml_addon.ps1
Builds a standalone .zip containing ONLY the ML libraries (TensorFlow, etc.)
#>
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distDir = Join-Path $root "dist"
$mlStaging = Join-Path $root "dist\ml-addon"
$mlZip = Join-Path $distDir "ml-engine.zip"

Write-Host "Building ML Add-on Package..." -ForegroundColor Cyan

# 1. Setup staging area
if (Test-Path $mlStaging) { Remove-Item -Recurse -Force $mlStaging }
New-Item -ItemType Directory -Force -Path $mlStaging | Out-Null

# 2. Use the existing build venv to drive pip
$py = Join-Path $root ".venv\Scripts\python.exe"

# 3. Install ONLY the ML extras into the staging folder
# We use --no-deps so we don't re-bundle numpy/pandas (which are already in the main app)
# WARNING: If tensorflow brings new dependencies not in 'base', remove --no-deps
Write-Host "Installing ML libs..."
& $py -m pip install ".[ml]" --target $mlStaging --no-deps

# 4. Clean up junk (dist-info, __pycache__) to save space
Get-ChildItem $mlStaging -Filter "*.dist-info" -Recurse | Remove-Item -Recurse -Force
Get-ChildItem $mlStaging -Filter "__pycache__" -Recurse | Remove-Item -Recurse -Force

# 5. Zip it up
Write-Host "Zipping to $mlZip..."
Compress-Archive -Path "$mlStaging\*" -DestinationPath $mlZip -Force

Write-Host "SUCCESS: ML Add-on created at $mlZip" -ForegroundColor Green

```

**Workflow:**

1. Run `.\scripts\package_ml_addon.ps1`.
2. It creates `dist/ml-engine.zip` (~1GB).
3. **Upload this zip** to your release server (e.g., GitHub Releases, AWS S3, or your VPS).

---

### Phase 3: Update Rust Backend (`src-tauri/src/main.rs`)

Now we teach the Rust app to check if TensorFlow is missing and download it on demand.

**1. Update `src-tauri/Cargo.toml` dependencies:**

```toml
[dependencies]
reqwest = { version = "0.11", features = ["blocking", "json"] } 
zip = "0.6"

```

**2. Add commands to `src-tauri/src/main.rs`:**

```rust
// Add imports
use std::fs::File;
use std::io::{Cursor, Read, Write};
use zip::ZipArchive;

// 1. Check if ML Engine exists
#[tauri::command]
fn check_ml_status(app: AppHandle) -> bool {
    let py_dir = managed_site_packages_dir(&app);
    // If 'tensorflow' folder exists, we assume the engine is ready
    py_dir.join("tensorflow").exists()
}

// 2. Download and Install Command
#[tauri::command]
async fn install_ml_engine(app: AppHandle, window: Window) -> Result<String, String> {
    // REPLACE THIS WITH YOUR REAL URL
    let url = "https://github.com/ruslanmv/BOT-MMORPG-AI/releases/download/v1.0.0/ml-engine.zip";
    let target_dir = managed_site_packages_dir(&app);

    window.emit("download_progress", "Downloading AI Engine (approx 1GB)...").unwrap();

    // A. Download (Blocking for simplicity, or use async stream for progress bar)
    let response = reqwest::get(url).await.map_err(|e| e.to_string())?;
    let content = response.bytes().await.map_err(|e| e.to_string())?;

    window.emit("download_progress", "Extracting...").unwrap();

    // B. Unzip directly into site-packages
    let reader = Cursor::new(content);
    let mut archive = ZipArchive::new(reader).map_err(|e| e.to_string())?;

    for i in 0..archive.len() {
        let mut file = archive.by_index(i).unwrap();
        // Security check: ensure file path doesn't escape directory
        let outpath = target_dir.join(file.mangled_name());

        if file.name().ends_with('/') {
            std::fs::create_dir_all(&outpath).unwrap();
        } else {
            if let Some(p) = outpath.parent() {
                if !p.exists() { std::fs::create_dir_all(p).unwrap(); }
            }
            let mut outfile = File::create(&outpath).unwrap();
            std::io::copy(&mut file, &mut outfile).unwrap();
        }
    }

    window.emit("download_progress", "AI Engine Ready!").unwrap();
    Ok("Success".to_string())
}

// REMEMBER to register these in the `tauri::Builder` invoke_handler!

```

---

### Phase 4: Frontend UI Logic (JavaScript)

In your `index.html` or main JS file, update the logic for the "Start Bot" or "Train" button.

```javascript
async function onStartBotClick() {
  // 1. Check if engine is installed
  const hasEngine = await window.__TAURI__.invoke('check_ml_status');

  if (!hasEngine) {
    // 2. Not found? Trigger download flow
    const confirm = await confirm("AI Engine missing. Download (~1GB)?");
    if (!confirm) return;

    // Show a progress spinner/modal here
    document.getElementById("status").innerText = "Downloading...";
    
    try {
      await window.__TAURI__.invoke('install_ml_engine');
      alert("Installation Complete!");
      // Recursively call start to run now
      onStartBotClick();
    } catch (err) {
      alert("Download failed: " + err);
    }
    return;
  }

  // 3. Engine found, proceed normally
  window.__TAURI__.invoke('start_bot');
}

```

---


dev0.1.9.0

## Architecture Overview (Optimized - No PyInstaller)

This application uses a **single embedded Python runtime** for all Python operations:
- ML scripts (collect, train, test)
- Backend API server (FastAPI)
- Model management (modelhub)

**Key benefit:** Installer size reduced from ~1.3GB to ~800MB by eliminating PyInstaller duplication.

---

## What happens when you build the EXE / installer

The build pipeline (`scripts/build_pipeline.ps1`) performs these steps:

1. **Prepare wheelhouse** - Downloads and builds all Python wheels for offline installation
2. **Bundle embedded Python** - Copies Python 3.10 embeddable runtime to resources
3. **Pre-install dependencies** - Installs TensorFlow, FastAPI, etc. into site-packages
4. **Verify backend** - Validates Python files exist (no PyInstaller build)
5. **Copy drivers** - Bundles Interception and vJoy drivers
6. **Bundle versions** - Copies ML scripts to resources
7. **Build Tauri** - Creates the Windows installer with NSIS

**Bundled resources:**
* `resources/python/` - Embedded Python 3.10 runtime + site-packages
* `resources/versions/` - ML scripts (collect, train, test)
* `resources/wheelhouse/` - Pre-built Python wheels (offline install)
* `backend/` - FastAPI backend Python files
* `modelhub/` - Model management Python modules
* `drivers/` - Interception and vJoy installers

---

## What happens on the user's machine at first run

**All data is stored in the installation directory** (`C:\Program Files\BOT-MMORPG-AI\`).

### 1) Copy bundled Python runtime

On first use, the app copies the bundled Python runtime to:

* `C:\Program Files\BOT-MMORPG-AI\runtime\py\python\`

### 2) Install Python dependencies (deterministic)

Dependencies are installed into portable site-packages:

* `C:\Program Files\BOT-MMORPG-AI\runtime\py\site-packages\`

**Offline mode (recommended):** Uses pre-bundled wheelhouse
```
pip install --no-index --find-links <wheelhouse> --target <site-packages> -r requirements.lock.txt
```

### 3) Start backend server

The backend runs as a **Python script** (not a PyInstaller EXE):
```
python.exe backend/entry_main.py --port 0 --token <token>
```

The Rust frontend sets `PYTHONPATH` to include:
- `backend/` directory
- `modelhub/` directory
- `site-packages/` directory

---

## What happens when the user clicks Record / Train / Test

### Script resolution

Scripts are resolved in this order:

1. **User override:** `<install_dir>\content\versions\0.01\<script>.py`
2. **Bundled resource:** `resources/versions/0.01/<script>.py`
3. **Legacy fallback:** `<install_dir>\_up_\versions\0.01\<script>.py`

### Python execution

All Python operations use the **same embedded runtime**:

* `C:\Program Files\BOT-MMORPG-AI\runtime\py\python\python.exe`

Environment variables set by Rust:
```
PYTHONPATH=<versions/0.01>;<site-packages>;<modelhub>
PYTHONUNBUFFERED=1
PYTHONUTF8=1
```

### Outputs

Working directories:
* `datasets/` - Training data (captured screen + inputs)
* `models/` - Trained neural network checkpoints
* `logs/` - Application and training logs
* `content/` - User script overrides

---

## Directory Structure (Final)

```
C:\Program Files\BOT-MMORPG-AI\
├── BOT-MMORPG-AI.exe           # Tauri application (Rust)
├── .env                         # User configuration
│
├── runtime/py/                  # SINGLE Python environment for everything
│   ├── python/                  # Embedded Python 3.10.11
│   │   ├── python.exe
│   │   ├── python310.dll
│   │   └── python310._pth       # Patched to include site-packages
│   └── site-packages/           # ALL Python dependencies
│       ├── torch/               # PyTorch 2.x
│       ├── torchvision/         # Pre-trained models
│       ├── timm/                # PyTorch Image Models
│       ├── numpy/
│       ├── opencv-python/
│       ├── fastapi/             # Backend API
│       └── uvicorn/             # ASGI server
│
├── resources/                   # Read-only bundled resources
│   ├── versions/0.01/           # ML scripts
│   │   ├── 1-collect_data.py
│   │   ├── 2-train_model.py
│   │   ├── 3-test_model.py
│   │   ├── models_pytorch.py    # PyTorch neural network architectures
│   │   ├── grabscreen.py        # Screen capture
│   │   └── directkeys.py        # Input injection
│   ├── backend/                 # FastAPI backend (Python)
│   │   └── entry_main.py
│   ├── modelhub/                # Model management
│   │   ├── tauri.py
│   │   ├── registry.py
│   │   └── model_metadata.py    # NEW: Structured metadata
│   └── wheelhouse/              # Pre-built wheels (offline)
│
├── datasets/                    # User's training data
│   └── genshin_impact/
│       └── training_data-*.npy
│
├── models/                      # User's trained models
│   └── genshin_impact/
│       └── efficientnet_lstm_20250127/
│           ├── model.pth        # PyTorch checkpoint (.pth)
│           ├── model_best.pth   # Best validation model
│           └── metadata.json    # Model metadata
│
├── logs/                        # Application logs
├── content/                     # User overrides
│   └── versions/0.01/           # Custom script modifications
│
└── drivers/                     # Driver installers
    ├── interception/
    └── vjoy/
```

---

## Model Metadata System (NEW)

Each trained model includes a `metadata.json` file with:

```json
{
  "model_id": "efficientnet_lstm_20250127",
  "model_name": "Genshin EfficientNet-LSTM",
  "version": "1.0.0",
  "game_id": "genshin_impact",
  "input_spec": {
    "width": 480,
    "height": 270,
    "channels": 3
  },
  "output_spec": {
    "num_classes": 29,
    "class_names": ["W", "S", "A", "D", "WA", "WD", "SA", "SD", "NONE", ...]
  },
  "training_config": {
    "architecture": "efficientnet_lstm",
    "learning_rate": 0.0001,
    "epochs_total": 50,
    "training_files": 50,
    "temporal_frames": 4
  },
  "performance": {
    "val_accuracy": 0.87,
    "inference_time_ms": 15.4
  },
  "compatibility": {
    "pytorch_version": "2.0+",
    "torchvision_version": "0.15+",
    "python_version": "3.10.11",
    "model_format": "pytorch",
    "temporal_frames": 4
  }
}
```

See `modelhub/model_metadata.py` for the full schema.

---

## Build Pipeline Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    BUILD TIME (Developer)                       │
├─────────────────────────────────────────────────────────────────┤
│  1. prepare_python_from_pyproject_embed310_target.ps1           │
│     └── Creates wheelhouse with all dependencies                │
│                                                                 │
│  2. build_pipeline.ps1                                          │
│     ├── Step 1: Prepare wheelhouse                              │
│     ├── Step 2: Bundle embedded Python 3.10                     │
│     ├── Step 3: Pre-install deps into site-packages             │
│     ├── Step 4: UI smoke tests                                  │
│     ├── Step 5: Verify backend Python files (NO PyInstaller)    │
│     ├── Step 6: Copy drivers and scripts                        │
│     └── Step 7: Build Tauri + NSIS installer                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    RUNTIME (User Machine)                       │
├─────────────────────────────────────────────────────────────────┤
│  BOT-MMORPG-AI.exe (Tauri/Rust)                                │
│       │                                                         │
│       ├── Starts backend: python.exe backend/entry_main.py     │
│       │   └── FastAPI server on random port                     │
│       │                                                         │
│       └── User actions:                                         │
│           ├── Record: python.exe 1-collect_data.py             │
│           ├── Train:  python.exe 2-train_model.py              │
│           └── Test:   python.exe 3-test_model.py               │
│                                                                 │
│  ALL using the SAME embedded Python runtime                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Development Testing (Without Building Installer)

Test the backend and ML scripts locally without building the full installer.

### Quick Start

**Windows (PowerShell):**
```powershell
# Test backend server
.\scripts\dev_test_backend.ps1 -Mode backend

# Test ML scripts syntax
.\scripts\dev_test_backend.ps1 -Mode ml

# Run all tests
.\scripts\dev_test_backend.ps1 -Mode full

# Keep test environment for debugging
.\scripts\dev_test_backend.ps1 -Mode full -KeepEnv

# Clean up
.\scripts\dev_test_backend.ps1 -Mode cleanup
```

**Cross-platform (Python):**
```bash
# Test backend server
python scripts/dev_test_backend.py --mode backend

# Test model metadata system
python scripts/dev_test_backend.py --mode metadata

# Test ML scripts
python scripts/dev_test_backend.py --mode ml

# Run all tests
python scripts/dev_test_backend.py --mode full

# Keep test environment for debugging
python scripts/dev_test_backend.py --mode full --keep-env

# Clean up
python scripts/dev_test_backend.py --mode cleanup
```

### What the Test Runner Does

1. **Creates mock production environment** in temp directory:
   - Mirrors `C:\Program Files\BOT-MMORPG-AI\` structure
   - Copies backend, modelhub, and ML scripts
   - Sets up environment variables as Rust would

2. **Tests Backend Server:**
   - Starts FastAPI server with test token
   - Verifies READY signal
   - Tests API endpoints (`/modelhub/available`, `/modelhub/games`)

3. **Tests ML Scripts:**
   - Validates Python syntax
   - Checks PyTorch imports
   - Verifies model architecture definitions (EfficientNet, MobileNet, etc.)

4. **Tests Model Metadata:**
   - Creates and validates metadata
   - Tests save/load round-trip
   - Verifies JSON serialization

### Test Environment Location

```
Windows: %TEMP%\BOT-MMORPG-AI-DevTest\
Linux:   /tmp/BOT-MMORPG-AI-DevTest/
```

Use `--keep-env` / `-KeepEnv` to preserve for debugging.

---

## In one line

**Single embedded Python 3.10 runtime handles everything (ML scripts + backend server) → no PyInstaller needed → smaller installer (~800MB) → simpler architecture → easier debugging.**

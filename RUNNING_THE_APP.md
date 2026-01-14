# Running BOT MMORPG AI - Complete Guide

## Quick Start

### 1. Install Dependencies

```bash
make install-all
```

This installs:
- Python dependencies (via uv)
- Creates virtual environment
- Installs all required packages

### 2. Run the Application

```bash
make run
```

**OR** (same thing):

```bash
make dev
```

This will:
- Start the Tauri development server
- Launch the desktop application window
- Automatically start the Python backend as a sidecar
- Open the UI at `tauri://localhost`

---

## Important: This is NOT a Node.js Project!

### ❌ Common Mistake

```bash
npm run dev  # ❌ This WILL NOT work!
```

**Error you'll see:**
```
npm error enoent Could not read package.json: Error: ENOENT: no such file or directory
```

### ✅ Correct Way

```bash
make run  # ✅ This is the correct way!
```

---

## Project Structure

```
BOT-MMORPG-AI/
├── tauri-ui/              # ← Frontend (Plain HTML/CSS/JavaScript)
│   ├── index.html         # Main UI
│   └── main.js            # JavaScript (ES modules)
│
├── backend/               # ← Python Backend
│   └── main_backend.py    # HTTP API server
│
├── src-tauri/             # ← Tauri (Rust) Desktop Framework
│   ├── src/main.rs        # Rust entry point
│   ├── tauri.conf.json    # Tauri configuration
│   └── Cargo.toml         # Rust dependencies
│
├── src/bot_mmorpg/        # ← Python Package
│   └── scripts/           # AI scripts (collect, train, play)
│
└── Makefile               # ← Commands for running the app
```

---

## Architecture

This is a **Tauri desktop application**:

```
┌────────────────────────────────────────────┐
│     Tauri Desktop Window                   │
│  ┌──────────────────────────────────────┐  │
│  │  Frontend (tauri-ui/)                │  │
│  │  - Plain HTML/CSS/JavaScript         │  │
│  │  - No npm, no webpack, no build step │  │
│  │  - Direct ES modules                 │  │
│  └──────────────────────────────────────┘  │
│              │                              │
│              │ HTTP/JSON                    │
│              ↓                              │
│  ┌──────────────────────────────────────┐  │
│  │  Backend (Python Sidecar)            │  │
│  │  - Starts automatically              │  │
│  │  - HTTP server on random port        │  │
│  │  - API endpoints for AI functions    │  │
│  └──────────────────────────────────────┘  │
└────────────────────────────────────────────┘
```

**Key Points:**
- ✅ Frontend uses **plain HTML/JavaScript** (no npm needed)
- ✅ Backend starts **automatically** when app launches
- ✅ Communication via **HTTP/JSON** on localhost
- ✅ No build step for frontend (direct file serving)

---

## Why No `package.json`?

This project deliberately avoids Node.js complexity:

### Traditional Web Dev
```
npm install → webpack → babel → 1000 packages → build → dist/
```

### This Project
```
Plain HTML/JS → Tauri → Done!
```

**Benefits:**
- 🚀 No npm dependency hell
- ⚡ No build time for frontend
- 🎯 Simple, direct development
- 📦 Smaller footprint

---

## Running Different Components

### Full Application (Recommended)
```bash
make run
```
Starts everything together.

### Backend Only (Testing)
```bash
make run-backend
```
Runs just the Python backend server.

### Python Scripts Directly
```bash
# Collect data
make collect-data

# Train model
make train-model

# Test model
make test-model
```

---

## Development Workflow

### 1. Make Changes to UI

Edit files in `tauri-ui/`:
```bash
# Edit the HTML
vim tauri-ui/index.html

# Edit the JavaScript
vim tauri-ui/main.js
```

Changes are **automatically reloaded** when you save!

### 2. Make Changes to Backend

Edit `backend/main_backend.py`:
```bash
vim backend/main_backend.py
```

Then **restart** the app:
```bash
# Stop the app (Ctrl+C)
# Start again
make run
```

### 3. Make Changes to Python Scripts

Edit scripts in `src/bot_mmorpg/scripts/`:
```bash
vim src/bot_mmorpg/scripts/collect_data.py
```

Changes take effect on next run (no restart needed).

---

## Prerequisites

### Required

1. **Python 3.10+**
   ```bash
   python --version
   ```

2. **Rust + Cargo** (for Tauri)
   ```bash
   cargo --version
   ```

   If missing: https://rustup.rs/

3. **uv** (Python package manager)
   ```bash
   make install-uv
   ```

### Optional (Windows only)

- **Visual Studio Build Tools** (for native Python packages)
- **NSIS** (for installer builds)

---

## Troubleshooting

### "npm run dev" doesn't work

**Problem:** Wrong command for this project.

**Solution:** Use `make run` instead.

### "cargo: command not found"

**Problem:** Rust not installed.

**Solution:**
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Or on Windows
# Download from: https://rustup.rs/

# Then restart terminal
cargo --version
```

### "uv: command not found"

**Problem:** uv not installed.

**Solution:**
```bash
make install-uv
# Then restart terminal
```

### Backend doesn't start

**Problem:** Python dependencies not installed.

**Solution:**
```bash
make install-all
```

### UI shows "Backend not ready"

**Problem:** Backend failed to start or crashed.

**Check:**
1. Look in terminal for Python errors
2. Verify Python 3.10+ is installed
3. Check that dependencies are installed

### Port already in use

**Problem:** Another instance is running.

**Solution:**
```bash
# Kill other instances
pkill -f main-backend

# Or on Windows
taskkill /F /IM main-backend.exe

# Then try again
make run
```

---

## Building the Installer

### Prerequisites (Windows Only)

1. Install all dependencies:
   ```bash
   make install-all
   ```

2. Install Rust:
   ```bash
   # Download from https://rustup.rs/
   ```

3. Install Tauri CLI:
   ```bash
   cargo install tauri-cli
   ```

### Build

```bash
make build-installer
```

This creates:
```
src-tauri/target/release/bundle/nsis/BOT-MMORPG-AI_0.1.5_x64-setup.exe
```

### Verify

```bash
make verify-installer
```

### Test

```bash
make test-installer
```

---

## Common Commands Reference

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make install-all` | Install all dependencies |
| `make run` | Run the application (dev mode) |
| `make dev` | Same as `make run` |
| `make run-backend` | Run only backend (testing) |
| `make collect-data` | Run data collection |
| `make train-model` | Train AI model |
| `make test-model` | Test trained model |
| `make build-installer` | Build Windows installer |
| `make verify-installer` | Verify installer build |
| `make test-installer` | Test installer package |
| `make clean` | Clean all build artifacts |

---

## FAQ

### Q: Can I use npm/webpack/vite?

**A:** Not needed! The frontend is intentionally simple (plain HTML/JS) to avoid build complexity.

### Q: How do I add a new UI feature?

**A:** Just edit `tauri-ui/index.html` or `tauri-ui/main.js`. Changes reload automatically.

### Q: How do I add a new backend endpoint?

**A:** Edit `backend/main_backend.py`, add your endpoint, restart the app.

### Q: Can I use TypeScript?

**A:** Not currently set up. The project uses plain JavaScript for simplicity.

### Q: Where are the AI models?

**A:** Models are in `artifacts/model/` (created by training) or downloaded to `models/` by the installer.

### Q: How do I debug?

**A:**
- Frontend: Browser DevTools (F12 in the app window)
- Backend: Check terminal output for Python errors
- Rust: Check terminal for Tauri/Rust errors

---

## Production Build

### For Distribution

```bash
# Windows
make artifact

# This creates a full installer at:
# src-tauri/target/release/bundle/nsis/BOT-MMORPG-AI_0.1.5_x64-setup.exe
```

The installer includes:
- ✅ Tauri desktop application
- ✅ Python backend (bundled)
- ✅ All dependencies
- ✅ Driver installers
- ✅ Component selection wizard
- ✅ Professional UI

Users can just run the installer - no Python, Rust, or dependencies needed!

---

## Summary

**To run the app:**
```bash
make install-all  # First time only
make run          # Start the app
```

**NOT this:**
```bash
npm run dev  # ❌ Wrong! This is not a Node.js project
```

**Frontend location:**
- ✅ `tauri-ui/` (correct)
- ❌ `frontend/` (doesn't exist)

**Frontend type:**
- ✅ Plain HTML/CSS/JavaScript
- ❌ NOT React/Vue/npm-based

**Backend:**
- ✅ Starts automatically as Tauri sidecar
- ✅ Python HTTP server
- ✅ No manual startup needed

---

**Happy Coding!** 🎮✨

If you have questions, check:
- `UI_BACKEND_INTEGRATION_ANALYSIS.md` - Architecture details
- `UI_IMPROVEMENTS_SUMMARY.md` - UI features
- `BUILD_STATUS.md` - Build system info
- `INSTALLER_IMPROVEMENTS.md` - Installer features

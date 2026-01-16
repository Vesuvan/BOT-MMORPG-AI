dev0.1.8.3
## What happens when you build the EXE / installer

* **Tauri bundles your native repo folder** `../versions/**` (so `versions/0.01/**` with *all* local Python modules like `grabscreen.py`, `models.py`, etc. is included in the installer/app resources).
* Tauri also bundles:

  * `resources/**` (where you can place the embedded Python runtime and optional wheelhouse)
  * `drivers/**` (your driver installers)
  * `../modelhub/**` (if you ship it)

This eliminates the previous “works only right after installer” behavior because the EXE always has a stable resource layout.

---

## What happens on the user’s machine at first run

The app uses a **managed embedded Python runtime + managed venv**, so it never depends on “system Python” being installed.

### 1) Copy bundled Python runtime

On first use of any Python tool (record/train/test), the app checks if a managed Python exists.

If missing, it copies the bundled runtime from the app resources into:

* **Python runtime (base)**

  * `%LOCALAPPDATA%\BOT-MMORPG-AI\runtime\py\python\`

This runtime is “owned” by your app and is stable across launches.

### 2) Create an isolated venv

Then it creates the venv:

* **Venv**

  * `%LOCALAPPDATA%\BOT-MMORPG-AI\runtime\py\venv\`

### 3) Install Python dependencies (deterministic)

Then it installs dependencies using the pinned lock file bundled from your repo:

* `versions/0.01/requirements.lock.txt`

Two supported modes:

* **Offline deterministic install (recommended)**
  If you ship wheels in:

  * `src-tauri/resources/wheelhouse/*.whl`
    then it runs:
  * `pip install --no-index --find-links <wheelhouse> -r requirements.lock.txt`

* **Online install (fallback)**
  If wheelhouse is empty, it can still do:

  * `pip install -r requirements.lock.txt`
    (but this depends on internet + PyPI availability, so wheelhouse is preferred for production)

### 4) Verify critical imports

It verifies at least:

* `import numpy`
  If that fails, it reports a clear error instead of “buttons do nothing”.

---

## What happens every time the user clicks Record / Train / Test

### Script resolution (stable)

The Rust backend resolves scripts in this order:

1. **User override (writable)**
   `%LOCALAPPDATA%\BOT-MMORPG-AI\content\versions\0.01\<script>.py`
   (lets you hotfix scripts without reinstalling)

2. **Bundled baseline (read-only)**
   `versions/0.01/<script>.py` from the EXE resources
   (this is the main shipped version)

3. **Legacy fallback** (only if it exists)
   `_up_/versions/...`
   (kept only for compatibility with old installs)

### Python execution (stable)

The app always runs **your managed venv python**, never `python` from PATH:

* `%LOCALAPPDATA%\BOT-MMORPG-AI\runtime\py\venv\Scripts\python.exe`

And before running, it injects:

* `PYTHONPATH=<versions/0.01 folder of the script>`

So imports like:

```py
from grabscreen import grab_screen
from models import alexnet2
```

work reliably because that folder is on the module path.

### Outputs (writable)

The working directory is a writable root under LocalAppData (not Program Files), so datasets/models/logs can be created without permission issues.

---

## In one line

**Build bundles `versions/0.01/**` + embedded Python assets → first run installs a private Python + venv in LocalAppData → installs deps from `requirements.lock.txt` (offline wheelhouse if present) → runs scripts using the venv python with PYTHONPATH set, so buttons always work.**

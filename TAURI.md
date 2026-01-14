# Tauri "Gamer-Easy" Installer Patch

This patch adds a Tauri desktop shell + Windows NSIS installer that:
- bundles a **Python backend sidecar** compiled with PyInstaller
- installs **Interception** and **vJoy** during setup (admin)
- creates **Desktop + Start Menu** shortcuts

## What gets added
- `src-tauri/` (Tauri app)
- `backend/main_backend.py` (HTTP sidecar)
- `tauri-ui/` (minimal UI)
- `installer/nsis_template.nsi` (custom template that installs drivers)
- `scripts/build_pipeline.ps1` (Windows build pipeline)
- `scripts/install_drivers.ps1` (driver repair installer script)

## How to apply into your repo
Copy these folders into the repository root:
- `src-tauri/`
- `backend/`
- `tauri-ui/`
- `installer/`
- `scripts/` (merge with existing, keep existing scripts)

## Build on Windows
Run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_pipeline.ps1
```

Installer output will be under:
`src-tauri\target\release\bundle\nsis`

## Notes
- The NSIS template requests admin because drivers require it.
- The backend exposes `http://127.0.0.1:<port>/health`, `/drivers`, and `/action/*`.
- Replace the stub implementations with your real training/play logic.

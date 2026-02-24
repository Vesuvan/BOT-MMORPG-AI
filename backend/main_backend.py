# backend/main_backend.py
#!/usr/bin/env python3
"""
Main backend sidecar entrypoint (PyInstaller target).

UPDATED for Launcher v0.1.8 upgrade:
- This sidecar now starts the local-only HTTP JSON API implemented in: modelhub/tauri.py
- It prints a single READY line (emitted by modelhub.tauri) that Rust can parse:
    READY url=http://127.0.0.1:<port> token=<token>

Why this file exists:
- Your build pipeline already packages backend/main_backend.py into main-backend.exe
- Tauri starts main-backend.exe as a sidecar (dev/prod)
- Keeping the entrypoint here avoids changing your PyInstaller pipeline structure

Usage (what Tauri should do):
  main-backend.exe --serve --port 0 --token <token> --project-root <repo_root>

Dev usage:
  python backend/main_backend.py --serve --port 0
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _resolve_project_root(cli_root: str | None) -> Path:
    """
    Determine the repo root so `import modelhub` works regardless of cwd / PyInstaller.
    Priority:
      1) --project-root CLI arg
      2) MODELHUB_PROJECT_ROOT env var
      3) backend/main_backend.py -> backend -> repo root
    """
    if cli_root and cli_root.strip():
        return Path(cli_root).expanduser().resolve()

    env_root = os.environ.get("MODELHUB_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()

    return Path(__file__).resolve().parent.parent


def _ensure_sys_path(project_root: Path) -> None:
    pr = str(project_root)
    if pr not in sys.path:
        sys.path.insert(0, pr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BOT-MMORPG-AI sidecar backend (starts ModelHub Tauri API)")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the local HTTP API (default behavior if no other mode is specified).",
    )
    parser.add_argument("--port", type=int, default=0, help="Port to bind on 127.0.0.1 (0 = auto)")
    parser.add_argument("--token", type=str, default="", help="Auth token (if empty, server generates one)")
    parser.add_argument("--project-root", type=str, default="", help="Repo root override (recommended in prod)")
    args = parser.parse_args(argv)

    # Default behavior: serve
    if not args.serve:
        args.serve = True

    project_root = _resolve_project_root(args.project_root)
    os.environ["MODELHUB_PROJECT_ROOT"] = str(project_root)
    _ensure_sys_path(project_root)

    if args.serve:
        # Defer to modelhub/tauri.py (FastAPI/uvicorn server)
        # It prints the READY line to stdout for Rust to parse.
        try:
            from modelhub.tauri import main as modelhub_tauri_main
        except Exception as e:
            # IMPORTANT: single-line failure marker for Rust logs
            print(f"FAILED error=Could not import modelhub.tauri: {e}", flush=True)
            return 1

        # Forward args to the server
        # modelhub.tauri expects --resource-root and --data-root (not --project-root)
        return int(
            modelhub_tauri_main(
                [
                    "--port",
                    str(args.port),
                    "--token",
                    args.token,
                    "--resource-root",
                    str(project_root),
                    "--data-root",
                    str(project_root),
                ]
            )
        )

    # (Future) You could add other modes here (e.g. one-shot CLI commands)
    print("FAILED error=No mode selected", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

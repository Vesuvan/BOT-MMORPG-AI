# backend/entry_main.py
"""
PyInstaller entrypoint for the ModelHub/Tauri sidecar.

This file must stay tiny + stable for packaging. It simply forwards CLI args to
modelhub.tauri.main(argv=...).

Rust should launch (DEV python or PROD exe):
  main-backend.exe --port 0 --token <token> --resource-root <...> --data-root <...>

modelhub/tauri.py prints (flush=True):
  READY url=http://127.0.0.1:<port> token=<token>
"""

from __future__ import annotations

import sys
from typing import List


def main() -> int:
    # Import the real sidecar entrypoint
    from modelhub.tauri import main as sidecar_main

    # Forward args exactly (skip program name)
    argv: List[str] = sys.argv[1:]

    # sidecar_main already returns an int exit code (0/1). Keep it safe anyway.
    rc = sidecar_main(argv)
    return int(rc) if rc is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())

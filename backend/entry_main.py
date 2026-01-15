# backend/entry_main.py
"""
PyInstaller entrypoint for the sidecar.

This is intentionally tiny and stable for packaging.
It forwards CLI args to modelhub.tauri.main(argv=...).

Rust should launch:
  main-backend.exe --port 0 --token <token> --resource-root <...> --data-root <...>

Your modelhub/tauri.py prints:
  READY url=http://127.0.0.1:<port> token=<token>
"""

from __future__ import annotations

import sys
from typing import List


def main() -> int:
    # Import your sidecar entry and call it with forwarded argv
    from modelhub.tauri import main as sidecar_main

    # Forward args exactly (skip program name)
    argv: List[str] = sys.argv[1:]
    return int(sidecar_main(argv) or 0)


if __name__ == "__main__":
    raise SystemExit(main())

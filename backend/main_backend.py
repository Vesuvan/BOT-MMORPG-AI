"""Main backend sidecar entrypoint.

This process is started by the Tauri frontend as a *sidecar*.
It exposes a small local HTTP API for:
- health/status
- driver status (Windows only)
- triggering actions (collect/train/play) by delegating to your Python package scripts

You can replace these stubs with the real game automation/training logic.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

APP_VERSION = "0.1.5"


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _driver_status() -> dict:
    """Best-effort driver status checks.

    Interception installs a driver service; vJoy installs a virtual device.
    We keep checks lightweight: existence of known files / registry queries would be more accurate.
    """
    status = {"windows": _is_windows(), "interception": None, "vjoy": None, "notes": []}
    if not _is_windows():
        status["notes"].append("Drivers are Windows-only; status unavailable on this OS.")
        return status

    # Interception: check if driver file exists in system32\drivers
    sysroot = os.environ.get("SystemRoot", r"C:\\Windows")
    interception_sys = Path(sysroot) / "System32" / "drivers" / "keyboard.sys"
    # Note: Interception driver name may differ by build; adjust as needed.
    status["interception"] = interception_sys.exists()

    # vJoy: check if vJoy registry key exists via reg.exe (no extra deps)
    try:
        p = subprocess.run(["reg", "query", r"HKLM\\SOFTWARE\\vJoy"], capture_output=True, text=True)
        status["vjoy"] = (p.returncode == 0)
    except Exception:
        status["vjoy"] = None
        status["notes"].append("Could not query registry for vJoy.")

    return status


def _run_action(action: str) -> dict:
    """Run one of the declared package scripts as a subprocess.

    In the future you may want to call functions directly instead of spawning.
    """
    module_map = {
        "collect": "bot_mmorpg.scripts.collect_data",
        "train": "bot_mmorpg.scripts.train_model",
        "play": "bot_mmorpg.scripts.test_model",
    }
    mod = module_map.get(action)
    if not mod:
        return {"ok": False, "error": f"Unknown action: {action}"}

    # Spawn the module using the embedded python runtime (this exe includes python).
    cmd = [sys.executable, "-m", mod]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-20000:],
        "stderr": proc.stderr[-20000:],
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "version": APP_VERSION, "pid": os.getpid()})
            return
        if self.path == "/drivers":
            self._send(200, _driver_status())
            return
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path.startswith("/action/"):
            action = self.path.split("/", 2)[2]
            result = _run_action(action)
            self._send(200 if result.get("ok") else 400, result)
            return
        self._send(404, {"ok": False, "error": "not found"})

    # quieter logs
    def log_message(self, fmt, *args):
        return


def _pick_port(preferred: int) -> int:
    if preferred:
        return preferred
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0, help="Port to bind on localhost")
    args = parser.parse_args(argv)

    port = _pick_port(args.port)
    server = HTTPServer(("127.0.0.1", port), Handler)

    # Print the port so the frontend can read it from stdout if desired
    print(json.dumps({"ok": True, "port": port, "version": APP_VERSION}), flush=True)

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    # keep process alive
    try:
        t.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

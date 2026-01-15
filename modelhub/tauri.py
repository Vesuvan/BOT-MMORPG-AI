# modelhub/tauri.py
#!/usr/bin/env python3
"""
ModelHub <-> Tauri bridge (local-only HTTP JSON API)

Production goals:
- Localhost-only server (127.0.0.1), no external exposure
- Token auth on every request (X-Auth-Token header)
- Works in dev (python -m modelhub.tauri) and in prod (PyInstaller sidecar)
- No UI/Eel dependencies
- Reuses your existing ModelHub + SessionManager logic

Run (dev):
  python -m modelhub.tauri --port 0

Run (fixed port):
  python -m modelhub.tauri --port 8787

Security:
  - Server generates a token by default and prints it in a READY line.
  - Rust should read stdout, extract URL + token, and then call the API with header X-Auth-Token.

READY line format (single line):
  READY url=http://127.0.0.1:<port> token=<token>

Requirements:
  pip install fastapi uvicorn
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ---- Ensure PROJECT_ROOT importability (critical for PyInstaller/cwd variability) ----
def _resolve_project_root() -> Path:
    """
    Try to locate repo root robustly:
    - Prefer explicit MODELHUB_PROJECT_ROOT env if set
    - Else use two parents up from this file: modelhub/tauri.py -> modelhub -> repo root
    """
    env_root = os.environ.get("MODELHUB_PROJECT_ROOT", "").strip()
    if env_root:
        p = Path(env_root).expanduser().resolve()
        return p

    # modelhub/tauri.py -> modelhub -> repo root
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT: Path = _resolve_project_root()

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---- ModelHub imports (match launcher.py behavior) ----
MODELHUB_AVAILABLE = False
session_manager = None

# Defaults (same as launcher.py v0.1.8)
DEFAULT_GAME_ID = "genshin_impact"

mh_list_games = None
mh_load_game = None
mh_discover_local_models = None
mh_validate_compatibility = None
mh_load_json = None
mh_load_settings = None
mh_get_datasets = None
mh_get_models = None
mh_delete_model_entry = None
mh_set_active_model = None
mh_get_active_model = None
mh_list_builtin_models = None

try:
    from modelhub.session_manager import SessionManager
    from modelhub.registry_store import (
        get_datasets,
        get_models,
        delete_model_entry,
        set_active_model,
        get_active_model,
    )
    from modelhub.local_store import discover_local_models as _discover_local_models
    from modelhub.registry import (
        list_games,
        load_game,
        ensure_default_catalog,
    )
    from modelhub.validator import (
        validate_compatibility,
        load_json,
    )
    from modelhub.settings import load_settings
    from modelhub.builtin_models import list_builtin_models

    mh_list_games = list_games
    mh_load_game = load_game
    mh_discover_local_models = _discover_local_models
    mh_validate_compatibility = validate_compatibility
    mh_load_json = load_json
    mh_load_settings = load_settings
    mh_get_datasets = get_datasets
    mh_get_models = get_models
    mh_delete_model_entry = delete_model_entry
    mh_set_active_model = set_active_model
    mh_get_active_model = get_active_model
    mh_list_builtin_models = list_builtin_models

    ensure_default_catalog()
    session_manager = SessionManager(PROJECT_ROOT)
    MODELHUB_AVAILABLE = True
except Exception as e:
    # Keep API alive even if modelhub fails; endpoints return ok:false
    MODELHUB_AVAILABLE = False
    session_manager = None
    _MODELHUB_INIT_ERROR = str(e)


def _normalize_game_id(game_id: Optional[str]) -> str:
    gid = (game_id or "").strip()
    return gid if gid else DEFAULT_GAME_ID


# ---- FastAPI server ----
def create_app(token: str):
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(
        title="ModelHub Tauri API",
        version="0.1.8",
        docs_url=None,      # disable docs for production-hardening
        redoc_url=None,
        openapi_url=None,
    )

    def _auth(x_auth_token: Optional[str]):
        if not x_auth_token or x_auth_token != token:
            raise HTTPException(status_code=401, detail="Unauthorized")

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        # Avoid leaking stack traces to callers; keep a compact error
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(exc)},
        )

    @app.get("/health")
    async def health(x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        return {
            "ok": True,
            "modelhub": MODELHUB_AVAILABLE,
            "project_root": str(PROJECT_ROOT),
            "version": "0.1.8",
            **({"warning": _MODELHUB_INIT_ERROR} if not MODELHUB_AVAILABLE else {}),
        }

    # -------- Session endpoints --------

    @app.get("/session/active")
    async def session_active(x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        if not session_manager or not getattr(session_manager, "active_session", None):
            return {"ok": True, "active": None}
        return {"ok": True, "active": session_manager.active_session}

    @app.post("/session/begin_recording")
    async def begin_recording(payload: Dict[str, Any], x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        if not session_manager:
            return {"ok": False, "error": "SessionManager not available"}
        gid = _normalize_game_id(payload.get("game_id"))
        dataset_name = (payload.get("dataset_name") or "Untitled").strip()
        session_manager.begin_recording(gid, dataset_name)
        return {"ok": True}

    @app.post("/session/begin_training")
    async def begin_training(payload: Dict[str, Any], x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        if not session_manager:
            return {"ok": False, "error": "SessionManager not available"}
        gid = _normalize_game_id(payload.get("game_id"))
        model_name = (payload.get("model_name") or "New Model").strip()
        dataset_id = (payload.get("dataset_id") or "").strip()
        arch = (payload.get("arch") or "custom").strip()
        session_manager.begin_training(gid, model_name, dataset_id, arch)
        return {"ok": True}

    @app.post("/session/finalize")
    async def finalize(payload: Dict[str, Any] | None = None, x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        if not session_manager or not getattr(session_manager, "active_session", None):
            return {"ok": True, "finalized": None}

        stype = session_manager.active_session.get("type")
        if stype == "recording":
            session_manager.finalize_recording()
            return {"ok": True, "finalized": "recording"}
        if stype == "training":
            session_manager.finalize_training()
            return {"ok": True, "finalized": "training"}
        # Unknown type; clear defensively if your SessionManager supports it
        return {"ok": True, "finalized": "unknown"}

    # -------- ModelHub endpoints --------

    @app.get("/modelhub/available")
    async def modelhub_available(x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        return {"ok": True, "available": MODELHUB_AVAILABLE}

    @app.get("/modelhub/games")
    async def modelhub_games(x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        if mh_list_games is None:
            return {"ok": True, "games": []}
        return {"ok": True, "games": mh_list_games()}

    @app.get("/modelhub/game")
    async def modelhub_game(game_id: str = "", x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        if mh_load_game is None:
            return {"ok": False, "error": "ModelHub not available"}
        gid = _normalize_game_id(game_id)
        return {"ok": True, "game": mh_load_game(gid)}

    @app.get("/modelhub/catalog")
    async def modelhub_catalog(game_id: str = "", x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        gid = _normalize_game_id(game_id)

        if not MODELHUB_AVAILABLE:
            return {"ok": True, "builtin_models": [], "datasets": [], "models": [], "active": None}

        builtin = mh_list_builtin_models(PROJECT_ROOT, gid) if mh_list_builtin_models else []
        datasets = mh_get_datasets(gid) if mh_get_datasets else []
        models = mh_get_models(gid) if mh_get_models else []
        active = mh_get_active_model() if mh_get_active_model else None

        # Include local trained_models discovery if settings + discover function exist
        local_models = []
        if mh_discover_local_models and mh_load_settings:
            try:
                s = mh_load_settings()
                local_models = mh_discover_local_models(PROJECT_ROOT / s.local_models_dir, gid)
            except Exception:
                local_models = []

        return {
            "ok": True,
            "builtin_models": builtin,
            "datasets": datasets,
            "models": models,
            "local_models": local_models,
            "active": active,
        }

    @app.post("/modelhub/active")
    async def modelhub_set_active(payload: Dict[str, Any], x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        if not MODELHUB_AVAILABLE or mh_set_active_model is None:
            return {"ok": False, "error": "ModelHub not available"}
        gid = _normalize_game_id(payload.get("game_id"))
        model_id = (payload.get("model_id") or "").strip()
        path = (payload.get("path") or "").strip()
        if not model_id or not path:
            return {"ok": False, "error": "model_id and path are required"}
        mh_set_active_model(gid, model_id, path)
        return {"ok": True}

    @app.post("/modelhub/delete")
    async def modelhub_delete(payload: Dict[str, Any], x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        if not MODELHUB_AVAILABLE:
            return {"ok": False, "error": "ModelHub not available"}

        gid = _normalize_game_id(payload.get("game_id"))
        model_id = (payload.get("model_id") or "").strip()
        path = (payload.get("path") or "").strip()
        if not model_id or not path:
            return {"ok": False, "error": "model_id and path are required"}

        # Safety: only allow deletes under trained_models/<gid>/
        try:
            full_path = (PROJECT_ROOT / path).resolve()
            safe_root = (PROJECT_ROOT / "trained_models" / gid).resolve()
            if safe_root not in full_path.parents and full_path != safe_root:
                return {"ok": False, "error": f"Refusing to delete outside trained_models/{gid}"}

            if full_path.exists():
                if full_path.is_dir():
                    import shutil
                    shutil.rmtree(full_path)
                else:
                    full_path.unlink()

            if mh_delete_model_entry:
                mh_delete_model_entry(gid, model_id)

            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.post("/modelhub/validate")
    async def modelhub_validate(payload: Dict[str, Any], x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        if mh_load_game is None or mh_validate_compatibility is None or mh_load_json is None:
            return {"ok": False, "message": "ModelHub not installed"}

        gid = _normalize_game_id(payload.get("game_id"))
        model_dir = (payload.get("model_dir") or "").strip()
        if not model_dir:
            return {"ok": False, "message": "model_dir is required"}

        blueprint = mh_load_game(gid)
        profile_path = Path(model_dir) / "profile.json"
        if not profile_path.exists():
            return {"ok": False, "message": "Missing profile.json"}

        profile = mh_load_json(profile_path)
        ok, msg = mh_validate_compatibility(blueprint, profile)
        return {"ok": True, "result": {"ok": ok, "message": msg}}

    @app.post("/modelhub/offline-eval")
    async def modelhub_offline_eval(payload: Dict[str, Any], x_auth_token: Optional[str] = Header(default=None)):
        _auth(x_auth_token)
        model_dir = (payload.get("model_dir") or "").strip()
        dataset_dir = (payload.get("dataset_dir") or "").strip()
        if not model_dir or not dataset_dir:
            return {"ok": False, "message": "model_dir and dataset_dir are required"}

        script = PROJECT_ROOT / "scripts" / "evaluate_local_model.py"
        if not script.exists():
            return {"ok": False, "message": f"Missing evaluation script at {script}"}

        import subprocess
        cmd = [sys.executable, str(script), "--model-dir", model_dir, "--dataset-dir", dataset_dir]
        subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))
        return {"ok": True, "cmd": cmd}

    return app


def _pick_host() -> str:
    # Hard bind to localhost for safety
    return "127.0.0.1"


def run_server(port: int, token: str) -> Tuple[str, str]:
    """
    Runs uvicorn server. If port==0, OS picks a free port.
    Returns (base_url, token). Prints READY line to stdout.
    """
    import uvicorn
    from uvicorn.config import Config
    from uvicorn.server import Server

    host = _pick_host()
    app = create_app(token)

    # Create server programmatically to read the chosen port when port==0
    config = Config(
        app=app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        lifespan="off",
    )
    server = Server(config=config)

    # We need to run in a way that reveals the bound port.
    # Uvicorn doesn't expose bound port until sockets are created; we can pre-bind ourselves.
    import socket

    if port == 0:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, 0))
        sock.listen(128)
        bound_port = sock.getsockname()[1]
        sockets = [sock]
    else:
        bound_port = port
        sockets = None

    base_url = f"http://{host}:{bound_port}"
    print(f"READY url={base_url} token={token}", flush=True)

    if sockets is not None:
        # Run with pre-bound socket(s)
        server.run(sockets=sockets)
    else:
        server.run()

    return base_url, token


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="ModelHub local HTTP API for Tauri")
    parser.add_argument("--port", type=int, default=0, help="Port to bind. Use 0 to auto-pick.")
    parser.add_argument("--token", type=str, default="", help="Auth token. If empty, generates one.")
    parser.add_argument("--project-root", type=str, default="", help="Override project root path.")
    args = parser.parse_args(argv)

    # Allow explicit project root override for odd packaging/cwd cases
    if args.project_root.strip():
        os.environ["MODELHUB_PROJECT_ROOT"] = args.project_root.strip()

    token = args.token.strip() or secrets.token_urlsafe(32)

    # Ensure the same root logic if project-root was provided
    global PROJECT_ROOT
    PROJECT_ROOT = _resolve_project_root()
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    try:
        run_server(args.port, token)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        # Emit a single-line failure marker for Rust logs
        print(f"FAILED error={e}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

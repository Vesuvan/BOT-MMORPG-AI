#!/usr/bin/env python3
"""
BOT-MMORPG-AI Launcher
Backend v0.1.8 - ModelHub + Session Manager + Built-in Models (local-only)

Production updates:
- Fix training to use the selected dataset path (no more data/raw missing)
- Save trained artifacts to trained_models/<game>/<model_name>/ for consistent discovery
- Non-blocking subprocess output streaming (background thread + queue) so UI never freezes
- Windows-safe stop (CTRL_BREAK_EVENT via CREATE_NEW_PROCESS_GROUP) with graceful fallback
- Avoids double-finalization: start_* stops previous process WITHOUT finalizing; stop/final exit finalizes
- Removes duplicated imports and improves reliability/log clarity

Additional production fixes (this patch):
- start_bot(): prevents passing resolution/preset strings as --model by mistake
- start_bot(): falls back to active model from ModelHub if UI passes garbage/empty
- start_bot(): supports relative model paths by resolving against PROJECT_ROOT
"""

from __future__ import annotations

import os
import sys
import time
import signal
import socket
import shutil
import subprocess
import threading
from collections import deque
from pathlib import Path

import eel
from dotenv import load_dotenv

# --- PROJECT SETUP ---
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_PATH = PROJECT_ROOT / "versions" / "0.01"
ENV_PATH = PROJECT_ROOT / ".env"

DEFAULT_GAME_ID = "genshin_impact"

# Load environment variables from .env file
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
    print(f"[Info] Loaded environment from {ENV_PATH}")
else:
    print("[Warning] No .env file found. Creating new one with defaults.")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("# BOT-MMORPG-AI Configuration\n")
        f.write('AI_PROVIDER="gemini"\n')

# Ensure repo root is on sys.path so "import modelhub" works from any cwd
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Global process handle
current_process: subprocess.Popen | None = None

# Output streaming (non-blocking)
_output_queue = deque()
_output_thread: threading.Thread | None = None
_output_stop = threading.Event()

# Initialize Eel with the web folder
eel.init(str(PROJECT_ROOT / "launcher" / "web"))

# --- MODELHUB (Local-Only Model Catalog) ---
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
session_manager = None
MODELHUB_AVAILABLE = False

try:
    from modelhub.session_manager import SessionManager
    from modelhub.registry_store import (
        get_datasets,
        get_models,
        delete_model_entry,
        set_active_model,
        get_active_model,
    )
    from modelhub.local_store import discover_local_models as mh_discover_local_models
    from modelhub.registry import (
        list_games as mh_list_games,
        load_game as mh_load_game,
        ensure_default_catalog,
    )
    from modelhub.validator import (
        validate_compatibility as mh_validate_compatibility,
        load_json as mh_load_json,
    )
    from modelhub.settings import load_settings as mh_load_settings
    from modelhub.builtin_models import list_builtin_models as mh_list_builtin_models

    mh_get_datasets = get_datasets
    mh_get_models = get_models
    mh_delete_model_entry = delete_model_entry
    mh_set_active_model = set_active_model
    mh_get_active_model = get_active_model

    ensure_default_catalog()
    session_manager = SessionManager(PROJECT_ROOT)
    MODELHUB_AVAILABLE = True
except Exception as e:
    print(f"[Warning] ModelHub init failed: {e}")
    MODELHUB_AVAILABLE = False
    session_manager = None


# --- HELPER FUNCTIONS ---

def find_free_port(start_port: int = 8080, tries: int = 50) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in {start_port}-{start_port + tries - 1}")


def update_env_file(key: str, value: str) -> None:
    """Update or add a key-value pair in the .env file safely."""
    lines = []
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

    key_found = False
    new_lines = []

    clean_val = str(value).strip().strip('"').strip("'")

    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f'{key}="{clean_val}"\n')
            key_found = True
        else:
            new_lines.append(line)

    if not key_found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f'{key}="{clean_val}"\n')

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def _normalize_game_id(game_id: str | None) -> str:
    gid = (game_id or "").strip()
    return gid if gid else DEFAULT_GAME_ID


def _start_output_pump(proc: subprocess.Popen) -> None:
    """Read proc.stdout in a background thread so UI loop never blocks."""
    global _output_thread
    _output_stop.clear()

    def _pump():
        try:
            if not proc.stdout:
                return
            for line in proc.stdout:
                if _output_stop.is_set():
                    break
                _output_queue.append(line.rstrip("\n"))
        except Exception as e:
            _output_queue.append(f"[Launcher] Output pump error: {e}")

    _output_thread = threading.Thread(target=_pump, daemon=True)
    _output_thread.start()


def _drain_output_queue() -> None:
    """Drain queued stdout lines into the UI terminal."""
    while _output_queue:
        line = _output_queue.popleft()
        try:
            eel.update_terminal(line)
        except Exception:
            # UI may not be ready yet; ignore
            pass


def _looks_like_model_path(s: str) -> bool:
    """
    Heuristic: accept if it looks like a path or a model file.
    Reject presets like '480x270'.
    """
    if not s:
        return False
    s = str(s).strip()
    if not s:
        return False

    # common preset pattern like 480x270 or 1920x1080
    if "x" in s:
        parts = s.lower().split("x")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return False

    lowered = s.lower()
    if any(lowered.endswith(ext) for ext in (".pt", ".pth", ".onnx", ".safetensors")):
        return True

    # path-ish
    if ("/" in s) or ("\\" in s):
        return True

    return False


def _resolve_model_arg(game_id: str | None, model_path: str | None) -> str | None:
    """
    Return a safe model path to pass to 3-test_model.py.

    Priority:
      1) UI-provided model_path if it actually looks like a path/file
      2) Active model from ModelHub (active_model.json)
      3) None
    """
    # 1) UI-provided path (only if it looks valid)
    if isinstance(model_path, str) and _looks_like_model_path(model_path):
        p = Path(model_path)
        # If relative, resolve against PROJECT_ROOT
        if not p.is_absolute():
            p = (PROJECT_ROOT / p).resolve()
        return str(p)

    # 2) Active model from ModelHub
    if mh_get_active_model:
        try:
            active = mh_get_active_model()
        except Exception:
            active = None

        if isinstance(active, dict):
            ap = active.get("path") or active.get("model_path")
            if isinstance(ap, str) and ap.strip():
                p = Path(ap.strip())
                if not p.is_absolute():
                    p = (PROJECT_ROOT / p).resolve()
                return str(p)

    # 3) None
    return None


# --- EEL EXPOSED FUNCTIONS ---

@eel.expose
def get_ai_config():
    """Return AI config so UI can pre-fill correct provider/key."""
    return {
        "provider": os.environ.get("AI_PROVIDER", "gemini"),
        "gemini_key": os.environ.get("GEMINI_API_KEY", ""),
        "openai_key": os.environ.get("OPENAI_API_KEY", ""),
    }


@eel.expose
def save_configuration(provider, api_key):
    """Save provider + key to .env."""
    try:
        print(f"[Settings] Saving configuration. Provider: {provider}")

        os.environ["AI_PROVIDER"] = provider
        update_env_file("AI_PROVIDER", provider)

        if provider == "gemini":
            os.environ["GEMINI_API_KEY"] = api_key.strip()
            update_env_file("GEMINI_API_KEY", api_key.strip())
        elif provider == "openai":
            os.environ["OPENAI_API_KEY"] = api_key.strip()
            update_env_file("OPENAI_API_KEY", api_key.strip())

        print(f"[Settings] Successfully saved. Active: {provider}")
        return True
    except Exception as e:
        print(f"[Error] Save failed: {str(e)}")
        return False


@eel.expose
def log_to_python(msg):
    print(f"[Frontend Log] {msg}")


@eel.expose
def start_recording(game_id="unknown", dataset_name="Untitled", monitor_id=None, resolution="480x270"):
    """Start 1-collect_data.py with session tracking."""
    global current_process
    script_path = SCRIPTS_PATH / "1-collect_data.py"
    gid = _normalize_game_id(game_id)

    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    try:
        # Stop any previous process WITHOUT finalizing sessions
        _stop_process_internal(finalize=False)

        if session_manager:
            session_manager.begin_recording(gid, dataset_name)

        print(
            f"[Process] Starting recording: {script_path} "
            f"(Session: {dataset_name}, Game: {gid}, Monitor: {monitor_id}, Res: {resolution})"
        )

        env = os.environ.copy()
        env["BOTMMO_GAME_ID"] = str(gid)
        env["BOTMMO_DATASET_NAME"] = str(dataset_name)
        if monitor_id is not None:
            env["BOTMMO_MONITOR_ID"] = str(monitor_id)
        env["BOTMMO_RESOLUTION"] = str(resolution)
        # Keep outputs under versions/0.01 by default (collector uses cwd); stored as datasets/...
        env.setdefault("BOTMMO_OUTPUT_DIR", "datasets")

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        current_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(SCRIPTS_PATH),
            env=env,
            creationflags=creationflags,
        )
        _start_output_pump(current_process)
        return "Recording started successfully"
    except Exception as e:
        return f"Error starting recording: {str(e)}"


@eel.expose
def start_training(game_id="unknown", model_name="New Model", dataset_id="", arch="custom"):
    """Start 2-train_model.py using the selected dataset and a consistent output path."""
    global current_process
    script_path = SCRIPTS_PATH / "2-train_model.py"
    gid = _normalize_game_id(game_id)

    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    if not dataset_id:
        return "Error: dataset_id is empty"

    # Datasets are stored at PROJECT_ROOT/datasets/<gid>/<dataset_id>/
    dataset_dir = (PROJECT_ROOT / "datasets" / gid / dataset_id).resolve()
    if not dataset_dir.exists():
        return f"Error: Dataset directory not found: {dataset_dir}"

    try:
        # Stop any previous process WITHOUT finalizing sessions
        _stop_process_internal(finalize=False)

        # Save models in a predictable place that UI already lists
        out_dir = (PROJECT_ROOT / "trained_models" / gid / model_name).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        # IMPORTANT: out_dir must exist before we pass it into the session manager
        if session_manager:
            # NOTE: SessionManager.begin_training must accept out_dir=...
            session_manager.begin_training(
                gid, model_name, dataset_id, arch,
                out_dir=str(out_dir)
            )

        cmd = [
            sys.executable, str(script_path),
            "--data", str(dataset_dir),
            "--out", str(out_dir),
            "--model", str(arch),
        ]

        print(f"[Process] Starting training: {script_path}")
        print(f"[Process]   Game    : {gid}")
        print(f"[Process]   Dataset : {dataset_dir}")
        print(f"[Process]   Out     : {out_dir}")
        print(f"[Process]   Arch    : {arch}")

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(SCRIPTS_PATH),
            creationflags=creationflags,
        )
        _start_output_pump(current_process)
        return "Training initialized..."
    except Exception as e:
        return f"Error starting training: {str(e)}"


@eel.expose
def start_bot(game_id=None, model_path=None):
    """
    Start 3-test_model.py.

    Production behavior:
    - Accepts UI args (game_id, model_path) but validates them.
    - If UI accidentally passes a preset/resolution (e.g., '480x270'), ignore it.
    - Falls back to ModelHub active model (active_model.json) if available.
    """
    global current_process
    script_path = SCRIPTS_PATH / "3-test_model.py"

    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    try:
        _stop_process_internal(finalize=False)

        gid = _normalize_game_id(game_id)

        resolved_model = _resolve_model_arg(gid, model_path)
        if not resolved_model:
            return "Error: No valid model selected. Equip a model first in Model Manager."

        print(f"[Process] Starting bot: {script_path}")
        print(f"[Process]   Game : {gid}")
        print(f"[Process]   Model: {resolved_model}")

        cmd = [sys.executable, str(script_path), "--model", resolved_model]

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(SCRIPTS_PATH),
            creationflags=creationflags,
        )
        _start_output_pump(current_process)
        return "Bot started successfully"
    except Exception as e:
        return f"Error starting bot: {str(e)}"


def _stop_process_internal(finalize: bool = True):
    """Stop current process. If finalize=True, finalize active session."""
    global current_process

    if not current_process:
        return "No process running"

    try:
        pid = getattr(current_process, "pid", None)
        if current_process.poll() is None:
            print(f"[Process] Stopping PID: {pid}")

            stopped = False

            # Windows-friendly graceful stop
            if os.name == "nt":
                try:
                    current_process.send_signal(signal.CTRL_BREAK_EVENT)
                    current_process.wait(timeout=12)
                    stopped = True
                    print(f"[Process] PID {pid} exited after CTRL_BREAK_EVENT.")
                except Exception:
                    stopped = False

            if not stopped:
                try:
                    current_process.send_signal(signal.SIGINT)
                    current_process.wait(timeout=12)
                    stopped = True
                    print(f"[Process] PID {pid} exited after SIGINT.")
                except Exception:
                    stopped = False

            if not stopped and current_process.poll() is None:
                try:
                    print("[Process] Graceful stop failed, terminating...")
                    current_process.terminate()
                    current_process.wait(timeout=6)
                    print(f"[Process] PID {pid} exited after terminate().")
                except subprocess.TimeoutExpired:
                    print("[Process] Force killing...")
                    current_process.kill()
                    current_process.wait()
                    print(f"[Process] PID {pid} killed.")

        # Stop output pump and allow flush
        _output_stop.set()
        time.sleep(0.3)

        if finalize and session_manager and getattr(session_manager, "active_session", None):
            stype = session_manager.active_session.get("type")
            if stype == "recording":
                session_manager.finalize_recording()
            elif stype == "training":
                session_manager.finalize_training()

        current_process = None
        return "Process stopped successfully"

    except Exception as e:
        return f"Error stopping process: {str(e)}"


@eel.expose
def stop_process():
    """Stop current process and finalize any active session (recording/training)."""
    return _stop_process_internal(finalize=True)


@eel.expose
def get_api_key():
    """Legacy (Gemini)."""
    return os.environ.get("GEMINI_API_KEY", "")


# --- MODELHUB & REGISTRY EXPOSED FUNCTIONS ---

@eel.expose
def modelhub_is_available():
    return MODELHUB_AVAILABLE


@eel.expose
def modelhub_list_games():
    if mh_list_games is None:
        return []
    return mh_list_games()


@eel.expose
def modelhub_get_game(game_id):
    if mh_load_game is None:
        return {}
    gid = _normalize_game_id(game_id)
    return mh_load_game(gid)


@eel.expose
def modelhub_list_local_models(game_id):
    """List managed local models in trained_models/<game_id>/*"""
    if mh_discover_local_models is None or mh_load_settings is None:
        return []
    gid = _normalize_game_id(game_id)
    s = mh_load_settings()
    return mh_discover_local_models(PROJECT_ROOT / s.local_models_dir, gid)


@eel.expose
def modelhub_list_builtin_models(game_id):
    """List built-in/testing models shipped with the repo (e.g. versions/0.01/model)."""
    if mh_list_builtin_models is None:
        return []
    gid = _normalize_game_id(game_id)
    return mh_list_builtin_models(PROJECT_ROOT, gid)


@eel.expose
def mh_get_catalog_data(game_id):
    """Return unified data: builtin models + registry datasets/models + active selection."""
    if not MODELHUB_AVAILABLE:
        return {"builtin_models": [], "datasets": [], "models": [], "active": None}

    gid = _normalize_game_id(game_id)

    builtin = mh_list_builtin_models(PROJECT_ROOT, gid) if mh_list_builtin_models else []
    datasets = mh_get_datasets(gid) if mh_get_datasets else []
    models = mh_get_models(gid) if mh_get_models else []
    active = mh_get_active_model() if mh_get_active_model else None

    return {"builtin_models": builtin, "datasets": datasets, "models": models, "active": active}


@eel.expose
def mh_delete_model(game_id, model_id, path):
    """Delete a model from disk and registry (only under trained_models)."""
    if not MODELHUB_AVAILABLE:
        return False

    gid = _normalize_game_id(game_id)

    try:
        full_path = PROJECT_ROOT / path

        safe_root = (PROJECT_ROOT / "trained_models" / gid).resolve()
        target = full_path.resolve()
        if safe_root not in target.parents and target != safe_root:
            print(f"[Safety] Refusing to delete outside trained_models/{gid}: {target}")
            return False

        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

        if mh_delete_model_entry:
            mh_delete_model_entry(gid, model_id)
        return True
    except Exception as e:
        print(f"Delete error: {e}")
        return False


@eel.expose
def mh_set_active(game_id, model_id, path):
    """Set active model (stored in active_model.json)."""
    if not MODELHUB_AVAILABLE or mh_set_active_model is None:
        return False
    gid = _normalize_game_id(game_id)
    mh_set_active_model(gid, model_id, path)
    return True


@eel.expose
def modelhub_validate_model(game_id, model_dir):
    """Validate a model profile vs game blueprint."""
    if mh_load_game is None or mh_validate_compatibility is None or mh_load_json is None:
        return {"ok": False, "message": "ModelHub not installed"}

    gid = _normalize_game_id(game_id)
    blueprint = mh_load_game(gid)
    profile_path = Path(model_dir) / "profile.json"
    if not profile_path.exists():
        return {"ok": False, "message": "Missing profile.json"}

    profile = mh_load_json(profile_path)
    ok, msg = mh_validate_compatibility(blueprint, profile)
    return {"ok": ok, "message": msg}


@eel.expose
def modelhub_run_offline_evaluation(model_dir, dataset_dir):
    """Offline evaluation only (recorded datasets)."""
    script = PROJECT_ROOT / "scripts" / "evaluate_local_model.py"
    if not script.exists():
        return {"ok": False, "message": f"Missing evaluation script at {script}"}

    cmd = [sys.executable, str(script), "--model-dir", model_dir, "--dataset-dir", dataset_dir]
    subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))
    return {"ok": True, "cmd": cmd}


# --- SCREEN CAPTURE & PREVIEW ---

@eel.expose
def list_monitors():
    """List available monitors for screen capture."""
    try:
        from bot_mmorpg.scripts.grabscreen import list_monitors as _list_monitors
        return _list_monitors()
    except Exception as e:
        print(f"[Error] list_monitors: {e}")
        return [{"id": 1, "name": "Primary (Unknown)", "width": 1920, "height": 1080, "left": 0, "top": 0}]


@eel.expose
def get_screen_preview(monitor_id=1):
    """Get base64-encoded screen preview for display in UI."""
    try:
        from bot_mmorpg.scripts.grabscreen import grab_screen_base64
        return {"ok": True, "image": grab_screen_base64(monitor_id, 640, 360, 60)}
    except Exception as e:
        print(f"[Error] get_screen_preview: {e}")
        return {"ok": False, "error": str(e)}


# --- DATASET MANAGEMENT ---

@eel.expose
def generate_dataset_name(game_id, task="general"):
    """Generate a standardized dataset name based on game and timestamp."""
    from datetime import datetime
    gid = _normalize_game_id(game_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    task_clean = task.replace(" ", "_").lower()
    return f"{gid}_{task_clean}_{timestamp}"


@eel.expose
def list_datasets(game_id):
    """List all datasets for a game."""
    gid = _normalize_game_id(game_id)
    datasets = []

    content_dir = PROJECT_ROOT / "content"
    if content_dir.exists():
        for item in content_dir.iterdir():
            if item.is_dir() and (gid in item.name.lower() or gid == "all"):
                file_count = len(list(item.glob("*.png"))) + len(list(item.glob("*.npy")))
                datasets.append({
                    "id": item.name,
                    "name": item.name,
                    "path": str(item.relative_to(PROJECT_ROOT)),
                    "samples": file_count,
                    "location": "content",
                })

    datasets_dir = PROJECT_ROOT / "datasets" / gid
    if datasets_dir.exists():
        for item in datasets_dir.iterdir():
            if item.is_dir():
                file_count = len(list(item.glob("*.png"))) + len(list(item.glob("*.npy")))
                datasets.append({
                    "id": item.name,
                    "name": item.name,
                    "path": str(item.relative_to(PROJECT_ROOT)),
                    "samples": file_count,
                    "location": "datasets",
                })

    return datasets


@eel.expose
def delete_dataset(game_id, dataset_id, path):
    """Delete a dataset from disk."""
    gid = _normalize_game_id(game_id)
    try:
        full_path = PROJECT_ROOT / path

        content_root = (PROJECT_ROOT / "content").resolve()
        datasets_root = (PROJECT_ROOT / "datasets").resolve()
        target = full_path.resolve()

        is_safe = (
            (content_root in target.parents or target == content_root) or
            (datasets_root in target.parents or target == datasets_root)
        )

        if not is_safe:
            print(f"[Safety] Refusing to delete outside content/ or datasets/: {target}")
            return {"ok": False, "error": "Invalid path"}

        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            print(f"[Dataset] Deleted: {target}")
            return {"ok": True}

        return {"ok": False, "error": "Dataset not found"}
    except Exception as e:
        print(f"[Error] delete_dataset: {e}")
        return {"ok": False, "error": str(e)}


@eel.expose
def list_trained_models(game_id):
    """List all trained models for a game (simple filesystem scan)."""
    gid = _normalize_game_id(game_id)
    models = []

    models_dir = PROJECT_ROOT / "trained_models" / gid
    if models_dir.exists():
        for item in models_dir.iterdir():
            if item.is_dir():
                has_model = (
                    (item / "model.pt").exists() or
                    (item / "model.pth").exists() or
                    any(item.glob("*.pt")) or
                    any(item.glob("*.pth"))
                )
                if has_model:
                    models.append({
                        "id": item.name,
                        "name": item.name,
                        "path": str(item.relative_to(PROJECT_ROOT)),
                        "location": "trained_models",
                    })

    legacy_dir = PROJECT_ROOT / "versions" / "0.01" / "model"
    if legacy_dir.exists() and (any(legacy_dir.glob("*.pt")) or any(legacy_dir.glob("*.pth"))):
        models.append({
            "id": "legacy_model",
            "name": "Legacy Model (v0.01)",
            "path": str(legacy_dir.relative_to(PROJECT_ROOT)),
            "location": "versions",
        })

    return models


@eel.expose
def delete_model(game_id, model_id, path):
    """Delete a trained model from disk."""
    gid = _normalize_game_id(game_id)
    try:
        full_path = PROJECT_ROOT / path

        safe_root = (PROJECT_ROOT / "trained_models").resolve()
        target = full_path.resolve()

        if safe_root not in target.parents and target != safe_root:
            print(f"[Safety] Refusing to delete outside trained_models/: {target}")
            return {"ok": False, "error": "Invalid path"}

        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            print(f"[Model] Deleted: {target}")
            return {"ok": True}

        return {"ok": False, "error": "Model not found"}
    except Exception as e:
        print(f"[Error] delete_model: {e}")
        return {"ok": False, "error": str(e)}


# --- SYSTEM HANDLERS ---

def signal_handler(sig, frame):
    print("\n[Info] Shutting down launcher...")
    stop_process()
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)

    print("=" * 60)
    print("BOT-MMORPG-AI Launcher v0.1.8 (Stable)")
    print("=" * 60)
    print(f"[Info] Scripts path: {SCRIPTS_PATH}")
    print("[Info] Initializing web interface...")

    def check_output():
        """Drain output (non-blocking) and auto-finalize sessions on natural exit."""
        global current_process

        _drain_output_queue()

        if not current_process:
            return

        if current_process.poll() is None:
            return

        print(f"[Launcher] Process {current_process.pid} finished.")
        _output_stop.set()

        if session_manager and getattr(session_manager, "active_session", None):
            stype = session_manager.active_session.get("type")
            if stype == "training":
                session_manager.finalize_training()
            elif stype == "recording":
                session_manager.finalize_recording()

        current_process = None

    try:
        port = find_free_port(8080)

        eel.start(
            "main.html",
            size=(1400, 900),
            port=port,
            mode="chrome",
            cmdline_args=["--disable-dev-shm-usage"],
            block=False,
        )

        print(f"[Info] Launcher is running on port {port}. Press Ctrl+C to exit.")

        while True:
            eel.sleep(0.1)
            check_output()

    except EnvironmentError:
        print("[Warning] Chrome not found, using default browser...")
        port = find_free_port(8080)
        eel.start(
            "main.html",
            size=(1400, 900),
            port=port,
            mode="default",
            block=False,
        )
        while True:
            eel.sleep(0.1)
            check_output()

    except KeyboardInterrupt:
        print("\n[Info] User requested exit.")
        stop_process()
        sys.exit(0)
    except Exception as e:
        print(f"[Fatal Error] {e}")
        stop_process()
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
BOT-MMORPG-AI Launcher
Backend v0.1.8 - ModelHub + Session Manager + Built-in Models (local-only)

Key changes vs v0.1.7:
- Ensures repo root is on sys.path (fixes "No module named modelhub")
- Avoids port conflicts by picking a free port
- Default game is genshin_impact when UI does not specify one
- SessionManager now detects ANY model outputs (including TF checkpoint folders/files)
- Adds "builtin models" support (e.g. versions/0.01/model) so you can test even before training
- Catalog APIs return both: builtin + managed registry + local trained_models
"""
from __future__ import annotations

import eel
import subprocess
import os
import sys
import signal
import socket
import shutil
from pathlib import Path
from dotenv import load_dotenv

# --- PROJECT SETUP ---
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_PATH = PROJECT_ROOT / "versions" / "0.01"
ENV_PATH = PROJECT_ROOT / ".env"

DEFAULT_GAME_ID = "genshin_impact"  # your default

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

# Initialize Eel with the web folder
eel.init(str(PROJECT_ROOT / "launcher" / "web"))

# --- MODELHUB (Local-Only Model Catalog) ---
# Initialize variables to None to prevent NameErrors if imports fail
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
    """Finds an available port starting from start_port."""
    for port in range(start_port, start_port + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in {start_port}-{start_port + tries - 1}")

def update_env_file(key: str, value: str) -> None:
    """Updates or adds a key-value pair in the .env file safely."""
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


# --- EEL EXPOSED FUNCTIONS (Called from JavaScript) ---

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
def start_recording(game_id="unknown", dataset_name="Untitled"):
    """Start 1-collect_data.py with session tracking (black-box)."""
    global current_process
    script_path = SCRIPTS_PATH / "1-collect_data.py"
    gid = _normalize_game_id(game_id)

    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    try:
        stop_process()

        if session_manager:
            session_manager.begin_recording(gid, dataset_name)

        print(f"[Process] Starting recording: {script_path} (Session: {dataset_name}, Game: {gid})")
        current_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(SCRIPTS_PATH),  # IMPORTANT: scripts write outputs relative to versions/0.01
        )
        return "Recording started successfully"
    except Exception as e:
        return f"Error starting recording: {str(e)}"


@eel.expose
def start_training(game_id="unknown", model_name="New Model", dataset_id="", arch="custom"):
    """Start 2-train_model.py with session tracking (black-box)."""
    global current_process
    script_path = SCRIPTS_PATH / "2-train_model.py"
    gid = _normalize_game_id(game_id)

    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    try:
        stop_process()

        if session_manager:
            session_manager.begin_training(gid, model_name, dataset_id, arch)

        print(f"[Process] Starting training: {script_path} (Session: {model_name}, Game: {gid})")
        current_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(SCRIPTS_PATH),  # IMPORTANT: training saves into versions/0.01/model/*
        )
        return "Training initialized..."
    except Exception as e:
        return f"Error starting training: {str(e)}"


@eel.expose
def start_bot():
    """Start 3-test_model.py (loads its own default model path)."""
    global current_process
    script_path = SCRIPTS_PATH / "3-test_model.py"

    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    try:
        stop_process()
        print(f"[Process] Starting bot: {script_path}")
        current_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(SCRIPTS_PATH),
        )
        return "Bot started successfully"
    except Exception as e:
        return f"Error starting bot: {str(e)}"


@eel.expose
def stop_process():
    """Stop current process and finalize any active session (recording/training)."""
    global current_process
    if current_process:
        try:
            if current_process.poll() is None:
                print(f"[Process] Stopping PID: {current_process.pid}")
                current_process.terminate()
                try:
                    current_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    print("[Process] Force killing...")
                    current_process.kill()
                    current_process.wait()

            # Finalize session safely
            if session_manager and getattr(session_manager, "active_session", None):
                stype = session_manager.active_session.get("type")
                if stype == "recording":
                    session_manager.finalize_recording()
                elif stype == "training":
                    session_manager.finalize_training()

            current_process = None
            return "Process stopped successfully"
        except Exception as e:
            return f"Error stopping process: {str(e)}"

    return "No process running"


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
    """
    Return unified data:
    - builtin models (for testing even before training)
    - datasets/models from registry
    - currently active model selection
    """
    if not MODELHUB_AVAILABLE:
        return {"builtin_models": [], "datasets": [], "models": [], "active": None}

    gid = _normalize_game_id(game_id)

    builtin = mh_list_builtin_models(PROJECT_ROOT, gid) if mh_list_builtin_models else []
    datasets = mh_get_datasets(gid) if mh_get_datasets else []
    models = mh_get_models(gid) if mh_get_models else []
    active = mh_get_active_model() if mh_get_active_model else None

    return {
        "builtin_models": builtin,
        "datasets": datasets,
        "models": models,
        "active": active,
    }


@eel.expose
def mh_delete_model(game_id, model_id, path):
    """Delete a model from disk and registry (only under trained_models)."""
    if not MODELHUB_AVAILABLE:
        return False

    gid = _normalize_game_id(game_id)

    try:
        full_path = PROJECT_ROOT / path

        # Safety: only allow deletes under trained_models/<gid>/
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
        """Poll subprocess output and auto-finalize sessions on natural exit."""
        global current_process
        if not current_process:
            return

        if current_process.poll() is None:
            if current_process.stdout:
                line = current_process.stdout.readline()
                if line:
                    eel.update_terminal(line.strip())
            return

        # Process finished
        print(f"[Launcher] Process {current_process.pid} finished.")
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

#!/bin/bash
set -euo pipefail

echo "========================================================="
echo " ModelHub Patch (LOCAL-ONLY) — Research/Evaluation UI"
echo " - Local model catalog by game"
echo " - Offline evaluation on recorded datasets"
echo " - Optional private S3/R2 vault (disabled by default)"
echo " - Non-destructive: adds new files; optional safe launcher hooks"
echo "========================================================="

ROOT_DIR="$(pwd)"

mkdir -p scripts modelhub catalog/games docs launcher_modelhub/web \
         tauri_modelhub/src/components tauri_modelhub/src-tauri/src

# ---------------------------------------------------------
# 0) Disclaimer (research / user responsibility)
# ---------------------------------------------------------
cat > docs/MODELHUB_DISCLAIMER.md <<'EOF'
This project provides tools to train and evaluate machine learning models from user-generated data.

Users are solely responsible for how they collect data, train models, and use them, and must comply with applicable laws and any relevant terms of service.
EOF

# ---------------------------------------------------------
# 1) Naming rules
# ---------------------------------------------------------
cat > docs/MODEL_NAMING_RULES.md <<'EOF'
# ModelHub Naming Rules (Local-Only Default)

## Game ID
- lowercase snake_case: a-z, 0-9, _
- examples: genshin_impact, world_of_warcraft, new_world

## Model ID
- lowercase snake_case
- include intent + arch + version suffix
- recommended pattern:
  <type>_<arch>_v<number>
- examples:
  combat_resnet50_v2
  farming_mobilenetv2_v1
  navigation_unet_v3

## Local folder layout
trained_models/<game_id>/<model_id>/

Required:
- profile.json
- model.keras OR model.h5

Optional:
- metrics.json
- README.md
EOF

# ---------------------------------------------------------
# 2) Catalog templates (starter games; you can add more)
# ---------------------------------------------------------
cat > catalog/catalog.json <<'EOF'
{
  "version": "1.0",
  "games": [
    "genshin_impact",
    "world_of_warcraft"
  ]
}
EOF

mkdir -p catalog/games/genshin_impact
cat > catalog/games/genshin_impact/game.json <<'EOF'
{
  "id": "genshin_impact",
  "display_name": "Genshin Impact",
  "recommended_resolution": [1920, 1080],
  "supported_inputs": ["keyboard", "gamepad"],
  "expected_input_shape": [480, 270, 3],
  "expected_classes": 29,
  "notes": "Local research template. Ensure profile.json matches input_shape/classes."
}
EOF
cat > catalog/games/genshin_impact/models.json <<'EOF'
{ "models": [] }
EOF

mkdir -p catalog/games/world_of_warcraft
cat > catalog/games/world_of_warcraft/game.json <<'EOF'
{
  "id": "world_of_warcraft",
  "display_name": "World of Warcraft",
  "recommended_resolution": [1920, 1080],
  "supported_inputs": ["keyboard", "gamepad"],
  "expected_input_shape": [480, 270, 3],
  "expected_classes": 29,
  "notes": "Local research template. Ensure profile.json matches input_shape/classes."
}
EOF
cat > catalog/games/world_of_warcraft/models.json <<'EOF'
{ "models": [] }
EOF

# ---------------------------------------------------------
# 3) ModelHub core (Python)
# ---------------------------------------------------------
cat > modelhub/__init__.py <<'EOF'
__all__ = ["naming", "settings", "registry", "validator", "local_store", "s3_backend"]
EOF

cat > modelhub/naming.py <<'EOF'
import re

_ALLOWED = re.compile(r"^[a-z0-9_]+$")

def slugify(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r"[^a-z0-9]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t

def validate_id(value: str) -> bool:
    return bool(_ALLOWED.match(value or ""))
EOF

cat > modelhub/settings.py <<'EOF'
from dataclasses import dataclass
import json
from pathlib import Path

SETTINGS_PATH = Path("modelhub_settings.json")

@dataclass
class ModelHubSettings:
    # Local-only by default
    enable_cloud: bool = False
    cloud_backend: str = "s3"  # "s3" also covers Cloudflare R2 (S3-compatible)
    local_models_dir: str = "trained_models"
    cache_dir: str = "downloaded_models"
    auto_validate: bool = True
    # Optional UX settings
    ui_show_advanced: bool = False

def load_settings() -> ModelHubSettings:
    if SETTINGS_PATH.exists():
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return ModelHubSettings(**{**ModelHubSettings().__dict__, **data})
    return ModelHubSettings()

def save_settings(s: ModelHubSettings) -> None:
    SETTINGS_PATH.write_text(json.dumps(s.__dict__, indent=2), encoding="utf-8")
EOF

cat > modelhub/registry.py <<'EOF'
import json
from pathlib import Path
from typing import Dict, Any, List

CATALOG_DIR = Path("catalog")
GAMES_DIR = CATALOG_DIR / "games"

def _read_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def list_games() -> List[Dict[str, Any]]:
    catalog = _read_json(CATALOG_DIR / "catalog.json")
    out = []
    for gid in catalog.get("games", []):
        gpath = GAMES_DIR / gid / "game.json"
        if gpath.exists():
            out.append(_read_json(gpath))
    return out

def load_game(game_id: str) -> Dict[str, Any]:
    return _read_json(GAMES_DIR / game_id / "game.json")

def list_catalog_models(game_id: str) -> List[Dict[str, Any]]:
    mpath = GAMES_DIR / game_id / "models.json"
    if not mpath.exists():
        return []
    data = _read_json(mpath)
    return data.get("models", [])

def add_or_update_catalog_model(game_id: str, model_entry: Dict[str, Any]) -> None:
    gdir = GAMES_DIR / game_id
    gdir.mkdir(parents=True, exist_ok=True)
    mpath = gdir / "models.json"
    data = {"models": []}
    if mpath.exists():
        data = _read_json(mpath)

    models = [m for m in data.get("models", []) if m.get("id") != model_entry.get("id")]
    models.append(model_entry)
    data["models"] = sorted(models, key=lambda x: x.get("id", ""))

    mpath.write_text(json.dumps(data, indent=2), encoding="utf-8")
EOF

cat > modelhub/validator.py <<'EOF'
import json
from pathlib import Path
from typing import Dict, Any, Tuple

def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def validate_compatibility(game_blueprint: Dict[str, Any], model_profile: Dict[str, Any]) -> Tuple[bool, str]:
    expected_shape = tuple(game_blueprint.get("expected_input_shape", []) or [])
    expected_classes = game_blueprint.get("expected_classes", None)

    profile_game = model_profile.get("game", None)
    profile_shape = tuple(model_profile.get("input_shape", []) or [])
    profile_classes = model_profile.get("classes", None)

    if profile_game and profile_game != game_blueprint.get("id"):
        return False, f"Profile game '{profile_game}' != blueprint '{game_blueprint.get('id')}'"

    if expected_shape and profile_shape and expected_shape != profile_shape:
        return False, f"Input shape mismatch: expected {expected_shape}, got {profile_shape}"

    if expected_classes is not None and profile_classes is not None:
        if int(expected_classes) != int(profile_classes):
            return False, f"Class count mismatch: expected {expected_classes}, got {profile_classes}"

    # Required minimum metadata
    if not model_profile.get("architecture"):
        return False, "Missing required field: architecture"
    if not model_profile.get("profile_name"):
        return False, "Missing required field: profile_name"

    return True, "OK"
EOF

cat > modelhub/local_store.py <<'EOF'
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

def _read_json(p: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def discover_local_models(local_models_dir: Path, game_id: str) -> List[Dict[str, Any]]:
    base = local_models_dir / game_id
    if not base.exists():
        return []

    out: List[Dict[str, Any]] = []
    for mdir in sorted([d for d in base.iterdir() if d.is_dir()]):
        profile = _read_json(mdir / "profile.json") or {}
        metrics = _read_json(mdir / "metrics.json") or None

        model_file = None
        for cand in ("model.keras", "model.h5"):
            if (mdir / cand).exists():
                model_file = cand
                break

        out.append({
            "id": mdir.name,
            "name": profile.get("profile_name") or mdir.name,
            "type": profile.get("type") or "model",
            "architecture": profile.get("architecture") or "unknown",
            "paths": {
                "dir": str(mdir),
                "model_file": model_file,
                "profile": str(mdir / "profile.json") if (mdir / "profile.json").exists() else None,
                "metrics": str(mdir / "metrics.json") if (mdir / "metrics.json").exists() else None
            },
            "profile": profile,
            "metrics": metrics
        })
    return out
EOF

# ---------------------------------------------------------
# 4) Optional private S3/R2 vault backend (disabled by default)
# ---------------------------------------------------------
cat > docs/OPTIONAL_S3_R2_VAULT.md <<'EOF'
# Optional Private S3 / Cloudflare R2 Vault (Opt-in)

Default behavior: local-only. No cloud activity.

If you enable cloud for private use, the backend uses S3-compatible APIs:
- AWS S3
- Cloudflare R2
- other S3-compatible providers

Required environment variables (ONLY when enable_cloud=true):
- S3_ENDPOINT_URL
- S3_ACCESS_KEY_ID
- S3_SECRET_ACCESS_KEY
- S3_BUCKET
- S3_REGION (optional)
EOF

cat > modelhub/s3_backend.py <<'EOF'
from pathlib import Path
from typing import List
import os

def ensure_boto3():
    try:
        import boto3  # noqa: F401
    except Exception as e:
        raise RuntimeError("Missing dependency: boto3. Install with: pip install boto3") from e

def _client():
    ensure_boto3()
    import boto3

    endpoint = os.environ.get("S3_ENDPOINT_URL", "")
    access = os.environ.get("S3_ACCESS_KEY_ID", "")
    secret = os.environ.get("S3_SECRET_ACCESS_KEY", "")
    bucket = os.environ.get("S3_BUCKET", "")
    region = os.environ.get("S3_REGION", "auto")

    missing = [k for k, v in {
        "S3_ENDPOINT_URL": endpoint,
        "S3_ACCESS_KEY_ID": access,
        "S3_SECRET_ACCESS_KEY": secret,
        "S3_BUCKET": bucket
    }.items() if not v]
    if missing:
        raise RuntimeError("Missing S3 env vars: " + ", ".join(missing))

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region,
    )
    return client, bucket

def upload_files(local_dir: Path, prefix: str, files: List[str]) -> None:
    client, bucket = _client()
    for f in files:
        src = local_dir / f
        if src.exists():
            client.upload_file(str(src), bucket, prefix + f)

def download_files(target_dir: Path, prefix: str, files: List[str]) -> None:
    client, bucket = _client()
    target_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        try:
            client.download_file(bucket, prefix + f, str(target_dir / f))
        except Exception:
            pass
EOF

# ---------------------------------------------------------
# 5) Offline evaluation script (safe: uses recorded datasets)
# ---------------------------------------------------------
mkdir -p scripts
cat > scripts/evaluate_local_model.py <<'EOF'
"""
Offline evaluation helper:
- Loads a local model (Keras .keras/.h5)
- Evaluates on a folder of recorded dataset chunks (.npy)
This script is intentionally limited to research/evaluation on recorded data.
"""
import argparse
from pathlib import Path
import json
import numpy as np

def load_model(model_path: Path):
    import tensorflow as tf
    return tf.keras.models.load_model(str(model_path))

def iter_npy_pairs(dataset_dir: Path):
    # Expected convention: X_*.npy and Y_*.npy (adjust to your project)
    xs = sorted(dataset_dir.glob("X_*.npy"))
    for x in xs:
        y = dataset_dir / x.name.replace("X_", "Y_")
        if y.exists():
            yield x, y

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True, help="Path to trained_models/<game>/<model_id>")
    ap.add_argument("--dataset-dir", required=True, help="Folder with recorded .npy chunks")
    ap.add_argument("--max-batches", type=int, default=10)
    args = ap.parse_args()

    model_dir = Path(args.model_dir)
    dataset_dir = Path(args.dataset_dir)

    model_file = model_dir / "model.keras"
    if not model_file.exists():
        model_file = model_dir / "model.h5"
    if not model_file.exists():
        raise SystemExit("No model.keras or model.h5 found in model-dir")

    profile_path = model_dir / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}

    model = load_model(model_file)

    batches = 0
    total = 0
    correct_top1 = 0

    for x_path, y_path in iter_npy_pairs(dataset_dir):
        X = np.load(x_path)
        Y = np.load(y_path)
        preds = model.predict(X, verbose=0)

        # simple top-1 metric for classification-style outputs
        y_true = np.argmax(Y, axis=1) if Y.ndim > 1 else Y
        y_pred = np.argmax(preds, axis=1) if preds.ndim > 1 else np.rint(preds).astype(int)

        correct_top1 += int((y_true == y_pred).sum())
        total += int(len(y_true))

        batches += 1
        if batches >= args.max_batches:
            break

    acc = (correct_top1 / total) if total else 0.0
    print(json.dumps({
        "profile_name": profile.get("profile_name"),
        "architecture": profile.get("architecture"),
        "evaluated_samples": total,
        "top1_accuracy": acc
    }, indent=2))

if __name__ == "__main__":
    main()
EOF

# ---------------------------------------------------------
# 6) ModelHub CLI for Makefile targets (cloud opt-in only)
# ---------------------------------------------------------
cat > modelhub/cli.py <<'EOF'
import argparse
import json
from pathlib import Path

from modelhub.settings import load_settings
from modelhub.registry import list_games, load_game
from modelhub.local_store import discover_local_models
from modelhub.validator import load_json, validate_compatibility
from modelhub.s3_backend import download_files, upload_files

DEFAULT_FILES = ["model.keras","model.h5","profile.json","metrics.json","README.md"]

def s3_prefix(game_id: str, model_id: str) -> str:
    return f"models/{game_id}/{model_id}/"

def cmd_list_games(_):
    print(json.dumps(list_games(), indent=2))

def cmd_list_local(args):
    s = load_settings()
    models = discover_local_models(Path(s.local_models_dir), args.game)
    print(json.dumps(models, indent=2))

def cmd_validate(args):
    blueprint = load_game(args.game)
    profile = load_json(Path(args.profile))
    ok, msg = validate_compatibility(blueprint, profile)
    print(json.dumps({"ok": ok, "message": msg}, indent=2))

def cmd_download(args):
    s = load_settings()
    if not s.enable_cloud:
        raise SystemExit("Cloud is disabled by default. Set modelhub_settings.json: enable_cloud=true to use download.")
    target = Path(s.cache_dir) / args.game / args.model
    download_files(target, s3_prefix(args.game, args.model), DEFAULT_FILES)
    print(f"Downloaded to: {target}")

def cmd_upload(args):
    s = load_settings()
    if not s.enable_cloud:
        raise SystemExit("Cloud is disabled by default. Set modelhub_settings.json: enable_cloud=true to use upload.")
    src = Path(args.source_dir)
    upload_files(src, s3_prefix(args.game, args.model), DEFAULT_FILES)
    print("Uploaded.")

def main():
    p = argparse.ArgumentParser(prog="modelhub", description="Local-only ModelHub (optional private S3/R2)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list-games"); s.set_defaults(func=cmd_list_games)

    s = sub.add_parser("list-local-models")
    s.add_argument("--game", required=True); s.set_defaults(func=cmd_list_local)

    s = sub.add_parser("validate-profile")
    s.add_argument("--game", required=True)
    s.add_argument("--profile", required=True)
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("download-model")
    s.add_argument("--game", required=True)
    s.add_argument("--model", required=True)
    s.set_defaults(func=cmd_download)

    s = sub.add_parser("upload-model")
    s.add_argument("--game", required=True)
    s.add_argument("--model", required=True)
    s.add_argument("--source-dir", required=True)
    s.set_defaults(func=cmd_upload)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
EOF

# ---------------------------------------------------------
# 7) Makefile include (opt-in)
# ---------------------------------------------------------
cat > Makefile.modelhub <<'EOF'
# Optional include:
#   include Makefile.modelhub
# Local-only by default. Cloud upload/download require enable_cloud=true in modelhub_settings.json

MODELHUB_PY ?= python
GAME ?=
MODEL ?=
PROFILE ?=
SOURCE ?=
MODEL_DIR ?=
DATASET_DIR ?=

modelhub-list-games:
	$(MODELHUB_PY) -m modelhub.cli list-games

modelhub-list-local-models:
	$(MODELHUB_PY) -m modelhub.cli list-local-models --game $(GAME)

modelhub-validate-profile:
	$(MODELHUB_PY) -m modelhub.cli validate-profile --game $(GAME) --profile $(PROFILE)

# Cloud is disabled by default; opt-in only:
modelhub-download-model:
	$(MODELHUB_PY) -m modelhub.cli download-model --game $(GAME) --model $(MODEL)

modelhub-upload-model:
	$(MODELHUB_PY) -m modelhub.cli upload-model --game $(GAME) --model $(MODEL) --source-dir $(SOURCE)

# Offline evaluation on recorded datasets:
modelhub-eval-local:
	$(MODELHUB_PY) scripts/evaluate_local_model.py --model-dir $(MODEL_DIR) --dataset-dir $(DATASET_DIR)
EOF

# ---------------------------------------------------------
# 8) Eel UI (ModelHub add-on app)
# ---------------------------------------------------------
cat > launcher_modelhub/launcher.py <<'EOF'
import eel
import subprocess
from pathlib import Path
import json
import os

from modelhub.registry import list_games, load_game
from modelhub.settings import load_settings, save_settings, ModelHubSettings
from modelhub.local_store import discover_local_models
from modelhub.validator import validate_compatibility, load_json

eel.init("launcher_modelhub/web")

@eel.expose
def api_get_disclaimer():
    return Path("docs/MODELHUB_DISCLAIMER.md").read_text(encoding="utf-8")

@eel.expose
def api_get_settings():
    s = load_settings()
    return s.__dict__

@eel.expose
def api_save_settings(new_settings):
    s = ModelHubSettings(**{**load_settings().__dict__, **new_settings})
    save_settings(s)
    return {"ok": True}

@eel.expose
def api_list_games():
    return list_games()

@eel.expose
def api_get_game(game_id):
    return load_game(game_id)

@eel.expose
def api_list_local_models(game_id):
    s = load_settings()
    return discover_local_models(Path(s.local_models_dir), game_id)

@eel.expose
def api_validate_model(game_id, model_dir):
    blueprint = load_game(game_id)
    profile_path = Path(model_dir) / "profile.json"
    if not profile_path.exists():
        return {"ok": False, "message": "Missing profile.json"}
    profile = load_json(profile_path)
    ok, msg = validate_compatibility(blueprint, profile)
    return {"ok": ok, "message": msg}

@eel.expose
def api_open_folder(path_str):
    p = Path(path_str)
    if not p.exists():
        return {"ok": False, "message": "Path not found"}
    # cross-platform open
    if os.name == "nt":
        os.startfile(str(p))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])
    return {"ok": True}

@eel.expose
def api_run_offline_evaluation(model_dir, dataset_dir):
    # Research/evaluation only: runs offline evaluation script on recorded data
    cmd = ["python", "scripts/evaluate_local_model.py", "--model-dir", model_dir, "--dataset-dir", dataset_dir]
    subprocess.Popen(cmd, cwd=str(Path.cwd()))
    return {"ok": True, "cmd": cmd}

def main():
    eel.start("index.html", size=(1240, 760))

if __name__ == "__main__":
    import sys
    main()
EOF

cat > launcher_modelhub/web/index.html <<'EOF'
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>ModelHub • Local Models (Research)</title>
  <link rel="stylesheet" href="styles.css"/>
  <script src="/eel.js"></script>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">ModelHub</div>
      <div class="sub">Local Model Catalog • Research</div>

      <div class="section">
        <div class="label">Games</div>
        <div id="gameList" class="list"></div>
      </div>

      <div class="section">
        <div class="label">Tools</div>
        <button id="settingsBtn" class="btn">Settings</button>
        <button id="disclaimerBtn" class="btn">Disclaimer</button>
      </div>

      <div class="footer">Default: <b>local-only</b> • Cloud: <b>off</b></div>
    </aside>

    <main class="main">
      <header class="header">
        <div>
          <div id="gameTitle" class="title">Select a game</div>
          <div id="gameNote" class="note"></div>
        </div>
        <div class="row">
          <input id="search" class="search" placeholder="Search local models…"/>
          <button id="refreshBtn" class="btn">Refresh</button>
        </div>
      </header>

      <section class="content">
        <div id="modelGrid" class="grid"></div>
      </section>
    </main>

    <aside class="details">
      <div class="panelTitle">Details</div>
      <pre id="detailsBox" class="pre">(select a local model)</pre>

      <div class="panelTitle" style="margin-top:12px;">Actions (Research)</div>

      <div class="formRow">
        <label>Recorded dataset folder</label>
        <input id="datasetDir" class="input" placeholder="e.g. data/recorded/ (contains X_*.npy & Y_*.npy)"/>
      </div>

      <button id="openBtn" class="btn" disabled>Open Model Folder</button>
      <button id="validateBtn" class="btn" disabled>Validate Compatibility</button>
      <button id="evalBtn" class="btn primary" disabled>Run Offline Evaluation</button>

      <div id="status" class="status"></div>
    </aside>
  </div>

  <div id="modal" class="modal hidden">
    <div class="modalCard">
      <div class="modalTitle" id="modalTitle"></div>
      <pre class="modalBody" id="modalBody"></pre>
      <div class="modalActions">
        <button id="modalClose" class="btn">Close</button>
      </div>
    </div>
  </div>

  <script src="app.js"></script>
</body>
</html>
EOF

cat > launcher_modelhub/web/styles.css <<'EOF'
:root{
  --bg:#0b0f17; --panel:#111827; --panel2:#0f172a; --text:#e5e7eb; --muted:#9ca3af;
  --accent:#60a5fa; --accent2:#34d399; --border:#1f2937;
  --radius:14px;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text)}
.layout{display:grid;grid-template-columns:260px 1fr 360px;height:100vh}
.sidebar{background:var(--panel);border-right:1px solid var(--border);padding:18px;position:relative}
.brand{font-size:20px;font-weight:900}
.sub{color:var(--muted);margin-top:4px;margin-bottom:14px}
.section{margin-top:12px}
.label{color:var(--muted);font-size:12px;margin-bottom:6px}
.list{display:flex;flex-direction:column;gap:8px}
.item{padding:10px 12px;border:1px solid var(--border);border-radius:12px;cursor:pointer;background:var(--panel2)}
.item:hover{border-color:var(--accent)}
.item.active{border-color:var(--accent);box-shadow:0 0 0 2px rgba(96,165,250,.15)}
.footer{position:absolute;bottom:16px;color:var(--muted);font-size:12px}

.main{padding:18px}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;gap:10px}
.row{display:flex;gap:10px;align-items:center}
.title{font-size:22px;font-weight:900}
.note{color:var(--muted);font-size:13px;margin-top:4px}
.search{width:320px;max-width:40vw;padding:10px;border-radius:12px;border:1px solid var(--border);background:var(--panel2);color:var(--text)}
.content{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:14px;height:calc(100vh - 90px);overflow:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.card{background:var(--panel2);border:1px solid var(--border);border-radius:14px;padding:12px;cursor:pointer}
.card:hover{border-color:var(--accent2)}
.card.active{border-color:var(--accent2);box-shadow:0 0 0 2px rgba(52,211,153,.12)}
.cardTitle{font-weight:900}
.cardMeta{color:var(--muted);font-size:12px;margin-top:6px}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;border:1px solid var(--border);color:var(--muted);font-size:11px;margin-right:6px}

.details{background:var(--panel);border-left:1px solid var(--border);padding:18px}
.panelTitle{font-weight:900;margin-bottom:8px}
.pre{background:#0b1220;border:1px solid var(--border);border-radius:12px;padding:12px;height:420px;overflow:auto;color:#d1d5db}
.input{width:100%;padding:10px;border-radius:12px;border:1px solid var(--border);background:var(--panel2);color:var(--text)}
.btn{background:transparent;border:1px solid var(--border);color:var(--text);padding:10px 12px;border-radius:12px;cursor:pointer}
.btn:hover{border-color:var(--accent)}
.btn.primary{background:rgba(96,165,250,.15);border-color:rgba(96,165,250,.35)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.status{margin-top:10px;color:var(--muted);font-size:12px;min-height:18px}
.formRow{margin:10px 0}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center}
.modal.hidden{display:none}
.modalCard{width:min(900px,92vw);max-height:85vh;background:var(--panel);border:1px solid var(--border);border-radius:16px;overflow:hidden}
.modalTitle{padding:14px 16px;font-weight:900;border-bottom:1px solid var(--border)}
.modalBody{margin:0;padding:16px;max-height:60vh;overflow:auto;background:#0b1220;color:#d1d5db}
.modalActions{padding:12px 16px;border-top:1px solid var(--border);display:flex;justify-content:flex-end}
EOF

cat > launcher_modelhub/web/app.js <<'EOF'
let selectedGame = null;
let selectedModel = null;
let allModels = [];

const gameList = document.getElementById('gameList');
const modelGrid = document.getElementById('modelGrid');
const detailsBox = document.getElementById('detailsBox');
const validateBtn = document.getElementById('validateBtn');
const evalBtn = document.getElementById('evalBtn');
const openBtn = document.getElementById('openBtn');
const statusBox = document.getElementById('status');
const gameTitle = document.getElementById('gameTitle');
const gameNote = document.getElementById('gameNote');
const search = document.getElementById('search');
const datasetDir = document.getElementById('datasetDir');

const modal = document.getElementById('modal');
const modalTitle = document.getElementById('modalTitle');
const modalBody = document.getElementById('modalBody');
document.getElementById('modalClose').onclick = () => modal.classList.add('hidden');

document.getElementById('refreshBtn').onclick = () => boot();
document.getElementById('settingsBtn').onclick = async () => {
  const s = await eel.api_get_settings()();
  openModal("Settings (modelhub_settings.json)", JSON.stringify(s, null, 2) + "\n\nLocal-only default. Cloud stays OFF unless you enable it manually.");
};
document.getElementById('disclaimerBtn').onclick = async () => {
  const txt = await eel.api_get_disclaimer()();
  openModal("Disclaimer", txt);
};

search.oninput = () => renderModels(filterModels(search.value));

validateBtn.onclick = async () => {
  if(!selectedGame || !selectedModel) return;
  statusBox.textContent = "Validating…";
  const res = await eel.api_validate_model(selectedGame.id, selectedModel.paths.dir)();
  statusBox.textContent = res.ok ? ("✅ " + res.message) : ("⚠️ " + res.message);
};

openBtn.onclick = async () => {
  if(!selectedModel) return;
  const res = await eel.api_open_folder(selectedModel.paths.dir)();
  statusBox.textContent = res.ok ? "Opened folder." : ("⚠️ " + res.message);
};

evalBtn.onclick = async () => {
  if(!selectedModel) return;
  if(!datasetDir.value.trim()){
    statusBox.textContent = "⚠️ Provide a dataset folder with X_*.npy and Y_*.npy.";
    return;
  }
  statusBox.textContent = "Launching offline evaluation…";
  const res = await eel.api_run_offline_evaluation(selectedModel.paths.dir, datasetDir.value.trim())();
  statusBox.textContent = res.ok ? "▶ Evaluation started (see console output)." : "Failed to start.";
};

function openModal(title, body){
  modalTitle.textContent = title;
  modalBody.textContent = body;
  modal.classList.remove('hidden');
}

function renderGames(games){
  gameList.innerHTML = "";
  games.forEach(g => {
    const div = document.createElement('div');
    div.className = "item";
    div.textContent = g.display_name;
    div.onclick = () => selectGame(g, div);
    gameList.appendChild(div);
  });
}

async function selectGame(game, el){
  selectedGame = game;
  selectedModel = null;
  [...document.querySelectorAll('.item')].forEach(x => x.classList.remove('active'));
  el.classList.add('active');

  const ginfo = await eel.api_get_game(game.id)();
  gameTitle.textContent = ginfo.display_name;
  gameNote.textContent = ginfo.notes || "";

  detailsBox.textContent = "(select a local model)";
  validateBtn.disabled = true;
  evalBtn.disabled = true;
  openBtn.disabled = true;
  statusBox.textContent = "";

  allModels = await eel.api_list_local_models(game.id)();
  renderModels(allModels);
}

function filterModels(q){
  q = (q || "").trim().toLowerCase();
  if(!q) return allModels;
  return allModels.filter(m =>
    (m.id||"").toLowerCase().includes(q) ||
    (m.name||"").toLowerCase().includes(q) ||
    (m.type||"").toLowerCase().includes(q) ||
    (m.architecture||"").toLowerCase().includes(q)
  );
}

function renderModels(models){
  modelGrid.innerHTML = "";
  models.forEach(m => {
    const card = document.createElement('div');
    card.className = "card";
    card.onclick = () => selectModel(m, card);

    const t = document.createElement('div');
    t.className = "cardTitle";
    t.textContent = m.name || m.id;

    const meta = document.createElement('div');
    meta.className = "cardMeta";
    meta.innerHTML = `
      <span class="badge">${m.type || "model"}</span>
      <span class="badge">${m.architecture || "unknown"}</span>
      <span class="badge">${m.id}</span>
    `;

    card.appendChild(t);
    card.appendChild(meta);
    modelGrid.appendChild(card);
  });

  if(models.length === 0){
    const empty = document.createElement('div');
    empty.className = "card";
    empty.innerHTML = `<div class="cardTitle">No local models found</div>
      <div class="cardMeta">Place models in: trained_models/${selectedGame?.id || "<game_id>"}/<model_id>/</div>`;
    modelGrid.appendChild(empty);
  }
}

function selectModel(model, el){
  selectedModel = model;
  [...document.querySelectorAll('.card')].forEach(x => x.classList.remove('active'));
  el.classList.add('active');

  detailsBox.textContent = JSON.stringify({
    id: model.id,
    name: model.name,
    type: model.type,
    architecture: model.architecture,
    profile: model.profile,
    metrics: model.metrics,
    paths: model.paths
  }, null, 2);

  validateBtn.disabled = false;
  evalBtn.disabled = false;
  openBtn.disabled = false;
  statusBox.textContent = "";
}

async function boot(){
  const games = await eel.api_list_games()();
  renderGames(games);
  gameTitle.textContent = "Select a game";
  gameNote.textContent = "";
  modelGrid.innerHTML = "";
  detailsBox.textContent = "(select a local model)";
  validateBtn.disabled = true;
  evalBtn.disabled = true;
  openBtn.disabled = true;
  statusBox.textContent = "";
}
boot();
EOF

# ---------------------------------------------------------
# 9) Optional: safe hint to integrate into existing launcher
#     (No edits done automatically; just creates a helper doc)
# ---------------------------------------------------------
cat > docs/LAUNCHER_INTEGRATION_HINT.md <<'EOF'
# Integrating ModelHub into your existing launcher (optional)

This patch ships ModelHub as a separate Eel app:
  python launcher_modelhub/launcher.py

If you want a button inside your existing Eel launcher to open ModelHub,
you can add a button in your current launcher UI that runs:

  python launcher_modelhub/launcher.py

Keep it separate so you don't risk breaking existing launcher code.
EOF

# ---------------------------------------------------------
# 10) Tauri UI scaffold (appearance + settings; no IPC yet)
# ---------------------------------------------------------
cat > tauri_modelhub/package.json <<'EOF'
{
  "name": "tauri-modelhub-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.8"
  }
}
EOF

cat > tauri_modelhub/vite.config.js <<'EOF'
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 }
});
EOF

mkdir -p tauri_modelhub/src
cat > tauri_modelhub/src/styles.css <<'EOF'
:root{
  --bg:#0b0f17; --panel:#111827; --panel2:#0f172a; --text:#e5e7eb; --muted:#9ca3af;
  --accent:#60a5fa; --accent2:#34d399; --border:#1f2937;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text)}
.app{display:grid;grid-template-columns:260px 1fr 360px;height:100vh}
.sidebar{background:var(--panel);border-right:1px solid var(--border);padding:18px}
.main{padding:18px}
.details{background:var(--panel);border-left:1px solid var(--border);padding:18px}
.card{background:var(--panel2);border:1px solid var(--border);border-radius:14px;padding:12px;margin-bottom:12px}
.btn{background:transparent;border:1px solid var(--border);color:var(--text);padding:10px 12px;border-radius:12px;cursor:pointer}
.btn.primary{background:rgba(96,165,250,.15);border-color:rgba(96,165,250,.35)}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;border:1px solid var(--border);color:var(--muted);font-size:11px;margin-right:6px}
.input{width:100%;padding:10px;border-radius:12px;border:1px solid var(--border);background:var(--panel2);color:var(--text)}
EOF

cat > tauri_modelhub/src/main.jsx <<'EOF'
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(<App />);
EOF

cat > tauri_modelhub/src/App.jsx <<'EOF'
import React, { useMemo, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import ModelCard from "./components/ModelCard.jsx";
import Settings from "./components/Settings.jsx";

const MOCK_GAMES = [
  { id: "genshin_impact", display_name: "Genshin Impact" },
  { id: "world_of_warcraft", display_name: "World of Warcraft" }
];

const MOCK_MODELS = {
  genshin_impact: [
    { id: "combat_resnet50_v2", name: "Combat ResNet50 v2", type: "combat", architecture: "ResNet50" }
  ],
  world_of_warcraft: []
};

export default function App(){
  const [tab, setTab] = useState("catalog");
  const [game, setGame] = useState(null);
  const [model, setModel] = useState(null);

  const models = useMemo(() => {
    if(!game) return [];
    return MOCK_MODELS[game.id] || [];
  }, [game]);

  return (
    <div className="app">
      <div className="sidebar">
        <Sidebar
          tab={tab}
          setTab={setTab}
          games={MOCK_GAMES}
          game={game}
          setGame={(g)=>{ setGame(g); setModel(null); }}
        />
      </div>

      <div className="main">
        {tab === "catalog" && (
          <>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
              <div>
                <div style={{fontSize:22,fontWeight:900}}>
                  {game ? game.display_name : "Select a game"}
                </div>
                <div style={{color:"var(--muted)", marginTop:4}}>
                  Local-only Model Catalog (UI scaffold). IPC will be wired later.
                </div>
              </div>
              <input className="input" placeholder="Search…" style={{maxWidth:360}} />
            </div>

            <div style={{marginTop:14}}>
              {models.length === 0 ? (
                <div className="card">
                  <div style={{fontWeight:900}}>No local models</div>
                  <div style={{color:"var(--muted)",marginTop:6}}>
                    Models should live in trained_models/&lt;game_id&gt;/&lt;model_id&gt;/
                  </div>
                </div>
              ) : (
                models.map(m => (
                  <ModelCard key={m.id} model={m} active={model?.id===m.id} onClick={()=>setModel(m)} />
                ))
              )}
            </div>
          </>
        )}

        {tab === "settings" && <Settings />}
      </div>

      <div className="details">
        <div style={{fontWeight:900, marginBottom:8}}>Details</div>
        <pre style={{background:"#0b1220", border:"1px solid var(--border)", borderRadius:12, padding:12, height:420, overflow:"auto"}}>
{model ? JSON.stringify(model, null, 2) : "(select a model)"}
        </pre>

        <div style={{fontWeight:900, margin:"12px 0 8px"}}>Actions (Research)</div>
        <input className="input" placeholder="Dataset folder…" />
        <div style={{display:"flex", gap:10, marginTop:10}}>
          <button className="btn" disabled={!model}>Validate</button>
          <button className="btn primary" disabled={!model}>Evaluate</button>
        </div>
        <div style={{color:"var(--muted)", fontSize:12, marginTop:10}}>
          This scaffold is UI-only; it does not execute gameplay automation.
        </div>
      </div>
    </div>
  );
}
EOF

cat > tauri_modelhub/src/components/Sidebar.jsx <<'EOF'
import React from "react";

export default function Sidebar({ tab, setTab, games, game, setGame }){
  return (
    <div>
      <div style={{fontSize:20,fontWeight:900}}>ModelHub</div>
      <div style={{color:"var(--muted)", marginTop:4}}>Local Models • Research</div>

      <div style={{marginTop:14}}>
        <div style={{color:"var(--muted)", fontSize:12, marginBottom:6}}>Tabs</div>
        <div style={{display:"flex", gap:10}}>
          <button className="btn" onClick={()=>setTab("catalog")} style={{borderColor: tab==="catalog" ? "var(--accent)" : "var(--border)"}}>Catalog</button>
          <button className="btn" onClick={()=>setTab("settings")} style={{borderColor: tab==="settings" ? "var(--accent)" : "var(--border)"}}>Settings</button>
        </div>
      </div>

      <div style={{marginTop:16}}>
        <div style={{color:"var(--muted)", fontSize:12, marginBottom:6}}>Games</div>
        {games.map(g => (
          <div
            key={g.id}
            onClick={()=>setGame(g)}
            style={{
              padding:"10px 12px",
              borderRadius:12,
              border:`1px solid ${game?.id===g.id ? "var(--accent)" : "var(--border)"}`,
              background:"var(--panel2)",
              cursor:"pointer",
              marginBottom:8
            }}
          >
            {g.display_name}
          </div>
        ))}
      </div>

      <div style={{color:"var(--muted)", fontSize:12, marginTop:16}}>
        Default: local-only • Cloud: off
      </div>
    </div>
  );
}
EOF

cat > tauri_modelhub/src/components/ModelCard.jsx <<'EOF'
import React from "react";

export default function ModelCard({ model, active, onClick }){
  return (
    <div className="card" onClick={onClick} style={{cursor:"pointer", borderColor: active ? "var(--accent2)" : "var(--border)"}}>
      <div style={{fontWeight:900}}>{model.name}</div>
      <div style={{color:"var(--muted)", fontSize:12, marginTop:6}}>
        <span className="badge">{model.type}</span>
        <span className="badge">{model.architecture}</span>
        <span className="badge">{model.id}</span>
      </div>
    </div>
  );
}
EOF

cat > tauri_modelhub/src/components/Settings.jsx <<'EOF'
import React, { useState } from "react";

export default function Settings(){
  const [cloud, setCloud] = useState(false);
  return (
    <div>
      <div style={{fontSize:22,fontWeight:900}}>Settings</div>
      <div style={{color:"var(--muted)", marginTop:6}}>
        Cloud stays disabled by default. This UI is a scaffold; wire IPC later.
      </div>

      <div className="card" style={{marginTop:14}}>
        <div style={{fontWeight:900}}>Storage</div>
        <label style={{display:"flex", gap:10, alignItems:"center", marginTop:10, color:"var(--muted)"}}>
          <input type="checkbox" checked={cloud} onChange={(e)=>setCloud(e.target.checked)} />
          Enable private cloud vault (S3/R2) — opt-in only
        </label>
        <div style={{color:"var(--muted)", fontSize:12, marginTop:8}}>
          Enabling cloud requires keys in env vars and enable_cloud=true in modelhub_settings.json.
        </div>
      </div>
    </div>
  );
}
EOF

# Minimal Tauri config placeholders (UI scaffold only)
cat > tauri_modelhub/src-tauri/Cargo.toml <<'EOF'
[package]
name = "tauri_modelhub"
version = "0.1.0"
edition = "2021"

[dependencies]
tauri = { version = "2", features = [] }

[build-dependencies]
tauri-build = "2"
EOF

cat > tauri_modelhub/src-tauri/src/main.rs <<'EOF'
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
  tauri::Builder::default()
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
EOF

cat > tauri_modelhub/src-tauri/tauri.conf.json <<'EOF'
{
  "productName": "ModelHub",
  "version": "0.1.0",
  "identifier": "com.modelhub.local",
  "build": {
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build",
    "devPath": "http://localhost:5173",
    "distDir": "../dist"
  },
  "app": {
    "windows": [
      {
        "title": "ModelHub • Local Models (Research)",
        "width": 1240,
        "height": 760,
        "resizable": true
      }
    ]
  }
}
EOF

# ---------------------------------------------------------
# Done
# ---------------------------------------------------------
echo ""
echo "✅ Patch complete (local-only ModelHub + Eel UI + Tauri scaffold)."
echo ""
echo "Run Eel ModelHub UI:"
echo "  pip install eel"
echo "  python launcher_modelhub/launcher.py"
echo ""
echo "Place local models here:"
echo "  trained_models/<game_id>/<model_id>/"
echo "    profile.json (required)"
echo "    model.keras or model.h5 (required)"
echo "    metrics.json (optional)"
echo ""
echo "Optional Makefile:"
echo "  include Makefile.modelhub"
echo ""
echo "Offline evaluation (safe research mode):"
echo "  make modelhub-eval-local MODEL_DIR=trained_models/<game>/<model> DATASET_DIR=<recorded_dataset_dir>"

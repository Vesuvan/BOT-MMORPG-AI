# modelhub/registry_store.py
import json
import time
from pathlib import Path
from typing import Dict, Any

REGISTRY_PATH = Path("modelhub_registry.json")
ACTIVE_MODEL_PATH = Path("active_model.json")

def _load() -> Dict:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def _save(data: Dict):
    REGISTRY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

def register_dataset(game_id: str, entry: Dict[str, Any]):
    db = _load()
    if game_id not in db: db[game_id] = {"models": [], "datasets": []}
    
    # Remove duplicates if ID exists
    db[game_id]["datasets"] = [d for d in db[game_id].get("datasets", []) if d["id"] != entry["id"]]
    db[game_id]["datasets"].append(entry)
    # Sort by date desc
    db[game_id]["datasets"].sort(key=lambda x: x.get("created_at", ""), reverse=True)
    _save(db)

def register_model(game_id: str, entry: Dict[str, Any]):
    db = _load()
    if game_id not in db: db[game_id] = {"models": [], "datasets": []}
    
    # Remove duplicates
    db[game_id]["models"] = [m for m in db[game_id].get("models", []) if m["id"] != entry["id"]]
    db[game_id]["models"].append(entry)
    db[game_id]["latest"] = entry["id"] # Auto set latest
    db[game_id]["models"].sort(key=lambda x: x.get("created_at", ""), reverse=True)
    _save(db)

def get_datasets(game_id: str):
    return _load().get(game_id, {}).get("datasets", [])

def get_models(game_id: str):
    return _load().get(game_id, {}).get("models", [])

def set_active_model(game_id: str, model_id: str, model_path: str):
    data = {"game": game_id, "model_id": model_id, "model_dir": model_path}
    ACTIVE_MODEL_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

def get_active_model():
    if ACTIVE_MODEL_PATH.exists():
        return json.loads(ACTIVE_MODEL_PATH.read_text(encoding="utf-8"))
    return None

def delete_model_entry(game_id: str, model_id: str):
    db = _load()
    if game_id in db:
        db[game_id]["models"] = [m for m in db[game_id]["models"] if m["id"] != model_id]
        _save(db)
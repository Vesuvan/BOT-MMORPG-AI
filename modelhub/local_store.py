# modelhub/local_store.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Optional


def _read_json(p: Path) -> Optional[Dict[str, Any]]:
    """
    Safe JSON reader. Returns None on any error.
    """
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def discover_local_models(local_models_dir: Path, game_id: str) -> List[Dict[str, Any]]:
    """
    Discovers locally stored models for a given game_id.

    Expected layout:
      trained_models/
        <game_id>/
          <model_id>/
            model.keras | model.h5 | saved_model/
            profile.json
            metrics.json (optional)

    Returns a list of dictionaries ready for UI consumption.
    """
    base = local_models_dir / game_id
    if not base.exists():
        return []

    out: List[Dict[str, Any]] = []

    for mdir in sorted([d for d in base.iterdir() if d.is_dir()]):
        profile = _read_json(mdir / "profile.json") or {}
        metrics = _read_json(mdir / "metrics.json")

        # Detect model artifact
        model_file: Optional[str] = None
        model_type: Optional[str] = None

        # Preferred single-file formats
        for cand in ("model.keras", "model.h5"):
            if (mdir / cand).exists():
                model_file = cand
                model_type = "single-file"
                break

        # TensorFlow SavedModel directory
        if model_file is None and (mdir / "saved_model").exists():
            model_file = "saved_model"
            model_type = "directory"

        out.append(
            {
                "id": mdir.name,
                "name": profile.get("profile_name") or mdir.name,
                "game": profile.get("game"),
                "type": profile.get("type", "model"),
                "architecture": profile.get("architecture", "unknown"),
                "dataset_id": profile.get("dataset_id"),
                "created_at": profile.get("created_at"),
                "paths": {
                    "dir": str(mdir),
                    "model": model_file,
                    "model_type": model_type,
                    "profile": str(mdir / "profile.json")
                    if (mdir / "profile.json").exists()
                    else None,
                    "metrics": str(mdir / "metrics.json")
                    if (mdir / "metrics.json").exists()
                    else None,
                },
                "profile": profile,
                "metrics": metrics,
                "valid": bool(profile),  # quick UI hint
            }
        )

    return out

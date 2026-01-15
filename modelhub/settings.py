# modelhub/settings.py
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict

SETTINGS_PATH = Path("modelhub_settings.json")


@dataclass
class ModelHubSettings:
    # Local-only by default
    enable_cloud: bool = False
    cloud_backend: str = "s3"  # "s3" also covers Cloudflare R2 (S3-compatible)

    # Storage locations
    local_models_dir: str = "trained_models"
    local_datasets_dir: str = "datasets"
    cache_dir: str = "downloaded_models"

    # Behavior
    auto_validate: bool = True

    # Optional UX settings
    ui_show_advanced: bool = False

    # Builtins (repo-shipping models) visibility
    show_builtin_models: bool = True

    # Default game selection in UI (your default is Genshin Impact)
    default_game_id: str = "genshin_impact"


def _merge_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge persisted settings with dataclass defaults safely:
    - ignore unknown keys (future-proof)
    - preserve defaults for missing keys
    """
    defaults = ModelHubSettings().__dict__
    out = dict(defaults)
    for k, v in (data or {}).items():
        if k in defaults:
            out[k] = v
    return out


def load_settings() -> ModelHubSettings:
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            # If file is corrupt, fall back to defaults (do not crash launcher)
            return ModelHubSettings()
        return ModelHubSettings(**_merge_defaults(data))
    return ModelHubSettings()


def save_settings(s: ModelHubSettings) -> None:
    SETTINGS_PATH.write_text(json.dumps(s.__dict__, indent=2), encoding="utf-8")

# scripts/modelhub_cli.py
"""
ModelHub CLI Bridge (Rust/Tauri friendly)

This script is a single JSON-only entrypoint so Tauri/Rust can call ModelHub
without re-implementing ModelHub logic in Rust.

Examples:
  python scripts/modelhub_cli.py list-games
  python scripts/modelhub_cli.py get-catalog --game genshin_impact
  python scripts/modelhub_cli.py set-active --game genshin_impact --model 20260112_test --path trained_models/genshin_impact/20260112_test
  python scripts/modelhub_cli.py validate --game genshin_impact --model-dir trained_models/genshin_impact/20260112_test
  python scripts/modelhub_cli.py run-offline-eval --model-dir trained_models/genshin_impact/20260112_test --dataset-dir datasets/genshin_impact/...
  python scripts/modelhub_cli.py builtin-models --game genshin_impact

Output:
  Always prints ONE JSON object to stdout.

Notes:
- Keep output clean for Rust: no prints except final JSON.
- Works with your existing modules:
    modelhub/registry.py
    modelhub/registry_store.py
    modelhub/validator.py
    modelhub/builtin_models.py (you asked to generate this earlier)
    modelhub/settings.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# --- Ensure project root is importable ---
# scripts/modelhub_cli.py -> scripts/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _ok(data: Any = None, **extra) -> Dict[str, Any]:
    out = {"ok": True}
    if data is not None:
        out["data"] = data
    out.update(extra)
    return out


def _err(msg: str, **extra) -> Dict[str, Any]:
    out = {"ok": False, "error": msg}
    out.update(extra)
    return out


def _print_json(obj: Dict[str, Any]) -> None:
    # Ensure stable JSON output
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False))
    sys.stdout.write("\n")


def _safe_imports():
    """
    Imports ModelHub modules. Returns tuple of modules/functions or raises ImportError.
    """
    from modelhub.registry import list_games, load_game  # type: ignore
    from modelhub.registry_store import (  # type: ignore
        get_datasets,
        get_models,
        get_active_model,
        set_active_model,
    )
    from modelhub.validator import load_json, validate_compatibility  # type: ignore

    # builtin_models is optional but requested in your design
    try:
        from modelhub.builtin_models import list_builtin_models  # type: ignore
    except Exception:
        list_builtin_models = None  # type: ignore

    return {
        "list_games": list_games,
        "load_game": load_game,
        "get_datasets": get_datasets,
        "get_models": get_models,
        "get_active_model": get_active_model,
        "set_active_model": set_active_model,
        "load_json": load_json,
        "validate_compatibility": validate_compatibility,
        "list_builtin_models": list_builtin_models,
    }


def cmd_list_games(mod) -> Dict[str, Any]:
    games = mod["list_games"]()
    return _ok(games)


def cmd_builtin_models(mod, game_id: str) -> Dict[str, Any]:
    fn = mod.get("list_builtin_models")
    if not fn:
        return _ok([], note="builtin_models module not available")
    try:
        data = fn(game_id=game_id, project_root=PROJECT_ROOT)
        return _ok(data)
    except TypeError:
        # if your implementation signature differs, try fallback
        data = fn(game_id)
        return _ok(data)


def cmd_get_catalog(mod, game_id: str) -> Dict[str, Any]:
    datasets = mod["get_datasets"](game_id)
    models = mod["get_models"](game_id)
    active = mod["get_active_model"]()

    builtin = []
    fn = mod.get("list_builtin_models")
    if fn:
        try:
            builtin = fn(game_id=game_id, project_root=PROJECT_ROOT)
        except Exception:
            try:
                builtin = fn(game_id)
            except Exception:
                builtin = []

    return _ok(
        {
            "game_id": game_id,
            "builtin_models": builtin,
            "datasets": datasets,
            "models": models,
            "active": active,
        }
    )


def cmd_set_active(mod, game_id: str, model_id: str, path: str) -> Dict[str, Any]:
    # path stored in active_model.json should be relative to project root, as your launcher does
    rel = Path(path)
    if rel.is_absolute():
        try:
            rel = rel.relative_to(PROJECT_ROOT)
        except Exception:
            # if outside project root, store absolute (not recommended but still works)
            rel = Path(path)

    mod["set_active_model"](game_id, model_id, str(rel))
    return _ok({"game_id": game_id, "model_id": model_id, "path": str(rel)})


def cmd_validate(mod, game_id: str, model_dir: str) -> Dict[str, Any]:
    blueprint = mod["load_game"](game_id)

    p = Path(model_dir)
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()

    profile_path = p / "profile.json"
    if not profile_path.exists():
        return _ok({"ok": False, "message": "Missing profile.json", "model_dir": str(p)})

    profile = mod["load_json"](profile_path)
    ok, msg = mod["validate_compatibility"](blueprint, profile)
    return _ok({"ok": bool(ok), "message": msg, "model_dir": str(p)})


def cmd_run_offline_eval(model_dir: str, dataset_dir: str) -> Dict[str, Any]:
    """
    Optional helper to start your offline evaluation script.
    Mirrors what your launcher.py exposed:
      scripts/evaluate_local_model.py --model-dir ... --dataset-dir ...
    """
    script = PROJECT_ROOT / "scripts" / "evaluate_local_model.py"
    if not script.exists():
        return _err(f"Missing evaluation script at {script}")

    mdir = Path(model_dir)
    dsdir = Path(dataset_dir)
    if not mdir.is_absolute():
        mdir = (PROJECT_ROOT / mdir).resolve()
    if not dsdir.is_absolute():
        dsdir = (PROJECT_ROOT / dsdir).resolve()

    cmd = [sys.executable, str(script), "--model-dir", str(mdir), "--dataset-dir", str(dsdir)]
    try:
        subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))
        return _ok({"started": True, "cmd": cmd})
    except Exception as e:
        return _err(f"Failed to start evaluation: {e}", cmd=cmd)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="modelhub_cli", add_help=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-games")

    s = sub.add_parser("get-catalog")
    s.add_argument("--game", required=True)

    s = sub.add_parser("set-active")
    s.add_argument("--game", required=True)
    s.add_argument("--model", required=True)
    s.add_argument("--path", required=True)

    s = sub.add_parser("validate")
    s.add_argument("--game", required=True)
    s.add_argument("--model-dir", required=True)

    s = sub.add_parser("run-offline-eval")
    s.add_argument("--model-dir", required=True)
    s.add_argument("--dataset-dir", required=True)

    s = sub.add_parser("builtin-models")
    s.add_argument("--game", required=True)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        mod = _safe_imports()

        if args.cmd == "list-games":
            out = cmd_list_games(mod)

        elif args.cmd == "get-catalog":
            out = cmd_get_catalog(mod, args.game)

        elif args.cmd == "set-active":
            out = cmd_set_active(mod, args.game, args.model, args.path)

        elif args.cmd == "validate":
            out = cmd_validate(mod, args.game, args.model_dir)

        elif args.cmd == "run-offline-eval":
            out = cmd_run_offline_eval(args.model_dir, args.dataset_dir)

        elif args.cmd == "builtin-models":
            out = cmd_builtin_models(mod, args.game)

        else:
            out = _err(f"Unknown command: {args.cmd}")

        _print_json(out)

    except Exception as e:
        # Keep JSON-only output even on crashes
        tb = traceback.format_exc()
        _print_json(_err(str(e), traceback=tb))


if __name__ == "__main__":
    main()

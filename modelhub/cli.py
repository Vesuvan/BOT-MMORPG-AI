# modelhub/cli.py
from __future__ import annotations

import argparse
import json
from pathlib import Path

from modelhub.settings import load_settings
from modelhub.registry import list_games, load_game, ensure_default_catalog
from modelhub.local_store import discover_local_models
from modelhub.validator import load_json, validate_compatibility

# Cloud backends are optional; import lazily inside commands to avoid forcing boto3 dependency.

DEFAULT_FILES = [
    "model.keras",
    "model.h5",
    "profile.json",
    "metrics.json",
    "README.md",
]


def s3_prefix(game_id: str, model_id: str) -> str:
    return f"models/{game_id}/{model_id}/"


def cmd_list_games(_args) -> None:
    ensure_default_catalog()
    print(json.dumps(list_games(), indent=2))


def cmd_list_local(args) -> None:
    s = load_settings()
    models = discover_local_models(Path(s.local_models_dir), args.game)
    print(json.dumps(models, indent=2))


def cmd_validate(args) -> None:
    blueprint = load_game(args.game)
    profile = load_json(Path(args.profile))
    ok, msg = validate_compatibility(blueprint, profile)
    print(json.dumps({"ok": ok, "message": msg}, indent=2))


def cmd_download(args) -> None:
    s = load_settings()
    if not s.enable_cloud:
        raise SystemExit(
            "Cloud is disabled by default. Set modelhub_settings.json: enable_cloud=true to use download."
        )

    from modelhub.s3_backend import download_files  # lazy import

    target = Path(s.cache_dir) / args.game / args.model
    download_files(target, s3_prefix(args.game, args.model), DEFAULT_FILES)
    print(f"Downloaded to: {target}")


def cmd_upload(args) -> None:
    s = load_settings()
    if not s.enable_cloud:
        raise SystemExit(
            "Cloud is disabled by default. Set modelhub_settings.json: enable_cloud=true to use upload."
        )

    from modelhub.s3_backend import upload_files  # lazy import

    src = Path(args.source_dir)
    if not src.exists():
        raise SystemExit(f"Source dir not found: {src}")

    upload_files(src, s3_prefix(args.game, args.model), DEFAULT_FILES)
    print("Uploaded.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="modelhub",
        description="Local-only ModelHub (optional private S3/R2)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list-games", help="List game blueprints from catalog/")
    s.set_defaults(func=cmd_list_games)

    s = sub.add_parser("list-local-models", help="List local models for a game")
    s.add_argument("--game", required=True, help="Game id (e.g. genshin_impact)")
    s.set_defaults(func=cmd_list_local)

    s = sub.add_parser("validate-profile", help="Validate a profile.json against a game blueprint")
    s.add_argument("--game", required=True, help="Game id (e.g. genshin_impact)")
    s.add_argument("--profile", required=True, help="Path to profile.json")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("download-model", help="(Opt-in) Download a model from private S3/R2")
    s.add_argument("--game", required=True)
    s.add_argument("--model", required=True)
    s.set_defaults(func=cmd_download)

    s = sub.add_parser("upload-model", help="(Opt-in) Upload a model to private S3/R2")
    s.add_argument("--game", required=True)
    s.add_argument("--model", required=True)
    s.add_argument("--source-dir", required=True, help="Folder containing model.keras/h5 + profile.json")
    s.set_defaults(func=cmd_upload)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

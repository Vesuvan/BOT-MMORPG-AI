# modelhub/session_manager.py
import shutil
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from modelhub.paths import get_candidate_paths
from modelhub.fs_snapshot import take_snapshot, find_changes, identify_primary_model_file
from modelhub.registry_store import register_dataset, register_model
from modelhub.profile_writer import write_profile
from modelhub.naming import slugify


class SessionManager:
    def __init__(self, project_root: Path):
        self.root = project_root
        self.candidates = get_candidate_paths(project_root)
        self.active_session: Optional[Dict[str, Any]] = None
        self._snapshot: Dict[str, float] = {}

    # -------------------------
    # RECORDING SESSION (DATA)
    # -------------------------
    def begin_recording(self, game_id: str, dataset_name: str):
        print(f"[Session] Starting recording session: {dataset_name}")
        self.active_session = {
            "type": "recording",
            "game_id": game_id,
            "name": dataset_name,
            "start_time": time.time(),
        }

        # 1-collect_data.py creates .npy files. Keep it tight to avoid grabbing unrelated files.
        self._snapshot = take_snapshot(self.candidates["data"], extensions={".npy"})

    def finalize_recording(self):
        if not self.active_session or self.active_session.get("type") != "recording":
            return

        print("[Session] Finalizing recording...")

        # Detect new/updated .npy files
        current_state = take_snapshot(self.candidates["data"], extensions={".npy"})
        changed_files = find_changes(self._snapshot, current_state)

        # Only keep the expected dataset pattern from your script
        changed_files = [
            f for f in changed_files
            if f.is_file() and f.name.startswith("preprocessed_training_data-") and f.suffix.lower() == ".npy"
        ]

        if not changed_files:
            print("[Session] Warning: No new dataset .npy files detected.")
            self.active_session = None
            return

        game_id = self.active_session["game_id"]
        safe_name = slugify(self.active_session["name"])
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        dataset_id = f"{timestamp}_{safe_name}"

        dest_dir = self.root / "datasets" / game_id / dataset_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        # IMPORTANT: copy (not move). Scripts may expect files to remain where created.
        count = 0
        for f in sorted(changed_files, key=lambda x: x.stat().st_mtime):
            try:
                shutil.copy2(str(f), str(dest_dir / f.name))
                count += 1
            except Exception as e:
                print(f"[Session] Error copying dataset file {f}: {e}")

        if count > 0:
            entry = {
                "id": dataset_id,
                "name": self.active_session["name"],
                "path": str(dest_dir.relative_to(self.root)),
                "file_count": count,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            register_dataset(game_id, entry)
            print(f"[Session] Archived dataset: {count} file(s) -> {entry['path']}")

        self.active_session = None

    # -------------------------
    # TRAINING SESSION (MODEL)
    # -------------------------
    def begin_training(self, game_id: str, model_name: str, dataset_id: str, arch: str):
        print(f"[Session] Starting training session: {model_name}")
        self.active_session = {
            "type": "training",
            "game_id": game_id,
            "name": model_name,
            "dataset_id": dataset_id,
            "architecture": arch,
            "start_time": time.time(),
        }

        # IMPORTANT: extensions=None so we detect TF checkpoints (checkpoint, .index, .data-*, .meta)
        self._snapshot = take_snapshot(self.candidates["model"], extensions=None)

    def finalize_training(self):
        if not self.active_session or self.active_session.get("type") != "training":
            return

        print("[Session] Finalizing training...")

        # IMPORTANT: extensions=None so we detect TF checkpoints
        current_state = take_snapshot(self.candidates["model"], extensions=None)
        changed_files = find_changes(self._snapshot, current_state)

        primary_artifact = identify_primary_model_file(changed_files)
        if not primary_artifact:
            print("[Session] Warning: No new model artifact detected.")
            self.active_session = None
            return

        game_id = self.active_session["game_id"]
        safe_name = slugify(self.active_session["name"])
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        model_id = f"{timestamp}_{safe_name}"

        dest_dir = self.root / "trained_models" / game_id / model_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Case A: Single-file model (.keras/.h5/.pt/.pth)
            if primary_artifact.is_file():
                # Standardize filename while preserving extension
                ext = primary_artifact.suffix.lower()
                if ext in (".keras", ".h5", ".pt", ".pth"):
                    dest_file = dest_dir / f"model{ext}"
                else:
                    dest_file = dest_dir / primary_artifact.name
                shutil.copy2(str(primary_artifact), str(dest_file))

            # Case B: TF checkpoint directory (your repo: versions/0.01/model)
            else:
                # copy entire folder as "checkpoint/"
                ckpt_dest = dest_dir / "checkpoint"
                if ckpt_dest.exists():
                    shutil.rmtree(ckpt_dest)
                shutil.copytree(str(primary_artifact), str(ckpt_dest))

            print(f"[Session] Archived model artifact -> {dest_dir}")

        except Exception as e:
            print(f"[Session] Error archiving model artifact: {e}")
            self.active_session = None
            return

        # Write profile.json (used by UI + validator)
        meta = {
            "model_name": self.active_session["name"],
            "game_id": game_id,
            "model_id": model_id,
            "dataset_id": self.active_session.get("dataset_id", ""),
            "architecture": self.active_session.get("architecture", "custom"),
        }
        write_profile(dest_dir, meta)

        entry = {
            "id": model_id,
            "name": self.active_session["name"],
            "path": str(dest_dir.relative_to(self.root)),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        register_model(game_id, entry)

        self.active_session = None

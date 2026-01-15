# modelhub/fs_snapshot.py
import os
from pathlib import Path
from typing import Dict, Optional, Set, List


def take_snapshot(search_paths: List[Path], extensions: Optional[Set[str]] = None) -> Dict[str, float]:
    """
    Scans given paths and returns a dict: { 'full_path': mtime }
    If a path is a directory, it scans recursively.

    Notes:
    - If extensions is None: includes ALL files (best for TF checkpoints: 'checkpoint', '*.index', '*.data-*', '*.meta').
    - If extensions is a set: filters by Path.suffix (e.g. {'.npy'}).
    """
    snapshot: Dict[str, float] = {}

    for p in search_paths:
        if not p.exists():
            continue

        if p.is_file():
            if extensions is not None and p.suffix not in extensions:
                continue
            snapshot[str(p.resolve())] = p.stat().st_mtime
            continue

        # Directory: walk recursively
        for root, _, files in os.walk(str(p)):
            for f in files:
                fp = Path(root) / f
                if extensions is not None and fp.suffix not in extensions:
                    continue
                snapshot[str(fp.resolve())] = fp.stat().st_mtime

    return snapshot


def find_changes(before: Dict[str, float], after: Dict[str, float]) -> List[Path]:
    """
    Returns list of paths that are either NEW or have a NEWER mtime.
    """
    changed: List[Path] = []
    for path_str, mtime_after in after.items():
        mtime_before = before.get(path_str)
        if mtime_before is None or mtime_after > mtime_before:
            changed.append(Path(path_str))
    return changed


def identify_primary_model_file(changed_files: List[Path]) -> Optional[Path]:
    """
    Heuristic to pick the 'main' model artifact from a list of changes.

    Supports:
    - Keras/TF saved single-file models: .keras / .h5
    - Torch: .pt / .pth
    - TensorFlow checkpoint format (your repo):
        versions/0.01/model/
          checkpoint
          test.index
          test.data-00000-of-00001
          test.meta (optional)

    Returns:
    - A Path to the primary file OR a directory (for checkpoint/saved_model) OR None.
    """
    if not changed_files:
        return None

    # 1) Prefer single-file model formats
    for ext in (".keras", ".h5", ".pt", ".pth"):
        candidates = [f for f in changed_files if f.is_file() and f.suffix.lower() == ext]
        if candidates:
            return max(candidates, key=lambda x: x.stat().st_mtime)

    # 2) TF checkpoint detection:
    # If 'checkpoint' file changed, treat its parent directory as the artifact.
    for f in changed_files:
        if f.is_file() and f.name.lower() == "checkpoint":
            return f.parent

    # If any .index appears, likely checkpoint prefix; return that directory.
    index_files = [f for f in changed_files if f.is_file() and f.suffix.lower() == ".index"]
    if index_files:
        newest_index = max(index_files, key=lambda x: x.stat().st_mtime)
        return newest_index.parent

    # 3) If a directory itself is in changed_files, return newest dir
    dirs = [f for f in changed_files if f.is_dir()]
    if dirs:
        return max(dirs, key=lambda x: x.stat().st_mtime)

    # 4) Fallback: newest changed file
    files = [f for f in changed_files if f.exists()]
    if files:
        return max(files, key=lambda x: x.stat().st_mtime)

    return None

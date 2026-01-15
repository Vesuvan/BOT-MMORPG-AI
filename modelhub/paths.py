# modelhub/paths.py
from pathlib import Path
from typing import Dict, List


def get_candidate_paths(project_root: Path) -> Dict[str, List[Path]]:
    """
    Returns lists of potential output locations for models and datasets.

    IMPORTANT for this repo:
    - 1-collect_data.py writes: preprocessed_training_data-*.npy (in the CURRENT WORKING DIRECTORY)
      So we must scan BOTH:
        - project_root
        - project_root/versions/0.01

    - 2-train_model.py writes TF checkpoints to: versions/0.01/model/ (prefix 'test')
      So we must include:
        - project_root/versions/0.01/model
    """
    v001 = project_root / "versions" / "0.01"

    # ---- Model outputs (include TF checkpoint directory) ----
    model_candidates = [
        # Root-level single-file models / folders (common patterns)
        project_root / "model.h5",
        project_root / "model.keras",
        project_root / "model",          # could be a folder
        project_root / "models",

        # Version folder outputs (your scripts)
        v001 / "model",                  # TF checkpoint folder used by your code (IMPORTANT)
        v001 / "model.h5",
        v001 / "model.keras",
        v001 / "models",
    ]

    # Keep existing paths if they exist (for files, check itself; for dirs, check itself)
    model_paths: List[Path] = [p for p in model_candidates if p.exists()]

    # ---- Dataset outputs (black-box script writes to CWD) ----
    # We scan likely CWDs plus common folders.
    data_candidates = [
        # Common folders
        project_root / "data",
        project_root / "dataset",
        v001 / "data",
        v001 / "dataset",

        # Likely CWDs (IMPORTANT)
        project_root,
        v001,
    ]

    data_paths: List[Path] = [p for p in data_candidates if p.exists()]

    # De-duplicate while preserving order
    def dedupe(paths: List[Path]) -> List[Path]:
        seen = set()
        out = []
        for p in paths:
            rp = str(p.resolve())
            if rp in seen:
                continue
            seen.add(rp)
            out.append(p)
        return out

    return {
        "model": dedupe(model_paths),
        "data": dedupe(data_paths),
    }

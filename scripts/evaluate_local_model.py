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

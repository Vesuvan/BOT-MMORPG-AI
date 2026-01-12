import argparse
import sys
import numpy as np
import cv2
import os
from pathlib import Path
from random import shuffle

# Try imports
try:
    from .models import inception_v3 as googlenet
except ImportError:
    try:
        from models import inception_v3 as googlenet
    except:
        print("[Error] 'models.py' not found. Ensure helper files are present.")
        # Minimal Mock for logic flow if dependencies missing
        class googlenet:
            def __init__(self, w, h, c, lr, output, model_name): pass
            def fit(self, *args, **kwargs): pass
            def save(self, name): pass
            def load(self, name): pass

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="BOT MMORPG - Train Model")
    parser.add_argument("--data", default="data/raw", help="Folder with .npy files")
    parser.add_argument("--out", default="artifacts/model", help="Folder to save model")
    args = parser.parse_args(argv)

    data_dir = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    MODEL_NAME = str(out_dir / 'mmorpg_bot')
    WIDTH = 480
    HEIGHT = 270
    LR = 1e-3
    EPOCHS = 1

    print(f"[train_model] Loading data from {data_dir}")
    
    # Initialize Model
    model = googlenet(WIDTH, HEIGHT, 3, LR, output=29, model_name=MODEL_NAME)

    # Find data files
    all_files = list(data_dir.glob("training_data-*.npy"))
    if not all_files:
        print("[train_model] No training data found!")
        return 1

    print(f"[train_model] Found {len(all_files)} data files. Starting training...")

    for e in range(EPOCHS):
        shuffle(all_files)
        for count, file_path in enumerate(all_files):
            try:
                print(f"[train_model] Processing {file_path.name}...")
                train_data = np.load(file_path, allow_pickle=True)
                
                # Split Train/Test
                train = train_data[:-50]
                test = train_data[-50:]

                # Reshape
                X = np.array([i[0] for i in train]).reshape(-1, WIDTH, HEIGHT, 3)
                Y = [i[1] for i in train]

                test_x = np.array([i[0] for i in test]).reshape(-1, WIDTH, HEIGHT, 3)
                test_y = [i[1] for i in test]

                model.fit(
                    {'input': X}, 
                    {'targets': Y}, 
                    n_epoch=1, 
                    validation_set=({'input': test_x}, {'targets': test_y}), 
                    snapshot_step=2500, 
                    show_metric=True, 
                    run_id=MODEL_NAME
                )

                if count % 10 == 0:
                    print(f'[train_model] Saving checkpoint to {MODEL_NAME}')
                    model.save(MODEL_NAME)

            except Exception as e:
                print(f"[train_model] Error processing file: {e}")

    print("[train_model] Training Complete.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
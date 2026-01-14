import argparse
import sys
import cv2
import numpy as np
import time
from pathlib import Path
from collections import deque
from statistics import mean

try:
    from .grabscreen import grab_screen
    from .directkeys import PressKey, ReleaseKey, W, A, S, D
    from .models import inception_v3 as googlenet
    from .getkeys import key_check
    from .vjoy2 import * # Assuming vjoy wrapper
except ImportError:
    from grabscreen import grab_screen
    from directkeys import PressKey, ReleaseKey, W, A, S, D
    from models import inception_v3 as googlenet
    from getkeys import key_check
    from vjoy2 import *

# Constants
GAME_WIDTH = 1920
GAME_HEIGHT = 1080
WIDTH = 480
HEIGHT = 270
LR = 1e-3

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="BOT MMORPG - Run Bot")
    parser.add_argument("--model", default="artifacts/model/mmorpg_bot", help="Path to model file")
    args = parser.parse_args(argv)

    print(f"[test_model] Loading model from {args.model}")
    
    # Init Model
    model = googlenet(WIDTH, HEIGHT, 3, LR, output=29)
    try:
        model.load(args.model)
        print("[test_model] Model loaded successfully.")
    except Exception as e:
        print(f"[test_model] Failed to load model: {e}")
        return 1

    print("[test_model] Starting Bot in 4 seconds...")
    for i in list(range(4))[::-1]:
        print(i+1)
        time.sleep(1)

    paused = False
    
    while True:
        if not paused:
            screen = grab_screen(region=(0, 40, GAME_WIDTH, GAME_HEIGHT+40))
            screen = cv2.cvtColor(screen, cv2.COLOR_BGR2RGB)
            screen = cv2.resize(screen, (WIDTH, HEIGHT))

            # Prediction
            prediction = model.predict([screen.reshape(WIDTH, HEIGHT, 3)])[0]
            
            # Weighted prediction logic (from original code)
            weights = np.array([4.5, 0.1, 0.1, 0.1, 1.8, 1.8, 0.5, 0.5, 0.2, 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1])
            prediction = np.array(prediction) * weights
            mode_choice = np.argmax(prediction)

            print(f"[Bot] Action: {mode_choice}")

            # --- CONTROL LOGIC ---
            if mode_choice == 0: # Straight
                PressKey(W); ReleaseKey(A); ReleaseKey(D); ReleaseKey(S)
            elif mode_choice == 1: # Reverse
                PressKey(S); ReleaseKey(A); ReleaseKey(W); ReleaseKey(D)
            elif mode_choice == 2: # Left
                PressKey(A); ReleaseKey(S); ReleaseKey(D) 
            elif mode_choice == 3: # Right
                PressKey(D); ReleaseKey(A); ReleaseKey(S)
            elif mode_choice == 8: # No Keys
                ReleaseKey(W); ReleaseKey(A); ReleaseKey(S); ReleaseKey(D)
            
            # ... Add gamepad logic here based on mode_choice ...

        # Pause Check
        keys = key_check()
        if 'T' in keys:
            if paused:
                paused = False
                print('[Bot] Resumed')
                time.sleep(1)
            else:
                paused = True
                print('[Bot] Paused')
                ReleaseKey(W); ReleaseKey(A); ReleaseKey(S); ReleaseKey(D)
                time.sleep(1)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
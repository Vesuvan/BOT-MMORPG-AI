import argparse
import sys
import os
import cv2
import numpy as np
import time
from pathlib import Path

# IMPORTANT: Ensure these helper modules are in the same folder or python path
try:
    from .grabscreen import grab_screen
    from .getkeys import key_check
    from .getgamepad import gamepad_check
except ImportError:
    # Fallback if running directly
    from grabscreen import grab_screen
    from getkeys import key_check
    from getgamepad import gamepad_check

def keys_to_output(keys):
    """One-hot encode keyboard input [W, S, A, D, WA, WD, SA, SD, NOKEY]"""
    # [W, S, A, D, WA, WD, SA, SD, NOKEY]
    output = [0,0,0,0,0,0,0,0,0]
    
    if 'W' in keys and 'A' in keys: output[4] = 1
    elif 'W' in keys and 'D' in keys: output[5] = 1
    elif 'S' in keys and 'A' in keys: output[6] = 1
    elif 'S' in keys and 'D' in keys: output[7] = 1
    elif 'W' in keys: output[0] = 1
    elif 'S' in keys: output[1] = 1
    elif 'A' in keys: output[2] = 1
    elif 'D' in keys: output[3] = 1
    else: output[8] = 1
    return output

def gamepad_keys_to_output(lista):
    return [int(elem) for elem in lista]

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="BOT MMORPG - Data Collection")
    parser.add_argument("--out", default="data/raw", help="Output folder")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[collect_data] Saving to: {out_dir.resolve()}")
    
    # Check existing files to resume count
    starting_value = 1
    while True:
        file_name = out_dir / f'training_data-{starting_value}.npy'
        if file_name.exists():
            starting_value += 1
        else:
            print(f"[collect_data] Starting with file index: {starting_value}")
            break

    training_data = []
    
    # Countdown
    for i in list(range(4))[::-1]:
        print(i+1)
        time.sleep(1)

    print('[collect_data] STARTING RECORDING!')
    paused = False
    
    while True:
        if not paused:
            # Capture Screen
            screen = grab_screen(region=(0, 40, 1920, 1120))
            # Resize
            screen = cv2.resize(screen, (480, 270))
            # Convert Color
            screen = cv2.cvtColor(screen, cv2.COLOR_BGR2RGB)

            # Capture Input
            keys = key_check()
            output = keys_to_output(keys)
            
            gamepad_keys = gamepad_check()
            output_gamepad = gamepad_keys_to_output(gamepad_keys)

            # Combine Inputs
            final_output = np.concatenate((output, output_gamepad), axis=None)
            training_data.append([screen, final_output])

            # Optional: Show preview (careful in headless envs)
            try:
                cv2.imshow('Recorder Preview', cv2.resize(screen, (640, 360)))
                if cv2.waitKey(25) & 0xFF == ord('q'):
                    break
            except Exception:
                pass # Ignore if no display available

            # Save Chunks
            if len(training_data) % 100 == 0:
                print(f"[collect_data] Buffer: {len(training_data)} frames")
                
                if len(training_data) == 500:
                    save_path = out_dir / f'training_data-{starting_value}.npy'
                    np.save(save_path, training_data)
                    print(f'[collect_data] Saved chunk {starting_value}')
                    training_data = []
                    starting_value += 1

        # Pause Logic
        keys = key_check()
        if 'T' in keys:
            if paused:
                paused = False
                print('[collect_data] Unpaused')
                time.sleep(1)
            else:
                paused = True
                print('[collect_data] Paused')
                time.sleep(1)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""
Data Collection Script for BOT-MMORPG-AI

Captures screen and input data for training neural networks.
Includes comprehensive error handling for production use.
"""

import argparse
import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Import helper modules with fallback
try:
    from .getgamepad import gamepad_check
    from .getkeys import key_check
    from .grabscreen import grab_screen
except ImportError:
    try:
        from getgamepad import gamepad_check
        from getkeys import key_check
        from grabscreen import grab_screen
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error(
            "Please ensure grabscreen.py, getkeys.py, and getgamepad.py are available"
        )
        grab_screen = None
        key_check = None
        gamepad_check = None


class DataCollectionError(Exception):
    """Custom exception for data collection errors."""

    pass


class ScreenCaptureError(DataCollectionError):
    """Raised when screen capture fails."""

    pass


class InputCaptureError(DataCollectionError):
    """Raised when input capture fails."""

    pass


def keys_to_output(keys: List[str]) -> List[int]:
    """
    One-hot encode keyboard input.

    Args:
        keys: List of pressed key characters

    Returns:
        One-hot encoded list [W, S, A, D, WA, WD, SA, SD, NOKEY]
    """
    output = [0, 0, 0, 0, 0, 0, 0, 0, 0]

    if "W" in keys and "A" in keys:
        output[4] = 1
    elif "W" in keys and "D" in keys:
        output[5] = 1
    elif "S" in keys and "A" in keys:
        output[6] = 1
    elif "S" in keys and "D" in keys:
        output[7] = 1
    elif "W" in keys:
        output[0] = 1
    elif "S" in keys:
        output[1] = 1
    elif "A" in keys:
        output[2] = 1
    elif "D" in keys:
        output[3] = 1
    else:
        output[8] = 1

    return output


def gamepad_keys_to_output(lista: List) -> List[int]:
    """Convert gamepad input to integer list."""
    return [int(elem) for elem in lista]


def validate_dependencies() -> bool:
    """
    Validate that all required dependencies are available.

    Returns:
        True if all dependencies are available

    Raises:
        DataCollectionError: If dependencies are missing
    """
    missing = []

    if grab_screen is None:
        missing.append("grabscreen")
    if key_check is None:
        missing.append("getkeys")
    if gamepad_check is None:
        missing.append("getgamepad")

    if missing:
        raise DataCollectionError(
            f"Missing required modules: {', '.join(missing)}. "
            "Please ensure all helper modules are installed."
        )

    return True


def capture_screen(
    region: Tuple[int, int, int, int], target_size: Tuple[int, int] = (480, 270)
) -> np.ndarray:
    """
    Capture and process screen region.

    Args:
        region: Screen region (x1, y1, x2, y2)
        target_size: Target resize dimensions (width, height)

    Returns:
        Processed screen image as numpy array

    Raises:
        ScreenCaptureError: If capture fails
    """
    try:
        screen = grab_screen(region=region)

        if screen is None or screen.size == 0:
            raise ScreenCaptureError("Screen capture returned empty image")

        # Resize
        screen = cv2.resize(screen, target_size)

        # Convert color space
        screen = cv2.cvtColor(screen, cv2.COLOR_BGR2RGB)

        return screen

    except ScreenCaptureError:
        raise
    except Exception as e:
        raise ScreenCaptureError(f"Failed to capture screen: {e}")


def capture_input() -> Tuple[List[int], List[int]]:
    """
    Capture keyboard and gamepad input.

    Returns:
        Tuple of (keyboard_output, gamepad_output)

    Raises:
        InputCaptureError: If input capture fails
    """
    try:
        # Capture keyboard
        keys = key_check() if key_check else []
        keyboard_output = keys_to_output(keys)

        # Capture gamepad (with fallback for missing gamepad)
        try:
            gamepad_keys = gamepad_check() if gamepad_check else []
            gamepad_output = (
                gamepad_keys_to_output(gamepad_keys) if gamepad_keys else []
            )
        except Exception:
            # Gamepad not available - use empty output
            gamepad_output = []

        return keyboard_output, gamepad_output

    except Exception as e:
        raise InputCaptureError(f"Failed to capture input: {e}")


def save_training_data(data: List, path: Path) -> bool:
    """
    Save training data to file with safety checks.

    Args:
        data: Training data to save
        path: Output file path

    Returns:
        True if save successful
    """
    try:
        # Create backup if file exists
        if path.exists():
            backup_path = path.with_suffix(".npy.bak")
            path.rename(backup_path)
            logger.info(f"Created backup: {backup_path}")

        # Save data – training samples are [screen_array, label_array] pairs
        # with different shapes, so we must use dtype=object + allow_pickle.
        arr = np.array(data, dtype=object)
        np.save(path, arr, allow_pickle=True)
        logger.info(f"Saved {len(data)} frames to {path}")

        # Verify save
        if not path.exists():
            raise IOError("Save verification failed - file not created")

        return True

    except Exception as e:
        logger.error(f"Failed to save training data: {e}")
        return False


def show_preview(screen: np.ndarray, window_name: str = "Recorder Preview") -> bool:
    """
    Show preview window if display is available.

    Args:
        screen: Screen image to display
        window_name: Window title

    Returns:
        False if user pressed 'q' to quit, True otherwise
    """
    try:
        preview = cv2.resize(screen, (640, 360))
        cv2.imshow(window_name, preview)

        if cv2.waitKey(25) & 0xFF == ord("q"):
            return False
        return True

    except Exception:
        # Display not available (headless mode)
        return True


def cleanup():
    """Clean up resources."""
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main data collection function.

    Args:
        argv: Command line arguments

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = argparse.ArgumentParser(
        description="BOT MMORPG - Data Collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Controls:
  T     - Toggle pause/resume
  Q     - Quit (in preview window)

Example:
  python collect_data.py --out data/my_session
        """,
    )
    parser.add_argument(
        "--out", default="data/raw", help="Output folder for training data"
    )
    parser.add_argument(
        "--region", default="0,40,1920,1120", help="Screen capture region (x1,y1,x2,y2)"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Frames per chunk file (default: 500)",
    )
    parser.add_argument(
        "--no-preview", action="store_true", help="Disable preview window"
    )
    args = parser.parse_args(argv)

    # Parse region
    try:
        region = tuple(map(int, args.region.split(",")))
        if len(region) != 4:
            raise ValueError("Region must have 4 values")
    except ValueError as e:
        logger.error(f"Invalid region format: {e}")
        logger.error("Use format: x1,y1,x2,y2 (e.g., 0,40,1920,1120)")
        return 1

    # Validate dependencies
    try:
        validate_dependencies()
    except DataCollectionError as e:
        logger.error(str(e))
        return 1

    # Setup output directory
    out_dir = Path(args.out)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {out_dir.resolve()}")
    except Exception as e:
        logger.error(f"Cannot create output directory: {e}")
        return 1

    # Find starting file index
    starting_value = 1
    while True:
        file_name = out_dir / f"training_data-{starting_value}.npy"
        if file_name.exists():
            starting_value += 1
        else:
            logger.info(f"Starting with file index: {starting_value}")
            break

    training_data = []
    paused = False
    frame_count = 0
    error_count = 0
    max_consecutive_errors = 10

    # Countdown
    logger.info("Starting in...")
    for i in range(3, 0, -1):
        logger.info(f"  {i}...")
        time.sleep(1)

    logger.info("RECORDING STARTED! Press 'T' to pause, 'Q' to quit.")

    try:
        while True:
            if not paused:
                try:
                    # Capture screen
                    screen = capture_screen(region=region)

                    # Capture input
                    keyboard_output, gamepad_output = capture_input()

                    # Combine inputs
                    final_output = (
                        np.concatenate((keyboard_output, gamepad_output), axis=None)
                        if gamepad_output
                        else np.array(keyboard_output)
                    )

                    training_data.append([screen, final_output])
                    frame_count += 1
                    error_count = 0  # Reset on success

                    # Show preview
                    if not args.no_preview:
                        if not show_preview(screen):
                            logger.info("User requested quit via preview window")
                            break

                    # Progress logging
                    if frame_count % 100 == 0:
                        logger.info(
                            f"Captured {frame_count} frames (buffer: {len(training_data)})"
                        )

                    # Save chunks
                    if len(training_data) >= args.chunk_size:
                        save_path = out_dir / f"training_data-{starting_value}.npy"
                        if save_training_data(training_data, save_path):
                            training_data = []
                            starting_value += 1
                        else:
                            logger.warning("Save failed, will retry on next chunk")

                except ScreenCaptureError as e:
                    error_count += 1
                    logger.warning(f"Screen capture error ({error_count}): {e}")

                except InputCaptureError as e:
                    error_count += 1
                    logger.warning(f"Input capture error ({error_count}): {e}")

                # Check for too many consecutive errors
                if error_count >= max_consecutive_errors:
                    logger.error(
                        f"Too many consecutive errors ({max_consecutive_errors}). Stopping."
                    )
                    break

            # Check for pause/quit
            try:
                keys = key_check() if key_check else []

                if "T" in keys:
                    paused = not paused
                    status = "PAUSED" if paused else "RESUMED"
                    logger.info(f"Recording {status}")
                    time.sleep(0.5)  # Debounce

                if "Q" in keys:
                    logger.info("User requested quit")
                    break

            except Exception:
                pass  # Ignore key check errors during pause check

            # Small delay to prevent CPU overload when paused
            if paused:
                time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")

    finally:
        # Save any remaining data
        if training_data:
            logger.info(f"Saving remaining {len(training_data)} frames...")
            save_path = out_dir / f"training_data-{starting_value}.npy"
            save_training_data(training_data, save_path)

        cleanup()
        logger.info(f"Data collection complete. Total frames: {frame_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

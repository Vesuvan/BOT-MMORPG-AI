#!/usr/bin/env python3
"""
BOT-MMORPG-AI Launcher
A gaming-style frontend launcher for the BOT-MMORPG-AI project
"""
import eel
import subprocess
import os
import sys
import signal
from pathlib import Path
from dotenv import load_dotenv

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_PATH = PROJECT_ROOT / "versions" / "0.01"

# Load environment variables from .env file
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[Info] Loaded environment from {env_path}")
else:
    print("[Warning] No .env file found. AI features may be disabled.")

# Global process handle
current_process = None

# Initialize Eel with the web folder
eel.init(str(PROJECT_ROOT / "launcher" / "web"))


@eel.expose
def start_recording():
    """
    Start the data collection script (1-collect_data.py)
    """
    global current_process
    script_path = SCRIPTS_PATH / "1-collect_data.py"

    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    try:
        # Stop any existing process
        stop_process()

        # Start the recording script
        current_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        return "Recording started successfully"
    except Exception as e:
        return f"Error starting recording: {str(e)}"


@eel.expose
def start_training():
    """
    Start the model training script (2-train_model.py)
    """
    global current_process
    script_path = SCRIPTS_PATH / "2-train_model.py"

    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    try:
        # Stop any existing process
        stop_process()

        # Start the training script
        current_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Read and return output
        output = []
        if current_process.stdout:
            for line in current_process.stdout:
                output.append(line.strip())
                eel.update_terminal(line.strip())

        current_process.wait()
        return "\n".join(output) if output else "Training completed"
    except Exception as e:
        return f"Error during training: {str(e)}"


@eel.expose
def start_bot():
    """
    Start the bot execution script (3-test_model.py)
    """
    global current_process
    script_path = SCRIPTS_PATH / "3-test_model.py"

    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    try:
        # Stop any existing process
        stop_process()

        # Start the bot script
        current_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        return "Bot started successfully"
    except Exception as e:
        return f"Error starting bot: {str(e)}"


@eel.expose
def stop_process():
    """
    Stop the currently running process
    """
    global current_process

    if current_process and current_process.poll() is None:
        try:
            # Send SIGTERM first (graceful shutdown)
            current_process.terminate()
            try:
                current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if still running
                current_process.kill()
                current_process.wait()
            return "Process stopped successfully"
        except Exception as e:
            return f"Error stopping process: {str(e)}"
    else:
        return "No process running"


@eel.expose
def get_api_key():
    """
    Get the Gemini API key from environment variable
    """
    return os.environ.get("GEMINI_API_KEY", "")


def signal_handler(sig, frame):
    """
    Handle Ctrl+C gracefully
    """
    print("\n[Info] Shutting down launcher...")
    stop_process()
    sys.exit(0)


def main():
    """
    Main launcher entry point
    """
    # Register signal handler for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)

    print("=" * 60)
    print("BOT-MMORPG-AI Launcher v0.1.2")
    print("=" * 60)
    print("[Info] Initializing web interface...")
    print(f"[Info] Scripts path: {SCRIPTS_PATH}")
    print("[Info] Starting launcher...")
    print("[Info] Press Ctrl+C to exit")
    print("=" * 60)

    try:
        # Start the Eel app with the main.html file
        eel.start(
            'main.html',
            size=(1400, 900),
            port=8080,
            mode='chrome',  # Try Chrome first
            cmdline_args=['--disable-dev-shm-usage']
        )
    except EnvironmentError:
        # If Chrome is not available, try default browser
        print("[Warning] Chrome not found, using default browser...")
        eel.start(
            'main.html',
            size=(1400, 900),
            port=8080,
            mode='default'
        )


if __name__ == "__main__":
    main()

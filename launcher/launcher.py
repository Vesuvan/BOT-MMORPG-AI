#!/usr/bin/env python3
"""
BOT-MMORPG-AI Launcher
Backend v0.1.4 - Supports Gemini & OpenAI + Debug Logs
A gaming-style frontend launcher for the BOT-MMORPG-AI project
"""
import eel
import subprocess
import os
import sys
import signal
from pathlib import Path
from dotenv import load_dotenv

# --- PROJECT SETUP ---
# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_PATH = PROJECT_ROOT / "versions" / "0.01"
ENV_PATH = PROJECT_ROOT / ".env"

# Load environment variables from .env file
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
    print(f"[Info] Loaded environment from {ENV_PATH}")
else:
    # Create empty .env with defaults if it doesn't exist
    print("[Warning] No .env file found. Creating new one with defaults.")
    with open(ENV_PATH, "w") as f:
        f.write("# BOT-MMORPG-AI Configuration\n")
        f.write("AI_PROVIDER=\"gemini\"\n")

# Global process handle
current_process = None

# Initialize Eel with the web folder
eel.init(str(PROJECT_ROOT / "launcher" / "web"))


# --- HELPER FUNCTIONS ---

def update_env_file(key, value):
    """
    Updates or adds a key-value pair in the .env file safely.
    It reads the file, finds the key to replace, or appends it if missing.
    """
    lines = []
    if ENV_PATH.exists():
        with open(ENV_PATH, "r") as f:
            lines = f.readlines()

    key_found = False
    new_lines = []
    
    # Clean the value (remove quotes if user added them, we add them back)
    clean_val = str(value).strip().strip('"').strip("'")
    
    for line in lines:
        # Check if line starts with KEY=
        if line.strip().startswith(f"{key}="):
            new_lines.append(f'{key}="{clean_val}"\n')
            key_found = True
        else:
            new_lines.append(line)
    
    if not key_found:
        # If file doesn't end with newline, add one
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines.append('\n')
        new_lines.append(f'{key}="{clean_val}"\n')

    with open(ENV_PATH, "w") as f:
        f.writelines(new_lines)


# --- EEL EXPOSED FUNCTIONS (Called from JavaScript) ---

@eel.expose
def get_ai_config():
    """
    Returns the full AI configuration to the frontend on startup.
    This allows the UI to pre-fill the correct API key and provider.
    """
    return {
        "provider": os.environ.get("AI_PROVIDER", "gemini"),
        "gemini_key": os.environ.get("GEMINI_API_KEY", ""),
        "openai_key": os.environ.get("OPENAI_API_KEY", "")
    }


@eel.expose
def save_configuration(provider, api_key):
    """
    Saves the provider and the specific key associated with it persistently.
    """
    try:
        print(f"[Settings] Saving configuration. Provider: {provider}")
        
        # 1. Update the Active Provider
        os.environ["AI_PROVIDER"] = provider
        update_env_file("AI_PROVIDER", provider)

        # 2. Update the specific API Key based on provider
        if provider == "gemini":
            os.environ["GEMINI_API_KEY"] = api_key.strip()
            update_env_file("GEMINI_API_KEY", api_key.strip())
        elif provider == "openai":
            os.environ["OPENAI_API_KEY"] = api_key.strip()
            update_env_file("OPENAI_API_KEY", api_key.strip())

        print(f"[Settings] Successfully saved. Active: {provider}")
        return True
    except Exception as e:
        print(f"[Error] Save failed: {str(e)}")
        return False


@eel.expose
def log_to_python(msg):
    """Allows frontend to print to Python console for debugging"""
    print(f"[Frontend Log] {msg}")


@eel.expose
def start_recording():
    """Start the data collection script (1-collect_data.py)"""
    global current_process
    script_path = SCRIPTS_PATH / "1-collect_data.py"
    
    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    try:
        stop_process()
        print(f"[Process] Starting recording: {script_path}")
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
    """Start the model training script (2-train_model.py)"""
    global current_process
    script_path = SCRIPTS_PATH / "2-train_model.py"

    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    try:
        stop_process()
        print(f"[Process] Starting training: {script_path}")
        current_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Merge stderr into stdout for training logs
            text=True,
            bufsize=1
        )
        return "Training initialized..."
    except Exception as e:
        return f"Error starting training: {str(e)}"


@eel.expose
def start_bot():
    """Start the bot execution script (3-test_model.py)"""
    global current_process
    script_path = SCRIPTS_PATH / "3-test_model.py"

    if not script_path.exists():
        return f"Error: Script not found at {script_path}"

    try:
        stop_process()
        print(f"[Process] Starting bot: {script_path}")
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
    """Stop the currently running process"""
    global current_process
    if current_process:
        try:
            if current_process.poll() is None:
                print(f"[Process] Stopping PID: {current_process.pid}")
                # Try graceful termination first
                current_process.terminate()
                try:
                    current_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    print("[Process] Force killing...")
                    current_process.kill()
                    current_process.wait()
                return "Process stopped successfully"
            else:
                current_process = None
                return "Process was already stopped"
        except Exception as e:
            return f"Error stopping process: {str(e)}"
    else:
        return "No process running"


@eel.expose
def get_api_key():
    """
    Legacy function: Get the Gemini API key. 
    Kept for backward compatibility if needed, but get_ai_config is preferred.
    """
    return os.environ.get("GEMINI_API_KEY", "")


# --- SYSTEM HANDLERS ---

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n[Info] Shutting down launcher...")
    stop_process()
    sys.exit(0)


def main():
    """Main launcher entry point"""
    # Register signal handler for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)

    print("=" * 60)
    print("BOT-MMORPG-AI Launcher v0.1.4 (Production Ready)")
    print("=" * 60)
    print(f"[Info] Scripts path: {SCRIPTS_PATH}")
    print("[Info] Initializing web interface...")

    # Background loop to read subprocess output and send to UI
    def check_output():
        global current_process
        if current_process and current_process.poll() is None:
            # Non-blocking read of stdout
            if current_process.stdout:
                line = current_process.stdout.readline()
                if line:
                    eel.update_terminal(line.strip())

    try:
        # Start the Eel app
        eel.start(
            'main.html',
            size=(1400, 900),
            port=8080,
            mode='chrome',  # Try Chrome first
            cmdline_args=['--disable-dev-shm-usage'],
            block=False     # Non-blocking to allow the while loop below
        )
        
        print("[Info] Launcher is running. Press Ctrl+C to exit.")
        
        # Main application loop
        while True:
            eel.sleep(0.1) # Yield to Eel's internal loop
            check_output() # Check for output from training/bot scripts

    except EnvironmentError:
        # Fallback if Chrome isn't installed
        print("[Warning] Chrome not found, using default browser...")
        eel.start(
            'main.html', 
            size=(1400, 900), 
            port=8080, 
            mode='default',
            block=False
        )
        while True:
            eel.sleep(0.1)
            check_output()
            
    except KeyboardInterrupt:
        print("\n[Info] User requested exit.")
        stop_process()
        sys.exit(0)
    except Exception as e:
        print(f"[Fatal Error] {e}")
        stop_process()
        sys.exit(1)


if __name__ == "__main__":
    main()
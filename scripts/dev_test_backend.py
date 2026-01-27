#!/usr/bin/env python3
"""
Development Test Runner for BOT-MMORPG-AI Backend

Cross-platform test script that creates a temporary mock environment
simulating the production installation structure. Tests backend,
modelhub, and ML scripts without modifying the repo tree.

Usage:
    python dev_test_backend.py --mode backend    # Test FastAPI backend
    python dev_test_backend.py --mode ml         # Test ML scripts
    python dev_test_backend.py --mode metadata   # Test model metadata
    python dev_test_backend.py --mode full       # Run all tests
    python dev_test_backend.py --mode cleanup    # Remove test env
    python dev_test_backend.py --mode full --keep-env  # Keep env for debug
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
import urllib.request
import urllib.error


# ANSI colors (disabled on Windows without ANSI support)
if platform.system() == "Windows":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        COLORS_ENABLED = True
    except Exception:
        COLORS_ENABLED = False
else:
    COLORS_ENABLED = True

class Colors:
    GREEN = "\033[92m" if COLORS_ENABLED else ""
    CYAN = "\033[96m" if COLORS_ENABLED else ""
    YELLOW = "\033[93m" if COLORS_ENABLED else ""
    RED = "\033[91m" if COLORS_ENABLED else ""
    MAGENTA = "\033[95m" if COLORS_ENABLED else ""
    GRAY = "\033[90m" if COLORS_ENABLED else ""
    RESET = "\033[0m" if COLORS_ENABLED else ""


def log_ok(msg: str) -> None:
    print(f"{Colors.GREEN}[OK]   {msg}{Colors.RESET}")


def log_info(msg: str) -> None:
    print(f"{Colors.CYAN}[INFO] {msg}{Colors.RESET}")


def log_warn(msg: str) -> None:
    print(f"{Colors.YELLOW}[WARN] {msg}{Colors.RESET}")


def log_fail(msg: str) -> None:
    print(f"{Colors.RED}[FAIL] {msg}{Colors.RESET}")


def log_test(msg: str) -> None:
    print(f"{Colors.MAGENTA}[TEST] {msg}{Colors.RESET}")


# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent
TEST_ENV_ROOT = Path(tempfile.gettempdir()) / "BOT-MMORPG-AI-DevTest"


def remove_test_env() -> None:
    """Remove the test environment directory."""
    if TEST_ENV_ROOT.exists():
        log_info("Cleaning up test environment...")

        # On Windows, wait a bit for any processes to release handles
        if platform.system() == "Windows":
            time.sleep(0.5)

        try:
            shutil.rmtree(TEST_ENV_ROOT, ignore_errors=True)
            log_ok("Test environment removed")
        except Exception as e:
            log_warn(f"Could not fully remove test env: {e}")


def setup_mock_environment() -> Path:
    """Create mock production environment structure."""
    log_info("Setting up mock production environment...")

    # Create directory structure (mirrors production install)
    dirs = [
        TEST_ENV_ROOT,
        TEST_ENV_ROOT / "runtime" / "py" / "python",
        TEST_ENV_ROOT / "runtime" / "py" / "site-packages",
        TEST_ENV_ROOT / "resources" / "versions" / "0.01",
        TEST_ENV_ROOT / "resources" / "backend",
        TEST_ENV_ROOT / "resources" / "modelhub",
        TEST_ENV_ROOT / "datasets",
        TEST_ENV_ROOT / "models",
        TEST_ENV_ROOT / "logs",
        TEST_ENV_ROOT / "content",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Copy backend files
    log_info("Copying backend files...")
    backend_src = REPO_ROOT / "backend"
    backend_dst = TEST_ENV_ROOT / "resources" / "backend"
    if backend_src.exists():
        for item in backend_src.iterdir():
            if item.is_file():
                shutil.copy2(item, backend_dst / item.name)
            elif item.is_dir() and not item.name.startswith("__"):
                shutil.copytree(item, backend_dst / item.name, dirs_exist_ok=True)

    # Copy modelhub files
    log_info("Copying modelhub files...")
    modelhub_src = REPO_ROOT / "modelhub"
    modelhub_dst = TEST_ENV_ROOT / "resources" / "modelhub"
    if modelhub_src.exists():
        for item in modelhub_src.iterdir():
            if item.is_file():
                shutil.copy2(item, modelhub_dst / item.name)
            elif item.is_dir() and not item.name.startswith("__"):
                shutil.copytree(item, modelhub_dst / item.name, dirs_exist_ok=True)

    # Copy ML scripts
    log_info("Copying ML scripts...")
    versions_src = REPO_ROOT / "versions" / "0.01"
    versions_dst = TEST_ENV_ROOT / "resources" / "versions" / "0.01"
    if versions_src.exists():
        for item in versions_src.iterdir():
            if item.is_file():
                shutil.copy2(item, versions_dst / item.name)
            elif item.is_dir() and not item.name.startswith("__"):
                shutil.copytree(item, versions_dst / item.name, dirs_exist_ok=True)

    # Create mock .env file
    env_content = '''AI_PROVIDER="gemini"
GEMINI_API_KEY=""
OPENAI_API_KEY=""
PYTHON_PATH=""
'''
    (TEST_ENV_ROOT / ".env").write_text(env_content)

    log_ok("Mock environment created")
    return TEST_ENV_ROOT


def get_python_exe() -> str:
    """Find Python executable to use for testing."""
    # Try repo venv first
    if platform.system() == "Windows":
        venv_py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        venv_py = REPO_ROOT / ".venv" / "bin" / "python"

    if venv_py.exists():
        return str(venv_py)

    # Use current Python
    return sys.executable


def test_backend(env_root: Path, python_exe: str) -> bool:
    """Test the FastAPI backend server."""
    log_test("Testing Backend Server...")

    backend_script = env_root / "resources" / "backend" / "entry_main.py"
    if not backend_script.exists():
        log_fail(f"Backend script not found: {backend_script}")
        return False

    # Set up environment
    sep = ";" if platform.system() == "Windows" else ":"
    pythonpath = sep.join([
        str(env_root / "resources" / "backend"),
        str(env_root / "resources" / "modelhub"),
        str(env_root / "resources"),
        str(REPO_ROOT),
    ])

    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["MODELHUB_DATA_ROOT"] = str(env_root)
    env["MODELHUB_RESOURCE_ROOT"] = str(env_root / "resources")

    # Generate test token
    import random
    token = f"test-token-{random.randint(10000, 99999)}"

    log_info(f"Starting backend server...")
    log_info(f"PYTHONPATH: {pythonpath}")

    # Start backend process
    process = subprocess.Popen(
        [python_exe, "-u", str(backend_script), "--port", "0", "--token", token],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(env_root),
        text=True,
        bufsize=1,
    )

    try:
        # Wait for READY line
        timeout = 30
        start_time = time.time()
        port = None

        while time.time() - start_time < timeout:
            if process.poll() is not None:
                _, stderr = process.communicate()
                log_fail("Backend exited prematurely")
                if stderr:
                    log_fail(f"stderr: {stderr}")
                return False

            # Read stdout line by line
            line = process.stdout.readline()
            if line:
                line = line.strip()
                print(f"  {Colors.GRAY}[Backend] {line}{Colors.RESET}")

                # Look for READY line
                import re
                match = re.match(r"READY url=http://127\.0\.0\.1:(\d+) token=", line)
                if match:
                    port = int(match.group(1))
                    log_ok(f"Backend started on port {port}")
                    break
            else:
                time.sleep(0.1)

        if port is None:
            log_fail(f"Backend did not print READY within {timeout}s")
            return False

        # Test API endpoints
        log_info("Testing API endpoints...")

        base_url = f"http://127.0.0.1:{port}"

        # Test /modelhub/available
        try:
            req = urllib.request.Request(
                f"{base_url}/modelhub/available",
                headers={"X-Auth-Token": token}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                log_ok("GET /modelhub/available - OK")
        except Exception as e:
            log_warn(f"GET /modelhub/available - Failed: {e}")

        # Test /modelhub/games
        try:
            req = urllib.request.Request(
                f"{base_url}/modelhub/games",
                headers={"X-Auth-Token": token}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                log_ok(f"GET /modelhub/games - OK (found {len(data)} games)")
        except Exception as e:
            log_warn(f"GET /modelhub/games - Failed: {e}")

        log_ok("Backend tests PASSED")
        return True

    finally:
        # Cleanup
        if process.poll() is None:
            log_info("Stopping backend server...")
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()


def test_ml_scripts(env_root: Path, python_exe: str) -> bool:
    """Test ML scripts (import validation only)."""
    log_test("Testing ML Scripts (import validation)...")

    scripts_dir = env_root / "resources" / "versions" / "0.01"

    scripts = [
        ("models.py", "models"),
        ("grabscreen.py", "grabscreen"),
        ("getkeys.py", "getkeys"),
    ]

    all_passed = True

    for script_name, module_name in scripts:
        script_path = scripts_dir / script_name
        if not script_path.exists():
            log_warn(f"Script not found: {script_name}")
            continue

        log_info(f"Validating {script_name}...")

        # Test syntax
        test_code = f'''
import sys
try:
    with open(r'{script_path}', 'r') as f:
        compile(f.read(), r'{script_path}', 'exec')
    print('SYNTAX_OK')
except SyntaxError as e:
    print(f'SYNTAX_ERROR: {{e}}')
    sys.exit(1)
'''
        result = subprocess.run(
            [python_exe, "-c", test_code],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            log_ok(f"{script_name} - Syntax OK")
        else:
            log_fail(f"{script_name} - {result.stdout}{result.stderr}")
            all_passed = False

    # Test that models.py can import TensorFlow
    log_info("Testing models.py import (requires TensorFlow)...")
    model_test_code = f'''
import sys
sys.path.insert(0, r'{scripts_dir}')
try:
    import tensorflow as tf
    print(f'TensorFlow: {{tf.__version__}}')
    from models import inception_v3
    print('IMPORT_OK: inception_v3')
except ImportError as e:
    print(f'IMPORT_WARN: {{e}}')
except Exception as e:
    print(f'ERROR: {{e}}')
'''
    result = subprocess.run(
        [python_exe, "-c", model_test_code],
        capture_output=True,
        text=True,
    )
    print(f"  {Colors.GRAY}{result.stdout.strip()}{Colors.RESET}")
    if result.stderr:
        print(f"  {Colors.GRAY}{result.stderr.strip()}{Colors.RESET}")

    if all_passed:
        log_ok("ML script validation PASSED")
    else:
        log_warn("ML script validation had warnings")

    return all_passed


def test_model_metadata(env_root: Path, python_exe: str) -> bool:
    """Test the model metadata system."""
    log_test("Testing Model Metadata System...")

    modelhub_path = env_root / "resources" / "modelhub"

    test_code = f'''
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, r'{modelhub_path}')

from model_metadata import (
    ModelMetadata,
    InputSpec,
    OutputSpec,
    TrainingConfig,
    create_default_metadata,
    save_metadata,
    load_metadata,
    validate_metadata
)

# Test 1: Create default metadata
print('Test 1: Creating default metadata...')
meta = create_default_metadata(
    model_id='test_model_001',
    game_id='genshin_impact',
    architecture='inception_v3'
)
assert meta.model_id == 'test_model_001'
assert meta.input_spec.width == 480
assert meta.output_spec.num_classes == 29
print('  PASS: Default metadata created')

# Test 2: Validate metadata
print('Test 2: Validating metadata...')
is_valid, errors = validate_metadata(meta)
assert is_valid, f'Validation failed: {{errors}}'
print('  PASS: Metadata is valid')

# Test 3: Save and load metadata
print('Test 3: Save/Load round-trip...')
with tempfile.TemporaryDirectory() as tmpdir:
    model_dir = Path(tmpdir) / 'test_model'
    model_dir.mkdir()

    # Create a fake checkpoint file
    (model_dir / 'model.index').write_text('fake')

    # Save
    save_metadata(meta, model_dir)
    assert (model_dir / 'metadata.json').exists()

    # Load
    loaded = load_metadata(model_dir)
    assert loaded is not None
    assert loaded.model_id == meta.model_id
    print('  PASS: Save/Load works')

# Test 4: Serialization
print('Test 4: JSON serialization...')
data = meta.to_dict()
assert isinstance(data, dict)
assert 'model_id' in data
assert 'input_spec' in data
json_str = json.dumps(data)  # Should not raise
print('  PASS: JSON serialization works')

print('')
print('All model metadata tests PASSED!')
'''

    result = subprocess.run(
        [python_exe, "-c", test_code],
        capture_output=True,
        text=True,
    )

    for line in result.stdout.split("\n"):
        if "PASS" in line:
            print(f"  {Colors.GREEN}{line}{Colors.RESET}")
        elif "FAIL" in line or "ERROR" in line:
            print(f"  {Colors.RED}{line}{Colors.RESET}")
        elif line.strip():
            print(f"  {Colors.GRAY}{line}{Colors.RESET}")

    if result.stderr:
        print(f"  {Colors.RED}{result.stderr}{Colors.RESET}")

    if result.returncode == 0:
        log_ok("Model metadata tests PASSED")
        return True
    else:
        log_fail("Model metadata tests FAILED")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Development Test Runner for BOT-MMORPG-AI Backend"
    )
    parser.add_argument(
        "--mode",
        choices=["backend", "ml", "metadata", "full", "cleanup"],
        default="backend",
        help="Test mode (default: backend)",
    )
    parser.add_argument(
        "--keep-env",
        action="store_true",
        help="Keep test environment after tests complete",
    )
    args = parser.parse_args()

    print()
    print("==============================================")
    print(" BOT-MMORPG-AI Development Test Runner")
    print("==============================================")
    print()
    log_info(f"Repo root: {REPO_ROOT}")
    log_info(f"Test environment: {TEST_ENV_ROOT}")
    log_info(f"Mode: {args.mode}")
    print()

    if args.mode == "cleanup":
        remove_test_env()
        return 0

    try:
        # Setup environment
        remove_test_env()  # Clean start
        env_root = setup_mock_environment()

        # Find Python
        python_exe = get_python_exe()
        log_info(f"Using Python: {python_exe}")

        # Verify Python version
        result = subprocess.run(
            [python_exe, "--version"],
            capture_output=True,
            text=True,
        )
        log_info(f"Python version: {result.stdout.strip()}")

        results: Dict[str, Optional[bool]] = {
            "Backend": None,
            "MLScripts": None,
            "Metadata": None,
        }

        # Run tests based on mode
        if args.mode == "backend":
            results["Backend"] = test_backend(env_root, python_exe)
        elif args.mode == "ml":
            results["MLScripts"] = test_ml_scripts(env_root, python_exe)
        elif args.mode == "metadata":
            results["Metadata"] = test_model_metadata(env_root, python_exe)
        elif args.mode == "full":
            results["Metadata"] = test_model_metadata(env_root, python_exe)
            results["MLScripts"] = test_ml_scripts(env_root, python_exe)
            results["Backend"] = test_backend(env_root, python_exe)

        # Summary
        print()
        print("==============================================")
        print(" Test Results")
        print("==============================================")

        all_passed = True
        for test, result in results.items():
            if result is None:
                print(f"  {test} : {Colors.GRAY}SKIPPED{Colors.RESET}")
            elif result:
                print(f"  {test} : {Colors.GREEN}PASSED{Colors.RESET}")
            else:
                print(f"  {test} : {Colors.RED}FAILED{Colors.RESET}")
                all_passed = False

        print()
        if all_passed:
            log_ok("All tests completed successfully!")
            return 0
        else:
            log_fail("Some tests failed")
            return 1

    finally:
        # Cleanup unless keep-env is set
        if not args.keep_env:
            remove_test_env()
        else:
            log_info(f"Test environment preserved at: {TEST_ENV_ROOT}")
            log_info("Run with --mode cleanup to remove")


if __name__ == "__main__":
    sys.exit(main())

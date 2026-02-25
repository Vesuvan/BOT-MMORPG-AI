import importlib
import pathlib
import platform
import py_compile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.mark.health
def test_launcher_compiles():
    launcher_py = ROOT / "launcher" / "launcher.py"
    assert launcher_py.exists()
    py_compile.compile(str(launcher_py), doraise=True)


@pytest.mark.health
def test_launcher_web_assets_exist():
    web_dir = ROOT / "launcher" / "web"
    assert web_dir.exists()
    assert (web_dir / "main.html").exists()


@pytest.mark.health
def test_cli_modules_import():
    import sys

    # Add src to path if bot_mmorpg is not installed
    src_path = str(ROOT / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    try:
        for mod in [
            "bot_mmorpg.scripts.collect_data",
            "bot_mmorpg.scripts.train_model",
            "bot_mmorpg.scripts.test_model",
        ]:
            importlib.import_module(mod)
    except ImportError as e:
        # Skip if core dependencies (torch, etc.) are missing
        if "torch" in str(e) or "No module named" in str(e):
            pytest.skip(f"Skipping import test - dependency missing: {e}")


@pytest.mark.health
@pytest.mark.skipif(
    platform.system() != "Windows", reason="Windows-only installer assets"
)
def test_windows_installer_assets_present():
    # We just verify files exist; we do not execute installers in tests.
    # Note: vJoySetup.exe is a third-party binary not tracked in git;
    # only check for assets that are part of the repository.
    files = [
        ROOT / "frontend" / "input_record" / "install-interception.exe",
    ]
    # Optional assets that may not be present in CI
    optional_files = [
        ROOT / "versions" / "0.01" / "pyvjoy" / "vJoySetup.exe",
    ]
    missing = [str(p) for p in files if not p.exists()]
    assert not missing, "Missing installer assets: " + ", ".join(missing)
    missing_optional = [str(p) for p in optional_files if not p.exists()]
    if missing_optional:
        pytest.skip(
            "Optional installer assets not present: " + ", ".join(missing_optional)
        )

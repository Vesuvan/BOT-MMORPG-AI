import importlib
import pathlib
import py_compile
import platform
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
    for mod in [
        "bot_mmorpg.scripts.collect_data",
        "bot_mmorpg.scripts.train_model",
        "bot_mmorpg.scripts.test_model",
    ]:
        importlib.import_module(mod)

@pytest.mark.health
@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only installer assets")
def test_windows_installer_assets_present():
    # We just verify files exist; we do not execute installers in tests.
    files = [
        ROOT / "frontend" / "input_record" / "install-interception.exe",
        ROOT / "versions" / "0.01" / "pyvjoy" / "vJoySetup.exe",
    ]
    missing = [str(p) for p in files if not p.exists()]
    assert not missing, "Missing installer assets: " + ", ".join(missing)

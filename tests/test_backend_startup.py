"""
Tests for backend sidecar startup and argument forwarding.

Validates that main_backend.py correctly parses CLI args and forwards
them to modelhub.tauri with the right parameter names.
"""

from unittest.mock import MagicMock, patch


class TestBackendArgParsing:
    """Test CLI argument parsing in main_backend.py."""

    def test_default_args(self):
        """Test default argument values parse without error."""
        captured_args = []

        def fake_tauri_main(argv):
            captured_args.extend(argv)
            return 0

        mock_module = MagicMock()
        mock_module.main = fake_tauri_main
        with patch.dict("sys.modules", {"modelhub": MagicMock(), "modelhub.tauri": mock_module}):
            import importlib

            import backend.main_backend

            importlib.reload(backend.main_backend)
            backend.main_backend.main([])

        # Default port is 0, default token is ""
        assert "--port" in captured_args
        assert "0" in captured_args
        assert "--resource-root" in captured_args

    def test_project_root_resolution(self, tmp_path):
        """Test project root resolution from CLI arg."""
        from pathlib import Path

        from backend.main_backend import _resolve_project_root

        test_dir = str(tmp_path / "testroot")
        result = _resolve_project_root(test_dir)
        assert result == Path(test_dir).resolve()

    def test_project_root_env_fallback(self, tmp_path):
        """Test project root resolution from environment variable."""
        import os
        from pathlib import Path

        from backend.main_backend import _resolve_project_root

        env_dir = str(tmp_path / "envroot")
        with patch.dict(os.environ, {"MODELHUB_PROJECT_ROOT": env_dir}):
            result = _resolve_project_root("")
            assert result == Path(env_dir).resolve()

    def test_project_root_auto_detection(self):
        """Test project root auto-detection from file location."""
        import os

        from backend.main_backend import _resolve_project_root

        # Clear env to test fallback
        with patch.dict(os.environ, {"MODELHUB_PROJECT_ROOT": ""}):
            result = _resolve_project_root("")
            # Should resolve to repo root (parent of backend/)
            assert result.exists()

    def test_forwards_resource_root_not_project_root(self):
        """Test that main_backend forwards --resource-root to modelhub.tauri."""
        import backend.main_backend as bm

        captured_args = []

        def fake_tauri_main(argv):
            captured_args.extend(argv)
            return 0

        with patch.object(bm, "_ensure_sys_path"):
            # Patch the import inside main
            mock_module = MagicMock()
            mock_module.main = fake_tauri_main
            with patch.dict(
                "sys.modules", {"modelhub": MagicMock(), "modelhub.tauri": mock_module}
            ):
                import importlib

                importlib.reload(bm)
                bm.main(["--port", "8080", "--token", "abc123"])

        # Verify --resource-root is passed (not --project-root)
        assert "--resource-root" in captured_args
        assert "--data-root" in captured_args
        assert "--project-root" not in captured_args
        assert "--port" in captured_args
        assert "8080" in captured_args
        assert "--token" in captured_args
        assert "abc123" in captured_args


class TestDataSavefix:
    """Test the numpy save fix for inhomogeneous training data (Issue #13/#6)."""

    def test_save_heterogeneous_training_data(self, tmp_path):
        """Verify that [screen, label] pairs with different shapes can be saved."""
        import numpy as np

        # Simulate real training data: screen (H, W, 3) + label vector (variable len)
        training_data = []
        for _ in range(10):
            screen = np.random.randint(0, 255, (270, 480, 3), dtype=np.uint8)
            label = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0])  # keyboard output
            training_data.append([screen, label])

        # This is the FIXED code from collect_data.py
        arr = np.array(training_data, dtype=object)
        path = tmp_path / "test_training.npy"
        np.save(str(path), arr, allow_pickle=True)

        # Verify load
        loaded = np.load(str(path), allow_pickle=True)
        assert loaded.shape[0] == 10
        assert loaded[0][0].shape == (270, 480, 3)
        assert len(loaded[0][1]) == 9

    def test_save_heterogeneous_with_gamepad(self, tmp_path):
        """Verify save works with keyboard+gamepad combined labels."""
        import numpy as np

        training_data = []
        for _ in range(5):
            screen = np.random.randint(0, 255, (270, 480, 3), dtype=np.uint8)
            # keyboard(9) + gamepad(20) = 29
            label = np.concatenate([np.zeros(9), np.zeros(20)])
            training_data.append([screen, label])

        arr = np.array(training_data, dtype=object)
        path = tmp_path / "test_gamepad.npy"
        np.save(str(path), arr, allow_pickle=True)

        loaded = np.load(str(path), allow_pickle=True)
        assert loaded.shape[0] == 5
        assert len(loaded[0][1]) == 29

    def test_save_heterogeneous_with_mouse(self, tmp_path):
        """Verify save works with keyboard+gamepad+mouse combined labels."""
        import numpy as np

        training_data = []
        for _ in range(5):
            screen = np.random.randint(0, 255, (270, 480, 3), dtype=np.uint8)
            # keyboard(9) + gamepad(20) + mouse(6) = 35
            label = np.concatenate([np.zeros(9), np.zeros(20), np.zeros(6)])
            training_data.append([screen, label])

        arr = np.array(training_data, dtype=object)
        path = tmp_path / "test_mouse.npy"
        np.save(str(path), arr, allow_pickle=True)

        loaded = np.load(str(path), allow_pickle=True)
        assert loaded.shape[0] == 5
        assert len(loaded[0][1]) == 35

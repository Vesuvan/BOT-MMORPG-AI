"""
Tests for optional Mouse Capture module.

Validates MouseState dataclass, MouseCapture coordinate normalization,
and thread safety — all without needing an actual display or pynput listener.
"""

import threading
import time

import numpy as np
import pytest


class TestMouseState:
    """Test MouseState dataclass and serialization."""

    def test_default_values(self):
        """Test default MouseState is all-zero."""
        from bot_mmorpg.scripts.mouse_capture import MouseState

        state = MouseState()
        assert state.x == 0.0
        assert state.y == 0.0
        assert state.lmb == 0
        assert state.rmb == 0
        assert state.mmb == 0
        assert state.scroll == 0.0

    def test_to_array_shape(self):
        """Test to_array returns correct shape and dtype."""
        from bot_mmorpg.scripts.mouse_capture import MouseState

        state = MouseState(x=0.5, y=0.25, lmb=1, rmb=0, mmb=1, scroll=-2.0)
        arr = state.to_array()

        assert arr.shape == (6,)
        assert arr.dtype == np.float32
        np.testing.assert_array_almost_equal(arr, [0.5, 0.25, 1.0, 0.0, 1.0, -2.0])

    def test_vector_size(self):
        """Test vector_size matches array length."""
        from bot_mmorpg.scripts.mouse_capture import MouseState

        assert MouseState.vector_size() == 6
        assert len(MouseState().to_array()) == MouseState.vector_size()

    def test_labels_match_vector_size(self):
        """Test labels list matches vector size."""
        from bot_mmorpg.scripts.mouse_capture import MouseState

        labels = MouseState.labels()
        assert len(labels) == MouseState.vector_size()
        assert "mouse_x" in labels
        assert "lmb" in labels

    def test_frozen_dataclass(self):
        """Test MouseState is immutable (frozen)."""
        from bot_mmorpg.scripts.mouse_capture import MouseState

        state = MouseState(x=0.5, y=0.5)
        with pytest.raises(AttributeError):
            state.x = 0.9  # type: ignore[misc]


class TestMouseCaptureNormalization:
    """Test coordinate normalization without pynput listener."""

    def test_normalize_center(self):
        """Test that center of region normalizes to (0.5, 0.5)."""
        from bot_mmorpg.scripts.mouse_capture import MouseCapture

        mc = MouseCapture(capture_region=(0, 0, 1920, 1080))

        # Simulate mouse at center
        with mc._state.lock:
            mc._state.abs_x = 960
            mc._state.abs_y = 540

        state = mc.snapshot()
        assert abs(state.x - 0.5) < 0.01
        assert abs(state.y - 0.5) < 0.01

    def test_normalize_origin(self):
        """Test that top-left of region normalizes to (0, 0)."""
        from bot_mmorpg.scripts.mouse_capture import MouseCapture

        mc = MouseCapture(capture_region=(100, 200, 1100, 1200))

        with mc._state.lock:
            mc._state.abs_x = 100
            mc._state.abs_y = 200

        state = mc.snapshot()
        assert state.x == 0.0
        assert state.y == 0.0

    def test_normalize_bottom_right(self):
        """Test that bottom-right of region normalizes to (1, 1)."""
        from bot_mmorpg.scripts.mouse_capture import MouseCapture

        mc = MouseCapture(capture_region=(0, 0, 800, 600))

        with mc._state.lock:
            mc._state.abs_x = 800
            mc._state.abs_y = 600

        state = mc.snapshot()
        assert state.x == 1.0
        assert state.y == 1.0

    def test_clamp_outside_region(self):
        """Test coordinates outside region are clamped to [0, 1]."""
        from bot_mmorpg.scripts.mouse_capture import MouseCapture

        mc = MouseCapture(capture_region=(100, 100, 500, 500))

        # Way outside left/top
        with mc._state.lock:
            mc._state.abs_x = 0
            mc._state.abs_y = 0

        state = mc.snapshot()
        assert state.x == 0.0
        assert state.y == 0.0

        # Way outside right/bottom
        with mc._state.lock:
            mc._state.abs_x = 9999
            mc._state.abs_y = 9999

        state = mc.snapshot()
        assert state.x == 1.0
        assert state.y == 1.0

    def test_custom_region(self):
        """Test normalization with offset capture region."""
        from bot_mmorpg.scripts.mouse_capture import MouseCapture

        mc = MouseCapture(capture_region=(200, 100, 1000, 700))

        with mc._state.lock:
            mc._state.abs_x = 600  # 50% of 800-wide region from 200
            mc._state.abs_y = 400  # 50% of 600-tall region from 100

        state = mc.snapshot()
        assert abs(state.x - 0.5) < 0.01
        assert abs(state.y - 0.5) < 0.01


class TestMouseCaptureButtons:
    """Test button and scroll state capture."""

    def test_button_states(self):
        """Test button states are captured correctly."""
        from bot_mmorpg.scripts.mouse_capture import MouseCapture

        mc = MouseCapture()

        with mc._state.lock:
            mc._state.lmb = 1
            mc._state.rmb = 0
            mc._state.mmb = 1

        state = mc.snapshot()
        assert state.lmb == 1
        assert state.rmb == 0
        assert state.mmb == 1

    def test_scroll_accumulation(self):
        """Test scroll delta accumulates and resets per snapshot."""
        from bot_mmorpg.scripts.mouse_capture import MouseCapture

        mc = MouseCapture()

        # Simulate scroll events
        with mc._state.lock:
            mc._state.scroll_accum = 3.0

        state1 = mc.snapshot()
        assert state1.scroll == 3.0

        # Scroll should be reset after snapshot
        state2 = mc.snapshot()
        assert state2.scroll == 0.0

    def test_negative_scroll(self):
        """Test negative scroll (scroll down)."""
        from bot_mmorpg.scripts.mouse_capture import MouseCapture

        mc = MouseCapture()

        with mc._state.lock:
            mc._state.scroll_accum = -5.0

        state = mc.snapshot()
        assert state.scroll == -5.0


class TestMouseCaptureThreadSafety:
    """Test thread safety of snapshot and state updates."""

    def test_concurrent_snapshots(self):
        """Test that concurrent snapshots don't corrupt data."""
        from bot_mmorpg.scripts.mouse_capture import MouseCapture

        mc = MouseCapture(capture_region=(0, 0, 1000, 1000))
        results = []
        errors = []

        def worker():
            try:
                for i in range(100):
                    with mc._state.lock:
                        mc._state.abs_x = i * 10
                        mc._state.abs_y = i * 10
                    state = mc.snapshot()
                    arr = state.to_array()
                    assert arr.shape == (6,)
                    assert 0.0 <= state.x <= 1.0
                    assert 0.0 <= state.y <= 1.0
                    results.append(state)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 400

    def test_snapshot_timestamp(self):
        """Test that snapshots have increasing timestamps."""
        from bot_mmorpg.scripts.mouse_capture import MouseCapture

        mc = MouseCapture()
        s1 = mc.snapshot()
        time.sleep(0.01)
        s2 = mc.snapshot()

        assert s2.timestamp > s1.timestamp


class TestMouseCaptureIntegration:
    """Test integration with existing data pipeline."""

    def test_concat_with_keyboard_gamepad(self):
        """Test that mouse vector concatenates with keyboard/gamepad vectors."""
        from bot_mmorpg.scripts.mouse_capture import MouseState

        # Simulate typical pipeline: keyboard(9) + gamepad(20) + mouse(6)
        keyboard_output = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0])
        gamepad_output = np.zeros(20, dtype=int)
        mouse_state = MouseState(x=0.5, y=0.3, lmb=1)
        mouse_output = mouse_state.to_array()

        combined = np.concatenate([keyboard_output, gamepad_output, mouse_output])

        assert combined.shape == (35,)  # 9 + 20 + 6
        assert combined[0] == 1  # W key
        assert abs(combined[29] - 0.5) < 0.01  # mouse_x
        assert abs(combined[30] - 0.3) < 0.01  # mouse_y
        assert combined[31] == 1.0  # lmb

    def test_array_save_load_roundtrip(self, tmp_path):
        """Test that mouse data survives numpy save/load."""
        from bot_mmorpg.scripts.mouse_capture import MouseState

        state = MouseState(x=0.75, y=0.25, lmb=1, rmb=0, mmb=0, scroll=2.5)
        arr = state.to_array()

        path = tmp_path / "mouse_test.npy"
        np.save(str(path), arr)
        loaded = np.load(str(path))

        np.testing.assert_array_almost_equal(arr, loaded)

"""
Mouse Capture Module for BOT-MMORPG-AI (Optional Feature)

Records mouse position and button state for training models that need
mouse input (e.g. camera control, targeting, menu navigation).

This module is OPTIONAL and not part of the core pipeline. Import it
only when mouse recording is explicitly enabled by the user.

Design goals:
- Zero impact on existing keyboard/gamepad pipeline
- Resolution-independent coordinates (normalized to [0, 1])
- Low overhead (< 1 ms per sample)
- Thread-safe for use alongside keyboard/gamepad capture

Usage:
    from bot_mmorpg.scripts.mouse_capture import MouseCapture

    mc = MouseCapture(capture_region=(0, 0, 1920, 1080))
    mc.start()
    ...
    state = mc.snapshot()   # MouseState dataclass
    ...
    mc.stop()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class MouseState:
    """Immutable snapshot of mouse state at a single point in time.

    All coordinates are normalized to [0, 1] relative to the capture region
    so the model is resolution-independent.
    """

    x: float = 0.0  # normalized x  [0, 1]
    y: float = 0.0  # normalized y  [0, 1]
    lmb: int = 0  # left mouse button  (0 or 1)
    rmb: int = 0  # right mouse button (0 or 1)
    mmb: int = 0  # middle mouse button(0 or 1)
    scroll: float = 0.0  # scroll delta since last snapshot
    timestamp: float = 0.0  # time.time() when captured

    def to_array(self) -> np.ndarray:
        """Return [x, y, lmb, rmb, mmb, scroll] as float32 array (len 6)."""
        return np.array(
            [self.x, self.y, float(self.lmb), float(self.rmb), float(self.mmb), self.scroll],
            dtype=np.float32,
        )

    @staticmethod
    def vector_size() -> int:
        """Number of elements in the output vector."""
        return 6

    @staticmethod
    def labels() -> list[str]:
        """Human-readable labels for each element."""
        return ["mouse_x", "mouse_y", "lmb", "rmb", "mmb", "scroll"]


@dataclass
class _RawMouseState:
    """Mutable internal state updated by the listener thread."""

    abs_x: int = 0
    abs_y: int = 0
    lmb: int = 0
    rmb: int = 0
    mmb: int = 0
    scroll_accum: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)


class MouseCapture:
    """Threaded mouse listener that provides low-latency snapshots.

    Parameters
    ----------
    capture_region : tuple (left, top, right, bottom)
        Pixel region used for normalization. Coordinates outside the region
        are clamped to [0, 1].
    """

    def __init__(self, capture_region: Tuple[int, int, int, int] = (0, 0, 1920, 1080)):
        self._region = capture_region
        self._width = max(1, capture_region[2] - capture_region[0])
        self._height = max(1, capture_region[3] - capture_region[1])
        self._state = _RawMouseState()
        self._listener: Optional[object] = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start capturing mouse events in a background thread."""
        if self._running:
            return

        try:
            from pynput import mouse  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "pynput is required for mouse capture. " "Install it with: pip install pynput"
            )

        def on_move(x: int, y: int) -> None:
            with self._state.lock:
                self._state.abs_x = x
                self._state.abs_y = y

        def on_click(x: int, y: int, button: mouse.Button, pressed: bool) -> None:
            val = 1 if pressed else 0
            with self._state.lock:
                self._state.abs_x = x
                self._state.abs_y = y
                if button == mouse.Button.left:
                    self._state.lmb = val
                elif button == mouse.Button.right:
                    self._state.rmb = val
                elif button == mouse.Button.middle:
                    self._state.mmb = val

        def on_scroll(x: int, y: int, dx: int, dy: int) -> None:
            with self._state.lock:
                self._state.abs_x = x
                self._state.abs_y = y
                self._state.scroll_accum += dy

        self._listener = mouse.Listener(
            on_move=on_move,
            on_click=on_click,
            on_scroll=on_scroll,
        )
        self._listener.start()
        self._running = True

    def stop(self) -> None:
        """Stop the listener thread."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def snapshot(self) -> MouseState:
        """Return an immutable snapshot of the current mouse state.

        Scroll accumulator is reset after each call so you get the delta
        since the previous snapshot (matches frame-by-frame recording).
        """
        with self._state.lock:
            raw_x = self._state.abs_x
            raw_y = self._state.abs_y
            lmb = self._state.lmb
            rmb = self._state.rmb
            mmb = self._state.mmb
            scroll = self._state.scroll_accum
            self._state.scroll_accum = 0.0

        # Normalize to [0, 1] relative to capture region
        left, top = self._region[0], self._region[1]
        norm_x = max(0.0, min(1.0, (raw_x - left) / self._width))
        norm_y = max(0.0, min(1.0, (raw_y - top) / self._height))

        return MouseState(
            x=norm_x,
            y=norm_y,
            lmb=lmb,
            rmb=rmb,
            mmb=mmb,
            scroll=scroll,
            timestamp=time.time(),
        )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __enter__(self) -> "MouseCapture":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    def __del__(self) -> None:
        self.stop()

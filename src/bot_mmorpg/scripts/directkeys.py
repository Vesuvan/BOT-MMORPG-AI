# direct inputs
# source to this solution and code:
# http://stackoverflow.com/questions/14489013/simulate-python-keypresses-for-controlling-a-game
# http://www.gamespp.com/directx/directInputKeyboardScanCodes.html
# Cross-platform support added for Linux/macOS

import ctypes
import platform
import time

# Platform detection
IS_WINDOWS = platform.system() == "Windows"

# DirectInput scan codes (used on Windows)
W = 0x11
A = 0x1E
S = 0x1F
D = 0x20

NP_2 = 0x50
NP_4 = 0x4B
NP_6 = 0x4D
NP_8 = 0x48

# Map scan codes to key names for cross-platform support
_SCANCODE_TO_KEY = {
    0x11: "w",  # W
    0x1E: "a",  # A
    0x1F: "s",  # S
    0x20: "d",  # D
    0x50: "num2",  # NP_2
    0x4B: "num4",  # NP_4
    0x4D: "num6",  # NP_6
    0x48: "num8",  # NP_8
}

if IS_WINDOWS:
    # Windows-specific implementation using DirectInput
    SendInput = ctypes.windll.user32.SendInput

    # C struct redefinitions
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class KeyBdInput(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", PUL),
        ]

    class HardwareInput(ctypes.Structure):
        _fields_ = [
            ("uMsg", ctypes.c_ulong),
            ("wParamL", ctypes.c_short),
            ("wParamH", ctypes.c_ushort),
        ]

    class MouseInput(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", PUL),
        ]

    class Input_I(ctypes.Union):
        _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]

    def PressKey(hexKeyCode):
        """Press a key using DirectInput (Windows)."""
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008, 0, ctypes.pointer(extra))
        x = Input(ctypes.c_ulong(1), ii_)
        ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

    def ReleaseKey(hexKeyCode):
        """Release a key using DirectInput (Windows)."""
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008 | 0x0002, 0, ctypes.pointer(extra))
        x = Input(ctypes.c_ulong(1), ii_)
        ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

else:
    # Cross-platform implementation using pynput (Linux/macOS)
    try:
        from pynput.keyboard import Controller, Key

        _keyboard = Controller()
        _PYNPUT_AVAILABLE = True

        # Map scan codes to pynput keys
        _SCANCODE_TO_PYNPUT = {
            0x11: "w",
            0x1E: "a",
            0x1F: "s",
            0x20: "d",
            0x50: Key.num_lock,  # Fallback for numpad
            0x4B: Key.num_lock,
            0x4D: Key.num_lock,
            0x48: Key.num_lock,
        }

        def PressKey(hexKeyCode):
            """Press a key using pynput (cross-platform)."""
            key = _SCANCODE_TO_PYNPUT.get(hexKeyCode, None)
            if key is None:
                key = _SCANCODE_TO_KEY.get(hexKeyCode, "a")
            if isinstance(key, str):
                _keyboard.press(key)
            else:
                _keyboard.press(key)

        def ReleaseKey(hexKeyCode):
            """Release a key using pynput (cross-platform)."""
            key = _SCANCODE_TO_PYNPUT.get(hexKeyCode, None)
            if key is None:
                key = _SCANCODE_TO_KEY.get(hexKeyCode, "a")
            if isinstance(key, str):
                _keyboard.release(key)
            else:
                _keyboard.release(key)

    except ImportError:
        _PYNPUT_AVAILABLE = False

        def PressKey(hexKeyCode):
            """Stub: pynput not available."""
            print(f"[directkeys] PressKey({hex(hexKeyCode)}) - pynput not installed, skipping")

        def ReleaseKey(hexKeyCode):
            """Stub: pynput not available."""
            print(f"[directkeys] ReleaseKey({hex(hexKeyCode)}) - pynput not installed, skipping")


if __name__ == "__main__":
    print(f"Platform: {platform.system()}")
    print(f"Windows mode: {IS_WINDOWS}")
    print("Testing key press/release in 3 seconds...")
    time.sleep(3)
    PressKey(W)
    time.sleep(1)
    ReleaseKey(W)
    time.sleep(1)
    print("Done!")

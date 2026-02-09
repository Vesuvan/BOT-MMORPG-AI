# Citation: Box Of Hats (https://github.com/Box-Of-Hats)
# Cross-platform support added for Linux/macOS

import time
import platform

# Platform detection
IS_WINDOWS = platform.system() == "Windows"

# Key list to monitor
keyList = ["\b"]
for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ 123456789,.'$/\\":
    keyList.append(char)

if IS_WINDOWS:
    # Windows-specific implementation using win32api
    try:
        import win32api as wapi

        _WIN32_AVAILABLE = True

        def key_check():
            """Check which keys are currently pressed (Windows)."""
            keys = []
            for key in keyList:
                if wapi.GetAsyncKeyState(ord(key)):
                    keys.append(key)
            return keys

    except ImportError:
        _WIN32_AVAILABLE = False
        # Fallback defined below

else:
    _WIN32_AVAILABLE = False

# Cross-platform implementation using pynput (Linux/macOS or Windows fallback)
if not IS_WINDOWS or not _WIN32_AVAILABLE:
    try:
        from pynput import keyboard

        _PYNPUT_AVAILABLE = True

        # Track currently pressed keys
        _pressed_keys = set()

        def _on_press(key):
            try:
                _pressed_keys.add(key.char.upper())
            except AttributeError:
                # Special keys (shift, ctrl, etc.)
                pass

        def _on_release(key):
            try:
                _pressed_keys.discard(key.char.upper())
            except AttributeError:
                pass

        # Start listener in non-blocking mode
        _listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
        _listener.start()

        def key_check():
            """Check which keys are currently pressed (cross-platform)."""
            keys = []
            for key in keyList:
                if key.upper() in _pressed_keys:
                    keys.append(key)
            return keys

    except ImportError:
        _PYNPUT_AVAILABLE = False

        def key_check():
            """Stub: no keyboard library available."""
            return []


if __name__ == "__main__":
    print(f"Platform: {platform.system()}")
    print(f"Windows mode: {IS_WINDOWS}")
    print("Press keys to see them detected (Ctrl+C to exit)...")
    try:
        while True:
            keys = key_check()
            if keys:
                print(f"Keys: {keys}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nDone!")

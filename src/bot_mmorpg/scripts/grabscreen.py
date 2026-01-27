# Done by Frannecklp
# Cross-platform support added for Linux/macOS

import cv2
import numpy as np
import platform

# Platform detection for cross-platform support
IS_WINDOWS = platform.system() == 'Windows'

if IS_WINDOWS:
    try:
        import win32gui, win32ui, win32con, win32api
        _WIN32_AVAILABLE = True
    except ImportError:
        _WIN32_AVAILABLE = False
else:
    _WIN32_AVAILABLE = False

# Cross-platform fallback using mss (works on all platforms)
try:
    import mss
    _MSS_AVAILABLE = True
except ImportError:
    _MSS_AVAILABLE = False


def _grab_screen_win32(region=None):
    """Windows-specific screen capture using Win32 API (original implementation)."""
    hwin = win32gui.GetDesktopWindow()

    if region:
        left, top, x2, y2 = region
        width = x2 - left + 1
        height = y2 - top + 1
    else:
        width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

    hwindc = win32gui.GetWindowDC(hwin)
    srcdc = win32ui.CreateDCFromHandle(hwindc)
    memdc = srcdc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(srcdc, width, height)
    memdc.SelectObject(bmp)
    memdc.BitBlt((0, 0), (width, height), srcdc, (left, top), win32con.SRCCOPY)

    signedIntsArray = bmp.GetBitmapBits(True)
    # Fix: Use np.frombuffer instead of deprecated np.fromstring
    img = np.frombuffer(signedIntsArray, dtype='uint8')
    img.shape = (height, width, 4)

    srcdc.DeleteDC()
    memdc.DeleteDC()
    win32gui.ReleaseDC(hwin, hwindc)
    win32gui.DeleteObject(bmp.GetHandle())

    return cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)


def _grab_screen_mss(region=None):
    """Cross-platform screen capture using mss library."""
    with mss.mss() as sct:
        if region:
            left, top, x2, y2 = region
            monitor = {
                "left": left,
                "top": top,
                "width": x2 - left + 1,
                "height": y2 - top + 1
            }
        else:
            # Capture full screen (primary monitor)
            monitor = sct.monitors[1]

        screenshot = sct.grab(monitor)
        # Convert to numpy array
        img = np.array(screenshot)
        # mss returns BGRA, convert to RGB
        return cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)


def grab_screen(region=None):
    """
    Capture a region of the screen.

    Args:
        region: Optional tuple (left, top, right, bottom) defining the capture area.
                If None, captures the entire screen.

    Returns:
        numpy.ndarray: RGB image array of the captured screen region.

    Cross-platform support:
        - Windows: Uses Win32 API (fast, original implementation)
        - Linux/macOS: Uses mss library (requires: pip install mss)
    """
    # Prefer Win32 on Windows for best performance
    if IS_WINDOWS and _WIN32_AVAILABLE:
        return _grab_screen_win32(region)

    # Fallback to mss (cross-platform)
    if _MSS_AVAILABLE:
        return _grab_screen_mss(region)

    # No screen capture available
    raise RuntimeError(
        "No screen capture method available. "
        "On Windows, install pywin32: pip install pywin32. "
        "On Linux/macOS, install mss: pip install mss"
    )

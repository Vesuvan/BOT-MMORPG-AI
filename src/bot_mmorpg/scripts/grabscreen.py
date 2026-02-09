# Done by Frannecklp
# Cross-platform support added for Linux/macOS

import cv2
import numpy as np
import platform
import base64
from io import BytesIO

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


def list_monitors():
    """
    List all available monitors/screens.

    Returns:
        list: List of monitor dictionaries with id, name, and dimensions.
              Example: [{"id": 0, "name": "Primary (1920x1080)", "width": 1920, "height": 1080, "left": 0, "top": 0}]
    """
    monitors = []

    if _MSS_AVAILABLE:
        with mss.mss() as sct:
            # Skip monitor 0 (it's the combined virtual screen on Windows)
            for i, mon in enumerate(sct.monitors[1:], start=1):
                monitors.append({
                    "id": i,
                    "name": f"Monitor {i} ({mon['width']}x{mon['height']})",
                    "width": mon['width'],
                    "height": mon['height'],
                    "left": mon['left'],
                    "top": mon['top']
                })
    elif IS_WINDOWS and _WIN32_AVAILABLE:
        # Fallback: just report primary monitor
        width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        monitors.append({
            "id": 1,
            "name": f"Primary ({width}x{height})",
            "width": width,
            "height": height,
            "left": 0,
            "top": 0
        })
    else:
        # Default fallback
        monitors.append({
            "id": 1,
            "name": "Primary (Unknown)",
            "width": 1920,
            "height": 1080,
            "left": 0,
            "top": 0
        })

    return monitors


def grab_screen_monitor(monitor_id=1):
    """
    Capture a specific monitor by ID.

    Args:
        monitor_id: Monitor ID (1-based, from list_monitors())

    Returns:
        numpy.ndarray: RGB image array of the captured monitor.
    """
    if _MSS_AVAILABLE:
        with mss.mss() as sct:
            if monitor_id < 1 or monitor_id >= len(sct.monitors):
                monitor_id = 1  # Default to primary
            monitor = sct.monitors[monitor_id]
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)

    # Fallback to full screen
    return grab_screen()


def grab_screen_thumbnail(monitor_id=1, max_width=320, max_height=180):
    """
    Capture a monitor and return a thumbnail-sized image.
    Useful for preview displays.

    Args:
        monitor_id: Monitor ID to capture
        max_width: Maximum thumbnail width
        max_height: Maximum thumbnail height

    Returns:
        numpy.ndarray: Resized RGB image array
    """
    img = grab_screen_monitor(monitor_id)
    h, w = img.shape[:2]

    # Calculate scale to fit within max dimensions
    scale = min(max_width / w, max_height / h)
    new_w = int(w * scale)
    new_h = int(h * scale)

    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def grab_screen_base64(monitor_id=1, max_width=640, max_height=360, quality=70):
    """
    Capture a monitor and return as base64 JPEG string.
    Perfect for sending to web UI.

    Args:
        monitor_id: Monitor ID to capture
        max_width: Maximum image width
        max_height: Maximum image height
        quality: JPEG quality (1-100)

    Returns:
        str: Base64-encoded JPEG image data
    """
    img = grab_screen_thumbnail(monitor_id, max_width, max_height)
    # Convert RGB to BGR for OpenCV encoding
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    # Encode as JPEG
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, buffer = cv2.imencode('.jpg', img_bgr, encode_param)
    # Convert to base64
    return base64.b64encode(buffer).decode('utf-8')


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

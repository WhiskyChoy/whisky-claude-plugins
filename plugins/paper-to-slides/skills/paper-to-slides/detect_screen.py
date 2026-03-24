#!/usr/bin/env python3
"""
detect_screen.py - Detect primary screen resolution and DPI scale factor.

Cross-platform script that identifies the PRIMARY monitor and reports:
  - Native resolution (physical pixels)
  - Scale factor (DPI scaling ratio, e.g., 1.0, 1.25, 1.5, 2.0)
  - Effective resolution (native / scale)
  - Whether the display qualifies as HiDPI/4K

Output is JSON for easy consumption by other tools.

Usage:
    python detect_screen.py
    python detect_screen.py --format text
"""

import json
import platform
import subprocess
import sys


def detect_windows():
    """Detect screen info on Windows using ctypes."""
    import ctypes
    from ctypes import wintypes

    # Constants
    MONITOR_DEFAULTTOPRIMARY = 1
    MDT_EFFECTIVE_DPI = 0

    user32 = ctypes.windll.user32
    shcore = None
    try:
        shcore = ctypes.windll.shcore
    except OSError:
        pass

    # Enable DPI awareness to get real resolution (not virtualized)
    try:
        # Windows 10 1607+
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        try:
            # Windows 8.1+
            if shcore:
                shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except (AttributeError, OSError):
            try:
                user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass

    # Get primary monitor resolution (physical pixels)
    native_width = user32.GetSystemMetrics(0)   # SM_CXSCREEN
    native_height = user32.GetSystemMetrics(1)  # SM_CYSCREEN

    # Get DPI of the primary monitor
    scale_factor = 1.0
    try:
        if shcore:
            # Get primary monitor handle
            point = ctypes.wintypes.POINT(0, 0)
            monitor = user32.MonitorFromPoint(point, MONITOR_DEFAULTTOPRIMARY)
            dpi_x = ctypes.c_uint()
            dpi_y = ctypes.c_uint()
            shcore.GetDpiForMonitor(monitor, MDT_EFFECTIVE_DPI,
                                   ctypes.byref(dpi_x), ctypes.byref(dpi_y))
            scale_factor = dpi_x.value / 96.0
    except (AttributeError, OSError):
        # Fallback: use DC-based DPI
        try:
            hdc = user32.GetDC(0)
            gdi32 = ctypes.windll.gdi32
            dpi = gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            user32.ReleaseDC(0, hdc)
            scale_factor = dpi / 96.0
        except (AttributeError, OSError):
            scale_factor = 1.0

    return native_width, native_height, scale_factor


def detect_macos():
    """Detect screen info on macOS using system_profiler."""
    try:
        result = subprocess.run(
            ['system_profiler', 'SPDisplaysDataType', '-json'],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        displays = data.get('SPDisplaysDataType', [])

        for gpu in displays:
            for display in gpu.get('spdisplays_ndrvs', []):
                # Look for the main display
                is_main = display.get('spdisplays_main', 'spdisplays_not_main')
                if is_main == 'spdisplays_yes' or is_main == 'spdisplays_main':
                    res_str = display.get('_spdisplays_resolution', '')
                    # Parse "3840 x 2160" or similar
                    parts = res_str.replace(' ', '').split('x')
                    if len(parts) == 2:
                        width = int(parts[0])
                        height = int(parts[1])
                    else:
                        width, height = 1920, 1080

                    # Retina displays have scale factor 2
                    is_retina = 'spdisplays_retina' in display.get('spdisplays_pixelresolution', '')
                    scale = 2.0 if is_retina else 1.0

                    return width, height, scale

    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass

    # Fallback
    return 1920, 1080, 1.0


def detect_linux():
    """Detect screen info on Linux using xrandr or wayland tools."""
    # Try xrandr first (X11)
    try:
        result = subprocess.run(
            ['xrandr', '--current'],
            capture_output=True, text=True, timeout=10
        )
        import re
        # Find primary monitor line
        for line in result.stdout.splitlines():
            if 'primary' in line.lower():
                match = re.search(r'(\d+)x(\d+)', line)
                if match:
                    width = int(match.group(1))
                    height = int(match.group(2))

                    # Try to detect scale from xrdb or GDK_SCALE
                    import os
                    scale = float(os.environ.get('GDK_SCALE', '1'))
                    return width, height, scale

        # No primary found, use first connected display
        for line in result.stdout.splitlines():
            if ' connected' in line:
                match = re.search(r'(\d+)x(\d+)', line)
                if match:
                    return int(match.group(1)), int(match.group(2)), 1.0

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Try wlr-randr (Wayland)
    try:
        result = subprocess.run(
            ['wlr-randr'],
            capture_output=True, text=True, timeout=10
        )
        import re
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            match = re.search(r'(\d+)x(\d+)', line)
            if match:
                width = int(match.group(1))
                height = int(match.group(2))
                # Check for scale on next lines
                scale = 1.0
                for j in range(i + 1, min(i + 5, len(lines))):
                    scale_match = re.search(r'scale:\s*([\d.]+)', lines[j])
                    if scale_match:
                        scale = float(scale_match.group(1))
                        break
                return width, height, scale

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return 1920, 1080, 1.0


def main():
    output_format = 'json'
    if len(sys.argv) > 1 and sys.argv[1] == '--format' and len(sys.argv) > 2:
        output_format = sys.argv[2]

    system = platform.system()

    if system == 'Windows':
        native_w, native_h, scale = detect_windows()
    elif system == 'Darwin':
        native_w, native_h, scale = detect_macos()
    elif system == 'Linux':
        native_w, native_h, scale = detect_linux()
    else:
        native_w, native_h, scale = 1920, 1080, 1.0

    effective_w = int(native_w / scale)
    effective_h = int(native_h / scale)
    is_hidpi = native_w >= 2560 or scale >= 1.5

    info = {
        'platform': system,
        'primary_monitor': {
            'native_width': native_w,
            'native_height': native_h,
            'scale_factor': round(scale, 2),
            'effective_width': effective_w,
            'effective_height': effective_h,
        },
        'is_hidpi': is_hidpi,
        'css_recommendation': 'boost' if is_hidpi else 'default',
    }

    if output_format == 'text':
        print(f"Platform:           {system}")
        print(f"Native resolution:  {native_w}x{native_h}")
        print(f"Scale factor:       {scale:.2f}x")
        print(f"Effective res:      {effective_w}x{effective_h}")
        print(f"HiDPI:              {'Yes' if is_hidpi else 'No'}")
        print(f"CSS recommendation: {'Boost font sizes (+50%)' if is_hidpi else 'Use defaults'}")
    else:
        print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()

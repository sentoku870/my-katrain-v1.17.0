# katrain/common/platform.py
"""Platform detection utilities (Kivy-independent).

This module provides platform detection without Kivy dependency,
using sys.platform for cross-platform compatibility.

Usage:
    from katrain.common.platform import get_platform

    if get_platform() == "win":
        # Windows-specific code
    elif get_platform() == "linux":
        # Linux-specific code
    else:
        # macOS or other
"""
import sys


def get_platform() -> str:
    """Return platform string compatible with Kivy's platform values.

    Returns:
        "win" for Windows
        "linux" for Linux
        "macosx" for macOS
        "unknown" for other platforms
    """
    if sys.platform == "win32":
        return "win"
    elif sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform == "darwin":
        return "macosx"
    else:
        return "unknown"

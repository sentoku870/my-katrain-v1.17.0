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
from pathlib import Path


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


def resolve_output_directory(config_dir: str) -> Path:
    """Resolve the output directory for reports/diagnostics.

    Resolution order:
    1. Explicit ``config_dir`` if it exists and is a directory.
    2. Platform Downloads folder (``~/Downloads`` on Linux, ``CSIDL_DOWNLOADS`` on Windows).
    3. If the chosen folder does not exist (e.g. WSL or minimal Linux), create it.
    4. Fallback to the user's home directory, creating a ``katrain_reports`` subdir.
    5. Last resort: current working directory.
    """
    if config_dir:
        path = Path(config_dir).expanduser()
        if path.exists() and path.is_dir():
            return path

    if sys.platform == "win32":
        try:
            import ctypes.wintypes

            CSIDL_DOWNLOADS = 0x000D
            SHGFP_TYPE_CURRENT = 0
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DOWNLOADS, None, SHGFP_TYPE_CURRENT, buf)
            candidate = Path(buf.value)
        except Exception:
            candidate = Path.home() / "Downloads"
    else:
        candidate = Path.home() / "Downloads"

    try:
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        pass

    home_fallback = Path.home() / "katrain_reports"
    try:
        home_fallback.mkdir(parents=True, exist_ok=True)
        return home_fallback
    except OSError:
        return Path.cwd()

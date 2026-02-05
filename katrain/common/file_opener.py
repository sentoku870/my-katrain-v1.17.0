"""Cross-platform file/folder opener (Kivy-independent).

Phase 26: Report Navigation UX Improvements.

Note: Contains Windows-specific code paths (os.startfile). On Linux CI,
mypy cannot resolve Windows API calls, but these are guarded by platform
checks and only execute on Windows.
"""

# mypy: ignore-errors
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from katrain.common.platform import get_platform


def _get_logger() -> logging.Logger:
    """Get module logger (lazy to avoid side effect at import time)."""
    return logging.getLogger(__name__)


@dataclass
class OpenResult:
    """Result of file/folder open operation."""

    success: bool
    error_message: str | None = None  # Internal error code (for debugging)
    error_detail: str | None = None  # Detailed message (for logging/UI)


def open_folder(path: Path) -> OpenResult:
    """Open a folder in the system file manager.

    Platform behavior:
    - Windows: os.startfile(path)
    - macOS: open <path>
    - Linux: xdg-open <path>
    """
    if not path.exists():
        return OpenResult(False, "path-not-exist", f"Path does not exist: {path}")
    if not path.is_dir():
        return OpenResult(False, "not-a-folder", f"Not a folder: {path}")

    platform = get_platform()
    try:
        if platform == "win":
            os.startfile(str(path))  # Windows only, safest option
        elif platform == "macosx":
            subprocess.run(["open", str(path)], check=True)
        else:  # linux, unknown
            subprocess.run(["xdg-open", str(path)], check=True)
        return OpenResult(True)
    except FileNotFoundError as e:
        return OpenResult(False, "command-not-found", str(e))
    except Exception as e:
        _get_logger().debug(f"open_folder failed: {e}")
        return OpenResult(False, "open-failed", str(e))


def open_file(path: Path) -> OpenResult:
    """Open a file with the default application.

    Platform behavior:
    - Windows: os.startfile(path)
    - macOS: open <path>
    - Linux: xdg-open <path>
    """
    if not path.exists():
        return OpenResult(False, "path-not-exist", f"Path does not exist: {path}")
    if not path.is_file():
        return OpenResult(False, "not-a-file", f"Not a file: {path}")

    platform = get_platform()
    try:
        if platform == "win":
            os.startfile(str(path))
        elif platform == "macosx":
            subprocess.run(["open", str(path)], check=True)
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
        return OpenResult(True)
    except FileNotFoundError as e:
        return OpenResult(False, "command-not-found", str(e))
    except Exception as e:
        _get_logger().debug(f"open_file failed: {e}")
        return OpenResult(False, "open-failed", str(e))


def open_file_in_folder(path: Path) -> OpenResult:
    """Open folder with the file selected.

    Platform behavior:
    - Windows: explorer /select, <path> (separate args for shell=False)
    - macOS: open -R <path>
    - Linux: xdg-open <parent> (selection not supported)
    """
    if not path.exists():
        return OpenResult(False, "path-not-exist", f"Path does not exist: {path}")

    platform = get_platform()
    try:
        if platform == "win":
            # shell=False with separate args handles spaces and Japanese paths safely
            subprocess.run(["explorer", "/select,", str(path)], check=False)
        elif platform == "macosx":
            subprocess.run(["open", "-R", str(path)], check=True)
        else:
            # Linux: selection not supported, open parent folder
            subprocess.run(["xdg-open", str(path.parent)], check=True)
        return OpenResult(True)
    except FileNotFoundError as e:
        return OpenResult(False, "command-not-found", str(e))
    except Exception as e:
        _get_logger().debug(f"open_file_in_folder failed: {e}")
        return OpenResult(False, "open-failed", str(e))

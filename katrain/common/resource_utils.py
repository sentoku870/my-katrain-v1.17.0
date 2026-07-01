"""Pure utility for locating package resources (Kivy-independent, Phase 163).

Moved from ``katrain.core.utils`` so that ``common/`` does not need to
import from ``core/``. The function is a simple wrapper around
``importlib.resources`` with no Kivy, GUI, or engine dependencies.
"""
from __future__ import annotations

import sys
from importlib import resources as pkg_resources
from pathlib import Path

_PATHS: dict[str, str] = {}


def get_package_path() -> str:
    """Return the absolute path to the installed ``katrain`` package directory.

    Returns:
        The package directory as an absolute string. If the package is not
        installed (e.g. in unusual deployment scenarios), returns the
        sentinel ``"FILENOTFOUND"`` and logs to stderr.
    """
    if not _PATHS.get("PACKAGE"):
        try:
            files_ref = pkg_resources.files("katrain")
            if hasattr(files_ref, "absolute"):
                _PATHS["PACKAGE"] = str(files_ref.absolute())
            else:
                _PATHS["PACKAGE"] = str(files_ref)
        except (ModuleNotFoundError, FileNotFoundError, ValueError) as e:
            print(f"Package path not found, installation possibly broken. Error: {e}", file=sys.stderr)
            _PATHS["PACKAGE"] = "FILENOTFOUND"
    return _PATHS["PACKAGE"]


def find_package_resource(path: str, silent_errors: bool = False) -> str:
    """Locate a resource bundled with the package.

    Args:
        path: A package-relative path starting with "katrain" (e.g.
            "katrain/config.json"), or an absolute/expanded user path.
        silent_errors: If True, suppress stderr output on lookup failure.

    Returns:
        Absolute filesystem path to the resource, or
        ``"FILENOTFOUND/{path}"`` if the package directory cannot be
        located (e.g. when the package is not properly installed).
    """
    if path.startswith("katrain"):
        package_path = get_package_path()
        if package_path == "FILENOTFOUND":
            return f"FILENOTFOUND/{path}"
        return str(Path(package_path) / path.replace("katrain\\", "katrain/").replace("katrain/", ""))
    return str(Path(path).expanduser().absolute())


__all__ = ["find_package_resource", "get_package_path"]

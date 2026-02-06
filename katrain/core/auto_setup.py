"""Auto setup module for Phase 89 - "Just Make It Work" mode.

This module provides automatic configuration for first-time users:
- Detects new vs existing users
- Selects lightweight model (b10c128) for auto mode
- Provides CPU fallback when OpenCL fails
- Manages auto_setup config section migration
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
from typing import TYPE_CHECKING, Any

from katrain.common.platform import get_platform
from katrain.core.constants import DATA_FOLDER
from katrain.core.utils import find_package_resource

from katrain.core.analysis_result import (
    EngineTestResult,
    ErrorCategory,
    run_engine_test,
    should_offer_cpu_fallback,
)

# =============================================================================
# Constants
# =============================================================================

# Default auto_setup config for new users
DEFAULT_AUTO_SETUP: dict[str, Any] = {
    "mode": "auto",  # New users start in auto mode
    "first_run_completed": False,
    "last_test_result": None,  # "success" | "failed" | None
}

# Default mode for existing users during migration
MIGRATED_DEFAULT_MODE: str = "standard"

# =============================================================================
# Package Defaults (for comparison)
# =============================================================================

# Cache for packaged config.json
_PACKAGED_DEFAULTS: dict[str, Any] | None = None


def _get_packaged_defaults() -> dict[str, Any]:
    """Get packaged config.json defaults (cached).

    Returns:
        The full packaged config dictionary.
    """
    global _PACKAGED_DEFAULTS
    if _PACKAGED_DEFAULTS is None:
        package_config = find_package_resource("katrain/config.json")
        with open(package_config, encoding="utf-8") as f:
            _PACKAGED_DEFAULTS = json.load(f)
    return _PACKAGED_DEFAULTS


def get_packaged_engine_defaults() -> dict[str, Any]:
    """Get packaged engine section defaults.

    Returns:
        The engine section from packaged config.
    """
    defaults = _get_packaged_defaults()
    engine = defaults.get("engine", {})
    return dict(engine) if engine else {}


# =============================================================================
# Auto Setup Config Management
# =============================================================================


def get_auto_setup_config(user_config: dict[str, Any], is_new_user: bool) -> dict[str, Any]:
    """Get auto_setup config section.

    Args:
        user_config: User config file contents only (before merge with package defaults).
                     Empty dict if file doesn't exist.
        is_new_user: True if USER_CONFIG_FILE didn't exist.

    Returns:
        auto_setup config dict with defaults filled in.

    Migration logic:
        1. Existing auto_setup section -> use as-is
        2. is_new_user=True -> mode="auto" (new user)
        3. Custom engine settings -> mode="advanced"
        4. No custom settings -> mode="standard"
    """
    # Existing auto_setup section - use it
    if "auto_setup" in user_config:
        return {**DEFAULT_AUTO_SETUP, **user_config["auto_setup"]}

    # New user - use auto mode
    if is_new_user:
        return {**DEFAULT_AUTO_SETUP}  # mode="auto"

    # Existing user migration
    user_engine = user_config.get("engine", {})
    has_custom_engine = _has_custom_engine_settings(user_engine)

    migrated = {**DEFAULT_AUTO_SETUP, "mode": MIGRATED_DEFAULT_MODE}
    if has_custom_engine:
        migrated["mode"] = "advanced"
    return migrated


def _has_custom_engine_settings(user_engine: dict[str, Any]) -> bool:
    """Check if user has custom engine settings.

    Compares against packaged defaults. Empty strings mean "use default".

    Args:
        user_engine: User's engine config section.

    Returns:
        True if user has customized engine settings.
    """
    packaged = get_packaged_engine_defaults()

    # katago path is set (non-empty) and different from package
    user_katago = user_engine.get("katago", "")
    if user_katago and user_katago != packaged.get("katago", ""):
        return True

    # model is different from package default
    user_model = user_engine.get("model", "")
    packaged_model = packaged.get("model", "")
    if user_model and user_model != packaged_model:
        return True

    # config is different from package default
    user_config_path = user_engine.get("config", "")
    packaged_config = packaged.get("config", "")
    return bool(user_config_path and user_config_path != packaged_config)


def should_show_auto_tab_first(auto_setup: dict[str, Any]) -> bool:
    """Determine if Auto Setup tab should be shown first in settings.

    Conditions (both must be true):
        1. mode == "auto"
        2. first_run_completed == False

    This ensures:
        - New users see Auto tab first
        - After first test attempt, normal tab order resumes
        - Users with standard/advanced mode see normal order

    Args:
        auto_setup: auto_setup config section.

    Returns:
        True if Auto Setup tab should be shown first.
    """
    return auto_setup.get("mode") == "auto" and auto_setup.get("first_run_completed", False) is False


# =============================================================================
# Model Search
# =============================================================================


def get_model_search_dirs() -> list[str]:
    """Get model search directories in priority order.

    Search order:
        1. User directory (DATA_FOLDER/models/) - writable
        2. Package directory (katrain/models/) - may be read-only

    Note:
        DATA_FOLDER is defined in constants.py (currently "~/.katrain").
        May change to appdirs in the future - never hardcode paths.

    Returns:
        List of existing directories in priority order.
    """
    dirs = []

    # 1. User directory (priority)
    user_models_dir = os.path.expanduser(os.path.join(DATA_FOLDER, "models"))
    if os.path.isdir(user_models_dir):
        dirs.append(user_models_dir)
    else:
        # Try to create if it doesn't exist
        try:
            os.makedirs(user_models_dir, exist_ok=True)
            dirs.append(user_models_dir)
        except OSError:
            pass  # Skip if creation fails

    # 2. Package directory (fallback)
    package_models_dir = find_package_resource("katrain/models")
    if os.path.isdir(package_models_dir):
        dirs.append(package_models_dir)

    return dirs


def find_lightweight_model() -> str | None:
    """Find a lightweight model (b10c128) for auto mode.

    Search order (from get_model_search_dirs()):
        1. User directory (DATA_FOLDER/models/)
        2. Package directory (katrain/models/)

    Selection criteria (if multiple found in same directory):
        1. Filename timestamp (YYYYMMDD format) - newest first
        2. File mtime if no timestamp - newest first

    Returns:
        Full path to the model, or None if not found.
    """
    for models_dir in get_model_search_dirs():
        pattern = os.path.join(models_dir, "*b10c128*.bin.gz")
        candidates = glob.glob(pattern)

        if not candidates:
            continue

        def extract_timestamp(path: str) -> tuple[int, float]:
            basename = os.path.basename(path)
            match = re.search(r"(\d{8})", basename)
            name_ts = int(match.group(1)) if match else 0
            mtime = os.path.getmtime(path)
            return (name_ts, mtime)

        candidates.sort(key=extract_timestamp, reverse=True)
        return candidates[0]

    return None


# =============================================================================
# CPU Fallback
# =============================================================================


def find_cpu_katago() -> str | None:
    """Find CPU (Eigen) KataGo binary for fallback.

    Search order (OS-specific):
        - Windows: katago-eigen.exe, katago-cpu.exe, katago.exe
        - Linux: katago-eigen, katago-cpu, katago
        - macOS: katago-eigen, katago-cpu, katago (Homebrew)

    Returns:
        Path to CPU binary, or None if not found.
    """
    plat = get_platform()

    # Candidate patterns (priority order)
    if plat == "win":
        candidates = [
            "katrain/KataGo/katago-eigen.exe",
            "katrain/KataGo/katago-cpu.exe",
            "katrain/KataGo/katago.exe",  # Default might be CPU
        ]
    elif plat == "linux":
        candidates = [
            "katrain/KataGo/katago-eigen",
            "katrain/KataGo/katago-cpu",
            "katrain/KataGo/katago",
        ]
    else:  # macOS
        candidates = [
            "katrain/KataGo/katago-eigen",
            "katrain/KataGo/katago-cpu",
            "katago",  # Homebrew
        ]

    for candidate in candidates:
        path: str | None
        if candidate.startswith("katrain"):
            path = find_package_resource(candidate)
        else:
            # Search in PATH
            path = shutil.which(candidate)

        if path and os.path.isfile(path):
            # Skip if likely OpenCL binary (filename-based heuristic)
            if not _is_likely_opencl_binary(path):
                return path

    return None


def _is_likely_opencl_binary(path: str) -> bool:
    """Check if path is likely an OpenCL binary (best-effort heuristic).

    Note:
        This is filename-based and not definitive.
        Real verification requires running the binary.

    Args:
        path: Path to check.

    Returns:
        True if filename suggests OpenCL/CUDA/TensorRT.
    """
    basename = os.path.basename(path).lower()
    return "opencl" in basename or "cuda" in basename or "tensorrt" in basename


# =============================================================================
# Auto Engine Settings
# =============================================================================


def resolve_auto_engine_settings(
    base_engine: dict[str, Any],
) -> tuple[dict[str, Any] | None, EngineTestResult | None]:
    """Build engine settings for auto mode.

    Note:
        - Does not take models_dir parameter (find_lightweight_model() manages search paths)
        - Errors returned as EngineTestResult (uses ErrorCategory.LIGHTWEIGHT_MISSING)

    Args:
        base_engine: Base engine config to extend.

    Returns:
        (engine_settings, error_result)
        - Success: (settings, None)
        - Lightweight model missing: (None, EngineTestResult(category=LIGHTWEIGHT_MISSING))
    """

    lightweight_model = find_lightweight_model()

    if lightweight_model is None:
        return None, EngineTestResult(
            success=False,
            error_category=ErrorCategory.LIGHTWEIGHT_MISSING,
            error_message="Lightweight model (b10c128) not found",
        )

    return {
        **base_engine,
        "model": lightweight_model,
        "max_visits": 100,
        "fast_visits": 10,
    }, None


# =============================================================================
# Reset to Auto Mode (Phase 90)
# =============================================================================


def prepare_reset_to_auto() -> dict[str, dict[str, Any]]:
    """Prepare config changes for reset to auto mode.

    Returns:
        Dict of config changes to apply.
        Does NOT apply changes (caller responsibility).

    Usage:
        changes = prepare_reset_to_auto()
        ctx.set_config_section("auto_setup", changes["auto_setup"])
        ctx.save_config("auto_setup")
    """
    return {
        "auto_setup": {
            **DEFAULT_AUTO_SETUP,
            "mode": "auto",
            "first_run_completed": False,
        }
    }

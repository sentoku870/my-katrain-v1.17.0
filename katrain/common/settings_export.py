# katrain/common/settings_export.py
"""Settings Export/Import/Reset utilities (Kivy-independent).

This module provides:
- Export settings to JSON (excluding sensitive/environment-specific data)
- Parse and validate imported settings
- Get package defaults for reset functionality
- Atomic file save for import operations
- Tab-to-keys mapping for per-tab reset

Usage:
    from katrain.common.settings_export import (
        export_settings,
        parse_exported_settings,
        get_default_value,
        atomic_save_config,
        TAB_RESET_KEYS,
    )
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple, cast

SCHEMA_VERSION = "1.0"

# --- Export exclusion settings ---
# These sections contain sensitive or environment-specific data
EXCLUDED_SECTIONS: Set[str] = {"engine", "export_settings", "ui_state"}

# Keys within sections to exclude (e.g., version, language, paths)
EXCLUDED_KEYS: Dict[str, Set[str]] = {
    "general": {"version", "lang", "sgf_load", "sgf_save"},
}

# --- Tab-to-keys mapping for per-tab reset ---
# NOTE: This mapping must be kept in sync with UI tab contents.
# When adding/modifying UI tabs, update this mapping accordingly.
#
# Reset criteria:
# - Only include user-configurable settings from UI
# - Exclude app version, language settings
# - Engine paths are excluded via EXCLUDED_SECTIONS
TAB_RESET_KEYS: Dict[str, List[Tuple[str, str]]] = {
    # Analysis tab: analysis-related presets
    "analysis": [
        ("engine", "analysis_engine"),  # Phase 34
        ("general", "skill_preset"),
        ("general", "pv_filter_level"),
    ],
    # Export tab: karte output settings
    "export": [
        ("mykatrain_settings", "default_user_name"),
        ("mykatrain_settings", "karte_output_directory"),
        ("mykatrain_settings", "batch_export_input_directory"),
        ("mykatrain_settings", "karte_format"),
        ("mykatrain_settings", "opponent_info_mode"),
    ],
    # Leela tab: Leela Zero integration settings
    "leela": [
        ("leela", "enabled"),
        ("leela", "exe_path"),  # Path, but user-configurable via UI
        ("leela", "loss_scale_k"),
        ("leela", "max_visits"),
        ("leela", "top_moves_show"),
        ("leela", "top_moves_show_secondary"),
    ],
}


def _ensure_json_safe(obj: Any) -> Any:
    """Convert value to JSON-safe type (non-serializable types become None).

    Args:
        obj: Any Python object

    Returns:
        JSON-serializable value, or None for non-serializable types
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_ensure_json_safe(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _ensure_json_safe(v) for k, v in obj.items() if isinstance(k, str)}
    return None  # Non-serializable types are skipped


@dataclass
class ExportedSettings:
    """Exported settings data structure."""

    schema_version: str
    app_version: str
    exported_at: str
    sections: Dict[str, Dict[str, Any]]


def export_settings(config: Dict[str, Any], app_version: str) -> str:
    """Export settings to JSON string.

    Excludes sensitive sections (engine, ui_state) and certain keys
    (version, lang, paths) to ensure portability across environments.

    Args:
        config: Configuration dictionary (ctx._config)
        app_version: Application version string

    Returns:
        JSON string with exported settings
    """
    filtered = {}
    for section, values in config.items():
        if section in EXCLUDED_SECTIONS:
            continue
        if not isinstance(values, dict):
            continue
        if section in EXCLUDED_KEYS:
            section_filtered = {
                k: v for k, v in values.items() if k not in EXCLUDED_KEYS[section]
            }
        else:
            section_filtered = dict(values)

        # Convert to JSON-safe values
        safe_section = _ensure_json_safe(section_filtered)
        if safe_section:
            filtered[section] = safe_section

    export_data = {
        "schema_version": SCHEMA_VERSION,
        "app_version": app_version,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sections": filtered,
    }
    return json.dumps(export_data, indent=2, ensure_ascii=False)


def parse_exported_settings(json_str: str) -> ExportedSettings:
    """Parse and validate exported settings JSON.

    Performs minimal validation:
    - schema_version must match SCHEMA_VERSION
    - sections must be a dict
    - Each section must be a dict (non-dict sections are skipped)

    Args:
        json_str: JSON string to parse

    Returns:
        ExportedSettings dataclass

    Raises:
        ValueError: If validation fails
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        raise ValueError("Root must be an object")

    schema_ver = data.get("schema_version")
    if schema_ver != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema version: {schema_ver} (expected {SCHEMA_VERSION})"
        )

    sections = data.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("'sections' must be an object")

    # Filter out non-dict sections
    valid_sections = {k: v for k, v in sections.items() if isinstance(v, dict)}

    return ExportedSettings(
        schema_version=data["schema_version"],
        app_version=data.get("app_version", "unknown"),
        exported_at=data.get("exported_at", ""),
        sections=valid_sections,
    )


@lru_cache(maxsize=1)
def get_package_defaults() -> Dict[str, Any]:
    """Get package default settings (cached).

    Returns:
        Default settings dictionary from katrain/config.json
    """
    from katrain.core.utils import find_package_resource

    package_config = find_package_resource("katrain/config.json")
    with open(package_config, "r", encoding="utf-8") as f:
        return cast(Dict[str, Any], json.load(f))


def get_default_value(section: str, key: str) -> Any:
    """Get default value for a specific setting key.

    Args:
        section: Section name (e.g., "general", "leela")
        key: Key name within section

    Returns:
        Default value, or None if not found
    """
    defaults = get_package_defaults()
    return defaults.get(section, {}).get(key)


def create_backup_path(config_file_path: str) -> str:
    """Generate backup file path with timestamp.

    Args:
        config_file_path: Original config file path

    Returns:
        Backup file path with timestamp suffix
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{config_file_path}.backup.{timestamp}"


def atomic_save_config(
    config: Dict[str, Any], config_file_path: str, indent: int = 4
) -> None:
    """Save config atomically using temp file and os.replace.

    This ensures that the config file is never left in a corrupted state,
    even if the write operation fails mid-way.

    Args:
        config: Configuration dictionary to save
        config_file_path: Destination file path
        indent: JSON indentation (default 4)

    Raises:
        OSError: If file operations fail
        TypeError: If JSON serialization fails
    """
    dirname = os.path.dirname(config_file_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        suffix=".json", prefix="config_", dir=dirname or "."
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=indent, ensure_ascii=False)
        os.replace(temp_path, config_file_path)
    except Exception as e:
        # Atomic save failed - clean up temp file before re-raising
        logging.debug(f"Atomic save failed, cleaning up temp file: {e}")
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except OSError as cleanup_err:
            # Cleanup failure is secondary; log but don't mask original error
            logging.debug(f"Failed to cleanup temp file {temp_path}: {cleanup_err}")
        raise  # Re-raise original exception with preserved traceback

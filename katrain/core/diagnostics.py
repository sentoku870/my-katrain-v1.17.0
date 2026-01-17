"""Diagnostics collection and export for bug reports.

Phase 29: Diagnostics + Bug Report Bundle.

This module collects system information, KataGo status, app info,
and logs for export as a sanitized ZIP bundle. It is Kivy-independent.
"""

import json
import os
import platform
import random
import string
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from katrain.common.sanitize import (
    SanitizationContext,
    sanitize_dict,
    sanitize_text,
)
from katrain.common.settings_export import EXCLUDED_SECTIONS


# --- Data Classes ---


@dataclass
class SystemInfo:
    """Operating system and Python information."""

    os_name: str
    os_version: str
    os_release: str
    python_version: str
    python_bits: str
    machine: str
    processor: str


@dataclass
class KataGoInfo:
    """KataGo engine information (sanitized paths)."""

    exe_path: str
    model_path: str
    config_path: str
    is_running: bool
    version: Optional[str] = None


@dataclass
class AppInfo:
    """Application information."""

    version: str
    config_path: str
    data_folder: str


@dataclass
class DiagnosticsBundle:
    """Collection of all diagnostic information."""

    system_info: SystemInfo
    katago_info: KataGoInfo
    app_info: AppInfo
    settings: dict[str, Any]
    logs: list[str]


@dataclass
class DiagnosticsResult:
    """Result of diagnostics ZIP generation."""

    success: bool
    output_path: Optional[Path] = None
    error_message: Optional[str] = None


# --- Collection Functions ---


def collect_system_info() -> SystemInfo:
    """Collect system information.

    Returns:
        SystemInfo with current system details.
    """
    return SystemInfo(
        os_name=platform.system(),
        os_version=platform.version(),
        os_release=platform.release(),
        python_version=platform.python_version(),
        python_bits="64-bit" if sys.maxsize > 2**32 else "32-bit",
        machine=platform.machine(),
        processor=platform.processor(),
    )


def collect_katago_info(
    exe_path: str = "",
    model_path: str = "",
    config_path: str = "",
    is_running: bool = False,
    version: Optional[str] = None,
) -> KataGoInfo:
    """Collect KataGo engine information.

    Args passed from GUI layer to avoid circular imports.
    """
    return KataGoInfo(
        exe_path=exe_path,
        model_path=model_path,
        config_path=config_path,
        is_running=is_running,
        version=version,
    )


def collect_app_info(
    version: str,
    config_path: str,
    data_folder: str,
) -> AppInfo:
    """Collect application information.

    Args passed from GUI layer to avoid importing app modules.
    """
    return AppInfo(
        version=version,
        config_path=config_path,
        data_folder=data_folder,
    )


def collect_settings_snapshot(
    config_data: dict[str, Any],
) -> dict[str, Any]:
    """Create a snapshot of settings with sensitive sections excluded.

    Args:
        config_data: Full config dictionary.

    Returns:
        Config dictionary with EXCLUDED_SECTIONS removed.
    """
    result: dict[str, Any] = {}
    for section, values in config_data.items():
        if section not in EXCLUDED_SECTIONS:
            result[section] = values
    return result


# --- Filename Generation ---


def generate_diagnostics_filename() -> str:
    """Generate a unique filename for diagnostics ZIP.

    Format: diagnostics_YYYYMMDD-HHMMSS_XXXX.zip
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"diagnostics_{timestamp}_{suffix}.zip"


# --- ZIP Generation ---


def _write_json_entry(
    zf: zipfile.ZipFile,
    name: str,
    data: dict[str, Any],
    ctx: SanitizationContext,
) -> None:
    """Write a JSON entry to the ZIP with sanitization.

    Applies sanitize_dict before JSON serialization for JSON safety.
    """
    sanitized = sanitize_dict(data, ctx)
    content = json.dumps(sanitized, indent=2, ensure_ascii=False)
    zf.writestr(name, content.encode("utf-8"))


def _write_logs_entry(
    zf: zipfile.ZipFile,
    name: str,
    lines: list[str],
    ctx: SanitizationContext,
) -> None:
    """Write log entries to the ZIP with per-line sanitization."""
    sanitized_lines = [sanitize_text(line, ctx) for line in lines]
    content = "\n".join(sanitized_lines)
    zf.writestr(name, content.encode("utf-8"))


def create_diagnostics_zip(
    bundle: DiagnosticsBundle,
    output_path: Path,
    ctx: SanitizationContext,
    *,
    now_fn: Optional[Callable[[], datetime]] = None,
) -> DiagnosticsResult:
    """Create a diagnostics ZIP bundle.

    Args:
        bundle: Collection of diagnostic information.
        output_path: Path for the output ZIP file.
        ctx: Sanitization context for privacy protection.
        now_fn: Optional datetime factory for testing.

    Returns:
        DiagnosticsResult with success status and output path.

    ZIP Structure:
        manifest.json      - Metadata and file list
        system_info.json   - OS/Python info (sanitized)
        katago_info.json   - Engine paths/status (sanitized)
        app_info.json      - App version/paths (sanitized)
        settings.json      - Settings snapshot (engine excluded)
        logs.txt           - Recent logs (sanitized)
    """
    try:
        now = (now_fn or datetime.now)()

        # Build manifest
        manifest = {
            "schema_version": "1.0",
            "generated_at": now.isoformat(timespec="seconds"),
            "generator": {
                "name": "myKatrain",
                "version": bundle.app_info.version,
            },
            "files": [
                {"name": "system_info.json", "type": "system"},
                {"name": "katago_info.json", "type": "katago"},
                {"name": "app_info.json", "type": "app"},
                {"name": "settings.json", "type": "settings"},
                {"name": "logs.txt", "type": "logs"},
            ],
            "privacy": {
                "sanitized": True,
                "rules_applied": ["paths", "username", "hostname"],
            },
        }

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # manifest.json - no sanitization needed (fixed values only)
            manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False)
            zf.writestr("manifest.json", manifest_json.encode("utf-8"))

            # system_info.json
            _write_json_entry(zf, "system_info.json", asdict(bundle.system_info), ctx)

            # katago_info.json
            _write_json_entry(zf, "katago_info.json", asdict(bundle.katago_info), ctx)

            # app_info.json
            _write_json_entry(zf, "app_info.json", asdict(bundle.app_info), ctx)

            # settings.json
            _write_json_entry(zf, "settings.json", bundle.settings, ctx)

            # logs.txt
            _write_logs_entry(zf, "logs.txt", bundle.logs, ctx)

        return DiagnosticsResult(success=True, output_path=output_path)

    except Exception as e:
        return DiagnosticsResult(success=False, error_message=str(e))

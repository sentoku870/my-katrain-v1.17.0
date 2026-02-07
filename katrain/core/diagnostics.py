"""Diagnostics collection and export for bug reports.

Phase 29: Diagnostics + Bug Report Bundle.

This module collects system information, KataGo status, app info,
and logs for export as a sanitized ZIP bundle. It is Kivy-independent.
"""

import json
import platform
import random
import string
import sys
import zipfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

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
    ram_total: str
    gpu_info: str


@dataclass
class KataGoInfo:
    """KataGo engine information (sanitized paths)."""

    exe_path: str
    model_path: str
    config_path: str
    is_running: bool
    version: str | None = None


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
    output_path: Path | None = None
    error_message: str | None = None


# --- Collection Functions ---


def _get_ram_info() -> str:
    """Get total RAM size."""
    try:
        if sys.platform == "win32":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return f"{stat.ullTotalPhys / (1024**3):.1f} GB"
        else:
            # Linux fallback
            with open("/proc/meminfo") as f:
                for line in f:
                    if "MemTotal" in line:
                        kb = int(line.split()[1])
                        return f"{kb / (1024**2):.1f} GB"
    except Exception:
        pass
    return "Unknown"


def _get_gpu_info() -> str:
    """Get GPU information."""
    try:
        if sys.platform == "win32":
            import subprocess

            cmd = "wmic path win32_videocontroller get name"
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
            out, _ = process.communicate()
            output = out.decode("utf-8", errors="ignore").strip().split("\n")
            if len(output) > 1:
                gpus = [line.strip() for line in output[1:] if line.strip()]
                return ", ".join(gpus)
        else:
            # Basic fallback for now, maybe lspci or nvidia-smi checking could go here
            pass
    except Exception:
        pass
    return "Unknown"


def collect_system_info() -> SystemInfo:
    """Collect system information.

    Returns:
        SystemInfo with current system details.
    """
    import os
    
    cpu_info = platform.processor()
    cpu_count = os.cpu_count()
    if cpu_count:
        cpu_info = f"{cpu_info} ({cpu_count} cores)"

    return SystemInfo(
        os_name=platform.system(),
        os_version=platform.version(),
        os_release=platform.release(),
        python_version=platform.python_version(),
        python_bits="64-bit" if sys.maxsize > 2**32 else "32-bit",
        machine=platform.machine(),
        processor=cpu_info,
        ram_total=_get_ram_info(),
        gpu_info=_get_gpu_info(),
    )


def collect_katago_info(
    exe_path: str = "",
    model_path: str = "",
    config_path: str = "",
    is_running: bool = False,
    version: str | None = None,
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


# --- Public API (Phase 90) ---


def collect_diagnostics_bundle(
    engine_info: tuple[str, str, str, bool, str | None] | None = None,
    app_version: str = "unknown",
    config_path: str = "",
    data_folder: str = "",
    config_data: dict[str, Any] | None = None,
    logs: list[str] | None = None,
) -> DiagnosticsBundle:
    """Public API to collect diagnostics bundle.

    This is the recommended entry point for diagnostics collection.
    Avoids direct access to private attributes.

    Args:
        engine_info: Tuple of (exe_path, model_path, config_path, is_running, version)
                     or None for default empty values.
        app_version: Application version string.
        config_path: Path to config file.
        data_folder: Data folder path.
        config_data: Config dictionary (will be snapshot filtered).
        logs: Log lines list.

    Returns:
        DiagnosticsBundle ready for ZIP generation or LLM text formatting.
    """
    system_info = collect_system_info()

    if engine_info:
        exe_path, model_path, cfg_path, is_running, version = engine_info
        katago_info = collect_katago_info(exe_path, model_path, cfg_path, is_running, version)
    else:
        katago_info = collect_katago_info("", "", "", False, None)

    app_info = collect_app_info(app_version, config_path, data_folder)
    settings = collect_settings_snapshot(config_data or {})

    return DiagnosticsBundle(
        system_info=system_info,
        katago_info=katago_info,
        app_info=app_info,
        settings=settings,
        logs=logs or [],
    )


def format_llm_diagnostics_text(
    bundle: DiagnosticsBundle,
    ctx: SanitizationContext,
    error_context: str = "",
    max_log_lines: int = 20,
) -> str:
    """Format diagnostics as LLM-ready text.

    Uses existing bundle data - no new collection.
    Output is sanitized and truncated to LLM_TEXT_MAX_BYTES.

    Args:
        bundle: DiagnosticsBundle from collect_diagnostics_bundle().
        ctx: SanitizationContext for privacy protection.
        error_context: Description of the error (will be included).
        max_log_lines: Maximum log lines to include (default 20).

    Returns:
        LLM-ready text, sanitized and byte-bounded (<= 4096 UTF-8 bytes).
    """
    from katrain.core.error_recovery import truncate_to_bytes

    sys_info = bundle.system_info
    kata_info = bundle.katago_info
    app_info = bundle.app_info

    # Sanitize paths
    exe_path = sanitize_text(kata_info.exe_path, ctx) if kata_info.exe_path else "Not configured"
    model_path = sanitize_text(kata_info.model_path, ctx) if kata_info.model_path else "Not configured"
    config_path = sanitize_text(kata_info.config_path, ctx) if kata_info.config_path else "Not configured"

    # Build log section (last N lines, sanitized)
    log_lines = bundle.logs[-max_log_lines:] if bundle.logs else []
    sanitized_logs = [sanitize_text(line, ctx) for line in log_lines]
    logs_text = "\n".join(sanitized_logs) if sanitized_logs else "(No logs available)"

    status = "Running" if kata_info.is_running else "Stopped"

    text = f"""=== myKatrain Diagnostics ===

## Environment
- OS: {sys_info.os_name} {sys_info.os_release}
- Python: {sys_info.python_version} ({sys_info.python_bits})
- Machine: {sys_info.machine}
- myKatrain: {app_info.version}

## KataGo
- Status: {status}
- Exe: {exe_path}
- Model: {model_path}
- Config: {config_path}

## Problem
{error_context if error_context else "(No error context provided)"}

## Recent Logs (last {len(log_lines)} lines)
{logs_text}

---
I want to run myKatrain but encountered an error.
Please help me troubleshoot based on the information above.
"""

    return truncate_to_bytes(text)


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
    extra_files: dict[str, str] | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> DiagnosticsResult:
    """Create a diagnostics ZIP bundle.

    Args:
        bundle: Collection of diagnostic information.
        output_path: Path for the output ZIP file.
        ctx: Sanitization context for privacy protection.
        extra_files: Optional dict of {filename: content} to add to ZIP.
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
        llm_prompt.txt     - LLM-ready text (if extra_files provided)
    """
    try:
        now = (now_fn or datetime.now)()

        # Build file list for manifest
        files_list = [
            {"name": "system_info.json", "type": "system"},
            {"name": "katago_info.json", "type": "katago"},
            {"name": "app_info.json", "type": "app"},
            {"name": "settings.json", "type": "settings"},
            {"name": "logs.txt", "type": "logs"},
        ]

        # Add extra files to manifest
        if extra_files:
            for filename in extra_files:
                files_list.append({"name": filename, "type": "extra"})

        # Build manifest
        manifest = {
            "schema_version": "1.0",
            "generated_at": now.isoformat(timespec="seconds"),
            "generator": {
                "name": "myKatrain",
                "version": bundle.app_info.version,
            },
            "files": files_list,
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

            # Extra files (e.g., llm_prompt.txt)
            if extra_files:
                for filename, content in extra_files.items():
                    zf.writestr(filename, content.encode("utf-8"))

        return DiagnosticsResult(success=True, output_path=output_path)

    except Exception as e:
        return DiagnosticsResult(success=False, error_message=str(e))

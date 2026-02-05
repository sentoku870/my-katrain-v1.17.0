"""Privacy-aware sanitization for diagnostics export.

Phase 29: Diagnostics + Bug Report Bundle.

Replaces sensitive information (paths, usernames, hostnames) with placeholders.
This module is Kivy-independent and can be used from both Core and GUI layers.
"""

from __future__ import annotations

import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SanitizationContext:
    """Context for sanitization operations.

    Contains the sensitive values to be replaced with placeholders.
    """

    username: str
    hostname: str
    home_dir: str
    app_dir: str

    def __post_init__(self) -> None:
        # Normalize paths for consistent matching
        # Note: We don't use Path.resolve() here because it would convert
        # Unix paths to Windows paths when running tests on Windows.
        # The caller is responsible for providing resolved paths if needed.
        pass


def get_sanitization_context(app_dir: str = "") -> SanitizationContext:
    """Get sanitization context from current environment.

    Args:
        app_dir: Application directory path. If empty, uses current working directory.

    Returns:
        SanitizationContext with current environment values.
    """
    username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    hostname = socket.gethostname()
    home_dir = str(Path(os.path.expanduser("~")).resolve())
    app_dir = str(Path.cwd().resolve()) if not app_dir else str(Path(app_dir).resolve())

    return SanitizationContext(
        username=username,
        hostname=hostname,
        home_dir=home_dir,
        app_dir=app_dir,
    )


def _normalize_path(path: str) -> str:
    """Normalize path for matching (forward slashes, lowercase on Windows)."""
    # Convert backslashes to forward slashes
    normalized = path.replace("\\", "/")
    # Remove trailing slash
    normalized = normalized.rstrip("/")
    return normalized


def _normalize_for_comparison(path: str) -> str:
    """Normalize path for case-insensitive comparison on Windows."""
    normalized = _normalize_path(path)
    # Windows paths are case-insensitive
    if os.name == "nt":
        normalized = normalized.lower()
    return normalized


def sanitize_path(path: str, ctx: SanitizationContext) -> str:
    """Replace absolute paths with placeholders.

    Handles:
    - Home directory -> <USER_HOME>
    - App directory -> <APP_DIR>
    - UNC paths with matching hostname -> \\\\<HOST>\\...

    Args:
        path: Path string to sanitize.
        ctx: Sanitization context.

    Returns:
        Sanitized path with placeholders.
    """
    if not path:
        return path

    # Handle UNC paths (\\HOST\share\... or //HOST/share/...)
    if path.startswith("\\\\") or path.startswith("//"):
        parts = _normalize_path(path).split("/")
        # parts = ["", "", "HOST", "share", ...]
        if len(parts) >= 3 and parts[2]:
            host_part = parts[2]
            if host_part.lower() == ctx.hostname.lower():
                parts[2] = "<HOST>"
                # Continue with sanitize_text for username in path
                result = "/".join(parts)
                return sanitize_text(result, ctx)
        # UNC path with different host - still apply text sanitization
        return sanitize_text(path, ctx)

    # Normalize for comparison
    normalized = _normalize_path(path)
    normalized_lower = _normalize_for_comparison(path)

    # Prepare context paths for comparison
    home_normalized = _normalize_for_comparison(ctx.home_dir)
    app_normalized = _normalize_for_comparison(ctx.app_dir)

    result = normalized

    # Replace app_dir first (it might be under home_dir)
    if app_normalized and normalized_lower.startswith(app_normalized):
        suffix = normalized[len(ctx.home_dir) :] if len(normalized) > len(app_normalized) else ""
        # Get the actual suffix from original normalized path
        suffix = normalized[len(_normalize_path(ctx.app_dir)) :]
        result = "<APP_DIR>" + suffix

    # Replace home_dir
    elif home_normalized and normalized_lower.startswith(home_normalized):
        suffix = normalized[len(_normalize_path(ctx.home_dir)) :]
        result = "<USER_HOME>" + suffix

    # Apply text sanitization for any remaining username/hostname
    return sanitize_text(result, ctx)


def sanitize_text(text: str, ctx: SanitizationContext) -> str:
    """Replace sensitive strings (username, hostname) in text.

    Performs case-insensitive replacement for Windows compatibility.

    Args:
        text: Text to sanitize.
        ctx: Sanitization context.

    Returns:
        Sanitized text with placeholders.
    """
    if not text:
        return text

    result = text

    # Replace username (case-insensitive)
    if ctx.username:
        pattern = re.compile(re.escape(ctx.username), re.IGNORECASE)
        result = pattern.sub("<USER>", result)

    # Replace hostname (case-insensitive)
    if ctx.hostname:
        pattern = re.compile(re.escape(ctx.hostname), re.IGNORECASE)
        result = pattern.sub("<HOST>", result)

    # Replace home directory path variants
    if ctx.home_dir:
        # Forward slash version
        home_forward = _normalize_path(ctx.home_dir)
        pattern = re.compile(re.escape(home_forward), re.IGNORECASE)
        result = pattern.sub("<USER_HOME>", result)
        # Backslash version
        home_back = ctx.home_dir.replace("/", "\\")
        pattern = re.compile(re.escape(home_back), re.IGNORECASE)
        result = pattern.sub("<USER_HOME>", result)

    # Replace app directory path variants
    if ctx.app_dir:
        # Forward slash version
        app_forward = _normalize_path(ctx.app_dir)
        pattern = re.compile(re.escape(app_forward), re.IGNORECASE)
        result = pattern.sub("<APP_DIR>", result)
        # Backslash version
        app_back = ctx.app_dir.replace("/", "\\")
        pattern = re.compile(re.escape(app_back), re.IGNORECASE)
        result = pattern.sub("<APP_DIR>", result)

    return result


def sanitize_dict(data: dict[str, Any], ctx: SanitizationContext) -> dict[str, Any]:
    """Recursively sanitize string values in a dictionary.

    Keys are preserved unchanged. Only string values are sanitized.

    Args:
        data: Dictionary to sanitize.
        ctx: Sanitization context.

    Returns:
        New dictionary with sanitized string values.
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = sanitize_text(value, ctx)
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, ctx)
        elif isinstance(value, list):
            result[key] = _sanitize_list(value, ctx)
        else:
            result[key] = value  # int, float, bool, None preserved
    return result


def _sanitize_list(items: list[Any], ctx: SanitizationContext) -> list[Any]:
    """Recursively sanitize string/dict values in a list."""
    return [
        sanitize_text(v, ctx)
        if isinstance(v, str)
        else sanitize_dict(v, ctx)
        if isinstance(v, dict)
        else _sanitize_list(v, ctx)
        if isinstance(v, list)
        else v
        for v in items
    ]

"""Test analysis module for Phase 89 - error classification and results.

This module provides:
- Error category classification for engine failures
- EngineTestResult dataclass for unified error handling
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ErrorCategory(Enum):
    """Categories of engine errors for auto mode recovery."""

    ENGINE_START_FAILED = "engine_start"
    MODEL_LOAD_FAILED = "model_load"
    BACKEND_ERROR = "backend"
    TIMEOUT = "timeout"
    LIGHTWEIGHT_MISSING = "lightweight_missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EngineTestResult:
    """Result of an engine test.

    Attributes:
        success: Whether the test passed.
        error_category: Category of error if failed.
        error_message: Detailed error message if failed.
    """

    success: bool
    error_category: ErrorCategory | None
    error_message: str | None


# =============================================================================
# Error Classification Patterns
# =============================================================================

# Strong signals - match these first (high confidence)
STRONG_BACKEND_PATTERNS: list[str] = [
    r"(?i)clGetPlatformIDs",
    r"(?i)cl_out_of_resources",
    r"(?i)cl_invalid_",
    r"(?i)opencl.*error",
    r"(?i)opencl.*failed",
    r"(?i)device not found",
    r"(?i)no opencl",
]

# Weak signals - only if no strong signals match
WEAK_BACKEND_PATTERNS: list[str] = [
    r"(?i)\bGPU\b.*(?:error|failed|not)",
    r"(?i)\bCUDA\b.*(?:error|failed|not)",
]

STRONG_MODEL_PATTERNS: list[str] = [
    r"(?i)failed to load.*model",
    r"(?i)model.*not found",
    r"(?i)invalid model",
    r"(?i)cannot open.*\.bin",
    r"(?i)\.bin\.gz.*(?:error|not found|missing)",
]

STRONG_ENGINE_START_PATTERNS: list[str] = [
    r"(?i)executable.*not found",
    r"(?i)permission denied",
    r"(?i)is not recognized as",
    r"(?i)no such file or directory",
    r"(?i)cannot find the path",
]


def _matches_any_pattern(text: str, patterns: list[str]) -> bool:
    """Check if text matches any of the patterns.

    Args:
        text: Text to search in.
        patterns: List of regex patterns.

    Returns:
        True if any pattern matches.
    """
    return any(re.search(pattern, text) for pattern in patterns)


def classify_engine_error(error_text: str, is_timeout: bool = False) -> ErrorCategory:
    """Classify engine error from error text.

    Uses a two-phase approach:
        1. Check strong signals first (high confidence)
        2. Check weak signals only if no strong signals match

    Args:
        error_text: Error text from engine or subprocess.
        is_timeout: True if this was a timeout (takes precedence).

    Returns:
        ErrorCategory classification.
    """
    if is_timeout:
        return ErrorCategory.TIMEOUT

    # Strong signals first
    if _matches_any_pattern(error_text, STRONG_ENGINE_START_PATTERNS):
        return ErrorCategory.ENGINE_START_FAILED

    if _matches_any_pattern(error_text, STRONG_MODEL_PATTERNS):
        return ErrorCategory.MODEL_LOAD_FAILED

    if _matches_any_pattern(error_text, STRONG_BACKEND_PATTERNS):
        return ErrorCategory.BACKEND_ERROR

    # Weak signals only if no strong signals matched
    if _matches_any_pattern(error_text, WEAK_BACKEND_PATTERNS):
        return ErrorCategory.BACKEND_ERROR

    return ErrorCategory.UNKNOWN

"""Batch analysis package for myKatrain.

This package provides batch SGF analysis functionality, fully Kivy-independent.

Phase 42-A: Models and helpers only.
For run_batch(), use katrain.tools.batch_analyze_sgf until 42-B.

Usage:
    from katrain.core.batch import BatchResult, WriteError, has_analysis

Structure:
    - models.py: WriteError, BatchResult dataclasses
    - helpers.py: Constants + pure helper functions
"""

# =============================================================================
# Explicit imports from models.py
# =============================================================================

from katrain.core.batch.models import (
    BatchResult,
    WriteError,
)

# =============================================================================
# Explicit imports from helpers.py
# =============================================================================

from katrain.core.batch.helpers import (
    # Constants
    DEFAULT_TIMEOUT_SECONDS,
    ENCODINGS_TO_TRY,
    # Variable visits
    choose_visits_for_sgf,
    # Loss calculation
    get_canonical_loss,
    # Timeout parsing
    parse_timeout_input,
    # File I/O
    safe_write_file,
    read_sgf_with_fallback,
    parse_sgf_with_fallback,
    has_analysis,
    # File discovery
    collect_sgf_files_recursive,
    collect_sgf_files,
    # Engine polling
    wait_for_analysis,
    # Filename sanitization
    sanitize_filename,
    get_unique_filename,
    normalize_player_name,
    # UI validation
    safe_int,
    needs_leela_karte_warning,
)

# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # === models.py ===
    "WriteError",
    "BatchResult",
    # === helpers.py ===
    # Constants
    "DEFAULT_TIMEOUT_SECONDS",
    "ENCODINGS_TO_TRY",
    # Variable visits
    "choose_visits_for_sgf",
    # Loss calculation
    "get_canonical_loss",
    # Timeout parsing
    "parse_timeout_input",
    # File I/O
    "safe_write_file",
    "read_sgf_with_fallback",
    "parse_sgf_with_fallback",
    "has_analysis",
    # File discovery
    "collect_sgf_files_recursive",
    "collect_sgf_files",
    # Engine polling
    "wait_for_analysis",
    # Filename sanitization
    "sanitize_filename",
    "get_unique_filename",
    "normalize_player_name",
    # UI validation
    "safe_int",
    "needs_leela_karte_warning",
]

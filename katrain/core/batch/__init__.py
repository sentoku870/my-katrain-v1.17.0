"""Batch analysis package for myKatrain.

This package provides batch SGF analysis functionality, fully Kivy-independent.

Usage:
    from katrain.core.batch import BatchResult, WriteError, has_analysis
    from katrain.core.batch import run_batch  # Lazy import via __getattr__

Structure:
    - models.py: WriteError, BatchResult dataclasses
    - helpers.py: Constants + pure helper functions
    - analysis.py: analyze_single_file, analyze_single_file_leela
    - orchestration.py: run_batch main entry point
    - stats.py: Game stats extraction and summary generation
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
    # === Lazy exports (via __getattr__) ===
    # analysis.py
    "analyze_single_file",
    "analyze_single_file_leela",
    # orchestration.py
    "run_batch",
    # stats.py
    "extract_game_stats",
    "build_batch_summary",
    "extract_players_from_stats",
    "build_player_summary",
]


# =============================================================================
# Lazy imports for heavy modules (Phase 42-B)
# =============================================================================

def __getattr__(name: str):
    """Lazy import for heavy modules to avoid circular imports.

    Available:
    - run_batch (from orchestration)
    - analyze_single_file, analyze_single_file_leela (from analysis)
    - extract_game_stats, build_batch_summary, extract_players_from_stats,
      build_player_summary (from stats)

    Note: Caches imported objects in globals() to avoid repeated imports.
    """
    # Analysis functions
    if name == "analyze_single_file":
        from katrain.core.batch.analysis import analyze_single_file
        globals()["analyze_single_file"] = analyze_single_file
        return analyze_single_file

    if name == "analyze_single_file_leela":
        from katrain.core.batch.analysis import analyze_single_file_leela
        globals()["analyze_single_file_leela"] = analyze_single_file_leela
        return analyze_single_file_leela

    # Orchestration
    if name == "run_batch":
        from katrain.core.batch.orchestration import run_batch
        globals()["run_batch"] = run_batch
        return run_batch

    # Stats functions
    if name == "extract_game_stats":
        from katrain.core.batch.stats import extract_game_stats
        globals()["extract_game_stats"] = extract_game_stats
        return extract_game_stats

    if name == "build_batch_summary":
        from katrain.core.batch.stats import build_batch_summary
        globals()["build_batch_summary"] = build_batch_summary
        return build_batch_summary

    if name == "extract_players_from_stats":
        from katrain.core.batch.stats import extract_players_from_stats
        globals()["extract_players_from_stats"] = extract_players_from_stats
        return extract_players_from_stats

    if name == "build_player_summary":
        from katrain.core.batch.stats import build_player_summary
        globals()["build_player_summary"] = build_player_summary
        return build_player_summary

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

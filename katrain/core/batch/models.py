"""Batch analysis data models.

This module contains dataclasses for batch processing results and errors.
All classes are Kivy-independent and can be used in headless contexts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WriteError:
    """Structured error entry for file write failures.

    Attributes:
        file_kind: Type of file ("karte", "summary", "analyzed_sgf")
        sgf_id: SGF file name or player name (for error reporting)
        target_path: Attempted output path
        exception_type: Exception class name (e.g., "PermissionError")
        message: Error message
    """

    file_kind: str
    sgf_id: str
    target_path: str
    exception_type: str
    message: str


@dataclass
class BatchResult:
    """Result of batch analysis operation.

    Attributes:
        success_count: Number of successfully analyzed files
        fail_count: Number of failed files
        skip_count: Number of skipped files (already analyzed)
        output_dir: Output directory path
        cancelled: Whether the operation was cancelled
        karte_written: Number of karte files successfully written
        karte_failed: Number of karte files that failed to write
        summary_written: Whether summary file was written
        summary_error: Error message if summary write failed
        analyzed_sgf_written: Number of analyzed SGF files written
        write_errors: List of structured write errors
        curator_ranking_written: Whether curator ranking JSON was written (Phase 64)
        curator_guide_written: Whether replay guide JSON was written (Phase 64)
        curator_games_scored: Number of games scored for curator ranking (Phase 64)
        curator_guides_generated: Number of replay guides generated (Phase 64)
        curator_errors: List of curator-related error messages (Phase 64)
        aborted: Whether batch was aborted due to circuit breaker (Phase 95C)
        abort_reason: Reason for abort if aborted (Phase 95C)
        engine_failure_count: Number of engine-related failures (timeout, dead) (Phase 95C)
        file_error_count: Number of file-related errors (SGF parse, I/O) (Phase 95C)
    """

    success_count: int = 0
    fail_count: int = 0
    skip_count: int = 0
    output_dir: str = ""
    cancelled: bool = False
    # Extended output counts
    karte_written: int = 0
    karte_failed: int = 0
    summary_written: bool = False
    summary_error: str | None = None
    analyzed_sgf_written: int = 0
    # Structured write errors (A3)
    write_errors: list[WriteError] = field(default_factory=list)
    # Curator outputs (Phase 64)
    curator_ranking_written: bool = False
    curator_guide_written: bool = False
    curator_games_scored: int = 0
    curator_guides_generated: int = 0
    curator_errors: list[str] = field(default_factory=list)
    # Circuit breaker fields (Phase 95C)
    aborted: bool = False
    abort_reason: str | None = None
    engine_failure_count: int = 0
    file_error_count: int = 0

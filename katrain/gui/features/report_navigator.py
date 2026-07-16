"""Report Navigator - Report Navigation UX Improvements (Phase 26).

Structure:
- Top-level: Pure functions (Kivy-independent, testable)
- Bottom: UI functions (lazy imports inside functions)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

# --- Constants ---

REPORT_PATTERNS = {
    "karte": "karte_*.json",
    "summary": "summary_*.json",
    "package": "llm_package_*.zip",
}


# --- Pure Functions (Kivy-independent) ---


def _get_logger() -> logging.Logger:
    """Get module logger (lazy to avoid side effect at import time)."""
    return logging.getLogger(__name__)


@dataclass
class ReportInfo:
    """Report information."""

    path: Path
    report_type: str  # "karte", "summary", "package"
    mtime: float  # Modified time (st_mtime)


def find_recent_reports(output_dir: Path, limit: int = 10) -> list[ReportInfo]:
    """Find recent reports in the output directory.

    Args:
        output_dir: Directory to search in.
        limit: Maximum number of reports to return.

    Returns:
        List of ReportInfo sorted by mtime (newest first).
    """
    if not output_dir.is_dir():
        return []

    reports = []
    for report_type, pattern in REPORT_PATTERNS.items():
        for path in output_dir.glob(pattern):
            if path.is_file():
                try:
                    mtime = path.stat().st_mtime
                    reports.append(ReportInfo(path=path, report_type=report_type, mtime=mtime))
                except OSError:
                    continue

    reports.sort(key=lambda r: r.mtime, reverse=True)
    return reports[:limit]


def get_latest_report(output_dir: Path) -> ReportInfo | None:
    """Get the most recent report.

    Args:
        output_dir: Directory to search in.

    Returns:
        ReportInfo for the most recent report, or None if no reports found.
    """
    reports = find_recent_reports(output_dir, limit=1)
    return reports[0] if reports else None


# Phase 227-C: types accepted as LLM Coach input. The popup auto-fills
# whichever was generated most recently. ``karte`` and ``summary`` are
# the two valid JSON report types; ``package`` is a zipped bundle not
# directly usable as an LLM prompt input.
_LLM_INPUT_TYPES: frozenset[str] = frozenset({"karte", "summary"})


def find_latest_llm_input(output_dir: Path) -> ReportInfo | None:
    """Phase 227-C: locate the most recent karte/summary report.

    Same as :func:`get_latest_report` but restricted to the two JSON
    types the LLM Coach popup can consume (``karte`` and ``summary``).
    ``package`` (.zip) bundles are skipped — the popup needs a raw JSON
    file to read.

    Args:
        output_dir: Directory to search in.

    Returns:
        The most recent :class:`ReportInfo` whose ``report_type`` is
        ``"karte"`` or ``"summary"``, or ``None`` when no such file
        exists. The caller is expected to dispatch on
        ``report_info.report_type`` to pick the right validator /
        prompt builder.
    """
    if not output_dir.is_dir():
        return None
    # limit=10 is a safety cap — we just need the most recent, but
    # this matches the existing ``find_recent_reports`` contract.
    reports = [r for r in find_recent_reports(output_dir, limit=10) if r.report_type in _LLM_INPUT_TYPES]
    if not reports:
        return None
    # ``find_recent_reports`` already returns mtime-desc sorted, so
    # the first match is the most recent.
    return reports[0]


# --- UI Functions (Kivy-dependent via lazy import) ---
# Phase 230-A.2: ``open_latest_report`` / ``open_output_folder`` は
# メニューからのみ呼ばれており完全削除。LLM Coach が使う
# ``find_latest_llm_input`` / ``get_latest_report`` / ``ReportInfo``
# は温存。
#
# Phase 230-A.2 完了後は UI 関数自体がなくなり、FeatureContext の
# TYPE_CHECKING import も不要になったため削除。

"""Report Navigator - Report Navigation UX Improvements (Phase 26).

Structure:
- Top-level: Pure functions (Kivy-independent, testable)
- Bottom: UI functions (lazy imports inside functions)
"""
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional
import logging

# --- Constants ---

REPORT_PATTERNS = {
    "karte": "karte_*.md",
    "summary": "summary_*.md",
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


def find_recent_reports(output_dir: Path, limit: int = 10) -> List[ReportInfo]:
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
                    reports.append(
                        ReportInfo(path=path, report_type=report_type, mtime=mtime)
                    )
                except OSError:
                    continue

    reports.sort(key=lambda r: r.mtime, reverse=True)
    return reports[:limit]


def get_latest_report(output_dir: Path) -> Optional[ReportInfo]:
    """Get the most recent report.

    Args:
        output_dir: Directory to search in.

    Returns:
        ReportInfo for the most recent report, or None if no reports found.
    """
    reports = find_recent_reports(output_dir, limit=1)
    return reports[0] if reports else None


# --- UI Functions (Kivy-dependent via lazy import) ---

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def open_latest_report(ctx: "FeatureContext") -> None:
    """Open the most recent report file."""
    from katrain.common.file_opener import open_file
    from katrain.core.constants import STATUS_ERROR, STATUS_INFO
    from katrain.core.lang import i18n
    from katrain.core.reports.package_export import resolve_output_directory

    # Get output directory (match existing pattern: ctx.config() or {})
    mykatrain_settings = ctx.config("mykatrain_settings") or {}
    config_dir = mykatrain_settings.get("karte_output_directory", "")
    output_dir = resolve_output_directory(config_dir)

    if not output_dir.is_dir():
        ctx.log(
            i18n._("mykatrain:folder-not-exist").format(path=str(output_dir)),
            STATUS_ERROR,
        )
        return

    # Find the most recent report
    report = get_latest_report(output_dir)
    if report is None:
        ctx.log(i18n._("mykatrain:no-reports-found"), STATUS_INFO)
        return

    # Open the file
    result = open_file(report.path)
    if not result.success:
        ctx.log(
            i18n._("mykatrain:open-failed").format(
                error=result.error_detail or "Unknown error"
            ),
            STATUS_ERROR,
        )


def open_output_folder(ctx: "FeatureContext") -> None:
    """Open the output folder in the system file manager."""
    from katrain.common.file_opener import open_folder
    from katrain.core.constants import STATUS_ERROR
    from katrain.core.lang import i18n
    from katrain.core.reports.package_export import resolve_output_directory

    # Get output directory (match existing pattern: ctx.config() or {})
    mykatrain_settings = ctx.config("mykatrain_settings") or {}
    config_dir = mykatrain_settings.get("karte_output_directory", "")
    output_dir = resolve_output_directory(config_dir)

    if not output_dir.is_dir():
        ctx.log(
            i18n._("mykatrain:folder-not-exist").format(path=str(output_dir)),
            STATUS_ERROR,
        )
        return

    result = open_folder(output_dir)
    if not result.success:
        ctx.log(
            i18n._("mykatrain:open-failed").format(
                error=result.error_detail or "Unknown error"
            ),
            STATUS_ERROR,
        )

"""Phase 242-D: Unified validation report renderer.

Centralises the two near-duplicate Markdown renderers that previously
lived in :mod:`katrain.gui.features.llm_coach`:

- :func:`_render_validation_report` (Karte case)
- :func:`_render_summary_validation_report` (Summary case)

The two shared the same severity banner / referenced-items / issues
sections. The differences were:

- Summary report has an extra ``summary-report-meta`` line ("N局 /
  focus") inserted right after the status banner.
- The "referenced items" list uses different keys per report type
  (symptom_ids / categories, moves, points_lost / moves, game_ids).

This module provides a single :func:`render_validation_report` with a
``ReferencedItem`` typed iterable so the same code path handles both
shapes. The existing GUI-side functions become thin wrappers that
construct the right ``ReferencedItem`` list and call the core helper.

Kivy-free. Safe to import from CLI / tests.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from katrain.core.lang import i18n


@dataclass(frozen=True)
class ReferencedItem:
    """One row in the "Referenced ..." list inside a validation report.

    Attributes:
        label_key: The i18n key for the row label
            (e.g. ``"mykatrain:llm-coach:referenced-symptoms"``).
        values: Iterable of display strings (e.g. symptom id list,
            category list, move numbers).
        joiner: ``", "`` for text lists, ``" "`` would be the natural
            alternative but the existing renderers use ``", "`` so we
            keep it.
    """

    label_key: str
    values: Iterable[Any]

    def render(self) -> str:
        """Render the row as a Markdown bullet."""
        values_str = ", ".join(str(v) for v in self.values)
        return f"**{i18n._(self.label_key)}**: {values_str}"


def _severity_banner(report: Any) -> list[str]:
    """Shared status + severity counter banner."""
    return [
        f"**{i18n._('mykatrain:llm-coach:status')}**: {report.summary_line()}",
        f"**HIGH**: {report.high_count} · **MEDIUM**: {report.medium_count} · **LOW**: {report.low_count}",
        "",
    ]


def _issues_block(report: Any) -> list[str]:
    """Shared issues list (or empty list when no issues)."""
    if not report.issues:
        return []
    lines: list[str] = ["", f"## {i18n._('mykatrain:llm-coach:issues')}", ""]
    for issue in report.issues:
        lines.append(f"- [{issue.severity.value.upper()}] **{issue.kind}**: {issue.message}")
    return lines


def render_validation_report(
    report: Any,
    referenced_items: Iterable[ReferencedItem],
    *,
    extra_meta: str | None = None,
) -> str:
    """Render a validation report as a multi-line Markdown string.

    Args:
        report: Either a :class:`ValidationReport` (Karte) or
            :class:`SummaryValidationReport` (Summary). The function
            only relies on the common attributes (.summary_line(),
            .high_count, .medium_count, .low_count, .issues, .severity).
        referenced_items: Rows to display in the "Referenced ..."
            section. Callers construct the rows from their report's
            specific attributes (symptom_ids / categories / moves /
            points_lost / game_ids).
        extra_meta: Optional line(s) to insert between the severity
            banner and the referenced items. The Summary renderer uses
            this for the "N局 / focus" line. Pass ``None`` to omit.

    Returns:
        Multi-line Markdown string suitable for display in a Kivy
        ``Label`` widget. Ends with a single trailing newline.

    Note:
        The function is intentionally tolerant of missing attributes —
        it relies on duck typing for the report object. Tests can use
        a SimpleNamespace or a real dataclass interchangeably.
    """
    lines: list[str] = _severity_banner(report)
    if extra_meta is not None:
        lines.append(extra_meta)
        lines.append("")
    for item in referenced_items:
        values = list(item.values)
        if not values:
            continue
        lines.append(item.render())
    lines.extend(_issues_block(report))
    return "\n".join(lines) + "\n"


__all__ = [
    "ReferencedItem",
    "render_validation_report",
]

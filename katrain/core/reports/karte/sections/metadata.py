"""Metadata section data builders for karte report (JSON output).

Phase 149 C-2: Refactored from markdown-line generators (list[str]) to JSON
data builders.

Functions:
- definitions_section(): Extends meta.definitions with localized labels
- data_quality_section(): Returns DataQualityStats dict

Note: For Phase 149 C-2, definitions_section() returns the existing definitions
block (no transformation needed since the JSON is language-neutral). The
function is kept as a stable API for future extension.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from katrain.core import eval_metrics

if TYPE_CHECKING:
    from katrain.core.analysis.models import AutoRecommendation
    from katrain.core.reports.karte.sections.context import KarteContext

logger = logging.getLogger(__name__)


def definitions_section(
    ctx: "KarteContext",
    auto_recommendation: "AutoRecommendation | None",
) -> dict[str, Any]:
    """Return the definitions block (currently the existing definitions dict).

    Phase 149 C-2: This function previously produced markdown. The JSON
    schema already carries the full definitions block via meta.definitions
    (see build_karte_json), so we return it unchanged. Kept as stable API
    for future extension (e.g., localized labels per skill_preset).

    Args:
        ctx: Karte context
        auto_recommendation: Auto strictness recommendation (unused for now)

    Returns:
        Empty dict (definitions live in meta.definitions)
    """
    # Definitions are already in meta.definitions (Phase 149 C-2).
    # This function is reserved for future extension.
    return {}


def data_quality_section(ctx: "KarteContext") -> dict[str, Any]:
    """Generate data quality section as DataQualityStats dict.

    Args:
        ctx: Karte context

    Returns:
        DataQualityStats dict (TypedDict-compatible) with reliability
        statistics. Always returns a populated dict (never None).
    """
    rel_stats = eval_metrics.compute_reliability_stats(
        ctx.snapshot.moves, target_visits=ctx.target_visits
    )

    confidence_level = ctx.confidence_level
    confidence_str = confidence_level.name.lower()  # high / medium / low

    result: dict[str, Any] = {
        "confidence_level": confidence_str,
        "total_moves": rel_stats.total_moves,
        "moves_with_visits": rel_stats.moves_with_visits,
        "coverage_pct": round(rel_stats.coverage_pct, 1),
        "reliable_count": rel_stats.reliable_count,
        "reliability_pct": round(rel_stats.reliability_pct, 1),
        "low_confidence_count": rel_stats.low_confidence_count,
        "low_confidence_pct": round(rel_stats.low_confidence_pct, 1),
        "avg_visits": int(rel_stats.avg_visits),
        "max_visits": int(rel_stats.max_visits),
        "effective_threshold": int(rel_stats.effective_threshold),
        "is_low_reliability": rel_stats.is_low_reliability,
    }

    if rel_stats.zero_visits_count > 0:
        result["zero_visits_count"] = rel_stats.zero_visits_count

    return result
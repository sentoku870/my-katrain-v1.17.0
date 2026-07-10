"""Metadata section data builders for karte report (JSON output).

Phase 149 C-2: Refactored from markdown-line generators (list[str]) to JSON
data builders.

Functions:
- data_quality_section(): Returns DataQualityStats dict
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from katrain.core import eval_metrics

if TYPE_CHECKING:
    from katrain.core.reports.karte.sections.context import KarteContext

logger = logging.getLogger(__name__)


def data_quality_section(ctx: KarteContext) -> dict[str, Any]:
    """Generate data quality section as DataQualityStats dict.

    Args:
        ctx: Karte context

    Returns:
        DataQualityStats dict (TypedDict-compatible) with reliability
        statistics. Always returns a populated dict (never None).
    """
    rel_stats = eval_metrics.compute_reliability_stats(ctx.snapshot.moves, target_visits=ctx.target_visits)

    confidence_level = ctx.confidence_level
    confidence_str = confidence_level.name.lower()  # high / medium / low

    # Phase 158-I: visits distribution (min / max / avg / stddev). The
    # previous "avg_visits + max_visits" pair was uninformative when a
    # run uses a fixed visit budget (every game reports the same
    # numbers, so LLMs cannot tell the games apart). Adding min / max
    # / stddev makes per-game variance visible without changing the
    # ``avg_visits`` / ``max_visits`` fields that older consumers may
    # be reading.
    visits_dist = _compute_visits_distribution(ctx.snapshot.moves)

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
        "visits": visits_dist,
    }

    if rel_stats.zero_visits_count > 0:
        result["zero_visits_count"] = rel_stats.zero_visits_count

    return result


def _compute_visits_distribution(moves: list[Any]) -> dict[str, float | int | None]:
    """Return per-move ``root_visits`` distribution for the LLM.

    Phase 158-I: lets the consumer see whether the run used a fixed
    visit budget (stddev ~= 0) or a varied one (stddev > 0). The
    ``min`` / ``max`` / ``avg`` / ``stddev`` fields are integers (rounded)
    so they read naturally in a prompt — stddev is also rounded to 1
    decimal because sub-visit precision is rarely meaningful.
    """
    visits = [int(m.root_visits or 0) for m in moves if m.root_visits]
    if not visits:
        return {"min": None, "max": None, "avg": None, "stddev": None}
    n = len(visits)
    vmin = min(visits)
    vmax = max(visits)
    vavg = sum(visits) / n
    # Population stddev (n divisor) — the Karte is the whole population,
    # not a sample, so dividing by n is correct.
    variance = sum((v - vavg) ** 2 for v in visits) / n
    vstd = variance**0.5
    return {
        "min": vmin,
        "max": vmax,
        "avg": round(vavg),
        "stddev": round(vstd, 1),
    }

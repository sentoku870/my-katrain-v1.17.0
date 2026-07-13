"""Phase 179: KataGo Uncertainty Hint Detector

Derives a beginner hint from ``rootInfo.scoreStdev`` — KataGo's own
confidence in its score estimate. High stdev means even KataGo finds the
position hard to read, which is a great teaching moment for beginners:
"This position is genuinely tricky, even for AI."

Category:
- KATAGO_UNCERTAIN: scoreStdev >= threshold (default 1.5)

Design notes:
- Pure detector: takes pre-extracted score_stdev via SummaryHintContext.
- Falls under the ``katago_uncertain`` config key (independent toggle).
- Severity is 0 (lowest). Pure context info; should never outrank a
  Mistake_BLUNDER or any structural hint.
- Phase 179.2: visits gate raised 200 → 300. Below ~300 visits the
  ``scoreStdev`` value is dominated by Monte-Carlo noise and routinely
  spikes well above the 1.5 threshold even on quiet positions, which
  produced false positives in the busy middle game. The outer
  ``compute_summary_hint`` already enforces ``root_visits >= 100`` via
  ``MIN_SUMMARY_VISITS``; this detector's two-tier gate keeps the other
  summary hints permissive while protecting KATAGO_UNCERTAIN from
  false positives.
"""

from __future__ import annotations

from katrain.core.beginner.models import BeginnerHint, HintCategory, SummaryHintContext

# Phase 179.2: minimum visits for KATAGO_UNCERTAIN to be meaningful.
# Higher than MIN_SUMMARY_VISITS (=100) on purpose: scoreStdev is
# Monte-Carlo-noisy at low visit counts even when the underlying
# position is calm.
_KATAGO_UNCERTAIN_MIN_VISITS = 300


def detect_katago_uncertain(ctx: SummaryHintContext) -> BeginnerHint | None:
    """Detect KataGo-uncertainty summary hint (Phase 179).

    Args:
        ctx: SummaryHintContext with score_stdev / root_visits.

    Returns:
        BeginnerHint with KATAGO_UNCERTAIN, or None.
    """
    if ctx.score_stdev is None:
        return None
    if ctx.root_visits < _KATAGO_UNCERTAIN_MIN_VISITS:
        return None

    stdev = float(ctx.score_stdev)
    threshold = float(ctx.score_stdev_threshold)
    if stdev < threshold:
        return None

    return BeginnerHint(
        category=HintCategory.KATAGO_UNCERTAIN,
        coords=None,
        severity=0,
        context={"score_stdev": stdev, "threshold": threshold},
    )


__all__ = ["detect_katago_uncertain"]

"""Phase 179: Mistake Summary Hint Detector

Derives beginner hints from the ``points_lost`` metric that was already
shown as a numerical row in the right panel.

Categories:
- MISTAKE_BLUNDER: pointsLost >= threshold_blunder (default 8.0)
- MISTAKE_MISTAKE: threshold_mistake <= pointsLost < threshold_blunder
- MISTAKE_GOOD: pointsLost < 0.5 かつ is_endgame かつ visits >= 300
                 (positive feedback; only at the very end where a single
                 good move is meaningful enough to point out)

Design notes:
- The detector is pure: takes a SummaryHintContext, returns BeginnerHint or None.
- Thresholds are passed via the context dataclass (defaults in models.py).
- Severity is set lower than structural hints (1 vs 2-3) so they never
  outrank the "あぶない手" structural warnings.
"""

from __future__ import annotations

from katrain.core.beginner.models import BeginnerHint, HintCategory, SummaryHintContext


def detect_mistake_summary(ctx: SummaryHintContext) -> BeginnerHint | None:
    """Detect Mistake / Good summary hint (Phase 179).

    Args:
        ctx: SummaryHintContext with points_lost and thresholds.

    Returns:
        BeginnerHint with MISTAKE_BLUNDER / MISTAKE_MISTAKE / MISTAKE_GOOD,
        or None when no category applies.
    """
    if ctx.points_lost is None:
        return None

    pts = max(float(ctx.points_lost), 0.0)
    blunder_t = float(ctx.score_loss_threshold_blunder)
    mistake_t = float(ctx.score_loss_threshold_mistake)

    if pts >= blunder_t:
        return BeginnerHint(
            category=HintCategory.MISTAKE_BLUNDER,
            coords=None,
            severity=2,
            context={"points_lost": pts, "threshold": blunder_t},
        )
    if pts >= mistake_t:
        return BeginnerHint(
            category=HintCategory.MISTAKE_MISTAKE,
            coords=None,
            severity=1,
            context={"points_lost": pts, "threshold": mistake_t},
        )
    if pts < 0.5 and ctx.is_endgame and ctx.root_visits >= 200:
        return BeginnerHint(
            category=HintCategory.MISTAKE_GOOD,
            coords=None,
            severity=0,
            context={"points_lost": pts, "move_number": ctx.move_number},
        )
    return None


__all__ = ["detect_mistake_summary"]


# Phase 179.1: removed unused ``_ensure_typed_dict`` placeholder helper
# and ``from typing import Any`` (no callers, no runtime effect).

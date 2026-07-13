"""Phase 182: Ownership Summary Hint Detector

Derives a beginner hint from KataGo's predicted ownership grid (territory
prediction). High one-sided ownership signals that the game is essentially
decided, which is useful teaching context for beginners who might not yet
recognize a lost position.

Category:
- OWNERSHIP_DOMINANT: |predicted_territory| >= threshold (default 0.85)

Design notes:
- Pure detector: takes a pre-normalised ``predicted_territory`` value
  (sum of ``node.ownership`` divided by cell count, range -1..+1) via
  SummaryHintContext. Returns BeginnerHint or None.
- Severity is 0 (lowest). Pure context info; never outranks mistake /
  structural hints.
- Requires ``root_visits >= 200`` for ownership stability. Below that,
  the noisy grid produces false positives (one cell out of 361 with
  confidence 0.7 is not the same as a 70%-leaning game).
- The detector doesn't know which side the mover played; the
  ``predicted_territory`` field already encodes who controls the board
  (positive = White, negative = Black from the JSON's per-cell -1..+1).
  Beginners benefit from the abstract observation ("one side dominates")
  without needing the side semantics yet.
"""

from __future__ import annotations

from katrain.core.beginner.models import BeginnerHint, HintCategory, SummaryHintContext

# Phase 182: ownership stability gate. Higher than MIN_SUMMARY_VISITS
# because ownership is a per-cell estimate that needs visits to converge.
_OWNERSHIP_MIN_VISITS = 200


def detect_ownership_dominant(ctx: SummaryHintContext) -> BeginnerHint | None:
    """Detect Ownership dominant summary hint (Phase 182).

    Args:
        ctx: SummaryHintContext with predicted_territory / root_visits.

    Returns:
        BeginnerHint with OWNERSHIP_DOMINANT, or None.
    """
    if ctx.predicted_territory is None:
        return None
    if ctx.root_visits < _OWNERSHIP_MIN_VISITS:
        return None

    value = float(ctx.predicted_territory)
    threshold = float(ctx.territory_dominant_threshold)
    if abs(value) < threshold:
        return None

    return BeginnerHint(
        category=HintCategory.OWNERSHIP_DOMINANT,
        coords=None,
        severity=0,
        context={
            "predicted_territory": value,
            "threshold": threshold,
        },
    )


__all__ = ["detect_ownership_dominant"]

"""Phase 179: Difficulty Summary Hint Detector

Derives beginner hints from ``DifficultyMetrics.overall_difficulty`` that was
already shown as 「局面難易度: 易 / 中 / 難」.

Categories:
- DIFFICULTY_TRICKY: overall_difficulty >= 0.7
- DIFFICULTY_CALM:   overall_difficulty <= 0.3

Design notes:
- Requires ``is_reliable=True`` (visits >= DIFFICULTY_MIN_VISITS=300).
  Unreliable difficulty values are noisy and would mislead beginners.
- Detector is pure: takes pre-computed DifficultyMetrics values via
  SummaryHintContext, returns BeginnerHint or None.
- Severity is 1 (informational). Lower than structural (2-3) and lower
  than Mistake_BLUNDER (2) so mistake severity still wins on display
  priority when multiple summary categories fire.
"""

from __future__ import annotations

from katrain.core.beginner.models import BeginnerHint, HintCategory, SummaryHintContext

# Phase 179: difficulty thresholds (same range as format_difficulty_metrics
# in core.analysis.presentation: < 0.3 = 易, < 0.6 = 中, else 難).
_DIFFICULTY_TRICKY_THRESHOLD = 0.7
_DIFFICULTY_CALM_THRESHOLD = 0.3


def detect_difficulty_summary(ctx: SummaryHintContext) -> BeginnerHint | None:
    """Detect Difficulty summary hint (Phase 179).

    Args:
        ctx: SummaryHintContext with overall_difficulty / is_reliable.

    Returns:
        BeginnerHint with DIFFICULTY_TRICKY or DIFFICULTY_CALM,
        or None when difficulty is unknown / unreliable.
    """
    if ctx.overall_difficulty is None:
        return None
    if not ctx.is_reliable:
        return None

    value = float(ctx.overall_difficulty)
    if value >= _DIFFICULTY_TRICKY_THRESHOLD:
        return BeginnerHint(
            category=HintCategory.DIFFICULTY_TRICKY,
            coords=None,
            severity=1,
            context={"overall_difficulty": value},
        )
    if value <= _DIFFICULTY_CALM_THRESHOLD:
        return BeginnerHint(
            category=HintCategory.DIFFICULTY_CALM,
            coords=None,
            severity=1,
            context={"overall_difficulty": value},
        )
    return None


__all__ = ["detect_difficulty_summary"]

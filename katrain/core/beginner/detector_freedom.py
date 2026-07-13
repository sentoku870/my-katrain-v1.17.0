"""Phase 179: Freedom Summary Hint Detector

Derives beginner hints from the candidate-moves histogram that was already
shown as 「手の自由度: 一択 / 狭い / 普通 / 広い」.

Categories:
- FREEDOM_ONLY_MOVE: good_moves <= 1 (only one solid candidate)
- FREEDOM_NARROW:   2 <= good_moves <= 3
- FREEDOM_WIDE:     good_moves >= 4

Design notes:
- ``count_freedom_candidates`` is the single source of truth for the
  good/near counting; both this detector and ``gui.controlspanel``'s
  numerical row import it (Phase 179.2 promotion). The thresholds
  ``GOOD_REL_THRESHOLD = 1.0`` and ``NEAR_REL_THRESHOLD = 2.0`` are the
  same ones the GUI row used inlined — promoted to module level so the
  two surfaces cannot drift apart.
- The detector is pure: takes pre-counted good/near candidate counts via
  SummaryHintContext, returns BeginnerHint or None.
- Severity is 1 (lower than structural). Freedom info is informational and
  should not override a real "あぶない手".
"""

from __future__ import annotations

from typing import Any

from katrain.core.beginner.models import BeginnerHint, HintCategory, SummaryHintContext

# Phase 179.2: candidate move classification thresholds. Used by both the
# hint detector and ``controlspanel.py``'s「手の自由度:」row so they
# cannot drift apart.
GOOD_REL_THRESHOLD: float = 1.0  # candidate with relativePointsLost <= 1.0 → "good"
NEAR_REL_THRESHOLD: float = 2.0  # candidate with relativePointsLost <= 2.0 → "near"


def count_freedom_candidates(candidate_moves: list[dict[str, Any]] | None) -> tuple[int, int]:
    """Count good/near candidates from a parent.candidate_moves list (Phase 179.2).

    Single source of truth for the freedom classification used by both the
    hint detector and the GUI's numerical row. Identical behaviour to the
    previous in-place logic in ``controlspanel.py``.

    Args:
        candidate_moves: ``parent.candidate_moves`` list (each entry is a
            dict containing ``relativePointsLost`` and/or ``pointsLost``).
            ``None`` and empty lists both yield ``(0, 0)``.

    Returns:
        ``(good_count, near_count)`` tuple. ``good_count`` is the number of
        candidates with relativePointsLost <= 1.0; ``near_count`` is the
        number of candidates with relativePointsLost <= 2.0.
    """
    if not candidate_moves:
        return 0, 0

    good_count = 0
    near_count = 0
    for mv in candidate_moves:
        rel = mv.get("relativePointsLost")
        if rel is None:
            rel = mv.get("pointsLost")
        if rel is None:
            continue
        rel_f = float(rel)
        if rel_f <= GOOD_REL_THRESHOLD:
            good_count += 1
        if rel_f <= NEAR_REL_THRESHOLD:
            near_count += 1
    return good_count, near_count


def detect_freedom_summary(ctx: SummaryHintContext) -> BeginnerHint | None:
    """Detect Freedom summary hint (Phase 179).

    Args:
        ctx: SummaryHintContext with good_move_count / near_move_count.

    Returns:
        BeginnerHint with FREEDOM_ONLY_MOVE / FREEDOM_NARROW / FREEDOM_WIDE,
        or None when good_move_count == 0 (caller didn't pass candidate data).
    """
    good = int(ctx.good_move_count)
    if good <= 0 and int(ctx.near_move_count) <= 0:
        return None

    if good <= 1:
        return BeginnerHint(
            category=HintCategory.FREEDOM_ONLY_MOVE,
            coords=None,
            severity=1,
            context={"good_moves": good, "near_moves": int(ctx.near_move_count)},
        )
    if good <= 3:
        return BeginnerHint(
            category=HintCategory.FREEDOM_NARROW,
            coords=None,
            severity=1,
            context={"good_moves": good, "near_moves": int(ctx.near_move_count)},
        )
    return BeginnerHint(
        category=HintCategory.FREEDOM_WIDE,
        coords=None,
        severity=1,
        context={"good_moves": good, "near_moves": int(ctx.near_move_count)},
    )


__all__ = [
    "GOOD_REL_THRESHOLD",
    "NEAR_REL_THRESHOLD",
    "count_freedom_candidates",
    "detect_freedom_summary",
]

"""Loss progression analysis (Phase 154-B).

Buckets a game's move-by-move loss into fixed-width move-number windows
and emits per-window aggregates. Used by the Karte/Summary "loss
progression" section to surface concentration-of-errors patterns
(e.g. mid-game focus drop).

Window convention: window ``i`` covers ``[start_move, end_move)`` where
``start_move = i * bucket_size + 1`` and ``end_move = min(start_move + bucket_size,
last_move + 1)``. The final window may be smaller when ``total_moves`` is
not a multiple of ``bucket_size``.
"""
from __future__ import annotations

from dataclasses import dataclass

from katrain.core.analysis.models.move_eval import get_canonical_loss_from_move
from katrain.core.analysis.models import MoveEval


@dataclass(frozen=True)
class LossBucket:
    """Aggregated loss statistics for a contiguous move-number window.

    Attributes:
        start_move: First move number (1-indexed, inclusive).
        end_move: Last move number (1-indexed, inclusive). May be smaller
            than ``start_move + bucket_size - 1`` for the final bucket.
        move_count: Number of moves in this window.
        total_loss: Sum of canonical loss (>= 0.0).
        avg_loss: ``total_loss / move_count`` (0.0 when empty).
        mistake_count: Number of moves whose canonical loss >= 1.0
            (mistake-or-worse). Tweak the threshold by changing
            :data:`MISTAKE_THRESHOLD` here.
    """

    start_move: int
    end_move: int
    move_count: int
    total_loss: float
    avg_loss: float
    mistake_count: int


# Threshold for counting a move as a "mistake-or-worse" in a bucket.
# Aligns with the standard preset's inaccuracy floor (1.0 point).
MISTAKE_THRESHOLD: float = 1.0


def compute_loss_progression(
    moves: list[MoveEval],
    *,
    bucket_size: int = 10,
) -> list[LossBucket]:
    """Compute per-window loss aggregates over the mainline.

    Args:
        moves: Move list in chronological order. Each entry is expected to
            carry ``points_lost`` / ``score_loss``; the canonical loss is
            used (``max(points_lost, score_loss, 0)``).
        bucket_size: Window width in move numbers. Default 10.

    Returns:
        List of :class:`LossBucket` ordered by ``start_move``. Empty when
        ``moves`` is empty.

    Notes:
        - ``move_number`` values are taken from the ``MoveEval`` instances
          directly, so any pre-filtering or re-numbering by the caller is
          preserved.
        - Windows with zero moves are omitted.
    """
    if not moves:
        return []
    if bucket_size <= 0:
        raise ValueError(f"bucket_size must be positive, got {bucket_size}")

    buckets_dict: dict[tuple[int, int], list[MoveEval]] = {}
    for mv in moves:
        start = ((mv.move_number - 1) // bucket_size) * bucket_size + 1
        end = start + bucket_size - 1
        buckets_dict.setdefault((start, end), []).append(mv)

    out: list[LossBucket] = []
    for (start, end) in sorted(buckets_dict):
        bucket_moves = buckets_dict[(start, end)]
        count = len(bucket_moves)
        total_loss = sum(get_canonical_loss_from_move(m) for m in bucket_moves)
        mistake_count = sum(
            1 for m in bucket_moves if get_canonical_loss_from_move(m) >= MISTAKE_THRESHOLD
        )
        out.append(
            LossBucket(
                start_move=start,
                end_move=min(end, max(mv.move_number for mv in bucket_moves)),
                move_count=count,
                total_loss=round(total_loss, 2),
                avg_loss=round(total_loss / count, 3) if count else 0.0,
                mistake_count=mistake_count,
            )
        )

    return out
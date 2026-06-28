"""Diagnosis section data builders for karte report (JSON output).

Phase 149 C-2: Refactored from markdown-line generators (list[str]) to JSON
data builders (list[WeaknessItem] / list[StreakItem]).
The compiled markdown is no longer produced — JSON is the canonical output
for LLM consumption and downstream tooling.

Phase 153-B: Removed `practice_priorities_for` (redundant with weaknesses).
Phase 153-C: Removed `urgent_miss_section_for` (merged into
`mistake_streaks_for`; both used the same threshold).

Functions:
- weakness_hypothesis_for(): Returns WeaknessItem list for one player
- mistake_streaks_for(): Returns StreakItem list (consecutive mistakes)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core import eval_metrics
from katrain.core.eval_metrics import (
    aggregate_phase_mistake_stats,
    detect_mistake_streaks,
    get_canonical_loss_from_move,
)

if TYPE_CHECKING:
    from katrain.core.analysis.models import MoveEval
    from katrain.core.reports.karte.sections.context import KarteContext


# Mapping from internal player color to JSON key
_PLAYER_KEY = {"B": "black", "W": "white"}


def _move_to_evidence(mv: MoveEval) -> dict[str, Any]:
    """Convert a MoveEval to a MoveEvidence dict."""
    loss = get_canonical_loss_from_move(mv)
    return {
        "move_number": mv.move_number,
        "gtp": mv.gtp or "-",
        "loss": round(loss, 2),
        "category": (mv.mistake_category.name if mv.mistake_category else "GOOD"),
    }


def _streak_to_item(s: Any) -> dict[str, Any]:
    """Convert a MistakeStreak to a StreakItem dict."""
    return {
        "start_move": s.start_move,
        "end_move": s.end_move,
        "move_count": s.move_count,
        "total_loss": round(s.total_loss, 2),
        "avg_loss": round(s.avg_loss, 2),
        "moves": [_move_to_evidence(mv) for mv in s.moves],
    }


def weakness_hypothesis_for(
    ctx: "KarteContext",
    player: str,
) -> list[dict[str, Any]]:
    """Generate weakness hypothesis data for a player (skill_preset thresholds).

    Args:
        ctx: Karte context
        player: "B" or "W"

    Returns:
        List of WeaknessItem dicts (top 2 by total_loss, excluding GOOD)
    """
    player_moves = [mv for mv in ctx.snapshot.moves if mv.player == player]
    if not player_moves:
        return []

    board_x = ctx.board_x
    preset = eval_metrics.get_skill_preset(ctx.skill_preset)
    score_thresholds = preset.score_thresholds

    stats = aggregate_phase_mistake_stats(
        player_moves,
        score_thresholds=score_thresholds,
        board_size=board_x,
    )

    sorted_combos = sorted(
        [(k, v) for k, v in stats.phase_mistake_loss.items() if k[1] != "GOOD" and v > 0],
        key=lambda x: x[1],
        reverse=True,
    )

    evidence_count = eval_metrics.get_evidence_count(ctx.confidence_level)
    confidence_str = ctx.confidence_level.name.lower()

    result: list[dict[str, Any]] = []
    for key, loss in sorted_combos[:2]:
        phase, category = key
        count = stats.phase_mistake_counts.get(key, 0)

        def phase_cat_filter(mv: Any) -> bool:
            mv_phase = mv.tag or "unknown"
            mv_cat = mv.mistake_category.name if mv.mistake_category else "GOOD"
            return mv_phase == phase and mv_cat == category

        evidence_moves = eval_metrics.select_representative_moves(
            player_moves,
            max_count=evidence_count,
            category_filter=phase_cat_filter,
        )

        result.append(
            {
                "phase": phase,
                "category": category,
                "count": count,
                "total_loss": round(loss, 2),
                "avg_loss": round(loss / count, 2) if count > 0 else 0.0,
                "confidence": confidence_str,
                "evidence": [_move_to_evidence(mv) for mv in evidence_moves],
            }
        )

    return result


def practice_priorities_for(
    ctx: "KarteContext",
    player: str,
) -> list[dict[str, Any]]:
    """Generate practice priorities data for a player.

    Phase 153-B: Returns empty list (section removed from output).
    Kept as a stub to avoid breaking callers that still import it; the
    function is scheduled for full removal in a follow-up cleanup pass.

    Args:
        ctx: Karte context (unused)
        player: "B" or "W" (unused)

    Returns:
        Empty list.
    """
    return []


def mistake_streaks_for(
    ctx: "KarteContext",
    player: str,
) -> list[dict[str, Any]]:
    """Detect and return consecutive mistake streaks for a player.

    Args:
        ctx: Karte context
        player: "B" or "W"

    Returns:
        List of StreakItem dicts (empty if no streaks detected)
    """
    player_moves = [mv for mv in ctx.snapshot.moves if mv.player == player]
    if not player_moves:
        return []

    urgent_config = eval_metrics.get_urgent_miss_config(ctx.skill_preset)
    streaks = detect_mistake_streaks(
        player_moves,
        loss_threshold=urgent_config.threshold_loss,
        min_consecutive=urgent_config.min_consecutive,
    )

    return [_streak_to_item(s) for s in streaks]
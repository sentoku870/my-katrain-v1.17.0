"""Diagnosis section data builders for karte report (JSON output).

Phase 149 C-2: Refactored from markdown-line generators (list[str]) to JSON
data builders (list[WeaknessItem] / list[PriorityItem] / list[StreakItem]).
The compiled markdown is no longer produced — JSON is the canonical output
for LLM consumption and downstream tooling.

Functions:
- weakness_hypothesis_for(): Returns WeaknessItem list for one player
- practice_priorities_for(): Returns PriorityItem list for one player
- mistake_streaks_for(): Returns StreakItem list (consecutive mistakes)
- urgent_miss_section_for(): Returns StreakItem list (urgent threshold)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core import eval_metrics
from katrain.core.eval_metrics import (
    aggregate_phase_mistake_stats,
    detect_mistake_streaks,
    get_canonical_loss_from_move,
    get_practice_priorities_from_stats,
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

    Args:
        ctx: Karte context
        player: "B" or "W"

    Returns:
        List of PriorityItem dicts (max 1 for MEDIUM, max 2 otherwise).
        Empty list when confidence is LOW or no priorities identified.
    """
    if ctx.confidence_level == eval_metrics.ConfidenceLevel.LOW:
        return []

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

    max_priorities = 1 if ctx.confidence_level == eval_metrics.ConfidenceLevel.MEDIUM else 2
    priorities = get_practice_priorities_from_stats(stats, max_priorities=max_priorities)

    result: list[dict[str, Any]] = []
    for priority_text in priorities:
        phase_key = None
        for phase_candidate in ("opening", "middle", "yose"):
            if phase_candidate in priority_text.lower():
                phase_key = phase_candidate
                break

        # Default to "middle" if no phase matched
        if phase_key is None:
            phase_key = "middle"

        category = "MISTAKE"
        # Try to extract category from priority text
        for cat_name in ("BLUNDER", "MISTAKE", "INACCURACY"):
            if cat_name.lower() in priority_text.lower():
                category = cat_name
                break

        priority_id = f"phase_{phase_key}_{category.lower()}_focus"

        # Find anchor move: worst move in this phase
        anchor_evidence: dict[str, Any] | None = None
        phase_moves = [
            mv for mv in player_moves
            if (mv.tag or "unknown") == phase_key and mv.score_loss is not None
        ]
        if phase_moves:
            anchor_move = max(
                phase_moves,
                key=lambda m: (m.score_loss or 0, -m.move_number),
            )
            anchor_loss = get_canonical_loss_from_move(anchor_move)
            if anchor_loss > 0.0:
                anchor_evidence = _move_to_evidence(anchor_move)

        result.append(
            {
                "priority_id": priority_id,
                "phase": phase_key,
                "category": category,
                "anchor_move": anchor_evidence,
            }
        )

    return result


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


def urgent_miss_section_for(
    ctx: "KarteContext",
    player: str,
) -> list[dict[str, Any]]:
    """Return urgent miss data (alias for mistake_streaks_for with urgent thresholds).

    Phase 149 C-2: Currently uses the same threshold as mistake_streaks; kept
    as separate API for future tuning.

    Args:
        ctx: Karte context
        player: "B" or "W"

    Returns:
        List of StreakItem dicts (empty if no urgent misses)
    """
    return mistake_streaks_for(ctx, player)
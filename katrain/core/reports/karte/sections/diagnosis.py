"""Diagnosis section data builders for karte report (JSON output).

Phase 149 C-2: Refactored from markdown-line generators (list[str]) to JSON
data builders (list[WeaknessItem] / list[StreakItem]).
The compiled markdown is no longer produced — JSON is the canonical output
for LLM consumption and downstream tooling.

Phase 153-B: Removed `practice_priorities_for` (redundant with weaknesses).
Phase 153-C: Removed `urgent_miss_section_for` (merged into
`mistake_streaks_for`; both used the same threshold).

Phase 158-F: weakness evidence filter re-aligned with the phase
classification used by ``aggregate_phase_mistake_stats``. Previously the
filter compared ``mv.tag`` (only set when ``dynamic_phase_detection`` is
on) against the phase key, so the ``evidence`` field was always ``[]``
when the report was generated without dynamic phase detection (the
default).

Functions:
- weakness_hypothesis_for(): Returns WeaknessItem list for one player
- mistake_streaks_for(): Returns StreakItem list (consecutive mistakes)
- weakness_by_tag_for(): Returns per-meaning-tag weakness aggregation
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core import analysis
from katrain.core.analysis import (
    aggregate_phase_mistake_stats,
    detect_mistake_streaks,
    get_canonical_loss_from_move,
)
from katrain.core.reports.constants import (
    MISTAKE_STREAK_MIN_CONSECUTIVE,
    MISTAKE_STREAK_THRESHOLD_LOSS,
)
from katrain.core.reports.definitions import PHASE_ALIASES


def _normalise_phase(phase: str) -> str:
    """Apply PHASE_ALIASES so JSON output uses public-facing names.

    PR-04d (H4): ``classify_game_phase`` and the dynamic phase detector
    can return the legacy ``"yose"`` string (kept for back-compat with
    internal callers). The Karte JSON contract documents only
    ``opening / middle / endgame`` (see docs/karte-schema.md §2.5), so
    we rewrite ``yose`` to ``endgame`` at the section boundary. Without
    this, ``weaknesses[*].phase`` could disagree with
    ``important_moves[*].phase`` in the same Karte.
    """
    return PHASE_ALIASES.get(phase, phase)


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


def _move_phase(mv: MoveEval, board_size: int) -> str:
    """Return the phase label for a move using the same classifier as
    :func:`aggregate_phase_mistake_stats` (``classify_game_phase``).

    Phase 158-F: ``aggregate_phase_mistake_stats`` writes phase keys from
    :func:`katrain.core.analysis.logic_phase.classify_game_phase`, but the
    evidence filter was reading ``mv.tag`` which is only populated when
    ``apply_dynamic_phases`` has been run. Reading the phase through the
    same classifier ensures the filter and the aggregation agree even
    without dynamic phase detection enabled.
    """
    from katrain.core.analysis import classify_game_phase

    return classify_game_phase(mv.move_number, board_size)


def weakness_hypothesis_for(
    ctx: KarteContext,
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
    preset = analysis.get_skill_preset(ctx.skill_preset)
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

    evidence_count = analysis.get_evidence_count(ctx.confidence_level)
    confidence_str = ctx.confidence_level.name.lower()

    result: list[dict[str, Any]] = []
    for key, loss in sorted_combos[:2]:
        phase, category = key
        count = stats.phase_mistake_counts.get(key, 0)

        def phase_cat_filter(
            mv: Any,
            _phase: str = phase,
            _category: str = category,
            _board: int = board_x,
        ) -> bool:
            return (
                _move_phase(mv, _board) == _phase
                and (mv.mistake_category.name if mv.mistake_category else "GOOD") == _category
            )

        evidence_moves = analysis.select_representative_moves(
            player_moves,
            max_count=evidence_count,
            category_filter=phase_cat_filter,
        )

        result.append(
            {
                "phase": _normalise_phase(phase),
                "category": category,
                "count": count,
                "total_loss": round(loss, 2),
                "avg_loss": round(loss / count, 2) if count > 0 else 0.0,
                "confidence": confidence_str,
                "evidence": [_move_to_evidence(mv) for mv in evidence_moves],
            }
        )

    return result


def mistake_streaks_for(
    ctx: KarteContext,
    player: str,
) -> list[dict[str, Any]]:
    """Detect and return consecutive mistake streaks for a player.

    Phase 158-F: use the mistake-level threshold
    (``MISTAKE_STREAK_THRESHOLD_LOSS`` = 2.0 points, min 2 consecutive
    moves) instead of the urgent-miss collapse threshold. The previous
    configuration only fired for catastrophic 20+ point life-and-death
    misses, which made the section effectively empty for sub-5-dan games.

    Args:
        ctx: Karte context
        player: "B" or "W"

    Returns:
        List of StreakItem dicts (empty if no streaks detected)
    """
    player_moves = [mv for mv in ctx.snapshot.moves if mv.player == player]
    if not player_moves:
        return []

    streaks = detect_mistake_streaks(
        player_moves,
        loss_threshold=MISTAKE_STREAK_THRESHOLD_LOSS,
        min_consecutive=MISTAKE_STREAK_MIN_CONSECUTIVE,
    )

    return [_streak_to_item(s) for s in streaks]


def weakness_by_tag_for(
    ctx: KarteContext,
    player: str,
    *,
    top_n: int = 3,
) -> list[dict[str, Any]]:
    """Aggregate the player's important mistakes by meaning tag (schema 3.5).

    The phase x category view (``weaknesses``) tells the LLM *when* the
    mistakes happened and *how big* they were, but not *what kind* of
    mistake they were ("opening BLUNDER x2" is weak coaching material).
    This section aggregates the same player's classified important moves
    by ``meaning_tag_id`` (12 diagnostic categories such as
    ``life_death_error`` / ``direction_error``), so the LLM can say
    e.g. "life-and-death misreads: 3 moves, 15.0 points total".

    Pool: ``ctx.important_moves`` for ``player`` with a non-None
    ``meaning_tag_id`` (these are the moves that already received the
    board-aware classification). Tags are ranked by total loss; ties
    break on tag id for determinism.

    Args:
        ctx: Karte context
        player: "B" or "W"
        top_n: Maximum tag buckets returned (default 3)

    Returns:
        List of WeaknessTagItem dicts (empty when no tagged mistakes).
    """
    tag_moves: dict[str, list[MoveEval]] = {}
    for mv in ctx.important_moves:
        if mv.player != player:
            continue
        tag = mv.meaning_tag_id
        if not tag:
            continue
        tag_moves.setdefault(tag, []).append(mv)

    if not tag_moves:
        return []

    def _total_loss(moves: list[MoveEval]) -> float:
        return sum(get_canonical_loss_from_move(mv) for mv in moves)

    # (total_loss desc, tag asc) for a deterministic ranking
    ranked = sorted(
        tag_moves.items(),
        key=lambda kv: (-_total_loss(kv[1]), kv[0]),
    )

    evidence_count = analysis.get_evidence_count(ctx.confidence_level)

    result: list[dict[str, Any]] = []
    for tag, moves in ranked[:top_n]:
        total = _total_loss(moves)
        evidence_moves = analysis.select_representative_moves(moves, max_count=evidence_count)
        result.append(
            {
                "tag": tag,
                "count": len(moves),
                "total_loss": round(total, 2),
                "avg_loss": round(total / len(moves), 2) if moves else 0.0,
                "evidence": [_move_to_evidence(mv) for mv in evidence_moves],
            }
        )

    return result

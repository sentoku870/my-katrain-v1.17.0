"""Important moves section data builders for karte report (JSON output).

Phase 149 C-2: Refactored from markdown-line generators (list[str]) to JSON
data builders.

Functions:
- get_context_info_for_move(): Returns context dict (kept as helper)
- reason_tags_distribution_for(): Returns dict[str, int] of tag counts
- critical_3_section_for(): Returns list[CriticalMoveItem] for focused review

Note: important_lines_for() was REMOVED in Phase 149 C-2 because its output
is functionally equivalent to build_karte_json's `important_moves` block
already emitted at the top level. The dead code was redundant.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from katrain.core import eval_metrics
from katrain.core.analysis.cluster_classifier import (
    StoneCache,
    _get_cluster_context_for_move,
)
from katrain.core.analysis.critical_moves import select_critical_moves
from katrain.core.analysis.meaning_tags import get_meaning_tag_label_safe
from katrain.core.batch.stats import get_area_from_gtp
from katrain.core.constants import OUTPUT_DEBUG
from katrain.core.eval_metrics import classify_mistake, get_canonical_loss_from_move
from katrain.common.locale_utils import to_iso_lang_code

if TYPE_CHECKING:
    from katrain.core.analysis.models import MoveEval
    from katrain.core.reports.karte.sections.context import KarteContext

logger = logging.getLogger(__name__)


def get_context_info_for_move(game: Any, move_eval: MoveEval) -> dict[str, Any]:
    """Extract context info (candidates, best gap, danger, best move) for a move.

    CRITICAL FIX: Best move and candidates are extracted from PRE-MOVE node
    (node.parent), not the post-move node. This ensures we see the candidate
    moves that were available BEFORE the move was played.

    Args:
        game: Game object
        move_eval: MoveEval to get context for

    Returns:
        Dict with keys: candidates, best_gap, danger, best_move
    """
    context: dict[str, Any] = {
        "candidates": None,
        "best_gap": None,
        "danger": None,
        "best_move": None,
    }

    try:
        node = game._find_node_by_move_number(move_eval.move_number)
        if not node:
            return context

        # CRITICAL: Use parent node for candidate moves (PRE-MOVE position)
        parent_node = getattr(node, "parent", None)

        if parent_node and hasattr(parent_node, "candidate_moves"):
            candidate_moves = parent_node.candidate_moves
            if candidate_moves:
                context["candidates"] = len(candidate_moves)

                # Best move is the first candidate (order=0)
                if candidate_moves:
                    best_candidate = candidate_moves[0]
                    context["best_move"] = best_candidate.get("move")

                # Best gap: find the played move in parent's candidates
                actual_move_gtp = move_eval.gtp
                if actual_move_gtp:
                    for candidate in candidate_moves:
                        if candidate.get("move") == actual_move_gtp:
                            winrate_lost = candidate.get("winrateLost")
                            if winrate_lost is not None:
                                context["best_gap"] = winrate_lost
                            break

        # Danger assessment from board_analysis - uses current node
        from katrain.core import board_analysis

        board_state = board_analysis.analyze_board_at_node(game, node)

        # Max danger of player's groups
        player = move_eval.player
        if player:
            my_groups = [g for g in board_state.groups if g.color == player]
            if my_groups:
                max_danger = max(
                    (board_state.danger_scores.get(g.group_id, 0) for g in my_groups),
                    default=0,
                )
                if max_danger >= 50:
                    context["danger"] = "High"
                elif max_danger >= 25:
                    context["danger"] = "Mid"
                else:
                    context["danger"] = "Low"

    except KeyError as e:
        # Expected: SGF tree structure issue (missing node data)
        if game.katrain:
            game.katrain.log(
                f"Context extraction skipped for move #{move_eval.move_number}: {e}",
                OUTPUT_DEBUG,
            )
    except Exception as e:
        # Unexpected: Internal bug - traceback required
        import traceback

        if game.katrain:
            game.katrain.log(
                f"Unexpected context error for move #{move_eval.move_number}: {e}\n{traceback.format_exc()}",
                OUTPUT_DEBUG,
            )

    return context


def reason_tags_distribution_for(
    ctx: "KarteContext",
    player: str,
) -> dict[str, int]:
    """Generate reason tags distribution for a player's important moves.

    Phase 149 C-2: Returns plain dict[str, int] (tag -> count) for JSON.
    Aliases are normalized via REASON_CODE_ALIASES so that downstream
    consumers see consistent tag IDs.

    Args:
        ctx: Karte context
        player: "B" or "W"

    Returns:
        Dict mapping tag_id -> count of occurrences across the player's
        important moves. Empty dict when no tags detected.
    """
    player_moves = [mv for mv in ctx.important_moves if mv.player == player]

    counts: dict[str, int] = {}
    for mv in player_moves:
        for tag in mv.reason_tags or []:
            counts[tag] = counts.get(tag, 0) + 1

    return counts


def critical_3_section_for(
    ctx: "KarteContext",
    player: str,
    level: str,
) -> list[dict[str, Any]]:
    """Generate Critical 3 section data for focused review (Phase 50).

    Selects top critical mistakes via select_critical_moves() and returns
    them as JSON-serializable dicts.

    Args:
        ctx: Karte context
        player: "B" or "W"
        level: Important move level setting

    Returns:
        List of CriticalMoveItem dicts (empty if no critical moves).
    """
    try:
        critical_moves = select_critical_moves(
            ctx.game,
            max_moves=3,
            lang=ctx.lang,
            level=level,
        )
    except KeyError as exc:
        # Expected: Game data structure issue
        if ctx.game.katrain:
            ctx.game.katrain.log(f"Critical 3 skipped: {exc}", OUTPUT_DEBUG)
        return []
    except Exception as exc:
        # Unexpected: Internal bug - traceback required
        import traceback

        if ctx.game.katrain:
            ctx.game.katrain.log(f"Unexpected Critical 3 error: {exc}\n{traceback.format_exc()}", OUTPUT_DEBUG)
        return []

    player_critical = [cm for cm in critical_moves if cm.player == player]
    if not player_critical:
        return []

    # Phase 82: Create cache for stone positions (shared across Critical Moves)
    stone_cache = StoneCache(ctx.game)

    iso_lang = to_iso_lang_code(ctx.lang)
    result: list[dict[str, Any]] = []
    for cm in player_critical:
        try:
            area = get_area_from_gtp(cm.gtp_coord, ctx.game.board_size)
        except Exception:
            area = None

        # Phase 149 C-2: Meaning tag label is informational only
        # (LLMs can resolve IDs from meta.definitions.primary_tags).
        # We include it for backward compatibility with existing LLM
        # consumers but the ID is the canonical field.
        meaning_tag_label = (
            get_meaning_tag_label_safe(cm.meaning_tag_id, iso_lang) if cm.meaning_tag_id else None
        )
        if not meaning_tag_label:
            meaning_tag_label = None

        result.append(
            {
                "move_number": cm.move_number,
                "gtp_coord": cm.gtp_coord,
                "player": cm.player,
                "score_loss": round(cm.score_loss, 2),
                "meaning_tag_id": cm.meaning_tag_id,
                "meaning_tag_label": meaning_tag_label,
                "game_phase": cm.game_phase,
                "position_difficulty": cm.position_difficulty.lower() if cm.position_difficulty else "unknown",
                "area": area,
                "reason_tags": list(cm.reason_tags) if cm.reason_tags else [],
                "complexity_discounted": bool(cm.complexity_discounted),
            }
        )

    return result
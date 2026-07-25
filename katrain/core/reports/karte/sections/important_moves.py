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

from katrain.common.locale_utils import to_iso_lang_code
from katrain.core.analysis.cluster_classifier import (
    StoneCache,
)
from katrain.core.analysis.critical_moves import select_critical_moves
from katrain.core.analysis.meaning_tags import get_meaning_tag_label_safe
from katrain.core.batch.stats import get_area_from_gtp
from katrain.core.constants.output import OUTPUT_DEBUG, OUTPUT_INFO
from katrain.core.reports.definitions import REASON_CODE_ALIASES

if TYPE_CHECKING:
    from katrain.core.analysis.models import MoveEval
    from katrain.core.reports.karte.sections.context import KarteContext

logger = logging.getLogger(__name__)


def get_best_move_gtp(game: Any, move_number: int) -> str | None:
    """Return KataGo's best move (GTP) for the position BEFORE ``move_number``.

    The candidate list of the *pre-move* node (``node.parent``) holds the
    moves KataGo considered for that position; the first candidate is the
    best one (order=0). This is the same pattern as
    :func:`get_context_info_for_move` (see its "CRITICAL FIX" comment).

    Args:
        game: Game object
        move_number: Target move number (1-indexed)

    Returns:
        GTP string of the best move, or None when the node / pre-move
        analysis is unavailable (never raises).
    """
    try:
        node = game._find_node_by_move_number(move_number)
        if not node:
            return None
        parent_node = getattr(node, "parent", None)
        if parent_node is None:
            return None
        candidate_moves = getattr(parent_node, "candidate_moves", None)
        if not candidate_moves:
            return None
        best = candidate_moves[0].get("move")
        return str(best) if best is not None else None
    except Exception:
        logger.debug("get_best_move_gtp failed for move #%s", move_number, exc_info=True)
        return None


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
    ctx: KarteContext,
    player: str,
) -> dict[str, int]:
    """Generate reason tags distribution for a player's important moves.

    Phase 149 C-2: Returns plain dict[str, int] (tag -> count) for JSON.
    Aliases are normalized via REASON_CODE_ALIASES so that downstream
    consumers see consistent tag IDs.

    Phase 158-F: applied ``REASON_CODE_ALIASES`` here too (Summary was
    already doing this). Without it, Karte emitted long-form names
    (``low_liberties``, ``need_connect``) while Summary used the short
    form (``liberties``, ``connection``) for the same concept, breaking
    downstream LLM tooling that joins the two datasets.

    Args:
        ctx: Karte context
        player: "B" or "W"

    Returns:
        Dict mapping tag_id -> count of occurrences across the player's
        important moves. Empty dict when no tags detected.
    """
    from katrain.core.reports.definitions import REASON_CODE_ALIASES

    player_moves = [mv for mv in ctx.important_moves if mv.player == player]

    counts: dict[str, int] = {}
    for mv in player_moves:
        for tag in mv.reason_tags or []:
            normalized = REASON_CODE_ALIASES.get(tag, tag)
            counts[normalized] = counts.get(normalized, 0) + 1

    return counts


def critical_3_section_for(
    ctx: KarteContext,
    player: str,
    level: str,
    max_moves: int = 3,
) -> list[dict[str, Any]]:
    """Generate Critical 3 section data for focused review (Phase 50).

    Selects top critical mistakes via :func:`select_critical_moves` and
    returns them as JSON-serializable dicts.

    Phase 158-G: pass ``player_filter=player`` so the greedy selector
    picks from this player's candidates only. The previous global pick
    could allocate all 3 slots to the opponent if they had higher-loss
    mistakes, leaving the requested player's section empty.

    Phase 158-H: pass ``pre_classified_moves=ctx.important_moves`` so
    the same MeaningTag / ReasonTag classification used by
    ``important_moves`` is reused here. Without this, the Critical 3
    re-classifier ran its own (board-less) classifier and frequently
    reported ``"uncertain"`` while ``important_moves`` had already
    attached ``"life_death_error"`` (etc.) for the same move.

    Phase 248-B2: ``max_moves`` is now parameterised so users can pick
    the number of critical moves shown per player in the Karte
    critical_3 section. Defaults to 3 to match the Phase 50 baseline.

    Args:
        ctx: Karte context
        player: "B" or "W"
        player: "B" or "W"
        level: Important move level setting

    Returns:
        List of CriticalMoveItem dicts (empty if no critical moves).
    """
    try:
        critical_moves = select_critical_moves(
            ctx.game,
            max_moves=max_moves,
            lang=ctx.lang,
            level=level,
            player_filter=player,
            pre_classified_moves=ctx.important_moves,
        )
    except KeyError as exc:
        # Expected: Game data structure issue.
        # Phase 248-F1: surface at INFO level instead of silently
        # swallowing the failure at DEBUG. Users with default logging
        # used to see "Critical 3: 0 件" and have no idea why; now
        # they get a one-line reason in the log.
        if ctx.game.katrain:
            ctx.game.katrain.log(
                f"Critical 3 skipped (KeyError, {player}): {exc}",
                OUTPUT_INFO,
            )
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
    StoneCache(ctx.game)

    # Phase 158-F: ``get_area_from_gtp`` expects an int board size, but
    # ``ctx.game.board_size`` returns a ``(width, height)`` tuple. Pass
    # the width explicitly so the function actually classifies the move
    # instead of raising TypeError (which was silently swallowed).
    game_board_size = ctx.game.board_size
    if isinstance(game_board_size, (tuple, list)) and game_board_size:
        area_board_size = game_board_size[0]
    else:
        area_board_size = int(game_board_size or 19)

    iso_lang = to_iso_lang_code(ctx.lang)
    result: list[dict[str, Any]] = []
    for cm in player_critical:
        try:
            area = get_area_from_gtp(cm.gtp_coord, area_board_size)
        except Exception:
            logger.debug("get_area_from_gtp label extraction", exc_info=True)
            area = None

        # Phase 149 C-2: Meaning tag label is informational only
        # (LLMs can resolve IDs from meta.definitions.primary_tags).
        # We include it for backward compatibility with existing LLM
        # consumers but the ID is the canonical field.
        meaning_tag_label = get_meaning_tag_label_safe(cm.meaning_tag_id, iso_lang) if cm.meaning_tag_id else None
        if not meaning_tag_label:
            meaning_tag_label = None

        # Schema 3.5: KataGo's best move for the pre-move position, so
        # the LLM coach can state the correct direction without
        # inventing coordinates.
        best_move = get_best_move_gtp(ctx.game, cm.move_number)

        # Normalize reason tags through the same alias map used by
        # ``important_moves`` so both sections speak the same vocabulary
        # (e.g. ``heavy_loss`` -> ``heavy``).
        normalized_reason_tags = (
            sorted({REASON_CODE_ALIASES.get(t, t) for t in cm.reason_tags}) if cm.reason_tags else []
        )

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
                "reason_tags": normalized_reason_tags,
                "complexity_discounted": bool(cm.complexity_discounted),
                "best_move": best_move,
            }
        )

    return result

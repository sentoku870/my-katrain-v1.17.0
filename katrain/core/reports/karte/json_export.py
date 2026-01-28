"""JSON export for karte report.

Contains:
- build_karte_json(): Build JSON-serializable karte structure for LLM consumption
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from katrain.core import eval_metrics
from katrain.core.analysis.meaning_tags import (
    ClassificationContext,
    classify_meaning_tag,
    get_meaning_tag_label_safe,
)
from katrain.core.eval_metrics import (
    classify_game_phase,
    classify_mistake,
    get_canonical_loss_from_move,
)


def build_karte_json(
    game: Any,  # Game object (Protocol in future)
    level: str = eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL,
    player_filter: Optional[str] = None,
    skill_preset: str = eval_metrics.DEFAULT_SKILL_PRESET,
    lang: str = "ja",
) -> Dict[str, Any]:
    """Build a JSON-serializable karte structure for LLM consumption.

    Phase 23 PR #2: LLM用JSON出力オプション
    Phase 47: Added meaning_tag to important_moves

    Args:
        game: Game object providing game state and analysis data
        level: Important move level setting
        player_filter: Filter by player ("B", "W", or None for both)
        skill_preset: Skill preset for strictness
        lang: Language code for localized labels ("ja" or "en"), defaults to "ja".

    Returns:
        Dict with schema_version, meta, summary, and important_moves.

    Example output:
        {
            "schema_version": "1.0",
            "meta": {
                "game_name": "game1.sgf",
                "date": "2024-01-15",
                "players": {"black": "Player1", "white": "Player2"},
                "result": "B+5.5",
                "skill_preset": "standard",
                "units": {
                    "points_lost": "目数（着手前評価 - 着手後評価、手番視点で正規化、常に0以上）"
                }
            },
            "summary": {
                "total_moves": 250,
                "total_points_lost": {"black": 15.3, "white": 12.7},
                "mistake_distribution": {
                    "black": {"good": 100, "inaccuracy": 15, "mistake": 5, "blunder": 2},
                    "white": {"good": 105, "inaccuracy": 12, "mistake": 4, "blunder": 1}
                }
            },
            "important_moves": [
                {
                    "move_number": 45,
                    "player": "black",
                    "coords": "D4",
                    "points_lost": 3.2,
                    "importance": 4.5,
                    "reason_tags": ["shape_mistake"],
                    "phase": "middle"
                }
            ]
        }
    """
    snapshot = game.build_eval_snapshot()
    moves = list(snapshot.moves)
    board_x, board_y = game.board_size

    # Get effective preset and thresholds
    effective_preset = skill_preset
    if skill_preset == "auto":
        focus_moves = moves
        auto_rec = eval_metrics.recommend_auto_strictness(focus_moves, game_count=1)
        effective_preset = auto_rec.recommended_preset

    preset = eval_metrics.get_skill_preset(effective_preset)
    score_thresholds = preset.score_thresholds

    # Meta section
    def get_property(prop: str, default: Optional[str] = None) -> Optional[str]:
        val = game.root.get_property(prop, default)
        return val if val not in [None, ""] else default

    game_name = os.path.splitext(os.path.basename(game.sgf_filename or ""))[0]
    if not game_name:
        game_name = get_property("GN") or game.game_id or "unknown"

    meta = {
        "game_name": game_name,
        "date": get_property("DT"),
        "players": {
            "black": get_property("PB", "unknown"),
            "white": get_property("PW", "unknown"),
        },
        "result": get_property("RE"),
        "skill_preset": effective_preset,
        "units": {
            "points_lost": "目数（着手前評価 - 着手後評価、手番視点で正規化、常に0以上）"
        },
    }

    # Summary section
    def compute_summary_for(player: str) -> Tuple[float, Dict[str, int]]:
        player_moves = [m for m in moves if m.player == player]
        total_lost = sum(
            max(0.0, m.points_lost)
            for m in player_moves
            if m.points_lost is not None
        )

        # Count by mistake category
        counts: Dict[str, int] = {"good": 0, "inaccuracy": 0, "mistake": 0, "blunder": 0}
        for m in player_moves:
            loss = get_canonical_loss_from_move(m)
            cat = classify_mistake(
                score_loss=loss, winrate_loss=None, score_thresholds=score_thresholds
            )
            key = cat.value.lower()
            if key in counts:
                counts[key] += 1

        return total_lost, counts

    black_lost, black_counts = compute_summary_for("B")
    white_lost, white_counts = compute_summary_for("W")

    summary = {
        "total_moves": len(moves),
        "total_points_lost": {
            "black": round(black_lost, 1),
            "white": round(white_lost, 1),
        },
        "mistake_distribution": {
            "black": black_counts,
            "white": white_counts,
        },
    }

    # Important moves section
    important_move_evals = game.get_important_move_evals(level=level)

    # Phase 47: Classify meaning tags for each important move
    total_moves_for_ctx = len(moves)
    classification_context = ClassificationContext(total_moves=total_moves_for_ctx)
    for mv in important_move_evals:
        if mv.meaning_tag_id is None:
            meaning_tag = classify_meaning_tag(mv, context=classification_context)
            mv.meaning_tag_id = meaning_tag.id.value

    # Apply player filter if specified
    if player_filter in ("B", "W"):
        important_move_evals = [
            m for m in important_move_evals if m.player == player_filter
        ]

    important_moves_list: List[Dict[str, Any]] = []
    for mv in important_move_evals:
        # Coords: handle pass and normal moves
        coords: Optional[str] = None
        if mv.gtp:
            if mv.gtp.lower() == "pass":
                coords = "pass"
            else:
                coords = mv.gtp

        # points_lost: use get_canonical_loss_from_move for consistency
        points_lost = get_canonical_loss_from_move(mv)

        # importance score
        importance = mv.importance_score if mv.importance_score is not None else 0.0

        # reason_tags
        reason_tags = list(mv.reason_tags) if mv.reason_tags else []

        # phase: use classify_game_phase
        try:
            phase = classify_game_phase(mv.move_number, board_x)
        except ValueError:
            # Expected: Invalid move number or board size
            phase = "unknown"
        except Exception:
            # Unexpected: Internal bug - traceback required
            import logging
            logging.getLogger(__name__).debug(
                f"Unexpected phase classification error for move {mv.move_number}",
                exc_info=True
            )
            phase = "unknown"

        # Phase 47: Get meaning tag info
        meaning_tag_id = mv.meaning_tag_id
        meaning_tag_label = get_meaning_tag_label_safe(meaning_tag_id, lang)

        important_moves_list.append(
            {
                "move_number": mv.move_number,
                "player": (
                    "black" if mv.player == "B" else "white" if mv.player == "W" else None
                ),
                "coords": coords,
                "points_lost": round(points_lost, 1),
                "importance": round(importance, 2),
                "reason_tags": reason_tags,
                "phase": phase,
                "meaning_tag": (
                    {
                        "id": meaning_tag_id,
                        "label": meaning_tag_label,
                    }
                    if meaning_tag_id
                    else None
                ),
            }
        )

    return {
        "schema_version": "1.0",
        "meta": meta,
        "summary": summary,
        "important_moves": important_moves_list,
    }

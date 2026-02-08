"""JSON export for karte report.

Contains:
- build_karte_json(): Build JSON-serializable karte structure for LLM consumption
"""

from __future__ import annotations

import os
from typing import Any

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
    player_filter: str | None = None,
    skill_preset: str = eval_metrics.DEFAULT_SKILL_PRESET,
    lang: str = "ja",
) -> dict[str, Any]:
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

    # Helper to get safe properties
    def get_property(prop: str, default: str | None = None) -> str | None:
        val = game.root.get_property(prop, default)
        return val if val not in [None, ""] else default

    # Identifiers
    # Generated at (timestamp)
    import time
    from datetime import datetime
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_id = f"run_{int(time.time())}"

    # Game ID: Unique identifier for the game itself (not this run)
    # Prefer SGF-derived ID or filename-based hash if possible
    game_uid = game.game_id or "unknown" 
    game_filename = os.path.basename(game.sgf_filename or "")
    if not game_filename:
        game_filename = get_property("GN") or "unknown_game.sgf"
    
    # 2) Definitions as data
    # Gather potential tags for definitions from MeaningTagId Enum
    from katrain.core.analysis.meaning_tags import MeaningTagId
    primary_tags_list = [tag.value for tag in MeaningTagId]
    
    # Gather reason codes from known board analysis tags
    # These are the actual reason tags that can appear in MoveEval.reason_tags
    reason_codes_list = [
        "shape", "atari", "clump", "heavy", "overconcentrated", "liberties",
        "endgame_hint", "connection", "urgent", "tenuki", "cut_risk",
        "thin", "chase_mode", "reading"
    ]

    # Phase thresholds based on board size (extract from classify_game_phase logic)
    phase_thresholds = {
        "opening_max": 50,  # <= 50 is opening (inclusive)
        "middle_max": 200,  # <= 200 is middle (inclusive)
        "endgame_min": 201, # > 200 is endgame
    }

    definitions = {
        "thresholds": {
            "loss": {
                "inaccuracy": score_thresholds[0],
                "mistake": score_thresholds[1],
                "blunder": score_thresholds[2],
            },
            "phase": phase_thresholds,
        },
        "mistake_types": [cat.value.lower() for cat in eval_metrics.MistakeCategory],
        "difficulty_levels": [d.value.lower() for d in eval_metrics.PositionDifficulty],
        "phases": ["opening", "middle", "endgame"],  # Canonical phase names
        "phase_aliases": {"yose": "endgame"},  # Internal name mappings
        "category_aliases": {
            "inaccuracy": "inaccuracy",
            "mistake": "mistake",
            "blunder": "blunder"
        },
        "reason_code_aliases": {
            "low_liberties": "liberties",
            "need_connect": "connection",
            "heavy_loss": "heavy",
            "reading_failure": "reading",
            "shape_mistake": "shape",
            "endgame_slip": "endgame_hint",
            "cut_risk": "cut_risk",
            "thin": "thin",
            "chase_mode": "chase_mode"
        },
        "primary_tags": primary_tags_list,
        "reason_codes": reason_codes_list,
        "importance": {
            "scale": "0.0 to 10.0+",
            "description": "Move interestingness score derived from loss and semantic tags",
            "thresholds": {
                "interesting": 1.0,
                "important": 3.0,
                "critical": 6.0
            }
        },
    }

    meta = {
        "game_id": game_uid,
        "generated_at": generated_at,
        "run_id": run_id,
        "source_filename": game_filename,
        "date": get_property("DT"),
        "players": {
            "black": get_property("PB", "unknown"),
            "white": get_property("PW", "unknown"),
        },
        "result": get_property("RE"),
        "komi": game.komi,
        "handicap": getattr(game.root, 'handicap', 0),
        "board_size": [board_x, board_y],
        "skill_preset": effective_preset,
        "loss_unit": "territory_points",
        "definitions": definitions,
        "derived_flags": [],
    }

    # Summary section (Unchanged logic, just ensure consistency)
    def compute_summary_for(player: str) -> tuple[float, dict[str, int]]:
        player_moves = [m for m in moves if m.player == player]
        total_lost = sum(max(0.0, m.points_lost) for m in player_moves if m.points_lost is not None)

        # Count by mistake category
        counts: dict[str, int] = {cat.value.lower(): 0 for cat in eval_metrics.MistakeCategory}
        for m in player_moves:
            loss = get_canonical_loss_from_move(m)
            cat = classify_mistake(score_loss=loss, winrate_loss=None, score_thresholds=score_thresholds)
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

    # Apply player filter if specified
    if player_filter in ("B", "W"):
        important_move_evals = [m for m in important_move_evals if m.player == player_filter]

    # Classify meaning tags
    total_moves_for_ctx = len(moves)
    classification_context = ClassificationContext(total_moves=total_moves_for_ctx)
    for mv in important_move_evals:
        if mv.meaning_tag_id is None:
            meaning_tag = classify_meaning_tag(mv, context=classification_context)
            mv.meaning_tag_id = meaning_tag.id.value

    important_moves_list: list[dict[str, Any]] = []
    for mv in important_move_evals:
        # Coords
        coords: str | None = None
        if mv.gtp:
            coords = "pass" if mv.gtp.lower() == "pass" else mv.gtp

        # 9) Raw and Clamped Loss
        loss_clamped = get_canonical_loss_from_move(mv)
        loss_raw = mv.points_lost if mv.points_lost is not None else mv.score_loss
        
        # importance score
        importance = mv.importance_score if mv.importance_score is not None else 0.0

        # 7) Reason codes (Normalized v6)
        raw_reason_codes = list(mv.reason_tags) if mv.reason_tags else []
        reason_codes = sorted(list(set(definitions["reason_code_aliases"].get(c, c) for c in raw_reason_codes)))
        
        # phase
        try:
            phase = classify_game_phase(mv.move_number, board_x)
            # Map internal "yose" to canonical "endgame" for JSON output
            if phase == "yose":
                phase = "endgame"
        except Exception:
            phase = "unknown"

        # 4) Unified mistake_type
        mistake_cat = classify_mistake(score_loss=loss_clamped, winrate_loss=None, score_thresholds=score_thresholds)
        
        # Meaning tag
        meaning_tag_id = mv.meaning_tag_id

        move_data = {
            "move_number": mv.move_number,
            "player": ("black" if mv.player == "B" else "white" if mv.player == "W" else "unknown"),
            "coords": coords,
            "loss_clamped": round(loss_clamped, 2),
            "loss_raw": round(loss_raw, 2) if loss_raw is not None else None,
            "importance": round(importance, 2),
            "mistake_type": mistake_cat.value.lower(), # Unified
            "phase": phase,
            "difficulty": mv.position_difficulty.value.lower() if mv.position_difficulty else "unknown", # Unified: "only"
            "reason_codes": reason_codes,
            "primary_tag": meaning_tag_id,
            "derived_flags": [],
        }

        important_moves_list.append(move_data)

    return {
        "schema_version": "2.0",
        "meta": meta,
        "summary": summary,
        "important_moves": important_moves_list,
    }

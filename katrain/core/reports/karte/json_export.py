"""JSON export for karte report.

Contains:
- build_karte_json(): Build JSON-serializable karte structure for LLM consumption
"""

from __future__ import annotations

import os
import time
import hashlib
from datetime import datetime
from typing import Any

from katrain.core import eval_metrics
from katrain.core.analysis.meaning_tags import (
    ClassificationContext,
    classify_meaning_tag,
)
from katrain.core.eval_metrics import (
    classify_mistake,
    get_canonical_loss_from_move,
)
from katrain.core.reports.definitions import (
    REPORT_SCHEMA_VERSION,
    REPORT_THRESHOLDS,
    MISTAKE_TYPES,
    DIFFICULTY_LEVELS,
    PHASES,
    PHASE_ALIASES,
    PRIMARY_TAGS,
    REASON_CODES,
    REASON_CODE_ALIASES,
    IMPORTANCE_DEF,
    CATEGORY_ALIASES,
)
from katrain.core.reports.schema import (
    KarteReport,
    Definitions,
    MetaData,
    MistakeItem,
)
from katrain.core.reports.extractors import MetaExtractor, MoveExtractor


def build_karte_json(
    game: Any,  # Game object (Protocol in future)
    level: str = eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL,
    player_filter: str | None = None,
    skill_preset: str = eval_metrics.DEFAULT_SKILL_PRESET,
    lang: str = "ja",
) -> KarteReport:
    """Build a JSON-serializable karte structure for LLM consumption.
    
    Args:
        game: Game object providing game state and analysis data
        level: Important move level setting
        player_filter: Filter by player ("B", "W", or None for both)
        skill_preset: Skill preset for strictness
        lang: Language code for localized labels ("ja" or "en"), defaults to "ja".

    Returns:
        KarteReport dict
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
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    game_uid = game.game_id or "unknown" 
    game_filename = os.path.basename(game.sgf_filename or "")
    if not game_filename:
        game_filename = get_property("GN") or "unknown_game.sgf"

    # Run ID
    ts = int(time.time())
    run_hash = hashlib.md5(f"{ts}{game_uid}".encode()).hexdigest()[:8]
    run_id = f"run_{ts}_{run_hash}"
    
    # Definitions (using centralized constants where possible)
    # Note: Karte has some specific requirements like category_aliases
    definitions: Definitions = {
        "thresholds": REPORT_THRESHOLDS,
        "mistake_types": MISTAKE_TYPES,
        "difficulty_levels": DIFFICULTY_LEVELS,
        "phases": PHASES,
        "phase_aliases": PHASE_ALIASES,
        "category_aliases": CATEGORY_ALIASES,
        "reason_code_aliases": REASON_CODE_ALIASES,
        "primary_tags": PRIMARY_TAGS,
        "reason_codes": REASON_CODES,
        "importance": IMPORTANCE_DEF,
    }

    # Meta
    # Use MetaExtractor for common fields, then extend
    common_meta = MetaExtractor.extract_game_meta(game, game_id=game_uid)
    
    meta: MetaData = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "game_id": game_uid,
        "generated_at": generated_at,
        "run_id": run_id,
        "source_filename": game_filename,
        "date": common_meta["date"],
        "players": common_meta["players"],
        "result": common_meta["result"],
        "komi": common_meta["komi"],
        "handicap": common_meta["handicap"],
        "board_size": common_meta["board_size"],
        "skill_preset": effective_preset,
        "loss_unit": "territory_points",
        "definitions": definitions,
        "date_range": None # Not applicable for single game karte
    }

    # Summary section (Unchanged logic, kept local as it's specific aggregation)
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

    # Use MoveExtractor for consistent output
    important_moves_list: list[MistakeItem] = []
    for mv in important_move_evals:
        item = MoveExtractor.extract(mv, game_id=game_uid, game_name=common_meta["name"], board_size=board_x)
        important_moves_list.append(item)

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "meta": meta,
        "summary": summary,
        "important_moves": important_moves_list,
    }

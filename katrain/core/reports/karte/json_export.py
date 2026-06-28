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
from katrain.core.analysis import _build_node_map
from katrain.core.analysis.meaning_tags import (
    build_classification_context_from_node,
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
    target_visits: int | None = None,
    include_definitions: bool = False,
) -> dict[str, Any]:
    """Build a JSON-serializable karte structure for LLM consumption.

    Phase 149 C-3: Extended to include the revived sections (weaknesses,
    practice_priorities, mistake_streaks, urgent_misses, critical_3,
    data_quality, common_difficult_positions, reason_tags_distribution).
    Schema bumped from 2.1 → 3.0.

    Phase 153-B: Removed `practice_priorities` and
    `common_difficult_positions` sections (redundant with weaknesses and
    critical_3). Schema bumped to 3.1.

    Phase 153-D: `include_definitions` defaults to False. The `definitions`
    block is opt-in to keep the report compact for LLM consumption; pass
    `include_definitions=True` when the consumer needs label mappings.

    Args:
        game: Game object providing game state and analysis data
        level: Important move level setting
        player_filter: Filter by player ("B", "W", or None for both)
        skill_preset: Skill preset for strictness
        lang: Language code (JSON output is language-agnostic; preserved
            for downstream helpers that may localize)
        target_visits: Target visits for effective reliability threshold.
        include_definitions: If True, embed the `definitions` block in
            `meta.definitions`. Default False for compact output.

    Returns:
        KarteReport dict (v3.1) with extended sections.
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
    definitions: Definitions = {
        "thresholds": REPORT_THRESHOLDS,
        "mistake_types": MISTAKE_TYPES,
        "phases": PHASES,
        "phase_aliases": PHASE_ALIASES,
        "category_aliases": CATEGORY_ALIASES,
        "reason_code_aliases": REASON_CODE_ALIASES,
        "primary_tags": PRIMARY_TAGS,
        "reason_codes": REASON_CODES,
        "importance": IMPORTANCE_DEF,
    }

    # Meta
    common_meta = MetaExtractor.extract_game_meta(game, game_id=game_uid)

    meta: MetaData = {
        "schema_version": "3.2",  # Phase 154-D: bumped from 3.1
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
        "definitions": definitions if include_definitions else None,
        "date_range": None,
    }

    # Summary section (kept local as it's specific aggregation)
    def compute_summary_for(player: str) -> tuple[float, dict[str, int]]:
        player_moves = [m for m in moves if m.player == player]
        total_lost = sum(max(0.0, m.points_lost) for m in player_moves if m.points_lost is not None)

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

    if player_filter in ("B", "W"):
        important_move_evals = [m for m in important_move_evals if m.player == player_filter]

    # Classify meaning tags (Phase 148-B'1)
    total_moves_for_ctx = len(moves)
    try:
        node_map = _build_node_map(game)
    except (TypeError, AttributeError):
        node_map = {}
    for mv in important_move_evals:
        if mv.meaning_tag_id is None:
            node = node_map.get(mv.move_number)
            classification_context = build_classification_context_from_node(
                node, mv.gtp, total_moves=total_moves_for_ctx
            )
            meaning_tag = classify_meaning_tag(mv, context=classification_context)
            mv.meaning_tag_id = meaning_tag.id.value

    important_moves_list: list[MistakeItem] = []
    for mv in important_move_evals:
        item = MoveExtractor.extract(mv, game_id=game_uid, game_name=common_meta["name"], board_size=board_x)
        important_moves_list.append(item)

    # Phase 149 C-3: Compute confidence level once for all extended sections
    confidence_level = eval_metrics.compute_confidence_level(snapshot.moves)

    # Phase 149 C-3: Build KarteContext for revived section generators
    from katrain.core.reports.karte.sections.context import KarteContext

    pb_name = common_meta["players"]["black"]
    pw_name = common_meta["players"]["white"]
    focus_color: str | None = None
    if player_filter in ("B", "W"):
        focus_color = player_filter

    ctx = KarteContext(
        snapshot=snapshot,
        game=game,
        thresholds=[],
        effective_thresholds=score_thresholds,
        effective_preset=effective_preset,
        auto_recommendation=None,
        confidence_level=confidence_level,
        pacing_map=None,
        histogram=None,
        board_x=board_x,
        board_y=board_y,
        pb=pb_name,
        pw=pw_name,
        focus_color=focus_color,
        important_moves=important_move_evals,
        total_moves=len(moves),
        settings=eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
            level,
            eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL[eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL],
        ),
        skill_preset=effective_preset,
        target_visits=target_visits,
        lang=lang,
    )

    # Phase 149 C-3: Invoke revived sections
    from katrain.core.reports.karte.sections.diagnosis import (
        mistake_streaks_for,
        weakness_hypothesis_for,
    )
    from katrain.core.reports.karte.sections.important_moves import (
        critical_3_section_for,
        reason_tags_distribution_for,
    )
    from katrain.core.reports.karte.sections.metadata import data_quality_section

    weaknesses = {
        "black": weakness_hypothesis_for(ctx, "B"),
        "white": weakness_hypothesis_for(ctx, "W"),
    }
    mistake_streaks = {
        "black": mistake_streaks_for(ctx, "B"),
        "white": mistake_streaks_for(ctx, "W"),
    }
    critical_3 = {
        "black": critical_3_section_for(ctx, "B", level),
        "white": critical_3_section_for(ctx, "W", level),
    }
    data_quality = data_quality_section(ctx)
    reason_tags_dist = {
        "black": reason_tags_distribution_for(ctx, "B"),
        "white": reason_tags_distribution_for(ctx, "W"),
    }

    # Phase 154-D: Win/loss analysis + loss progression
    from katrain.core.reports.sections import build_win_loss_analysis
    from katrain.core.reports.utils.result_parser import parse_result
    from katrain.core.reports.utils.loss_progression import compute_loss_progression

    game_outcome = parse_result(common_meta.get("result"))
    win_loss = build_win_loss_analysis(
        game_summary=None,
        snapshot_moves=list(snapshot.moves),
        outcome=game_outcome,
    )

    loss_buckets = compute_loss_progression(list(snapshot.moves), bucket_size=10)
    loss_progression = [
        {
            "start_move": b.start_move,
            "end_move": b.end_move,
            "move_count": b.move_count,
            "total_loss": b.total_loss,
            "avg_loss": b.avg_loss,
            "mistake_count": b.mistake_count,
        }
        for b in loss_buckets
    ]

    result: dict[str, Any] = {
        "schema_version": "3.2",
        "meta": meta,
        "summary": summary,
        "important_moves": important_moves_list,
        "weaknesses": weaknesses,
        "mistake_streaks": mistake_streaks,
        "critical_3": critical_3,
        "data_quality": data_quality,
        "reason_tags_distribution": reason_tags_dist,
        "win_loss_analysis": win_loss,
        "loss_progression": loss_progression,
    }
    return result

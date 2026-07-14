"""JSON export for summary report (multi-game).

Contains:
- build_summary_json(): Build JSON-serializable summary structure for LLM consumption.
- _build_player_stats_block(): Phase 157-C helper extracted to share
  per-game-type aggregation between the ``all`` / ``even`` / ``handicapped``
  sub-stats blocks.
- _compute_loss_progression_block(): Build the per-game-type
  ``loss_progression`` sub-list.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import time
from typing import Any

from katrain.common.short_hash import short_hash
from katrain.core import analysis as eval_metrics
from katrain.core.analysis import (
    GameSummaryData,
    MistakeCategory,
    get_canonical_loss_from_move,
)
from katrain.core.reports.definitions import (
    CATEGORY_ALIASES,
    IMPORTANCE_DEF,
    MISTAKE_TYPES,
    PHASE_ALIASES,
    PHASES,
    PRIMARY_TAGS,
    REASON_CODE_ALIASES,
    REASON_CODES,
    REPORT_SCHEMA_HASH,
    REPORT_SCHEMA_VERSION,
    REPORT_THRESHOLDS,
)
from katrain.core.reports.extractors import MetaExtractor, MoveExtractor
from katrain.core.reports.schema import (
    Definitions,
    GameMeta,
    MetaData,
    MistakeItem,
    SummaryReport,
)
from katrain.core.reports.summary_logic import SummaryAnalyzer

# Phase H-4: minimum sample count below which per-player aggregates
# are too noisy to be meaningful. Matches the threshold already used
# by ``opponent_strength_loss_correlation``.
_MIN_GAMES_FOR_COMPUTED = 2

# 3-state data status values for the ``meta.data_status`` field. The
# names mirror the curator ``score_status`` (Phase H-1) so the LLM
# sees a consistent vocabulary across reports.
_DATA_STATUS_NO_GAMES = "not_applicable_no_games"
_DATA_STATUS_INSUFFICIENT = "insufficient_data"
_DATA_STATUS_COMPUTED = "computed"


def _data_status_for(games_count: int) -> str:
    """Return the 3-state ``data_status`` for a Summary run.

    - ``"not_applicable_no_games"`` -- the batch was empty.
    - ``"insufficient_data"`` -- only one game (need >= 2 for
      meaningful per-player aggregates).
    - ``"computed"`` -- the normal 2+ game case.
    """
    if games_count == 0:
        return _DATA_STATUS_NO_GAMES
    if games_count < _MIN_GAMES_FOR_COMPUTED:
        return _DATA_STATUS_INSUFFICIENT
    return _DATA_STATUS_COMPUTED


def _ensure_tags_for_top_moves(
    top_moves: list[tuple[str, Any]],
    all_games_for_top_mistakes: list[GameSummaryData],
) -> None:
    """Back-fill ``reason_tags`` and ``meaning_tag_id`` for moves that
    lack them.

    Phase 158-G: ``SummaryAnalyzer`` records every move with
    ``loss > BAD_MOVE_LOSS_THRESHOLD`` as a worst-moves candidate, but
    only moves that pass through ``get_important_move_evals`` (Karte
    path) have tags propagated onto the snapshot. When the JSON
    ``top_mistakes`` section is built from a worst-moves candidate that
    was never classified, the emitted ``reason_codes`` list ends up
    empty and ``primary_tag`` ends up ``null``.

    Back-fills two things, in order:

    1. ``meaning_tag_id`` via :func:`classify_meaning_tag` (no board
       re-analysis needed; classifier only needs the snapshot context).
    2. ``reason_tags`` via the heuristic-only fields of
       :func:`get_reason_tags_for_move`. We cannot re-run the full
       board analyzer here (it would require ``BoardState`` for every
       candidate), but a no-board variant emits ``heavy_loss`` /
       ``endgame_hint`` based on the move's loss and move-number —
       enough to give consumers a non-empty ``reason_codes`` list.

    The reason_tags are normalized via ``REASON_CODE_ALIASES`` inside
    :class:`MoveExtractor`, so we can keep the raw tag names here.
    """
    if not top_moves:
        return

    from katrain.core.analysis import build_node_map
    from katrain.core.analysis.meaning_tags import (
        build_classification_context_from_node,
        classify_meaning_tag,
    )

    # Build a game_name -> game lookup once
    games_by_name = {g.game_name: g for g in all_games_for_top_mistakes}

    for game_name, move in top_moves:
        if move.meaning_tag_id is None:
            game = games_by_name.get(game_name)
            if game is not None:
                try:
                    node_map = build_node_map(game)
                except (TypeError, AttributeError):
                    node_map = {}
                node = node_map.get(move.move_number)
                context = build_classification_context_from_node(
                    node,
                    move.gtp,
                    total_moves=len(game.snapshot.moves),
                )
                try:
                    tag = classify_meaning_tag(move, context=context)
                except Exception:
                    logger.debug('classify_meaning_tag during karte summary build', exc_info=True)
                    tag = None
                if tag is not None:
                    move.meaning_tag_id = tag.id.value

        # Phase 158-G: derive a minimum ``reason_tags`` set when the
        # move was never board-analyzed. Without this, the LLM
        # consumer would see ``reason_codes: []`` next to fully
        # classified entries. The heuristic uses only the move's own
        # ``points_lost`` / ``move_number`` — no board state required.
        if not move.reason_tags:
            move.reason_tags = _derive_basic_reason_tags(move)


def _derive_basic_reason_tags(move: Any) -> list[str]:
    """Heuristic-only reason-tag derivation for moves that were never
    board-analyzed (Phase 158-G).

    Used by :func:`_ensure_tags_for_top_moves` so ``top_mistakes`` entries
    always carry *some* tactical signal — at minimum ``heavy_loss`` when
    the move lost a lot of points and ``endgame_hint`` when the move
    happened in the late game. Re-running the full
    :func:`get_reason_tags_for_move` would require rebuilding
    ``BoardState`` for every candidate, which is too expensive for a
    worst-moves pass that may run after the Karte pipeline has already
    pruned the original board analyses.
    """
    from katrain.core.analysis.logic_phase import classify_game_phase
    from katrain.core.analysis.models import get_canonical_loss_from_move
    from katrain.core.reports.constants import BAD_MOVE_LOSS_THRESHOLD

    tags: list[str] = []
    loss = get_canonical_loss_from_move(move)
    # Use the same heuristic thresholds as ``get_reason_tags_for_move``
    # so the LLM sees consistent tags whether the move came from the
    # Karte path or the Summary worst-moves path.
    if loss >= BAD_MOVE_LOSS_THRESHOLD * 4:  # >= 2.0 points
        tags.append("heavy_loss")
    phase = classify_game_phase(move.move_number or 0, 19)
    if phase == "yose":
        tags.append("endgame_hint")
    return tags


def _compute_player_win_loss_analysis(
    game_data_list: list[GameSummaryData],
    player_name: str,
) -> dict[str, Any]:
    """Aggregate per-player win/loss stats (Phase 154-D).

    Phase 157-C: extracted to ``_build_player_stats_block`` so the same
    calculation runs once per game-type bucket (``all`` / ``even`` /
    ``handicapped``).
    """
    from katrain.core.reports.utils.result_parser import (
        PlayerOutcome,
        parse_result,
    )

    win_games = loss_games = draw_games = unknown_games = 0
    win_total_loss = loss_total_loss = draw_total_loss = 0.0
    win_count_loss = loss_count_loss = draw_count_loss = 0
    for gd in game_data_list:
        outcome = gd.outcome if gd.outcome is not None else (parse_result(gd.result) if gd.result else None)
        if outcome is None:
            unknown_games += 1
            continue
        player_outcome = outcome.black if player_name == gd.player_black else outcome.white
        if player_outcome == PlayerOutcome.WIN:
            win_games += 1
            for m in gd.snapshot.moves:
                if m.player == ("B" if player_name == gd.player_black else "W"):
                    # Phase 159A: use canonical loss (matches rest of Summary JSON).
                    # Previously used `m.points_lost or m.score_loss or 0.0` which
                    # fell through to score_loss when points_lost was exactly 0.0,
                    # potentially inflating totals for perfect moves.
                    loss_v = get_canonical_loss_from_move(m)
                    win_total_loss += loss_v
                    win_count_loss += 1
        elif player_outcome == PlayerOutcome.LOSS:
            loss_games += 1
            for m in gd.snapshot.moves:
                if m.player == ("B" if player_name == gd.player_black else "W"):
                    loss_v = get_canonical_loss_from_move(m)
                    loss_total_loss += loss_v
                    loss_count_loss += 1
        elif player_outcome == PlayerOutcome.DRAW:
            draw_games += 1
            for m in gd.snapshot.moves:
                if m.player == ("B" if player_name == gd.player_black else "W"):
                    loss_v = get_canonical_loss_from_move(m)
                    draw_total_loss += loss_v
                    draw_count_loss += 1
        else:
            unknown_games += 1

    return {
        "win": {
            "games": win_games,
            "total_loss": round(win_total_loss, 2),
            "avg_loss": round(win_total_loss / win_count_loss, 3) if win_count_loss else 0.0,
        },
        "loss": {
            "games": loss_games,
            "total_loss": round(loss_total_loss, 2),
            "avg_loss": round(loss_total_loss / loss_count_loss, 3) if loss_count_loss else 0.0,
        },
        "draw": {
            "games": draw_games,
            "total_loss": round(draw_total_loss, 2),
            "avg_loss": round(draw_total_loss / draw_count_loss, 3) if draw_count_loss else 0.0,
        },
        "unknown_games": unknown_games,
    }


def _build_player_stats_block(
    game_data_list: list[GameSummaryData],
    player_name: str,
    all_games_for_top_mistakes: list[GameSummaryData],
) -> dict[str, Any]:
    """Build the per-player stats block for a given game-type subset.

    Phase 157-C: the block is reused three times per player (once for
    ``all``, once for ``even``, once for ``handicapped``). The
    ``all_games_for_top_mistakes`` argument keeps ``top_mistakes`` keyed
    on cross-game data so the displayed moves don't shrink as the
    subset narrows.

    Phase C-1: split into focused helpers (``_build_overall_block``,
    ``_build_mistake_distribution``, ``_build_phase_distribution``,
    ``_build_reason_tags_block``, ``_build_mistake_sequences_block``,
    ``_build_top_mistakes_block``) so the orchestrator stays
    declarative and each section is independently testable.

    Returns a plain ``dict`` (not a ``SummaryPlayerStats`` TypedDict
    instance) so it can be safely embedded under the ``even`` /
    ``handicapped`` keys of the outer block without mypy flagging the
    structurally-different shape. The required keys for
    ``SummaryPlayerStats`` are still produced when ``stats`` is found.
    """
    # Phase 157-C: re-run the analyzer over this subset so per-player
    # aggregates reflect only the relevant game-type.
    sub_analyzer = SummaryAnalyzer(game_data_list)
    sub_player_stats = sub_analyzer.get_all_player_stats()
    stats = sub_player_stats.get(player_name)
    if stats is None:
        # Player never appears in this subset (e.g. only ever played
        # ``even`` games so the ``handicapped`` block is empty).
        return _build_empty_player_stats_block(game_data_list, player_name)

    confidence_level = eval_metrics.compute_confidence_level(stats.all_moves)
    confidence_val = confidence_level.name.lower()  # high, medium, low

    # Phase 158-I: mistake sequences and top mistakes continue to draw
    # from the cross-game pool (``all_games_for_top_mistakes``) so the
    # displayed moves are stable across ``all`` / ``even`` / ``handicapped``
    # views. Sequence detection is rerun on the subset.
    sequences, filtered_moves = sub_analyzer.detect_mistake_sequences(player_name)
    full_analyzer = SummaryAnalyzer(all_games_for_top_mistakes)
    _full_sequences, full_filtered = full_analyzer.detect_mistake_sequences(player_name)
    filtered_moves_for_top = full_filtered if all_games_for_top_mistakes else filtered_moves

    return {
        "overall": _build_overall_block(stats, confidence_val),
        "mistakes": _build_mistake_distribution(stats),
        "phases": _build_phase_distribution(stats),
        "reason_tags": _build_reason_tags_block(stats),
        "mistake_sequences": _build_mistake_sequences_block(
            sequences=sequences,
            game_data_list=game_data_list,
        ),
        "top_mistakes": _build_top_mistakes_block(
            filtered_moves_for_top=filtered_moves_for_top,
            all_games_for_top_mistakes=all_games_for_top_mistakes,
            confidence_level=confidence_level,
        ),
        "win_loss_analysis": _compute_player_win_loss_analysis(game_data_list, player_name),
        "opponent_strength_loss_correlation": _build_opponent_correlation_block(game_data_list, player_name),
    }


# ---------------------------------------------------------------------------
# Phase C-1: per-section helpers extracted from _build_player_stats_block.
# Each is small (≤ 30 lines) and independently testable; the orchestrator
# above stays declarative.
# ---------------------------------------------------------------------------


def _build_empty_player_stats_block(
    game_data_list: list[GameSummaryData],
    player_name: str,
) -> dict[str, Any]:
    """Empty player block when the player has no games in the subset.

    Phase 157-C: the ``handicapped`` block is empty for players who
    only ever played even games. We still produce a structurally-valid
    block so the JSON consumer does not have to special-case missing
    keys.
    """
    return {
        "overall": {
            "total_games": 0,
            "total_moves": 0,
            "total_loss": 0.0,
            "avg_loss": 0.0,
            "confidence": "low",
        },
        "mistakes": {},
        "phases": {},
        "reason_tags": {
            "status": "computed_empty",
            "data": {},
            "stats": {"tagged_moves_count": 0, "tag_occurrences_total": 0},
        },
        # Phase 158-I: distinguish "no games" from "no streak" for
        # the LLM. ``game_data_list`` is non-empty here (otherwise
        # we would have taken the early return above), so
        # ``not_applicable_no_games`` is reserved for the empty
        # case.
        "mistake_sequences": {"status": "no_streak_detected", "data": []},
        "top_mistakes": [],
        "win_loss_analysis": _compute_player_win_loss_analysis(game_data_list, player_name),
    }


def _build_overall_block(stats: Any, confidence_val: str) -> dict[str, Any]:
    """Build the ``overall`` sub-block (5 fields, 1-decimal loss)."""
    return {
        "total_games": stats.total_games,
        "total_moves": stats.total_moves,
        "total_loss": round(stats.total_points_lost, 1),
        "avg_loss": round(stats.avg_points_lost_per_move, 3),
        "confidence": confidence_val,
    }


def _build_mistake_distribution(stats: Any) -> dict[str, dict[str, Any]]:
    """Per-category mistake distribution (count, pct, avg_loss)."""
    out: dict[str, dict[str, Any]] = {}
    for cat in MistakeCategory:
        key = cat.value.lower()
        out[key] = {
            "count": stats.mistake_counts.get(cat, 0),
            "pct": round(stats.get_mistake_percentage(cat), 1),
            "denominator": stats.total_moves,
            "avg_loss": round(stats.get_mistake_avg_loss(cat), 2),
        }
    return out


def _build_phase_distribution(stats: Any) -> dict[str, dict[str, Any]]:
    """Per-phase loss distribution. Reports under the public-facing
    ``opening/middle/endgame/unknown`` keys; the internal ``yose`` key
    is mapped to ``endgame`` for downstream consumers."""
    out: dict[str, dict[str, Any]] = {}
    for phase in PHASES:
        internal_phase = "yose" if phase == "endgame" else phase
        loss = stats.phase_loss.get(internal_phase, 0.0)
        out[phase] = {
            "moves": stats.phase_moves.get(internal_phase, 0),
            # Phase 158-H: round to 2 decimals to align with the rest of
            # the Summary / Karte JSON (which uses 2 decimals for total
            # loss fields). Previously ``phases.*.total_loss`` was the
            # only field using 1 decimal.
            "total_loss": round(loss, 2),
            "avg_loss": round(stats.get_phase_avg_loss(internal_phase), 3),
        }
    return out


def _build_reason_tags_block(stats: Any) -> dict[str, Any]:
    """Reason tags block with 4-state status (Phase 158-I)."""
    reason_tags_dist: dict[str, dict[str, Any]] = {}
    if stats.tag_occurrences_total > 0:
        normalized_counts: dict[str, int] = {}
        for tag, count in stats.reason_tags_counts.items():
            norm_tag = REASON_CODE_ALIASES.get(tag, tag)
            normalized_counts[norm_tag] = normalized_counts.get(norm_tag, 0) + count
        sorted_tags = sorted(normalized_counts.items(), key=lambda x: -x[1])
        for tag, count in sorted_tags:
            reason_tags_dist[tag] = {
                "count": count,
                "pct": round(100.0 * count / stats.tag_occurrences_total, 1),
                "denominator_type": "tag_occurrences",
                "total_tag_occurrences": stats.tag_occurrences_total,
            }
        return {
            "status": "computed" if reason_tags_dist else "computed_empty",
            "data": reason_tags_dist,
            "stats": {
                "tagged_moves_count": stats.tagged_moves_count,
                "tag_occurrences_total": stats.tag_occurrences_total,
            },
        }
    return {
        "status": "computed_empty",
        "data": {},
        "stats": {"tagged_moves_count": 0, "tag_occurrences_total": 0},
    }


def _build_mistake_sequences_block(
    sequences: list[dict[str, Any]],
    game_data_list: list[GameSummaryData],
) -> dict[str, Any]:
    """Mistake sequences with 3-state status (Phase 158-I).

    Status values:
    - ``not_applicable_no_games`` when ``game_data_list`` is empty
    - ``no_streak_detected`` when no runs of consecutive large losses
      were found in a non-empty input
    - ``computed`` otherwise
    """
    formatted: list[dict[str, Any]] = []
    for seq in sequences:
        formatted.append(
            {
                "game_name": seq["game"],
                "move_range": [seq["start"], seq["end"]],
                "count": seq["count"],
                "total_loss": round(seq["total_loss"], 1),
                "avg_loss": round(seq["total_loss"] / seq["count"], 1),
            }
        )

    if not game_data_list:
        status = "not_applicable_no_games"
    elif not formatted:
        # ``detect_mistake_sequences`` only fires on runs of
        # consecutive large-loss moves. An empty result on a
        # non-empty input therefore means "no streak detected", not
        # "missing data".
        status = "no_streak_detected"
    else:
        status = "computed"

    return {"status": status, "data": formatted}


def _build_top_mistakes_block(
    filtered_moves_for_top: list[tuple[str, Any]],
    all_games_for_top_mistakes: list[GameSummaryData],
    confidence_level: Any,
) -> list[MistakeItem]:
    """Top-mistakes display list.

    Sorts by canonical loss, back-fills tags via
    :func:`_ensure_tags_for_top_moves` (Phase 158-G), and stamps
    ``in_individual_karte`` so the LLM knows which moves are already
    covered in the per-game report (Phase 158-I).
    """
    from katrain.core.reports.constants import SUMMARY_DEFAULT_MAX_WORST_MOVES

    max_count = eval_metrics.get_important_moves_limit(confidence_level)
    display_limit = min(SUMMARY_DEFAULT_MAX_WORST_MOVES, max_count)

    sorted_moves = sorted(
        filtered_moves_for_top,
        # Phase 159A: use canonical loss for sort key (was Bug-4 from
        # Phase 158-H/I report: `or` short-circuit mis-categorised
        # moves with points_lost==0).
        key=lambda x: get_canonical_loss_from_move(x[1]),
        reverse=True,
    )
    # Phase 158-G: back-fill missing reason_tags / meaning_tag_id on
    # candidate moves. ``worst_moves`` is computed from every move with
    # loss > threshold (see ``summary_logic``), but only moves that
    # passed the Karte ``get_important_move_evals`` path have reason
    # tags propagated to the snapshot (see ``batch/stats/extraction``).
    # Without this back-fill a single ``worst_moves`` candidate can show
    # up in the JSON with ``reason_codes: []`` and ``primary_tag: null``
    # next to fully classified entries.
    top_candidates = sorted_moves[:display_limit]
    _ensure_tags_for_top_moves(top_candidates, all_games_for_top_mistakes)
    return [_format_top_mistake_item(game_name, move, all_games_for_top_mistakes) for game_name, move in top_candidates]


def _format_top_mistake_item(
    game_name: str,
    move: Any,
    all_games_for_top_mistakes: list[GameSummaryData],
) -> MistakeItem:
    """Format a single top-mistake item with the Karte cross-ref flag."""
    game_ref = next((g for g in all_games_for_top_mistakes if g.game_name == game_name), None)
    game_id = game_ref.game_id if game_ref else None
    board_size = game_ref.board_size[0] if game_ref else 19
    item = MoveExtractor.extract(move, game_id, game_name, board_size=board_size)
    # Phase 158-I: ``in_individual_karte`` flags worst-moves that
    # were also surfaced in the corresponding individual Karte's
    # ``important_moves`` block. Without this the LLM cannot tell
    # whether a top-mistake has already been covered in detail by
    # the per-game report, or only in the cross-game aggregate.
    # The ``getattr`` defaults to an empty set so test fixtures
    # built before Phase 158-I still work.
    im_keys = getattr(game_ref, "important_moves_keys", set()) or set()
    item["in_individual_karte"] = (move.move_number, move.player) in im_keys
    return item


def _build_opponent_correlation_block(
    game_data_list: list[GameSummaryData],
    player_name: str,
) -> Any:
    """Compute the opponent-strength loss correlation sub-block."""
    from katrain.core.reports.sections import build_opponent_strength_loss_correlation

    return build_opponent_strength_loss_correlation(game_data_list, player_name)


def _compute_loss_progression_block(
    game_data_list: list[GameSummaryData],
) -> list[dict[str, float | int]]:
    """Aggregate the loss progression for a game-type subset (Phase 157-C).

    Uses ``truncate_end_move=False`` so identical windows from games of
    different lengths share the same ``(start_move, end_move)`` key
    (Phase 157-A bug fix).
    """
    from katrain.core.reports.utils.loss_progression import compute_loss_progression

    aggregated_buckets: dict[tuple[int, int], dict[str, float | int]] = {}
    for gd in game_data_list:
        for b in compute_loss_progression(list(gd.snapshot.moves), bucket_size=10, truncate_end_move=False):
            bucket_key: tuple[int, int] = (b.start_move, b.end_move)
            if bucket_key not in aggregated_buckets:
                aggregated_buckets[bucket_key] = {
                    "start_move": b.start_move,
                    "end_move": b.end_move,
                    "move_count": 0,
                    "total_loss": 0.0,
                    "avg_loss": 0.0,
                    "mistake_count": 0,
                }
            agg: dict[str, float | int] = aggregated_buckets[bucket_key]
            agg["move_count"] = int(agg["move_count"]) + b.move_count
            agg["total_loss"] = float(agg["total_loss"]) + b.total_loss
            agg["mistake_count"] = int(agg["mistake_count"]) + b.mistake_count

    out: list[dict[str, float | int]] = []
    for bk in sorted(aggregated_buckets):
        agg = aggregated_buckets[bk]
        mc = agg["move_count"]
        agg["total_loss"] = round(agg["total_loss"], 2)
        agg["avg_loss"] = round(agg["total_loss"] / mc, 3) if mc else 0.0
        out.append(agg)
    return out


def build_summary_json(
    game_data_list: list[GameSummaryData],
    focus_player: str | None = None,
    include_definitions: bool = False,
    dynamic_phase_detection: bool = True,
) -> SummaryReport:
    """Build a JSON-serializable summary structure for LLM consumption.

    Adheres to "Pure Data" requirements:
    - No instructional text
    - Explicit units
    - Raw numeric values
    - Full IDs

    Phase 153-D: `include_definitions` defaults to False. The `definitions`
    block is opt-in to keep the summary compact for LLM consumption; pass
    `include_definitions=True` when the consumer needs label mappings.

    Phase 156 / Phase 158-F: `dynamic_phase_detection` defaults to True.
    When True, each game's move tags are rewritten using the
    scoreStdev-based detector. Falls back to the static classifier
    when scoreStdev is missing (unanalyzed).

    Phase 157-C: per-player blocks now include ``even`` and
    ``handicapped`` sub-stats (subset of the cross-game ``all`` block).
    The top-level ``loss_progression`` is a dict
    (``{"all": [...], "even": [...], "handicapped": [...]}``) instead of
    a single flat list. ``meta.games_by_type`` carries the game counts
    per regime. ``schema_version`` is bumped to 3.4.

    Phase 157-D: top-level ``win_loss_analysis`` was removed (was always
    ``null``); per-player aggregation lives under
    ``players[...].win_loss_analysis``.
    """

    # Phase 156: opt-in dynamic phase detection (rewrites move.tag)
    if dynamic_phase_detection:
        from katrain.core.analysis import apply_dynamic_phases

        for gd in game_data_list:
            board_size = gd.board_size[0] if isinstance(gd.board_size, tuple) else int(gd.board_size or 19)
            apply_dynamic_phases(list(gd.snapshot.moves), board_size=board_size)

    # Initialize Logic Analyzer
    analyzer = SummaryAnalyzer(game_data_list, focus_player)
    player_stats = analyzer.get_all_player_stats()

    # Meta Section
    all_players: set[str] = set()
    dates: list[str] = []
    presets: set[str] = set()

    # Games Metadata List
    games_meta: list[GameMeta] = []

    for gd in game_data_list:
        all_players.add(gd.player_black)
        all_players.add(gd.player_white)
        if gd.date:
            dates.append(gd.date)
        if gd.skill_preset:
            presets.add(gd.skill_preset)

        games_meta.append(MetaExtractor.extract_game_meta(gd))

    # Definitions
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

    # Meta - Add run_id
    ts = int(time.time())
    game_ids_str = "".join(sorted([g.game_id or "" for g in game_data_list]))
    # Phase H-3: switched from MD5 to blake2b for non-cryptographic IDs.
    run_hash = short_hash(f"{ts}{game_ids_str}", 8)
    run_id = f"summary_run_{ts}_{run_hash}"

    # Resolve skill_preset for meta
    if len(presets) == 1:
        skill_preset_meta = list(presets)[0]
    elif len(presets) > 1:
        skill_preset_meta = "mixed"
    else:
        skill_preset_meta = "unknown"

    # Phase 157-C: classify games into even / handicapped / unknown.
    from katrain.core.reports.utils.game_classifier import classify_games

    buckets = classify_games(game_data_list)

    meta: MetaData = {
        "schema_version": REPORT_SCHEMA_VERSION,
        # Phase 158-I: short fingerprint of the *exact* schema + constants
        # that generated this Summary. See ``definitions.REPORT_SCHEMA_HASH``.
        "schema_hash": REPORT_SCHEMA_HASH,
        "run_id": run_id,
        "games_analyzed": len(game_data_list),
        # Phase H-4: surface *why* the run is what it is. The 3-state
        # value mirrors the one used for ``opponent_strength_loss_correlation``
        # and the curator ``score_status`` (Phase H-1):
        #   - "not_applicable_no_games" -- the batch was empty
        #   - "insufficient_data"        -- a single game (need >= 2 for
        #                                   meaningful per-player aggregates)
        #   - "computed"                 -- the normal 2+ game case
        "data_status": _data_status_for(len(game_data_list)),
        "date_range": [min(dates), max(dates)] if dates else None,
        "loss_unit": "territory_points",
        "skill_preset": skill_preset_meta,
        "definitions": definitions if include_definitions else None,
        "game_id": None,  # Not applicable for summary
        "games_by_type": {
            "even": len(buckets["even"]),
            "handicapped": len(buckets["handicapped"]),
            "unknown": len(buckets["unknown"]),
        },
    }

    players_data: dict[str, Any] = {}

    # Phase 157-C: build the per-player block three times per player so
    # the ``even`` and ``handicapped`` sub-stats stay consistent with the
    # ``all`` aggregate. ``all_games_for_top_mistakes`` keeps the
    # worst-moves list keyed on the cross-game pool.
    #
    # Phase 158-G: skip the per-game-type sub-block when only one
    # game-type is present in the run (e.g. all-even, no handicapped).
    # Without this guard the sub-block is a structural duplicate of
    # ``overall`` and the Summary JSON roughly doubles in size without
    # carrying any extra information. The split is only informative when
    # both regimes exist; otherwise the meta ``games_by_type`` field is
    # enough for downstream consumers to know which regime was used.
    only_even = bool(buckets["even"]) and not buckets["handicapped"] and not buckets["unknown"]
    only_handicapped = bool(buckets["handicapped"]) and not buckets["even"] and not buckets["unknown"]
    for player_name, _stats in player_stats.items():
        all_block = _build_player_stats_block(game_data_list, player_name, all_games_for_top_mistakes=game_data_list)
        block: dict[str, Any] = dict(all_block)  # shallow copy

        if buckets["even"] and not only_even:
            block["even"] = _build_player_stats_block(
                buckets["even"],
                player_name,
                all_games_for_top_mistakes=game_data_list,
            )
        if buckets["handicapped"] and not only_handicapped:
            block["handicapped"] = _build_player_stats_block(
                buckets["handicapped"],
                player_name,
                all_games_for_top_mistakes=game_data_list,
            )

        players_data[player_name] = block

    # Phase 157-C: ``loss_progression`` is now a dict keyed by game type.
    # The ``all`` key is always emitted; ``even`` / ``handicapped`` are
    # emitted only when *both* regimes are present (Phase 158-H). A
    # single-type run (e.g. all-even) would emit a structural duplicate
    # of ``all`` under ``even``, roughly doubling the report size
    # without adding information.
    loss_progression: dict[str, list[dict[str, float | int]]] = {
        "all": _compute_loss_progression_block(game_data_list),
    }
    only_even_lp = bool(buckets["even"]) and not buckets["handicapped"] and not buckets["unknown"]
    only_handicapped_lp = bool(buckets["handicapped"]) and not buckets["even"] and not buckets["unknown"]
    if buckets["even"] and not only_even_lp:
        loss_progression["even"] = _compute_loss_progression_block(buckets["even"])
    if buckets["handicapped"] and not only_handicapped_lp:
        loss_progression["handicapped"] = _compute_loss_progression_block(buckets["handicapped"])

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "meta": meta,
        "games": games_meta,
        "players": players_data,
        "loss_progression": loss_progression,
    }

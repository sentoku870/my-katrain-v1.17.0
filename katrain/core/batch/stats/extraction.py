"""Statistics extraction functions for batch analysis.

This module contains:
- extract_game_stats()
- extract_players_from_stats()

Dependencies:
- models.py (SKIP_PLAYER_NAMES)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from katrain.core.analysis.models import get_canonical_loss_from_move

from .models import SKIP_PLAYER_NAMES

_logger = logging.getLogger("katrain.core.batch.stats")

if TYPE_CHECKING:
    from katrain.core.game import Game


def _classify_and_propagate_tags(game: Game, stats: dict[str, Any], snapshot: Any) -> None:
    """Classify reason tags / meaning tags from important moves and propagate them.

    Issues addressed:
    - Issue A: reason_tags come from get_important_move_evals(), not snapshot
    - Issue 1: Propagate reason_tags back to snapshot moves so GameSummaryData sees them
    - Issue 3: Propagate meaning_tag_id (primary_tag)
    - PR1-1: Track important_count / tagged_count / tag_occurrences
    - Phase 47: Classify meaning tags for Top 3 Mistake Types
    - Phase 148-B'1: Build per-move context with distance/scoreStdev

    Side effects (load-bearing behavior):
    - Mutates ``move.meaning_tag_id`` on important moves
    - Mutates ``snapshot.moves[k].reason_tags`` and ``.meaning_tag_id``
    - Mutates ``stats["reason_tags_by_player"]``, ``stats["important_moves_stats_by_player"]``,
      ``stats["meaning_tags_by_player"]``

    Silently swallows all exceptions (defensive: stats still valid without tags).
    """
    from katrain.core.analysis import validate_reason_tag
    from katrain.core.analysis.meaning_tags import (
        MeaningTagId,
        build_classification_context_from_node,
        classify_meaning_tag,
    )

    try:
        important_moves = game.get_important_move_evals(compute_reason_tags=True)

        total_moves = stats["total_moves"]
        try:
            from katrain.core.analysis import build_node_map

            node_map = build_node_map(game)
        except (TypeError, AttributeError):
            # Incomplete/mock game without traversable children -> degrade gracefully
            node_map = {}

        for move in important_moves:
            player = move.player
            if player in ("B", "W"):
                im_stats = stats["important_moves_stats_by_player"][player]
                im_stats["important_count"] += 1
                if move.reason_tags:
                    im_stats["tagged_count"] += 1
                    for tag in move.reason_tags:
                        if validate_reason_tag(tag):
                            stats["reason_tags_by_player"][player][tag] = (
                                stats["reason_tags_by_player"][player].get(tag, 0) + 1
                            )
                            im_stats["tag_occurrences"] += 1

                if move.meaning_tag_id is None:
                    node = node_map.get(move.move_number)
                    classification_context = build_classification_context_from_node(
                        node, move.gtp, total_moves=total_moves
                    )
                    meaning_tag = classify_meaning_tag(move, context=classification_context)
                    move.meaning_tag_id = meaning_tag.id.value

                if move.meaning_tag_id and move.meaning_tag_id != MeaningTagId.UNCERTAIN.value:
                    stats["meaning_tags_by_player"][player][move.meaning_tag_id] = (
                        stats["meaning_tags_by_player"][player].get(move.meaning_tag_id, 0) + 1
                    )

        if important_moves:
            move_map = {m.move_number: m for m in snapshot.moves}
            for im in important_moves:
                if im.move_number in move_map:
                    target = move_map[im.move_number]
                    if im.reason_tags:
                        target.reason_tags = im.reason_tags
                    if im.meaning_tag_id:
                        target.meaning_tag_id = im.meaning_tag_id

    except Exception:
        # If important moves extraction fails, reason_tags will be empty but stats still valid
        pass


def _build_summary_data(
    game: Game,
    rel_path: str,
    meta: dict[str, Any],
    snapshot: Any,
    skill_preset: str | None,
    stats: dict[str, Any],
) -> Any:
    """Build GameSummaryData for the JSON-based SummaryAnalyzer (Phase 55).

    Also collects the (move_number, player) pairs selected as important_moves
    so Summary's top_mistakes can flag entries that also appear in Karte.
    """
    from katrain.core.analysis.models import GameSummaryData

    im_keys: set[tuple[int, str]] = set()
    try:
        for im in game.get_important_move_evals(compute_reason_tags=False):
            if im.player and im.move_number:
                im_keys.add((im.move_number, im.player))
    except Exception:
        im_keys = set()

    return GameSummaryData(
        game_name=rel_path,
        player_black=meta["player_black"],
        player_white=meta["player_white"],
        snapshot=snapshot,
        board_size=(meta["board_size"], meta["board_size"]),
        date=meta["date"],
        game_id=game.game_id if hasattr(game, "game_id") else None,
        result=meta["result"],
        handicap=meta["handicap"],
        komi=meta["komi"],
        skill_preset=skill_preset,
        rank_black=meta["rank_black"],
        rank_white=meta["rank_white"],
        important_moves_keys=im_keys,
        reason_tags_by_player=dict(stats.get("reason_tags_by_player", {})),
        important_moves_stats_by_player=dict(stats.get("important_moves_stats_by_player", {})),
    )


def _extract_pattern_data(snapshot: Any) -> list[dict[str, Any]]:
    """Extract pattern data for pattern mining (Phase 85).

    Only includes MISTAKE/BLUNDER moves with at least one loss field set.
    The list is then consumed by curator/pattern mining downstream.
    """
    from katrain.core import analysis

    pattern_data = []
    for move in snapshot.moves:
        if move.mistake_category not in (
            analysis.MistakeCategory.MISTAKE,
            analysis.MistakeCategory.BLUNDER,
        ):
            continue
        has_loss = move.score_loss is not None or move.points_lost is not None
        if not has_loss:
            continue
        pattern_data.append(
            {
                "move_number": move.move_number,
                "player": move.player,
                "gtp": move.gtp,
                "score_loss": move.score_loss,
                "points_lost": move.points_lost,
                "mistake_category": move.mistake_category.name,
                "meaning_tag_id": move.meaning_tag_id,
            }
        )
    return pattern_data


def _init_stats_dict(
    rel_path: str,
    meta: dict[str, Any],
    snapshot: Any,
    source_index: int,
) -> dict[str, Any]:
    """Initialize the stats dict with zeroed containers for all counters.

    Args:
        rel_path: Relative path of the SGF file (used as game_name).
        meta: Metadata dict from _extract_sgf_metadata().
        snapshot: EvalSnapshot with moves and total_points_lost.
        source_index: Deterministic sort tie-breaker (Phase 85).

    Returns:
        A fresh stats dict with 30+ keys initialized to zero/empty values.
    """
    from katrain.core import analysis

    return {
        "game_name": rel_path,
        "player_black": meta["player_black"],
        "player_white": meta["player_white"],
        "rank_black": meta["rank_black"],  # Phase 155-C
        "rank_white": meta["rank_white"],  # Phase 155-C
        "handicap": meta["handicap"],
        "date": meta["date"],
        "board_size": (meta["board_size"], meta["board_size"]),
        "total_moves": len(snapshot.moves),
        "source_index": source_index,  # Phase 85: deterministic sort tie-breaker
        "total_points_lost": snapshot.total_points_lost,
        "moves_by_player": {"B": 0, "W": 0},
        "loss_by_player": {"B": 0.0, "W": 0.0},
        "mistake_counts": {cat: 0 for cat in analysis.MistakeCategory},
        "mistake_total_loss": {cat: 0.0 for cat in analysis.MistakeCategory},
        "freedom_counts": {diff: 0 for diff in analysis.PositionDifficulty},
        "phase_moves": {"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
        "phase_loss": {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0},
        "phase_mistake_counts": {},
        "phase_mistake_loss": {},
        "worst_moves": [],
        # Per-player stats for player summary
        "mistake_counts_by_player": {
            "B": {cat: 0 for cat in analysis.MistakeCategory},
            "W": {cat: 0 for cat in analysis.MistakeCategory},
        },
        "mistake_total_loss_by_player": {
            "B": {cat: 0.0 for cat in analysis.MistakeCategory},
            "W": {cat: 0.0 for cat in analysis.MistakeCategory},
        },
        "freedom_counts_by_player": {
            "B": {diff: 0 for diff in analysis.PositionDifficulty},
            "W": {diff: 0 for diff in analysis.PositionDifficulty},
        },
        "phase_moves_by_player": {
            "B": {"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
            "W": {"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
        },
        "phase_loss_by_player": {
            "B": {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0},
            "W": {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0},
        },
        "phase_mistake_counts_by_player": {"B": {}, "W": {}},
        "phase_mistake_loss_by_player": {"B": {}, "W": {}},
        # Reason tags for player summary (Issue 2)
        # Tags are computed for important moves only (get_important_move_evals)
        "reason_tags_by_player": {"B": {}, "W": {}},
        # Important moves stats for Reason Tags clarity (PR1-1)
        "important_moves_stats_by_player": {
            "B": {"important_count": 0, "tagged_count": 0, "tag_occurrences": 0},
            "W": {"important_count": 0, "tagged_count": 0, "tag_occurrences": 0},
        },
        # Phase 47: Meaning tags for player summary (Top 3 Mistake Types)
        "meaning_tags_by_player": {"B": {}, "W": {}},
        # Reliability stats for Data Quality section
        "reliability_by_player": {
            "B": {
                "total": 0,
                "reliable": 0,
                "low_confidence": 0,
                "total_visits": 0,
                "with_visits": 0,
                "max_visits": 0,
            },
            "W": {
                "total": 0,
                "reliable": 0,
                "low_confidence": 0,
                "total_visits": 0,
                "with_visits": 0,
                "max_visits": 0,
            },
        },
    }


def _extract_sgf_metadata(game: Game) -> dict[str, Any]:
    """Extract SGF metadata from game root (PB/PW/HA/DT/SZ/KM/RE/BR/WR).

    Returns a dict with keys: player_black, player_white, handicap, date,
    board_size (int), komi (float), result (str|None), rank_black (str|None),
    rank_white (str|None).

    Falls back to safe defaults for malformed SGF properties.
    """
    root = game.root
    board_size_prop = root.get_property("SZ", "19")
    try:
        board_size = int(board_size_prop)
    except (ValueError, TypeError):
        board_size = 19

    komi_prop = root.get_property("KM", "6.5")
    try:
        komi = float(komi_prop)
    except (ValueError, TypeError):
        komi = 6.5

    return {
        "player_black": root.get_property("PB", "Black"),
        "player_white": root.get_property("PW", "White"),
        "handicap": int(root.get_property("HA", "0") or "0"),
        "date": root.get_property("DT", None),
        "board_size": board_size,
        "komi": komi,
        "result": root.get_property("RE", None),
        "rank_black": root.get_property("BR", None),
        "rank_white": root.get_property("WR", None),
    }


def extract_game_stats(
    game: Game,
    rel_path: str,
    log_cb: Callable[[str], None] | None = None,
    target_visits: int | None = None,
    source_index: int = 0,
    snapshot: Any | None = None,
    skill_preset: str | None = None,  # Phase 126
) -> dict[str, Any] | None:
    """Extract statistics from a Game object for summary generation.

    Args:
        game: The Game object to extract stats from
        rel_path: Relative path of the SGF file (for game_name)
        log_cb: Optional callback for logging errors
        target_visits: Target visits for effective reliability threshold calculation.
            If None, uses the hardcoded RELIABILITY_VISITS_THRESHOLD (200).
        source_index: Index for deterministic sorting (Phase 85).
            Used as tie-breaker when game_name, date, total_moves are identical.
        snapshot: Optional pre-built EvalSnapshot. If provided, uses this instead of
            calling game.build_eval_snapshot(). Phase 171 で Leela 専用利用を廃止し、
            KataGo 共通の前処理オプションとして残している（実際は使われない）。

    Returns:
        Dictionary with game statistics, or None if extraction failed
    """
    try:
        from katrain.core import analysis
        from katrain.core.analysis import compute_effective_threshold

        # Phase 87.5: Use provided snapshot or build from game
        if snapshot is None:
            snapshot = game.build_eval_snapshot()
        if not snapshot.moves:
            if log_cb:
                log_cb(f"  Stats skipped for {rel_path}: no valid moves in snapshot")
            return None

        # Get game metadata. The individual keys are looked up on
        # demand below; unpacking them all up-front would create
        # lint warnings for the values that are not consumed in this
        # particular stats pipeline. Only the keys actually read are
        # extracted.
        meta = _extract_sgf_metadata(game)
        board_size = meta["board_size"]

        # Calculate stats from snapshot
        stats = _init_stats_dict(rel_path, meta, snapshot, source_index)

        # Phase 44: Compute effective threshold once before the loop
        effective_threshold = compute_effective_threshold(target_visits)

        for move in snapshot.moves:
            player = move.player
            canonical_loss = get_canonical_loss_from_move(move)
            stats["moves_by_player"][player] = stats["moves_by_player"].get(player, 0) + 1
            stats["loss_by_player"][player] = stats["loss_by_player"].get(player, 0.0) + canonical_loss

            # Phase classification
            phase = analysis.classify_game_phase(move.move_number, board_size=board_size)
            move.tag = phase  # Ensure move carries the tag for downstream aggregators
            stats["phase_moves"][phase] = stats["phase_moves"].get(phase, 0) + 1
            stats["phase_loss"][phase] = stats["phase_loss"].get(phase, 0.0) + canonical_loss

            # Per-player phase stats
            if player in ("B", "W"):
                stats["phase_moves_by_player"][player][phase] = stats["phase_moves_by_player"][player].get(phase, 0) + 1
                stats["phase_loss_by_player"][player][phase] = (
                    stats["phase_loss_by_player"][player].get(phase, 0.0) + canonical_loss
                )

            # Mistake category
            # Phase 148-C1: Exclude BLUNDER on ONLY_MOVE (forced) from severity aggregation
            # (a forced move has no real choice, so a "blunder" there has low learning value)
            is_forced_blunder = (
                move.mistake_category == analysis.MistakeCategory.BLUNDER
                and getattr(move, "position_difficulty", None) == analysis.PositionDifficulty.ONLY_MOVE
            )
            if move.mistake_category and not is_forced_blunder:
                stats["mistake_counts"][move.mistake_category] = (
                    stats["mistake_counts"].get(move.mistake_category, 0) + 1
                )
                stats["mistake_total_loss"][move.mistake_category] = (
                    stats["mistake_total_loss"].get(move.mistake_category, 0.0) + canonical_loss
                )

                # Per-player mistake stats
                if player in ("B", "W"):
                    stats["mistake_counts_by_player"][player][move.mistake_category] = (
                        stats["mistake_counts_by_player"][player].get(move.mistake_category, 0) + 1
                    )
                    stats["mistake_total_loss_by_player"][player][move.mistake_category] = (
                        stats["mistake_total_loss_by_player"][player].get(move.mistake_category, 0.0) + canonical_loss
                    )

                # Phase x Mistake
                key = (phase, move.mistake_category.name)
                stats["phase_mistake_counts"][key] = stats["phase_mistake_counts"].get(key, 0) + 1
                stats["phase_mistake_loss"][key] = stats["phase_mistake_loss"].get(key, 0.0) + canonical_loss

                # Per-player Phase x Mistake
                if player in ("B", "W"):
                    stats["phase_mistake_counts_by_player"][player][key] = (
                        stats["phase_mistake_counts_by_player"][player].get(key, 0) + 1
                    )
                    stats["phase_mistake_loss_by_player"][player][key] = (
                        stats["phase_mistake_loss_by_player"][player].get(key, 0.0) + canonical_loss
                    )

            # Freedom/difficulty
            if move.position_difficulty:
                stats["freedom_counts"][move.position_difficulty] = (
                    stats["freedom_counts"].get(move.position_difficulty, 0) + 1
                )

                # Per-player freedom stats
                if player in ("B", "W"):
                    stats["freedom_counts_by_player"][player][move.position_difficulty] = (
                        stats["freedom_counts_by_player"][player].get(move.position_difficulty, 0) + 1
                    )

            # Track reliability stats for Data Quality section
            # Phase 44: Use effective threshold (computed once before the loop)
            if player in ("B", "W"):
                rel = stats["reliability_by_player"][player]
                rel["total"] += 1
                visits = move.root_visits or 0
                if visits == 0:
                    rel["low_confidence"] += 1
                elif visits >= effective_threshold:
                    rel["reliable"] += 1
                    rel["total_visits"] += visits
                    rel["with_visits"] += 1
                else:
                    rel["low_confidence"] += 1
                    rel["total_visits"] += visits
                    rel["with_visits"] += 1
                # PR1-2: Track max visits
                if visits > rel["max_visits"]:
                    rel["max_visits"] = visits

            # Track worst moves
            if move.points_lost and move.points_lost >= 2.0:
                stats["worst_moves"].append(
                    (move.move_number, player, move.gtp, move.points_lost, move.mistake_category)
                )

        # Sort worst moves by loss
        stats["worst_moves"].sort(key=lambda x: x[3], reverse=True)
        stats["worst_moves"] = stats["worst_moves"][:10]  # Keep top 10

        _classify_and_propagate_tags(game, stats, snapshot)

        stats["pattern_data"] = _extract_pattern_data(snapshot)

        stats["summary_data"] = _build_summary_data(game, rel_path, meta, snapshot, skill_preset, stats)

        return stats
    except Exception as e:
        if log_cb:
            log_cb(f"  Stats extraction failed for {rel_path}: {e}")
        return None


def extract_players_from_stats(
    game_stats_list: list[dict[str, Any]],
    min_games: int = 3,
    skip_names: frozenset[str] | None = None,
) -> dict[str, list[tuple[dict[str, Any], str]]]:
    """
    Extract player names and group their games.

    Args:
        game_stats_list: List of game stats dicts
        min_games: Minimum games required per player
        skip_names: Player names to skip (default: SKIP_PLAYER_NAMES)

    Returns:
        Dict mapping player_display_name -> [(game_stats, role), ...]
        where role is "B" or "W"

    Design Notes:
        - Names are normalized via normalize_player_name()
        - Original display name (first occurrence) preserved for output
        - Generic names ("Black", "White", "黒", "白", etc.) are skipped
        - Players with < min_games are excluded
    """
    from katrain.core.batch.filenames import normalize_player_name

    if skip_names is None:
        skip_names = SKIP_PLAYER_NAMES

    # Track: normalized_name -> [(stats, role, original_name), ...]
    player_games: dict[str, list[tuple[dict[str, Any], str, str]]] = defaultdict(list)

    for stats in game_stats_list:
        pb_orig = stats.get("player_black", "").strip()
        pw_orig = stats.get("player_white", "").strip()

        if pb_orig and pb_orig not in skip_names:
            pb_norm = normalize_player_name(pb_orig)
            player_games[pb_norm].append((stats, "B", pb_orig))

        if pw_orig and pw_orig not in skip_names:
            pw_norm = normalize_player_name(pw_orig)
            player_games[pw_norm].append((stats, "W", pw_orig))

    # Filter by min_games and convert to output format
    result: dict[str, list[tuple[dict[str, Any], str]]] = {}
    for _norm_name, games in player_games.items():
        if len(games) >= min_games:
            # Use first original name as display name
            display_name = games[0][2]
            result[display_name] = [(g[0], g[1]) for g in games]

    return result

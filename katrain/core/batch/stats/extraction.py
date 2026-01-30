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
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from katrain.core.batch.helpers import get_canonical_loss

from .models import SKIP_PLAYER_NAMES

_logger = logging.getLogger("katrain.core.batch.stats")

if TYPE_CHECKING:
    from katrain.core.game import Game


def extract_game_stats(
    game: "Game",
    rel_path: str,
    log_cb: Optional[Callable[[str], None]] = None,
    target_visits: Optional[int] = None,
    source_index: int = 0,
) -> Optional[dict]:
    """Extract statistics from a Game object for summary generation.

    Args:
        game: The Game object to extract stats from
        rel_path: Relative path of the SGF file (for game_name)
        log_cb: Optional callback for logging errors
        target_visits: Target visits for effective reliability threshold calculation.
            If None, uses the hardcoded RELIABILITY_VISITS_THRESHOLD (200).
        source_index: Index for deterministic sorting (Phase 85).
            Used as tie-breaker when game_name, date, total_moves are identical.

    Returns:
        Dictionary with game statistics, or None if extraction failed
    """
    try:
        from katrain.core import eval_metrics
        from katrain.core.eval_metrics import compute_effective_threshold
        from katrain.core.analysis.meaning_tags import (
            ClassificationContext,
            MeaningTagId,
            classify_meaning_tag,
        )
        from katrain.core.analysis.skill_radar import (
            MIN_MOVES_FOR_RADAR,
            compute_radar_from_moves,
        )

        snapshot = game.build_eval_snapshot()
        if not snapshot.moves:
            return None

        # Get game metadata
        root = game.root
        player_black = root.get_property("PB", "Black")
        player_white = root.get_property("PW", "White")
        handicap = int(root.get_property("HA", "0") or "0")
        date = root.get_property("DT", None)
        board_size_prop = root.get_property("SZ", "19")
        try:
            board_size = int(board_size_prop)
        except (ValueError, TypeError):
            board_size = 19

        # Calculate stats from snapshot
        stats = {
            "game_name": rel_path,
            "player_black": player_black,
            "player_white": player_white,
            "handicap": handicap,
            "date": date,
            "board_size": (board_size, board_size),
            "total_moves": len(snapshot.moves),
            "source_index": source_index,  # Phase 85: deterministic sort tie-breaker
            "total_points_lost": snapshot.total_points_lost,
            "moves_by_player": {"B": 0, "W": 0},
            "loss_by_player": {"B": 0.0, "W": 0.0},
            "mistake_counts": {cat: 0 for cat in eval_metrics.MistakeCategory},
            "mistake_total_loss": {cat: 0.0 for cat in eval_metrics.MistakeCategory},
            "freedom_counts": {diff: 0 for diff in eval_metrics.PositionDifficulty},
            "phase_moves": {"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
            "phase_loss": {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0},
            "phase_mistake_counts": {},
            "phase_mistake_loss": {},
            "worst_moves": [],
            # Per-player stats for player summary
            "mistake_counts_by_player": {
                "B": {cat: 0 for cat in eval_metrics.MistakeCategory},
                "W": {cat: 0 for cat in eval_metrics.MistakeCategory},
            },
            "mistake_total_loss_by_player": {
                "B": {cat: 0.0 for cat in eval_metrics.MistakeCategory},
                "W": {cat: 0.0 for cat in eval_metrics.MistakeCategory},
            },
            "freedom_counts_by_player": {
                "B": {diff: 0 for diff in eval_metrics.PositionDifficulty},
                "W": {diff: 0 for diff in eval_metrics.PositionDifficulty},
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
                "B": {"total": 0, "reliable": 0, "low_confidence": 0, "total_visits": 0, "with_visits": 0, "max_visits": 0},
                "W": {"total": 0, "reliable": 0, "low_confidence": 0, "total_visits": 0, "with_visits": 0, "max_visits": 0},
            },
        }

        # Phase 44: Compute effective threshold once before the loop
        effective_threshold = compute_effective_threshold(target_visits)

        for move in snapshot.moves:
            player = move.player
            canonical_loss = get_canonical_loss(move.points_lost)
            stats["moves_by_player"][player] = stats["moves_by_player"].get(player, 0) + 1
            stats["loss_by_player"][player] = stats["loss_by_player"].get(player, 0.0) + canonical_loss

            # Phase classification
            phase = eval_metrics.classify_game_phase(move.move_number, board_size=board_size)
            stats["phase_moves"][phase] = stats["phase_moves"].get(phase, 0) + 1
            stats["phase_loss"][phase] = stats["phase_loss"].get(phase, 0.0) + canonical_loss

            # Per-player phase stats
            if player in ("B", "W"):
                stats["phase_moves_by_player"][player][phase] = (
                    stats["phase_moves_by_player"][player].get(phase, 0) + 1
                )
                stats["phase_loss_by_player"][player][phase] = (
                    stats["phase_loss_by_player"][player].get(phase, 0.0) + canonical_loss
                )

            # Mistake category
            if move.mistake_category:
                stats["mistake_counts"][move.mistake_category] = stats["mistake_counts"].get(move.mistake_category, 0) + 1
                stats["mistake_total_loss"][move.mistake_category] = stats["mistake_total_loss"].get(move.mistake_category, 0.0) + canonical_loss

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
                stats["freedom_counts"][move.position_difficulty] = stats["freedom_counts"].get(move.position_difficulty, 0) + 1

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
                stats["worst_moves"].append((move.move_number, player, move.gtp, move.points_lost, move.mistake_category))

        # Sort worst moves by loss
        stats["worst_moves"].sort(key=lambda x: x[3], reverse=True)
        stats["worst_moves"] = stats["worst_moves"][:10]  # Keep top 10

        # Issue A fix: Get reason_tags from important moves (not from all moves)
        # Reason tags are computed in get_important_move_evals(), not in build_eval_snapshot()
        # PR1-1: Also track important_moves_count and tagged_moves_count for clarity
        # Phase 47: Also classify meaning tags for Top 3 Mistake Types
        try:
            from katrain.core.eval_metrics import validate_reason_tag
            important_moves = game.get_important_move_evals(compute_reason_tags=True)

            # Phase 47: Create context once with total_moves
            # Other context fields (policy, distance, etc.) are not available here
            total_moves = stats["total_moves"]
            classification_context = ClassificationContext(total_moves=total_moves)

            for move in important_moves:
                player = move.player
                if player in ("B", "W"):
                    im_stats = stats["important_moves_stats_by_player"][player]
                    im_stats["important_count"] += 1
                    if move.reason_tags:
                        im_stats["tagged_count"] += 1
                        for tag in move.reason_tags:
                            # Validate tag before counting (A1 requirement)
                            if validate_reason_tag(tag):
                                stats["reason_tags_by_player"][player][tag] = (
                                    stats["reason_tags_by_player"][player].get(tag, 0) + 1
                                )
                                im_stats["tag_occurrences"] += 1

                    # Phase 47: Classify meaning tag if not already done
                    if move.meaning_tag_id is None:
                        meaning_tag = classify_meaning_tag(move, context=classification_context)
                        move.meaning_tag_id = meaning_tag.id.value

                    # Count meaning tags by player (skip UNCERTAIN for Top 3)
                    if move.meaning_tag_id and move.meaning_tag_id != MeaningTagId.UNCERTAIN.value:
                        stats["meaning_tags_by_player"][player][move.meaning_tag_id] = (
                            stats["meaning_tags_by_player"][player].get(move.meaning_tag_id, 0) + 1
                        )
        except Exception:
            # If important moves extraction fails, reason_tags will be empty but stats still valid
            pass

        # Phase 49: Compute radar per player (19x19 only)
        radar_by_player: Dict[str, Optional[Dict[str, Any]]] = {"B": None, "W": None}

        if board_size == 19 and snapshot and snapshot.moves:
            for player in ("B", "W"):
                player_moves = [m for m in snapshot.moves if m.player == player]
                if len(player_moves) >= MIN_MOVES_FOR_RADAR:
                    try:
                        radar = compute_radar_from_moves(player_moves, player=player)
                        # Store even if some axes are UNKNOWN (per-axis aggregation later)
                        radar_by_player[player] = radar.to_dict()
                    except Exception as e:
                        # Log failure but don't break batch processing
                        _logger.debug(
                            "Radar computation failed for player=%s in %s: %s",
                            player, rel_path, e
                        )
                        # radar_by_player[player] remains None

        stats["radar_by_player"] = radar_by_player

        # Phase 85: Extract pattern_data for pattern mining
        # Only include MISTAKE/BLUNDER moves with at least one loss field set
        pattern_data = []
        for move in snapshot.moves:
            # Only MISTAKE or BLUNDER
            if move.mistake_category not in (
                eval_metrics.MistakeCategory.MISTAKE,
                eval_metrics.MistakeCategory.BLUNDER,
            ):
                continue

            # Skip if ALL loss fields are None
            has_loss = (
                move.score_loss is not None
                or move.leela_loss_est is not None
                or move.points_lost is not None
            )
            if not has_loss:
                continue

            pattern_data.append({
                "move_number": move.move_number,
                "player": move.player,
                "gtp": move.gtp,
                "score_loss": move.score_loss,
                "leela_loss_est": move.leela_loss_est,
                "points_lost": move.points_lost,
                "mistake_category": move.mistake_category.name,
                "meaning_tag_id": move.meaning_tag_id,
            })
        stats["pattern_data"] = pattern_data

        return stats

    except Exception:
        return None


def extract_players_from_stats(
    game_stats_list: List[dict],
    min_games: int = 3,
    skip_names: Optional[frozenset] = None,
) -> Dict[str, List[Tuple[dict, str]]]:
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
    from katrain.core.batch.helpers import normalize_player_name

    if skip_names is None:
        skip_names = SKIP_PLAYER_NAMES

    # Track: normalized_name -> [(stats, role, original_name), ...]
    player_games: Dict[str, List[Tuple[dict, str, str]]] = defaultdict(list)

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
    result: Dict[str, List[Tuple[dict, str]]] = {}
    for norm_name, games in player_games.items():
        if len(games) >= min_games:
            # Use first original name as display name
            display_name = games[0][2]
            result[display_name] = [(g[0], g[1]) for g in games]

    return result

"""
Stats extraction helper for E2E summary golden tests.

This module extracts statistics from mock-analyzed Game objects
in the same format expected by build_summary_from_stats().

Note: This is a test-only helper. Production code uses
extract_sgf_statistics() which reads KT properties from SGF files.
"""

from typing import Dict, Any, List, Tuple

from katrain.core import eval_metrics


def extract_stats_from_nodes(game: Any) -> Dict[str, Any]:
    """
    Extract stats dict from a mock-analyzed Game object.

    Follows the same logic as summary_stats.py but reads from
    node.analysis instead of KT properties.

    Args:
        game: Game object with mock analysis injected

    Returns:
        Stats dict compatible with build_summary_from_stats()
    """
    # Extract metadata from SGF root node properties
    root = game.root
    player_black = root.get_property("PB", "Black")
    player_white = root.get_property("PW", "White")
    handicap_str = root.get_property("HA", "0")
    try:
        handicap = int(handicap_str) if handicap_str else 0
    except (ValueError, TypeError):
        handicap = 0
    date = root.get_property("DT", None)
    board_size_prop = root.get_property("SZ", "19")
    try:
        board_size = (int(board_size_prop), int(board_size_prop))
    except (ValueError, TypeError):
        board_size = (19, 19)
    rank_black = root.get_property("BR", None)
    rank_white = root.get_property("WR", None)

    stats: Dict[str, Any] = {
        # Metadata fields (required by build_summary_from_stats)
        "game_name": game.sgf_filename or "unknown",
        "player_black": player_black,
        "player_white": player_white,
        "rank_black": rank_black,
        "rank_white": rank_white,
        "handicap": handicap,
        "date": date,
        "board_size": board_size,
        # Statistics fields
        "total_moves": 0,
        "total_points_lost": 0.0,
        "mistake_counts": {cat: 0 for cat in eval_metrics.MistakeCategory},
        "mistake_total_loss": {cat: 0.0 for cat in eval_metrics.MistakeCategory},
        "freedom_counts": {diff: 0 for diff in eval_metrics.PositionDifficulty},
        "phase_moves": {"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
        "phase_loss": {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0},
        "phase_mistake_counts": {},
        "phase_mistake_loss": {},
        "worst_moves": [],
        "reason_tags_counts": {},
        "moves_by_player": {"B": 0, "W": 0},
        "loss_by_player": {"B": 0.0, "W": 0.0},
    }

    prev_score = None
    move_num = 0

    for node in game.root.nodes_in_tree:
        if node.move is None:
            # Root node
            if node.analysis and "root" in node.analysis:
                prev_score = node.analysis["root"].get("scoreLead", 0.0)
            continue

        move_num += 1
        player = node.move.player

        if node.analysis and "root" in node.analysis:
            score = node.analysis["root"].get("scoreLead", 0.0)

            if prev_score is not None:
                # Calculate points_lost (same logic as summary_stats.py:157-159)
                player_sign = 1 if player == "B" else -1
                points_lost = player_sign * (prev_score - score)

                stats["total_moves"] += 1
                stats["moves_by_player"][player] += 1

                if points_lost > 0:
                    stats["total_points_lost"] += points_lost
                    stats["loss_by_player"][player] += points_lost

                # Classify mistake
                canonical_loss = max(0.0, points_lost)
                category = eval_metrics.classify_mistake(canonical_loss, None)
                stats["mistake_counts"][category] += 1
                stats["mistake_total_loss"][category] += canonical_loss

                # Freedom (unknown since we don't have real analysis)
                freedom = eval_metrics.PositionDifficulty.UNKNOWN
                stats["freedom_counts"][freedom] += 1

                # Phase classification
                phase = eval_metrics.classify_game_phase(move_num)
                stats["phase_moves"][phase] += 1
                if canonical_loss > 0:
                    stats["phase_loss"][phase] += canonical_loss

                # Phase x Mistake cross-tabulation
                key = (phase, category)
                stats["phase_mistake_counts"][key] = stats["phase_mistake_counts"].get(key, 0) + 1
                if canonical_loss > 0:
                    stats["phase_mistake_loss"][key] = stats["phase_mistake_loss"].get(key, 0.0) + canonical_loss

                # Track worst moves
                if points_lost > 0.5:
                    importance = max(0, points_lost)
                    stats["worst_moves"].append(
                        (move_num, player, node.move.gtp(), points_lost, importance, category)
                    )

            prev_score = score

    # Sort worst moves by loss (descending), keep top 10
    stats["worst_moves"].sort(key=lambda x: x[3], reverse=True)
    stats["worst_moves"] = stats["worst_moves"][:10]

    return stats

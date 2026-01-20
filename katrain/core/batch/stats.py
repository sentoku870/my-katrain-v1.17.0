"""Statistics extraction and summary generation for batch analysis.

This module contains functions to extract game statistics and build
per-player summaries for batch SGF analysis.

All functions are Kivy-independent and can be used in headless contexts.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

from katrain.core.batch.helpers import get_canonical_loss

if TYPE_CHECKING:
    from katrain.core.game import Game

# Import from eval_metrics (these are all dataclasses/enums, not Kivy-dependent)
from katrain.core.eval_metrics import (
    MistakeCategory,
    PositionDifficulty,
    REASON_TAG_LABELS,
    get_reason_tag_label,
    validate_reason_tag,
    SKILL_PRESETS,
    DEFAULT_SKILL_PRESET,
    RELIABILITY_VISITS_THRESHOLD,
    get_phase_thresholds,
    classify_game_phase,
    AutoConfidence,
    AutoRecommendation,
    PRESET_ORDER,
    _distance_from_range,
    recommend_auto_strictness,
    SKILL_PRESET_LABELS,
    CONFIDENCE_LABELS,
)


# Generic player names to skip
SKIP_PLAYER_NAMES = frozenset({"Black", "White", "黒", "白", "", "?", "Unknown", "不明"})


def extract_game_stats(
    game: "Game",
    rel_path: str,
    log_cb: Optional[Callable[[str], None]] = None,
) -> Optional[dict]:
    """Extract statistics from a Game object for summary generation.

    Args:
        game: The Game object to extract stats from
        rel_path: Relative path of the SGF file (for game_name)
        log_cb: Optional callback for logging errors

    Returns:
        Dictionary with game statistics, or None if extraction failed
    """
    try:
        from katrain.core import eval_metrics

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
            # Reliability stats for Data Quality section
            "reliability_by_player": {
                "B": {"total": 0, "reliable": 0, "low_confidence": 0, "total_visits": 0, "with_visits": 0, "max_visits": 0},
                "W": {"total": 0, "reliable": 0, "low_confidence": 0, "total_visits": 0, "with_visits": 0, "max_visits": 0},
            },
        }

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
            if player in ("B", "W"):
                rel = stats["reliability_by_player"][player]
                rel["total"] += 1
                visits = move.root_visits or 0
                if visits == 0:
                    rel["low_confidence"] += 1
                elif visits >= RELIABILITY_VISITS_THRESHOLD:
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
        try:
            important_moves = game.get_important_move_evals(compute_reason_tags=True)
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
        except Exception:
            # If important moves extraction fails, reason_tags will be empty but stats still valid
            pass

        return stats

    except Exception:
        return None


def build_batch_summary(
    game_stats_list: List[dict],
    focus_player: Optional[str] = None,
) -> str:
    """Build a multi-game summary markdown from collected stats.

    Args:
        game_stats_list: List of game stats dictionaries
        focus_player: Optional player name to focus on

    Returns:
        Markdown string with the summary
    """
    if not game_stats_list:
        return "# Multi-Game Summary\n\nNo games processed."

    lines = ["# Multi-Game Summary\n"]
    lines.append(f"**Games analyzed**: {len(game_stats_list)}\n")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # Aggregate stats
    total_moves = sum(s["total_moves"] for s in game_stats_list)
    total_loss = sum(s["total_points_lost"] for s in game_stats_list)

    lines.append("\n## Overview\n")
    lines.append(f"- Total moves: {total_moves}")
    lines.append(f"- Total points lost: {total_loss:.1f}")
    if total_moves > 0:
        lines.append(f"- Average loss per move: {total_loss / total_moves:.2f}")

    # Phase x Mistake breakdown
    lines.append("\n## Phase x Mistake Breakdown\n")

    phase_mistake_counts: Dict[Tuple[str, str], int] = {}
    phase_mistake_loss: Dict[Tuple[str, str], float] = {}
    for stats in game_stats_list:
        for key, count in stats.get("phase_mistake_counts", {}).items():
            phase_mistake_counts[key] = phase_mistake_counts.get(key, 0) + count
        for key, loss in stats.get("phase_mistake_loss", {}).items():
            phase_mistake_loss[key] = phase_mistake_loss.get(key, 0.0) + loss

    if phase_mistake_counts:
        lines.append("| Phase | Mistake | Count | Total Loss |")
        lines.append("|-------|---------|------:|----------:|")
        for key in sorted(phase_mistake_counts.keys(), key=lambda x: phase_mistake_loss.get(x, 0), reverse=True):
            phase, category = key
            count = phase_mistake_counts[key]
            loss = phase_mistake_loss.get(key, 0.0)
            lines.append(f"| {phase} | {category} | {count} | {loss:.1f} |")

    # Worst moves across all games
    lines.append("\n## Top 10 Worst Moves (All Games)\n")
    all_worst: List[Tuple[str, int, str, str, float, Optional[MistakeCategory]]] = []
    for stats in game_stats_list:
        game_name = stats["game_name"]
        for move_num, player, gtp, loss, cat in stats.get("worst_moves", []):
            all_worst.append((game_name, move_num, player, gtp, loss, cat))

    all_worst.sort(key=lambda x: x[4], reverse=True)
    all_worst = all_worst[:10]

    if all_worst:
        lines.append("| Game | Move | Player | Position | Loss | Category |")
        lines.append("|------|-----:|:------:|----------|-----:|----------|")
        for game_name, move_num, player, gtp, loss, cat in all_worst:
            cat_name = cat.name if cat else "—"
            lines.append(f"| {game_name[:30]} | {move_num} | {player} | {gtp} | {loss:.1f} | {cat_name} |")

    # Games list
    lines.append("\n## Games Included\n")
    for i, stats in enumerate(game_stats_list, 1):
        game_name = stats["game_name"]
        loss = stats["total_points_lost"]
        moves = stats["total_moves"]
        lines.append(f"{i}. {game_name} — {moves} moves, {loss:.1f} pts lost")

    return "\n".join(lines)


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


def build_player_summary(
    player_name: str,
    player_games: List[Tuple[dict, str]],
    skill_preset: str = DEFAULT_SKILL_PRESET,
    *,
    analysis_settings: Optional[Dict[str, any]] = None,
) -> str:
    """
    Build summary for a single player across their games.

    Args:
        player_name: Display name of the player
        player_games: List of (game_stats, role) tuples where role is "B" or "W"
        skill_preset: Skill preset for strictness ("auto" or one of SKILL_PRESETS keys)
        analysis_settings: Optional dict with configured analysis settings:
            - config_visits: base visits value
            - variable_visits: bool, whether variable visits is enabled
            - jitter_pct: float, jitter percentage (if variable_visits)
            - deterministic: bool, whether deterministic mode (if variable_visits)
            - timeout: float or None, timeout in seconds

    Returns:
        Markdown summary string
    """
    lines = [f"# Player Summary: {player_name}\n"]
    lines.append(f"**Games analyzed**: {len(player_games)}\n")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Aggregate only this player's moves across all games
    total_moves = 0
    total_loss = 0.0
    all_worst: List[Tuple[str, int, str, float, Optional[MistakeCategory]]] = []
    games_as_black = 0
    games_as_white = 0

    # Aggregated per-player stats
    mistake_counts: Dict[MistakeCategory, int] = {cat: 0 for cat in MistakeCategory}
    mistake_total_loss: Dict[MistakeCategory, float] = {cat: 0.0 for cat in MistakeCategory}
    freedom_counts: Dict[PositionDifficulty, int] = {diff: 0 for diff in PositionDifficulty}
    phase_moves: Dict[str, int] = {"opening": 0, "middle": 0, "yose": 0, "unknown": 0}
    phase_loss: Dict[str, float] = {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0}
    phase_mistake_counts: Dict[Tuple[str, str], int] = {}
    phase_mistake_loss: Dict[Tuple[str, str], float] = {}
    reason_tags_counts: Dict[str, int] = {}  # Issue 2: aggregate reason tags
    # PR1-1: Important moves stats for Reason Tags clarity
    important_moves_total = 0
    tagged_moves_total = 0
    tag_occurrences_total = 0

    # Reliability stats for Data Quality section
    reliability_total = 0
    reliability_reliable = 0
    reliability_low_conf = 0
    reliability_total_visits = 0
    reliability_with_visits = 0
    reliability_max_visits = 0  # PR1-2: Track max visits across all games
    board_sizes: set = set()  # Track unique board sizes for Definitions

    for stats, role in player_games:
        if role == "B":
            games_as_black += 1
        else:
            games_as_white += 1

        # Only count this player's moves/loss
        total_moves += stats["moves_by_player"].get(role, 0)
        total_loss += stats["loss_by_player"].get(role, 0.0)

        # Aggregate per-player mistake counts
        if "mistake_counts_by_player" in stats and role in stats["mistake_counts_by_player"]:
            for cat, count in stats["mistake_counts_by_player"][role].items():
                mistake_counts[cat] = mistake_counts.get(cat, 0) + count
        if "mistake_total_loss_by_player" in stats and role in stats["mistake_total_loss_by_player"]:
            for cat, loss in stats["mistake_total_loss_by_player"][role].items():
                mistake_total_loss[cat] = mistake_total_loss.get(cat, 0.0) + loss

        # Aggregate per-player freedom counts
        if "freedom_counts_by_player" in stats and role in stats["freedom_counts_by_player"]:
            for diff, count in stats["freedom_counts_by_player"][role].items():
                freedom_counts[diff] = freedom_counts.get(diff, 0) + count

        # Aggregate per-player phase stats
        if "phase_moves_by_player" in stats and role in stats["phase_moves_by_player"]:
            for phase, count in stats["phase_moves_by_player"][role].items():
                phase_moves[phase] = phase_moves.get(phase, 0) + count
        if "phase_loss_by_player" in stats and role in stats["phase_loss_by_player"]:
            for phase, loss in stats["phase_loss_by_player"][role].items():
                phase_loss[phase] = phase_loss.get(phase, 0.0) + loss

        # Aggregate per-player phase x mistake counts
        if "phase_mistake_counts_by_player" in stats and role in stats["phase_mistake_counts_by_player"]:
            for key, count in stats["phase_mistake_counts_by_player"][role].items():
                phase_mistake_counts[key] = phase_mistake_counts.get(key, 0) + count
        if "phase_mistake_loss_by_player" in stats and role in stats["phase_mistake_loss_by_player"]:
            for key, loss in stats["phase_mistake_loss_by_player"][role].items():
                phase_mistake_loss[key] = phase_mistake_loss.get(key, 0.0) + loss

        # Collect worst moves for this player
        for move_num, player, gtp, loss, cat in stats.get("worst_moves", []):
            if player == role:
                all_worst.append((stats["game_name"], move_num, gtp, loss, cat))

        # Aggregate reason tags (Issue 2)
        if "reason_tags_by_player" in stats and role in stats["reason_tags_by_player"]:
            for tag, count in stats["reason_tags_by_player"][role].items():
                reason_tags_counts[tag] = reason_tags_counts.get(tag, 0) + count

        # PR1-1: Aggregate important moves stats for Reason Tags clarity
        if "important_moves_stats_by_player" in stats and role in stats["important_moves_stats_by_player"]:
            im_stats = stats["important_moves_stats_by_player"][role]
            important_moves_total += im_stats.get("important_count", 0)
            tagged_moves_total += im_stats.get("tagged_count", 0)
            tag_occurrences_total += im_stats.get("tag_occurrences", 0)

        # Aggregate reliability stats for Data Quality
        if "reliability_by_player" in stats and role in stats["reliability_by_player"]:
            rel = stats["reliability_by_player"][role]
            reliability_total += rel.get("total", 0)
            reliability_reliable += rel.get("reliable", 0)
            reliability_low_conf += rel.get("low_confidence", 0)
            reliability_total_visits += rel.get("total_visits", 0)
            reliability_with_visits += rel.get("with_visits", 0)
            # PR1-2: Track max visits across all games
            game_max = rel.get("max_visits", 0)
            if game_max > reliability_max_visits:
                reliability_max_visits = game_max

        # Track board sizes for Definitions section
        if "board_size" in stats:
            board_sizes.add(stats["board_size"][0])  # (x, y) tuple, use x

    # =========================================================================
    # Compute auto recommendation if skill_preset is "auto"
    # =========================================================================
    game_count = len(player_games)
    auto_recommendation: Optional[AutoRecommendation] = None
    effective_preset = skill_preset

    if skill_preset == "auto" and reliability_total > 0:
        # For multi-game summaries, we use aggregated mistake_counts
        # to compute blunder/important counts without re-scanning moves
        rel_pct = 100.0 * reliability_reliable / reliability_total if reliability_total > 0 else 0.0

        # Count blunders and important moves from aggregated stats
        blunder_count = mistake_counts.get(MistakeCategory.BLUNDER, 0)
        important_count = blunder_count + mistake_counts.get(MistakeCategory.MISTAKE, 0)

        # Target ranges scaled by game count
        target_blunder = (3 * game_count, 10 * game_count)
        target_important = (10 * game_count, 30 * game_count)

        # Calculate scores for each preset
        b_score = _distance_from_range(blunder_count, target_blunder) * 2
        i_score = _distance_from_range(important_count, target_important) * 1
        total_score = b_score + i_score

        # Reliability gate
        if rel_pct < 20.0:
            conf = AutoConfidence.LOW
            effective_preset = "standard"
            reason = f"Low reliability ({rel_pct:.1f}%)"
        else:
            # Determine confidence based on score
            if total_score == 0:
                conf = AutoConfidence.HIGH
            elif total_score <= 5:
                conf = AutoConfidence.MEDIUM
            else:
                conf = AutoConfidence.LOW

            # Heuristic: adjust preset based on blunder density
            blunder_per_game = blunder_count / game_count if game_count > 0 else 0
            if blunder_per_game > 10:
                effective_preset = "advanced"  # Too many blunders, use stricter
            elif blunder_per_game < 3:
                effective_preset = "beginner"  # Too few blunders, use looser
            else:
                effective_preset = "standard"
            reason = f"blunder={blunder_count}, important={important_count}"

        auto_recommendation = AutoRecommendation(
            recommended_preset=effective_preset,
            confidence=conf,
            blunder_count=blunder_count,
            important_count=important_count,
            score=total_score,
            reason=reason,
        )

    # =========================================================================
    # Definitions Section (before Overview)
    # =========================================================================
    preset = SKILL_PRESETS.get(effective_preset, SKILL_PRESETS[DEFAULT_SKILL_PRESET])
    t1, t2, t3 = preset.score_thresholds

    # Build strictness info line using JP labels
    effective_label = SKILL_PRESET_LABELS.get(effective_preset, effective_preset)
    if skill_preset == "auto" and auto_recommendation:
        conf_label = CONFIDENCE_LABELS.get(auto_recommendation.confidence.value, auto_recommendation.confidence.value)
        strictness_info = (
            f"自動 → {effective_label} "
            f"(信頼度: {conf_label}, "
            f"大悪手={auto_recommendation.blunder_count}, 重要={auto_recommendation.important_count})"
        )
    else:
        strictness_info = f"{effective_label} (手動)"

    lines.append("\n## Definitions\n")
    lines.append(f"- Strictness: {strictness_info}")

    # Feature 3: Show auto recommendation hint even in manual mode
    if skill_preset != "auto" and game_count > 0:
        # Compute auto recommendation for hint
        blunder_count = mistake_counts.get(MistakeCategory.BLUNDER, 0)
        important_count = blunder_count + mistake_counts.get(MistakeCategory.MISTAKE, 0)
        rel_pct = 100.0 * reliability_reliable / reliability_total if reliability_total > 0 else 0.0

        # Simplified auto recommendation for multi-game context
        target_blunder = (3 * game_count, 10 * game_count)
        target_important = (10 * game_count, 30 * game_count)
        b_score = _distance_from_range(blunder_count, target_blunder) * 2
        i_score = _distance_from_range(important_count, target_important) * 1
        total_score = b_score + i_score

        if rel_pct < 20.0:
            hint_conf = AutoConfidence.LOW
            hint_preset = "standard"
        else:
            if total_score == 0:
                hint_conf = AutoConfidence.HIGH
            elif total_score <= 5:
                hint_conf = AutoConfidence.MEDIUM
            else:
                hint_conf = AutoConfidence.LOW

            blunder_per_game = blunder_count / game_count if game_count > 0 else 0
            if blunder_per_game > 10:
                hint_preset = "advanced"
            elif blunder_per_game < 3:
                hint_preset = "beginner"
            else:
                hint_preset = "standard"

        hint_label = SKILL_PRESET_LABELS.get(hint_preset, hint_preset)
        hint_conf_label = CONFIDENCE_LABELS.get(hint_conf.value, hint_conf.value)
        lines.append(f"- Auto recommended: {hint_label} (信頼度: {hint_conf_label})")

    lines.append("")
    lines.append("| Metric | Definition |")
    lines.append("|--------|------------|")
    lines.append("| Points Lost | Score difference between actual move and best move (clamped to ≥0) |")
    lines.append(f"| Good | Loss < {t1:.1f} pts |")
    lines.append(f"| Inaccuracy | Loss {t1:.1f} - {t2:.1f} pts |")
    lines.append(f"| Mistake | Loss {t2:.1f} - {t3:.1f} pts |")
    lines.append(f"| Blunder | Loss ≥ {t3:.1f} pts |")

    # Phase thresholds - handle mixed board sizes
    if len(board_sizes) == 1:
        board_size = list(board_sizes)[0]
        opening_end, middle_end = get_phase_thresholds(board_size)
        lines.append(f"| Phase ({board_size}x{board_size}) | Opening: <{opening_end}, Middle: {opening_end}-{middle_end-1}, Endgame: ≥{middle_end} |")
    else:
        lines.append("| Phase | Mixed board sizes - thresholds vary |")

    # =========================================================================
    # Analysis Settings Section (configured values)
    # =========================================================================
    if analysis_settings:
        lines.append("\n## Analysis Settings\n")
        # Config visits
        config_visits = analysis_settings.get("config_visits")
        if config_visits is not None:
            lines.append(f"- Config visits: {config_visits:,}")

        # Variable visits settings
        variable_visits = analysis_settings.get("variable_visits", False)
        if variable_visits:
            lines.append("- Variable visits: on")
            jitter_pct = analysis_settings.get("jitter_pct")
            if jitter_pct is not None:
                lines.append(f"- Visits jitter: {jitter_pct}%")
            deterministic = analysis_settings.get("deterministic", False)
            lines.append(f"- Deterministic: {'on' if deterministic else 'off'}")
            # Show actual selected visits distribution (if recorded)
            selected_stats = analysis_settings.get("selected_visits_stats")
            if selected_stats:
                lines.append(
                    f"- Selected visits (per game): "
                    f"min={selected_stats['min']}, "
                    f"avg={selected_stats['avg']:.1f}, "
                    f"max={selected_stats['max']}"
                )
        else:
            lines.append("- Variable visits: off")

        # Timeout
        timeout = analysis_settings.get("timeout")
        if timeout is not None:
            lines.append(f"- Timeout: {timeout}s")
        else:
            lines.append("- Timeout: None")

        # Reliable threshold (constant)
        lines.append(f"- Reliable threshold: {RELIABILITY_VISITS_THRESHOLD} visits")

    # =========================================================================
    # Data Quality Section (PR1-2: Add max visits and measured note)
    # =========================================================================
    lines.append("\n## Data Quality\n")
    lines.append(f"- Moves analyzed: {reliability_total}")
    if reliability_total > 0:
        rel_pct = 100.0 * reliability_reliable / reliability_total
        low_pct = 100.0 * reliability_low_conf / reliability_total
        lines.append(f"- Reliable (visits ≥ {RELIABILITY_VISITS_THRESHOLD}): {reliability_reliable} ({rel_pct:.1f}%)")
        lines.append(f"- Low-confidence: {reliability_low_conf} ({low_pct:.1f}%)")
        if reliability_with_visits > 0:
            avg_visits = reliability_total_visits / reliability_with_visits
            lines.append(f"- Avg visits: {avg_visits:,.0f}")
            # PR1-2: Add max visits to help users understand the data
            if reliability_max_visits > 0:
                lines.append(f"- Max visits: {reliability_max_visits:,}")
        if rel_pct < 20.0:
            lines.append("")
            lines.append("⚠ Low analysis reliability (<20%). Results may be unstable.")
    # PR1-2: Add note about measured values
    lines.append("")
    lines.append("*Visits are measured from KataGo analysis (root_visits).*")

    # =========================================================================
    # Section 1: Overview
    # =========================================================================
    lines.append("\n## Overview\n")
    lines.append(f"- Games as Black: {games_as_black}")
    lines.append(f"- Games as White: {games_as_white}")
    lines.append(f"- Total moves: {total_moves}")
    lines.append(f"- Total points lost: {total_loss:.1f}")
    if total_moves > 0:
        lines.append(f"- Average loss per move: {total_loss / total_moves:.2f}")

    # Per-game metrics
    games_analyzed = len(player_games)
    if games_analyzed > 0:
        points_per_game = total_loss / games_analyzed
        blunders_total = mistake_counts.get(MistakeCategory.BLUNDER, 0)
        mistakes_total = mistake_counts.get(MistakeCategory.MISTAKE, 0)
        important_total = blunders_total + mistakes_total
        blunders_per_game = blunders_total / games_analyzed
        important_per_game = important_total / games_analyzed
        lines.append("")
        lines.append("**Per-game averages:**")
        lines.append(f"- Points lost/game: {points_per_game:.1f}")
        lines.append(f"- Blunders/game: {blunders_per_game:.1f}")
        lines.append(f"- Mistakes+Blunders/game: {important_per_game:.1f}")
    else:
        lines.append("")
        lines.append("**Per-game averages:** -")

    # =========================================================================
    # Section 2: Mistake Distribution
    # =========================================================================
    lines.append("\n## Mistake Distribution\n")
    lines.append("| Category | Count | Percentage | Avg Loss |")
    lines.append("|----------|------:|------------|----------|")

    category_labels = {
        MistakeCategory.GOOD: "Good",
        MistakeCategory.INACCURACY: "Inaccuracy",
        MistakeCategory.MISTAKE: "Mistake",
        MistakeCategory.BLUNDER: "Blunder",
    }

    total_categorized = sum(mistake_counts.values())
    for cat in [MistakeCategory.GOOD, MistakeCategory.INACCURACY,
                MistakeCategory.MISTAKE, MistakeCategory.BLUNDER]:
        count = mistake_counts.get(cat, 0)
        pct = (count / total_categorized * 100) if total_categorized > 0 else 0.0
        avg_loss = (mistake_total_loss.get(cat, 0.0) / count) if count > 0 else 0.0
        lines.append(f"| {category_labels[cat]} | {count} | {pct:.1f}% | {avg_loss:.2f} |")

    # =========================================================================
    # Section 3: Phase Breakdown
    # =========================================================================
    lines.append("\n## Phase Breakdown\n")
    lines.append("| Phase | Moves | Points Lost | Avg Loss |")
    lines.append("|-------|------:|------------:|----------|")

    phase_labels = {
        "opening": "Opening",
        "middle": "Middle game",
        "yose": "Endgame",
        "unknown": "Unknown",
    }

    for phase in ["opening", "middle", "yose", "unknown"]:
        count = phase_moves.get(phase, 0)
        loss = phase_loss.get(phase, 0.0)
        avg_loss = (loss / count) if count > 0 else 0.0
        lines.append(f"| {phase_labels.get(phase, phase)} | {count} | {loss:.1f} | {avg_loss:.2f} |")

    # =========================================================================
    # Section 4: Phase × Mistake Breakdown
    # =========================================================================
    lines.append("\n## Phase × Mistake Breakdown\n")
    lines.append("| Phase | Good | Inaccuracy | Mistake | Blunder | Total Loss |")
    lines.append("|-------|------|------------|---------|---------|------------|")

    for phase in ["opening", "middle", "yose"]:
        cells = [phase_labels.get(phase, phase)]

        for cat in [MistakeCategory.GOOD, MistakeCategory.INACCURACY,
                    MistakeCategory.MISTAKE, MistakeCategory.BLUNDER]:
            key = (phase, cat.name)
            count = phase_mistake_counts.get(key, 0)
            loss = phase_mistake_loss.get(key, 0.0)

            if count > 0 and cat != MistakeCategory.GOOD:
                cells.append(f"{count} ({loss:.1f})")
            else:
                cells.append(str(count))

        # Total loss for this phase
        phase_total_loss = phase_loss.get(phase, 0.0)
        cells.append(f"{phase_total_loss:.1f}")

        lines.append("| " + " | ".join(cells) + " |")

    # =========================================================================
    # Section 5: Top 10 Worst Moves
    # =========================================================================
    lines.append("\n## Top 10 Worst Moves\n")
    all_worst.sort(key=lambda x: x[3], reverse=True)
    all_worst = all_worst[:10]

    if all_worst:
        lines.append("| Game | Move | Position | Loss | Category |")
        lines.append("|------|-----:|----------|-----:|----------|")
        for game_name, move_num, gtp, loss, cat in all_worst:
            cat_name = cat.name if cat else "—"
            short_game = game_name[:30] + "..." if len(game_name) > 33 else game_name
            lines.append(f"| {short_game} | {move_num} | {gtp} | {loss:.1f} | {cat_name} |")
    else:
        lines.append("- No significant mistakes found.")

    # =========================================================================
    # Section 6: Reason Tags Distribution (Issue 2 + PR1-1 clarity)
    # =========================================================================
    lines.append("\n## Reason Tags (Top 10)\n")

    # PR1-1: Add explanatory note about what is counted
    if important_moves_total > 0:
        lines.append(f"*Tags computed for {important_moves_total} important moves "
                     f"(mistakes/blunders with loss ≥ threshold). "
                     f"{tagged_moves_total} moves had ≥1 tag.*\n")

    if reason_tags_counts:
        # Sort by count desc, then by tag name asc for deterministic ordering
        sorted_tags = sorted(
            reason_tags_counts.items(),
            key=lambda x: (-x[1], x[0])
        )[:10]  # Top 10

        # PR1-1: Use tag_occurrences_total as denominator (sum of all tag counts)
        # Percentage = this tag's occurrences / total tag occurrences
        for tag, count in sorted_tags:
            pct = (count / tag_occurrences_total * 100) if tag_occurrences_total > 0 else 0.0
            label = get_reason_tag_label(tag, fallback_to_raw=True)
            lines.append(f"- {label}: {count} ({pct:.1f}%)")
    else:
        lines.append("- No reason tags recorded.")

    # =========================================================================
    # Section 7: Weakness Hypothesis
    # =========================================================================
    lines.append("\n## Weakness Hypothesis\n")

    # Determine weaknesses based on cross-tabulation
    weaknesses = []

    # Check phase with highest average loss
    phase_avg: Dict[str, float] = {}
    for phase in ["opening", "middle", "yose"]:
        count = phase_moves.get(phase, 0)
        loss = phase_loss.get(phase, 0.0)
        if count > 0:
            phase_avg[phase] = loss / count

    if phase_avg:
        worst_phase = max(phase_avg.items(), key=lambda x: x[1])
        if worst_phase[1] > 0.5:  # Only if avg loss > 0.5
            weaknesses.append(
                f"**{phase_labels.get(worst_phase[0], worst_phase[0])}** shows highest "
                f"average loss ({worst_phase[1]:.2f} pts/move)"
            )

    # Check for high blunder rate
    total_bad = mistake_counts.get(MistakeCategory.MISTAKE, 0) + mistake_counts.get(MistakeCategory.BLUNDER, 0)
    if total_categorized > 0:
        bad_rate = total_bad / total_categorized * 100
        if bad_rate > 10:
            weaknesses.append(
                f"High mistake/blunder rate: {bad_rate:.1f}% of moves are mistakes or blunders"
            )

    # Check for phase-specific problems
    for phase in ["opening", "middle", "yose"]:
        blunder_key = (phase, MistakeCategory.BLUNDER.name)
        blunder_count = phase_mistake_counts.get(blunder_key, 0)
        blunder_loss = phase_mistake_loss.get(blunder_key, 0.0)
        if blunder_count >= 3 and blunder_loss >= 10:
            weaknesses.append(
                f"{phase_labels.get(phase, phase)}: {blunder_count} blunders "
                f"totaling {blunder_loss:.1f} points lost"
            )

    if weaknesses:
        for w in weaknesses:
            lines.append(f"- {w}")
    else:
        lines.append("- No clear weakness pattern detected. Keep up the good work!")

    # =========================================================================
    # Section 8: Practice Priorities
    # =========================================================================
    lines.append("\n## Practice Priorities\n")
    lines.append("Based on the data above, consider focusing on:\n")

    priorities = []

    # Priority 1: Worst phase
    if phase_avg:
        worst_phase = max(phase_avg.items(), key=lambda x: x[1])
        if worst_phase[1] > 0.5:
            if worst_phase[0] == "opening":
                priorities.append("Study **opening principles and joseki** (highest avg loss)")
            elif worst_phase[0] == "middle":
                priorities.append("Practice **fighting and reading** (highest avg loss in middle game)")
            else:
                priorities.append("Study **endgame techniques** (highest avg loss)")

    # Priority 2: High blunder areas
    for phase in ["opening", "middle", "yose"]:
        blunder_key = (phase, MistakeCategory.BLUNDER.name)
        blunder_count = phase_mistake_counts.get(blunder_key, 0)
        if blunder_count >= 3:
            phase_name = phase_labels.get(phase, phase)
            priorities.append(f"Review {phase_name.lower()} blunders ({blunder_count} occurrences)")

    # Priority 3: Life and death if many blunders
    total_blunders = mistake_counts.get(MistakeCategory.BLUNDER, 0)
    if total_blunders >= 5:
        priorities.append("Practice **life and death problems** to reduce blunders")

    if priorities:
        for i, p in enumerate(priorities[:5], 1):  # Max 5 priorities
            lines.append(f"{i}. {p}")
    else:
        lines.append("- No specific priorities identified. Continue balanced practice!")

    # =========================================================================
    # Section 9: Games Included
    # =========================================================================
    lines.append("\n## Games Included\n")
    for i, (stats, role) in enumerate(player_games, 1):
        game_name = stats["game_name"]
        player_loss = stats["loss_by_player"].get(role, 0.0)
        player_moves = stats["moves_by_player"].get(role, 0)
        color = "Black" if role == "B" else "White"
        lines.append(f"{i}. {game_name} ({color}) — {player_moves} moves, {player_loss:.1f} pts lost")

    return "\n".join(lines)


# Private function aliases for backward compatibility
_extract_game_stats = extract_game_stats
_build_batch_summary = build_batch_summary
_extract_players_from_stats = extract_players_from_stats
_build_player_summary = build_player_summary

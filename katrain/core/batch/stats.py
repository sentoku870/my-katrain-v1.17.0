"""Statistics extraction and summary generation for batch analysis.

This module contains functions to extract game statistics and build
per-player summaries for batch SGF analysis.

All functions are Kivy-independent and can be used in headless contexts.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from katrain.core.batch.helpers import (
    escape_markdown_table_cell,
    get_canonical_loss,
    make_markdown_link_target,
    truncate_game_name,
)
from katrain.common.locale_utils import normalize_lang_code

_logger = logging.getLogger("katrain.core.batch.stats")

if TYPE_CHECKING:
    from katrain.core.game import Game

# Phase 47: Import meaning tags classifier
from katrain.core.analysis.meaning_tags import (
    ClassificationContext,
    MeaningTagId,
    classify_meaning_tag,
)

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
    compute_effective_threshold,  # Phase 44: relative reliability threshold
)

# Phase 49: Radar imports
from katrain.core.analysis.skill_radar import (
    RadarAxis,
    RadarMetrics,
    SkillTier,
    AggregatedRadarResult,
    MIN_MOVES_FOR_RADAR,
    compute_radar_from_moves,
    radar_from_dict,
    aggregate_radar,
    round_score,
)

# Phase 53: Confidence label for auto-strictness (推定確度)
from katrain.core.analysis.presentation import get_auto_confidence_label


# Generic player names to skip
SKIP_PLAYER_NAMES = frozenset({"Black", "White", "黒", "白", "", "?", "Unknown", "不明"})


def extract_game_stats(
    game: "Game",
    rel_path: str,
    log_cb: Optional[Callable[[str], None]] = None,
    target_visits: Optional[int] = None,
) -> Optional[dict]:
    """Extract statistics from a Game object for summary generation.

    Args:
        game: The Game object to extract stats from
        rel_path: Relative path of the SGF file (for game_name)
        log_cb: Optional callback for logging errors
        target_visits: Target visits for effective reliability threshold calculation.
            If None, uses the hardcoded RELIABILITY_VISITS_THRESHOLD (200).

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
            display_name = escape_markdown_table_cell(truncate_game_name(game_name))
            lines.append(f"| {display_name} | {move_num} | {player} | {gtp} | {loss:.1f} | {cat_name} |")

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


# =============================================================================
# Phase 49: Skill Profile Helper Functions
# =============================================================================

# Tier label mapping (i18n keys with English fallback)
TIER_LABELS = {
    SkillTier.TIER_1: "Tier 1 (Novice)",
    SkillTier.TIER_2: "Tier 2 (Apprentice)",
    SkillTier.TIER_3: "Tier 3 (Proficient)",
    SkillTier.TIER_4: "Tier 4 (Advanced)",
    SkillTier.TIER_5: "Tier 5 (Elite)",
    SkillTier.TIER_UNKNOWN: "N/A",
}

# Axis label mapping (i18n keys with English fallback)
AXIS_LABELS = {
    RadarAxis.OPENING: "Opening",
    RadarAxis.FIGHTING: "Fighting",
    RadarAxis.ENDGAME: "Endgame",
    RadarAxis.STABILITY: "Stability",
    RadarAxis.AWARENESS: "Awareness",
}

# Practice hints for weak axes (English - default)
AXIS_PRACTICE_HINTS = {
    RadarAxis.OPENING: "Study fuseki patterns and joseki choices",
    RadarAxis.FIGHTING: "Practice life & death problems and fighting tesuji",
    RadarAxis.ENDGAME: "Study yose counting and endgame sequences",
    RadarAxis.STABILITY: "Focus on solid shape; avoid overplays in won positions",
    RadarAxis.AWARENESS: "Review AI's top choices to calibrate intuition",
}

# =============================================================================
# Phase 54: Localization Helpers
# =============================================================================

# Localized axis practice hints
AXIS_PRACTICE_HINTS_LOCALIZED: Dict[str, Dict[RadarAxis, str]] = {
    "jp": {
        RadarAxis.OPENING: "布石のパターンと定石選択を学ぶ",
        RadarAxis.FIGHTING: "詰碁と戦いの手筋を練習する",
        RadarAxis.ENDGAME: "ヨセの計算と終盤の手順を学ぶ",
        RadarAxis.STABILITY: "堅実な形を心がけ、優勢での無理を避ける",
        RadarAxis.AWARENESS: "AIの候補手を確認し、直感を調整する",
    },
    "en": AXIS_PRACTICE_HINTS,  # Use English defaults
}

# Meaning tag practice hints (lowercase snake_case IDs)
MTAG_PRACTICE_HINTS: Dict[str, Dict[str, str]] = {
    "jp": {
        "connection_miss": "石の連絡を意識した打ち方を練習",
        "reading_failure": "詰碁で読みを強化",
        "life_death_error": "死活問題を集中的に解く",
        "overplay": "形勢判断を意識し、無理な手を避ける",
        "slow_move": "盤面全体を見渡し、大きな場所を探す",
        "direction_error": "石の方向性と全局的なバランスを意識",
        "shape_error": "良い形・悪い形を学び、効率を高める",
        "timing_error": "手順の優先度を見直す",
    },
    "en": {
        "connection_miss": "Practice connecting moves and cut prevention",
        "reading_failure": "Strengthen reading with tsumego",
        "life_death_error": "Focus on life & death problems",
        "overplay": "Consider whole-board evaluation before aggressive moves",
        "slow_move": "Look for bigger moves across the board",
        "direction_error": "Study directional play and whole-board balance",
        "shape_error": "Learn good/bad shapes to improve efficiency",
        "timing_error": "Review move order priorities",
    },
}

# Reason tag practice hints (lowercase snake_case keys)
RTAG_PRACTICE_HINTS: Dict[str, Dict[str, str]] = {
    "jp": {
        "need_connect": "石の連絡と切断に注意",
        "low_liberties": "呼吸点の管理を意識",
        "atari": "アタリへの反応を確認",
        "reading_failure": "読みの深さを意識",
        "life_death": "死活の判断を磨く",
        "territory_loss": "地の損失を意識",
    },
    "en": {
        "need_connect": "Pay attention to connections and cuts",
        "low_liberties": "Manage liberties carefully",
        "atari": "Check responses to atari",
        "reading_failure": "Deepen reading depth",
        "life_death": "Improve life & death judgment",
        "territory_loss": "Consider territory implications",
    },
}

# Localized intro texts
PRACTICE_INTRO_TEXTS: Dict[str, str] = {
    "jp": "上記のデータに基づき、以下を重点的に練習してください：\n",
    "en": "Based on the data above, consider focusing on:\n",
}

# Localized notes headers
NOTES_HEADERS: Dict[str, str] = {
    "jp": "## 注記",
    "en": "## Notes",
}

# Localized hint line formats
HINT_LINE_FORMATS: Dict[str, str] = {
    "jp": "**{label}**（{count}回）→ {hint}",
    "en": "**{label}** ({count}x) -> {hint}",
}

# Localized percentage notes
PERCENTAGE_NOTES: Dict[str, str] = {
    "jp": "*パーセンテージはタグ出現回数の割合です（重要局面あたりではありません）*",
    "en": "*Percentages represent tag occurrence ratios (not per critical move)*",
}

# Localized color bias notes
COLOR_BIAS_NOTES: Dict[str, Dict[str, str]] = {
    "jp": {
        "B": "*注: 全て黒番のデータです*",
        "W": "*注: 全て白番のデータです*",
    },
    "en": {
        "B": "*Note: All games played as Black*",
        "W": "*Note: All games played as White*",
    },
}

# Localized phase-based priority texts
PHASE_PRIORITY_TEXTS: Dict[str, Dict[str, str]] = {
    "jp": {
        "opening": "**布石の原理と定石**を学ぶ（平均損失が最も高い）",
        "middle": "**戦いと読み**を練習する（中盤での平均損失が高い）",
        "yose": "**ヨセの技術**を学ぶ（平均損失が最も高い）",
        "blunder_review": "{phase}の大悪手を復習（{count}回発生）",
        "life_death": "**死活問題**を練習して大悪手を減らす",
        "no_priority": "特に優先すべき課題なし。バランスの良い練習を続けてください！",
        "no_weakness": "明確な弱点パターンなし。この調子で頑張ってください！",
    },
    "en": {
        "opening": "Study **opening principles and joseki** (highest avg loss)",
        "middle": "Practice **fighting and reading** (highest avg loss in middle game)",
        "yose": "Study **endgame techniques** (highest avg loss)",
        "blunder_review": "Review {phase} blunders ({count} occurrences)",
        "life_death": "Practice **life and death problems** to reduce blunders",
        "no_priority": "No specific priorities identified. Continue balanced practice!",
        "no_weakness": "No clear weakness pattern detected. Keep up the good work!",
    },
}

# Localized phase labels
PHASE_LABELS_LOCALIZED: Dict[str, Dict[str, str]] = {
    "jp": {
        "opening": "序盤",
        "middle": "中盤",
        "yose": "終盤",
    },
    "en": {
        "opening": "opening",
        "middle": "middle game",
        "yose": "endgame",
    },
}

# Localized section headers
SECTION_HEADERS: Dict[str, Dict[str, str]] = {
    "jp": {
        "practice_priorities": "## 練習の優先順位",
        "games_included": "## 含まれる対局",
        "skill_profile": "## スキルプロファイル",
        "weak_areas": "**弱点エリア (< 2.5)**",
        "practice_label": "**練習の優先順位:**",
    },
    "en": {
        "practice_priorities": "## Practice Priorities",
        "games_included": "## Games Included",
        "skill_profile": "## Skill Profile",
        "weak_areas": "**Weak areas (< 2.5)**",
        "practice_label": "**Practice priorities:**",
    },
}


def get_phase_priority_text(key: str, lang: str = "jp", **kwargs) -> str:
    """Get localized phase priority text with optional formatting."""
    normalized = normalize_lang_code(lang)
    texts = PHASE_PRIORITY_TEXTS.get(normalized, PHASE_PRIORITY_TEXTS["en"])
    template = texts.get(key, "")
    if kwargs:
        return template.format(**kwargs)
    return template


def get_phase_label_localized(phase: str, lang: str = "jp") -> str:
    """Get localized phase label."""
    normalized = normalize_lang_code(lang)
    labels = PHASE_LABELS_LOCALIZED.get(normalized, PHASE_LABELS_LOCALIZED["en"])
    return labels.get(phase, phase)


def get_section_header(key: str, lang: str = "jp") -> str:
    """Get localized section header."""
    normalized = normalize_lang_code(lang)
    headers = SECTION_HEADERS.get(normalized, SECTION_HEADERS["en"])
    return headers.get(key, key)


def get_practice_intro_text(lang: str = "jp") -> str:
    """Get localized practice intro text."""
    normalized = normalize_lang_code(lang)
    return PRACTICE_INTRO_TEXTS.get(normalized, PRACTICE_INTRO_TEXTS["en"])


def get_notes_header(lang: str = "jp") -> str:
    """Get localized notes header."""
    normalized = normalize_lang_code(lang)
    return NOTES_HEADERS.get(normalized, NOTES_HEADERS["en"])


def get_axis_practice_hint(axis: RadarAxis, lang: str = "jp") -> str:
    """Get localized practice hint for a radar axis."""
    normalized = normalize_lang_code(lang)
    hints = AXIS_PRACTICE_HINTS_LOCALIZED.get(normalized, AXIS_PRACTICE_HINTS_LOCALIZED["en"])
    return hints.get(axis, "")


def get_mtag_practice_hint(tag_id: str, lang: str = "jp") -> Optional[str]:
    """Get localized practice hint for a meaning tag ID.

    Args:
        tag_id: Meaning tag ID (lowercase snake_case, e.g., "connection_miss")
        lang: Language code ("jp", "en", "ja")

    Returns:
        Hint text or None if tag not found
    """
    normalized = normalize_lang_code(lang)
    hints = MTAG_PRACTICE_HINTS.get(normalized, MTAG_PRACTICE_HINTS["en"])
    return hints.get(tag_id.lower())


def get_rtag_practice_hint(tag: str, lang: str = "jp") -> Optional[str]:
    """Get localized practice hint for a reason tag.

    Args:
        tag: Reason tag (lowercase snake_case, e.g., "need_connect")
        lang: Language code ("jp", "en", "ja")

    Returns:
        Hint text or None if tag not found
    """
    normalized = normalize_lang_code(lang)
    hints = RTAG_PRACTICE_HINTS.get(normalized, RTAG_PRACTICE_HINTS["en"])
    return hints.get(tag.lower())


def format_hint_line(label: str, count: int, hint: str, lang: str = "jp") -> str:
    """Format a practice hint line with localized format.

    Args:
        label: Tag label (localized)
        count: Occurrence count
        hint: Practice hint text
        lang: Language code

    Returns:
        Formatted hint line (JP: "**label**（N回）→ hint", EN: "**label** (Nx) -> hint")
    """
    normalized = normalize_lang_code(lang)
    fmt = HINT_LINE_FORMATS.get(normalized, HINT_LINE_FORMATS["en"])
    return fmt.format(label=label, count=count, hint=hint)


def get_percentage_note(lang: str = "jp") -> str:
    """Get localized percentage explanation note."""
    normalized = normalize_lang_code(lang)
    return PERCENTAGE_NOTES.get(normalized, PERCENTAGE_NOTES["en"])


def get_color_bias_note(bias: str, lang: str = "jp") -> str:
    """Get localized color bias note.

    Args:
        bias: "B" for all-Black, "W" for all-White
        lang: Language code

    Returns:
        Localized note text
    """
    normalized = normalize_lang_code(lang)
    notes = COLOR_BIAS_NOTES.get(normalized, COLOR_BIAS_NOTES["en"])
    return notes.get(bias, "")


def detect_color_bias(player_games: List[Tuple[dict, str]]) -> Optional[str]:
    """Detect if all games are played as one color.

    Args:
        player_games: List of (stats, role) tuples

    Returns:
        "B" if all Black, "W" if all White, None if mixed
    """
    if not player_games:
        return None
    b_games = sum(1 for _, role in player_games if role == "B")
    w_games = sum(1 for _, role in player_games if role == "W")
    if b_games > 0 and w_games == 0:
        return "B"
    elif w_games > 0 and b_games == 0:
        return "W"
    return None


def get_dominant_tags(
    tag_counts: Dict[str, int],
    min_count: int = 3,
    max_tags: int = 3,
) -> List[Tuple[str, int]]:
    """Get dominant tags sorted by count.

    Args:
        tag_counts: Dict of tag -> count
        min_count: Minimum count to include
        max_tags: Maximum number of tags to return

    Returns:
        List of (tag, count) tuples, sorted by count descending
    """
    qualified = [(tag, count) for tag, count in tag_counts.items() if count >= min_count]
    qualified.sort(key=lambda x: -x[1])
    return qualified[:max_tags]


def build_tag_based_hints(
    mtag_counts: Dict[str, int],
    rtag_counts: Dict[str, int],
    lang: str = "jp",
    min_count: int = 3,
    max_hints: int = 4,
) -> List[str]:
    """Build practice hint lines based on dominant meaning/reason tags.

    Args:
        mtag_counts: Meaning tag ID -> count
        rtag_counts: Reason tag -> count
        lang: Language code
        min_count: Minimum occurrences to include
        max_hints: Maximum total hints to generate

    Returns:
        List of formatted hint lines (empty if no qualified tags with hints)
    """
    from katrain.core.analysis.meaning_tags.integration import get_meaning_tag_label_safe
    from katrain.common.locale_utils import to_iso_lang_code

    hints = []

    # Get dominant meaning tags
    top_mtags = get_dominant_tags(mtag_counts, min_count, max_hints)
    for tag_id, count in top_mtags:
        hint = get_mtag_practice_hint(tag_id, lang)
        if hint:
            # Get localized label for meaning tag (needs ISO code for lookup)
            iso_lang = to_iso_lang_code(lang)
            label = get_meaning_tag_label_safe(tag_id, iso_lang)
            if label:
                hints.append(format_hint_line(label, count, hint, lang))

    # Get dominant reason tags if we have room
    remaining = max_hints - len(hints)
    if remaining > 0:
        top_rtags = get_dominant_tags(rtag_counts, min_count, remaining)
        for tag, count in top_rtags:
            hint = get_rtag_practice_hint(tag, lang)
            if hint:
                label = get_reason_tag_label(tag, fallback_to_raw=True)
                hints.append(format_hint_line(label, count, hint, lang))

    return hints


def _get_tier_label(tier: SkillTier) -> str:
    """Get display label for a tier."""
    return TIER_LABELS.get(tier, "N/A")


def _get_axis_label(axis: RadarAxis) -> str:
    """Get display label for an axis."""
    return AXIS_LABELS.get(axis, axis.value)


def _build_skill_profile_section(
    radar: Optional[AggregatedRadarResult],
    lang: str = "jp",
) -> List[str]:
    """Build Skill Profile section for player summary.

    Args:
        radar: Aggregated radar result, or None if no data
        lang: Language code for output ("jp", "en", "ja")

    Returns:
        List of markdown lines to append to summary
    """
    lines = [f"\n{get_section_header('skill_profile', lang)}\n"]

    if not radar:
        lines.append("*No radar data available (requires 19x19 games with analysis)*\n")
        return lines

    # Overall tier header
    overall_label = _get_tier_label(radar.overall_tier)
    lines.append(f"**Overall: {overall_label}** ({radar.games_aggregated} games aggregated)\n")

    # 5-axis table
    lines.append("| Axis | Score | Tier | Moves |")
    lines.append("|------|------:|------|------:|")

    for axis in RadarAxis:
        axis_label = _get_axis_label(axis)
        score = getattr(radar, axis.value)
        tier = getattr(radar, f"{axis.value}_tier")
        count = radar.valid_move_counts.get(axis, 0)

        # Format score (use round_score for display)
        score_str = "N/A" if score is None else f"{round_score(score)}"
        tier_str = _get_tier_label(tier)

        lines.append(f"| {axis_label} | {score_str} | {tier_str} | {count} |")

    # Weak areas (score < 2.5)
    weak_axes = [
        (axis, getattr(radar, axis.value))
        for axis in RadarAxis
        if radar.is_weak_axis(axis)
    ]

    if weak_axes:
        # Sort by score (lowest first)
        weak_axes.sort(key=lambda x: x[1])
        weak_list = [
            f"{_get_axis_label(axis)} ({round_score(score)})"
            for axis, score in weak_axes
        ]
        lines.append("")
        lines.append(f"{get_section_header('weak_areas', lang)}: {', '.join(weak_list)}")

        # Practice priorities (max 2)
        lines.append("")
        lines.append(get_section_header("practice_label", lang))
        for axis, _ in weak_axes[:2]:
            hint = get_axis_practice_hint(axis, lang)
            if hint:
                lines.append(f"- {_get_axis_label(axis)}: {hint}")

    # JSON output block
    lines.extend(_build_radar_json_section(radar))

    return lines


def _build_radar_json_section(
    radar: Optional[AggregatedRadarResult],
) -> List[str]:
    """Build JSON output block for radar data.

    Args:
        radar: Aggregated radar result, or None

    Returns:
        List of markdown lines with JSON block
    """
    if not radar:
        return []

    import json

    # Use canonical to_dict() - single source of truth
    data = radar.to_dict()

    return [
        "\n### Radar Data (JSON)\n",
        "```json",
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
    ]


def build_player_summary(
    player_name: str,
    player_games: List[Tuple[dict, str]],
    skill_preset: str = DEFAULT_SKILL_PRESET,
    *,
    analysis_settings: Optional[Dict[str, any]] = None,
    karte_path_map: Optional[Dict[str, str]] = None,
    summary_dir: Optional[str] = None,
    lang: str = "jp",
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
        karte_path_map: Optional mapping from rel_path to absolute karte file path
        summary_dir: Directory where the summary file is being written (for relative links)
        lang: Language code for output ("jp", "en", "ja"). Defaults to "jp".

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
    meaning_tags_counts: Dict[str, int] = {}  # Phase 47: aggregate meaning tags
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

    # Phase 49: Radar metrics collection for aggregation
    radar_list: List[RadarMetrics] = []

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

        # Phase 47: Aggregate meaning tags for Top 3 Mistake Types
        if "meaning_tags_by_player" in stats and role in stats["meaning_tags_by_player"]:
            for tag, count in stats["meaning_tags_by_player"][role].items():
                meaning_tags_counts[tag] = meaning_tags_counts.get(tag, 0) + count

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

        # Phase 49: Collect radar metrics for aggregation
        if "radar_by_player" in stats:
            radar_dict = stats["radar_by_player"].get(role)
            if radar_dict:
                radar = radar_from_dict(radar_dict)
                if radar:
                    radar_list.append(radar)

    # Phase 49: Aggregate radar metrics
    aggregated_radar = aggregate_radar(radar_list)  # Uniform weighting only

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
        # Phase 53: Use get_auto_confidence_label for 推定確度 (not 信頼度)
        conf_label = get_auto_confidence_label(auto_recommendation.confidence.value)
        strictness_info = (
            f"自動 → {effective_label} "
            f"({conf_label}, "
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
        # Phase 53: Use get_auto_confidence_label for 推定確度
        hint_conf_label = get_auto_confidence_label(hint_conf.value)
        lines.append(f"- Auto recommended: {hint_label} ({hint_conf_label})")

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

        # Reliable threshold (Phase 44: relative to config_visits, capped at 200)
        config_visits = analysis_settings.get("config_visits")
        effective_threshold = compute_effective_threshold(config_visits)
        lines.append(f"- Reliable threshold: {effective_threshold} visits")

    # =========================================================================
    # Data Quality Section (PR1-2: Add max visits and measured note)
    # Phase 44: Use effective threshold (relative to config_visits, capped at 200)
    # =========================================================================
    # Compute effective threshold for Data Quality display
    dq_config_visits = analysis_settings.get("config_visits") if analysis_settings else None
    dq_effective_threshold = compute_effective_threshold(dq_config_visits)

    lines.append("\n## Data Quality\n")
    lines.append(f"- Moves analyzed: {reliability_total}")
    if reliability_total > 0:
        rel_pct = 100.0 * reliability_reliable / reliability_total
        low_pct = 100.0 * reliability_low_conf / reliability_total
        lines.append(f"- Reliable (visits ≥ {dq_effective_threshold}): {reliability_reliable} ({rel_pct:.1f}%)")
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
    # Phase 49: Skill Profile Section
    # =========================================================================
    lines.extend(_build_skill_profile_section(aggregated_radar, lang=lang))

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
    # Section 5: Top 10 Worst Moves (Phase 53: added カルテ column)
    # =========================================================================
    lines.append("\n## Top 10 Worst Moves\n")
    all_worst.sort(key=lambda x: x[3], reverse=True)
    all_worst = all_worst[:10]

    if all_worst:
        lines.append("| Game | Move | Position | Loss | Category | カルテ |")
        lines.append("|------|-----:|----------|-----:|----------|--------|")
        for game_name, move_num, gtp, loss, cat in all_worst:
            cat_name = cat.name if cat else "—"
            display_name = escape_markdown_table_cell(truncate_game_name(game_name))

            # Phase 53: Generate karte link if mapping available
            karte_path = karte_path_map.get(game_name) if karte_path_map else None
            if karte_path and summary_dir:
                link_target = make_markdown_link_target(summary_dir, karte_path)
                karte_cell = f"[表示]({link_target})"
            else:
                karte_cell = "-"

            lines.append(f"| {display_name} | {move_num} | {gtp} | {loss:.1f} | {cat_name} | {karte_cell} |")
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
    # Section 6b: Top 3 Mistake Types (Phase 47: Meaning Tags)
    # =========================================================================
    lines.append("\n## Top 3 Mistake Types\n")

    if meaning_tags_counts:
        # Sort by count desc, then by tag name asc for deterministic ordering
        sorted_tags = sorted(
            meaning_tags_counts.items(),
            key=lambda x: (-x[1], x[0])
        )[:3]  # Top 3

        total_meaning_tags = sum(meaning_tags_counts.values())
        for tag_id, count in sorted_tags:
            pct = (count / total_meaning_tags * 100) if total_meaning_tags > 0 else 0.0
            # Use safe label getter (returns None for invalid IDs)
            from katrain.core.analysis.meaning_tags import get_meaning_tag_label_safe
            label = get_meaning_tag_label_safe(tag_id, "ja") or tag_id
            lines.append(f"- {label}: {count} ({pct:.1f}%)")
    else:
        lines.append("- No meaning tags classified.")

    # Phase 54: Add percentage explanation note
    lines.append("")
    lines.append(get_percentage_note(lang))

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
        lines.append(f"- {get_phase_priority_text('no_weakness', lang)}")

    # =========================================================================
    # Section 8: Practice Priorities
    # =========================================================================
    lines.append(f"\n{get_section_header('practice_priorities', lang)}\n")
    lines.append(get_practice_intro_text(lang))

    priorities = []

    # Priority 1: Worst phase
    if phase_avg:
        worst_phase = max(phase_avg.items(), key=lambda x: x[1])
        if worst_phase[1] > 0.5:
            priorities.append(get_phase_priority_text(worst_phase[0], lang))

    # Priority 2: High blunder areas
    for phase in ["opening", "middle", "yose"]:
        blunder_key = (phase, MistakeCategory.BLUNDER.name)
        blunder_count = phase_mistake_counts.get(blunder_key, 0)
        if blunder_count >= 3:
            phase_name = get_phase_label_localized(phase, lang)
            priorities.append(
                get_phase_priority_text("blunder_review", lang, phase=phase_name, count=blunder_count)
            )

    # Priority 3: Life and death if many blunders
    total_blunders = mistake_counts.get(MistakeCategory.BLUNDER, 0)
    if total_blunders >= 5:
        priorities.append(get_phase_priority_text("life_death", lang))

    if priorities:
        for i, p in enumerate(priorities[:5], 1):  # Max 5 priorities
            lines.append(f"{i}. {p}")
    else:
        lines.append(f"- {get_phase_priority_text('no_priority', lang)}")

    # Phase 54: Add tag-based practice hints
    tag_hints = build_tag_based_hints(
        meaning_tags_counts,
        reason_tags_counts,
        lang=lang,
        min_count=3,
        max_hints=4,
    )
    if tag_hints:
        lines.append("")
        lines.append(get_notes_header(lang))
        lines.append("")
        for hint in tag_hints:
            lines.append(f"- {hint}")

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

    # Phase 54: Add color bias note if all games are same color
    color_bias = detect_color_bias(player_games)
    if color_bias:
        lines.append("")
        lines.append(get_color_bias_note(color_bias, lang))

    return "\n".join(lines)


# Private function aliases for backward compatibility
_extract_game_stats = extract_game_stats
_build_batch_summary = build_batch_summary
_extract_players_from_stats = extract_players_from_stats
_build_player_summary = build_player_summary

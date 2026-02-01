# katrain/gui/features/summary_formatter.py
"""サマリMarkdown生成モジュール.

__main__.py から抽出した _build_summary_from_stats のMarkdown生成ロジック。
Pure関数として実装（self を受け取らない）。

Phase 23 PR #3: 型ヒント追加
Phase 85: Pattern to Summary Integration
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union

from katrain.core import eval_metrics
from katrain.core.analysis.reason_generator import generate_reason_safe
from katrain.core.batch.helpers import truncate_game_name
from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty
from katrain.gui.features.summary_aggregator import collect_rank_info

if TYPE_CHECKING:
    from katrain.core.batch.stats.pattern_miner import GameRef, PatternCluster

_logger = logging.getLogger("katrain.gui.features.summary_formatter")

# GTP coordinate pattern: letter (A-T, excluding I) + number (1-25)
_GTP_COORD_PATTERN = re.compile(r"^[a-hj-t](?:[1-9]|1[0-9]|2[0-5])$", re.IGNORECASE)

# Type aliases for clarity
StatsDict = Dict[str, Any]
ConfigFn = Callable[[str], Any]
PhaseMistakeKey = Tuple[str, MistakeCategory]

# Phase 85: i18n key mappings for pattern fields
PHASE_KEYS = {
    "opening": "pattern:phase-opening",
    "middle": "pattern:phase-middle",
    "endgame": "pattern:phase-endgame",
}
AREA_KEYS = {
    "corner": "pattern:area-corner",
    "edge": "pattern:area-edge",
    "center": "pattern:area-center",
}
SEVERITY_KEYS = {
    "mistake": "pattern:severity-mistake",
    "blunder": "pattern:severity-blunder",
}
PLAYER_KEYS = {
    "B": "pattern:player-black",
    "W": "pattern:player-white",
    "?": "pattern:player-unknown",
}
MAX_DISPLAY_REFS = 3


# =============================================================================
# Phase 85: Pattern Mining Integration
# =============================================================================


class _PatternMoveEval:
    """Duck-typed MoveEval for pattern mining.

    Safely handles invalid/missing data without raising exceptions.
    """
    __slots__ = (
        "move_number", "player", "gtp", "score_loss",
        "leela_loss_est", "points_lost", "mistake_category", "meaning_tag_id"
    )

    # Type annotations for __slots__ members (Phase 111)
    mistake_category: Optional[MistakeCategory]

    def __init__(self, data: Dict[str, Any]) -> None:
        # Safe extraction with defaults
        self.move_number = data.get("move_number", 0)
        self.player = data.get("player")
        self.gtp = data.get("gtp")
        self.score_loss = data.get("score_loss")
        self.leela_loss_est = data.get("leela_loss_est")
        self.points_lost = data.get("points_lost")
        self.meaning_tag_id = data.get("meaning_tag_id")

        # Safe mistake_category conversion
        cat_name = data.get("mistake_category")
        if cat_name:
            try:
                self.mistake_category = eval_metrics.MistakeCategory[cat_name]
            except KeyError:
                _logger.warning(
                    "Invalid mistake_category '%s' at move %d; skipping.",
                    cat_name,
                    self.move_number,
                )
                self.mistake_category = None
        else:
            self.mistake_category = None


class _FakeSnapshot:
    """Duck-typed EvalSnapshot for pattern mining."""
    __slots__ = ("moves",)

    def __init__(self, moves: List["_PatternMoveEval"]) -> None:
        self.moves = moves


def _normalize_board_size(bs: Union[Tuple[int, int], List[int], None]) -> Optional[Tuple[int, int]]:
    """Normalize board_size to (w, h) tuple.

    Handles both tuple and list (from JSON deserialization).

    Returns:
        (w, h) tuple, or None if invalid.
    """
    if bs is None:
        return None
    if not isinstance(bs, (tuple, list)) or len(bs) < 2:
        return None
    try:
        return (int(bs[0]), int(bs[1]))
    except (ValueError, TypeError):
        return None


def _filter_by_board_size(
    stats_list: List[StatsDict],
) -> Tuple[List[StatsDict], Optional[int]]:
    """Filter stats_list to games with consistent board size.

    Only square boards (w == h) are supported for pattern mining.
    Handles both tuple and list board_size formats.

    Args:
        stats_list: List of stats dictionaries

    Returns:
        Tuple of (filtered_stats_list, board_size as int).
        If no valid games, returns ([], None).
    """
    # Count normalized (w, h) tuples
    size_counts: Counter[Tuple[int, int]] = Counter()
    non_square_games: List[str] = []
    invalid_games: List[str] = []

    for stats in stats_list:
        game_name = stats.get("game_name", "unknown")
        bs_normalized = _normalize_board_size(stats.get("board_size"))

        if bs_normalized is None:
            invalid_games.append(game_name)
            continue

        w, h = bs_normalized
        if w != h:
            non_square_games.append(f"{game_name} ({w}x{h})")
            continue

        size_counts[bs_normalized] += 1

    # Log invalid board_size
    if invalid_games:
        _logger.debug(
            "Skipping %d game(s) with missing/invalid board_size: %s",
            len(invalid_games),
            ", ".join(invalid_games[:5]) + ("..." if len(invalid_games) > 5 else ""),
        )

    # Log non-square games
    if non_square_games:
        _logger.warning(
            "Skipping %d non-square board game(s) for pattern mining: %s",
            len(non_square_games),
            ", ".join(non_square_games[:5]) + ("..." if len(non_square_games) > 5 else ""),
        )

    if not size_counts:
        _logger.debug("No games have valid square board_size; skipping pattern mining.")
        return [], None

    # Find most common size
    most_common_tuple = size_counts.most_common(1)[0][0]
    most_common_size = most_common_tuple[0]  # w == h, so use either

    # Check for mixed sizes
    if len(size_counts) > 1:
        skipped_count = sum(c for t, c in size_counts.items() if t != most_common_tuple)
        _logger.warning(
            "Mixed board sizes detected: %s. Using %dx%d for pattern mining; "
            "skipping %d game(s) with other sizes.",
            {f"{t[0]}x{t[1]}": c for t, c in size_counts.items()},
            most_common_size,
            most_common_size,
            skipped_count,
        )

    # Filter to only games with the most common size (using normalized comparison)
    filtered = [
        s for s in stats_list
        if _normalize_board_size(s.get("board_size")) == most_common_tuple
    ]

    return filtered, most_common_size


def _stable_sort_key(stats: StatsDict) -> Tuple[str, str, int, int]:
    """Generate fully stable sort key for stats dict.

    Returns:
        (game_name, date, total_moves, source_index) for deterministic ordering.
        Uses empty string / 0 as defaults for missing values.
    """
    return (
        stats.get("game_name", ""),
        stats.get("date", "") or "",
        stats.get("total_moves", 0),
        stats.get("source_index", 0),  # Final tie-breaker
    )


def _is_valid_player(player: Optional[str]) -> bool:
    """Check if player is valid ("B" or "W")."""
    return player in ("B", "W")


def _is_valid_gtp(gtp: Optional[str], board_size: int = 19) -> bool:
    """Check if gtp is a valid coordinate for the given board size.

    Validates:
    - Non-empty string
    - Not pass/resign
    - Matches GTP coordinate pattern (letter + number)
    - Within board bounds

    Args:
        gtp: GTP coordinate string (e.g., "D4", "Q16")
        board_size: Board size (default 19)

    Returns:
        True if valid coordinate, False otherwise
    """
    if not gtp or not isinstance(gtp, str):
        return False

    gtp_stripped = gtp.strip()
    gtp_lower = gtp_stripped.lower()

    # Reject pass/resign
    if gtp_lower in ("pass", "resign"):
        return False

    # Validate format with regex
    if not _GTP_COORD_PATTERN.match(gtp_stripped):
        return False

    # Validate within board bounds
    try:
        col_char = gtp_lower[0]
        row_num = int(gtp_stripped[1:])

        # GTP columns: A-H, J-T (I is skipped), max 19 for 19x19
        col_index = ord(col_char) - ord('a')
        if col_char >= 'j':
            col_index -= 1  # Adjust for skipped 'I'

        if col_index < 0 or col_index >= board_size:
            return False
        if row_num < 1 or row_num > board_size:
            return False

        return True
    except (ValueError, IndexError):
        return False


def _is_valid_move_number(move_number: Any) -> bool:
    """Check if move_number is a positive integer."""
    return isinstance(move_number, int) and move_number > 0


def _reconstruct_pattern_input(
    stats_list: List[StatsDict],
    board_size: int,
) -> List[Tuple[str, _FakeSnapshot]]:
    """Reconstruct pattern mining input from stats_list.

    Returns games sorted by (game_name, date, total_moves, source_index),
    with each game's moves sorted by (move_number, player, gtp).
    Invalid moves are skipped with warning log.
    """
    games = []
    skipped_moves_count = 0

    # Sort by stable composite key
    sorted_stats = sorted(stats_list, key=_stable_sort_key)

    for stats in sorted_stats:
        pattern_data = stats.get("pattern_data", [])
        if not pattern_data:
            continue

        game_name = stats.get("game_name", "unknown")

        # Sort moves deterministically within game
        sorted_data = sorted(
            pattern_data,
            key=lambda d: (
                d.get("move_number", 0),
                d.get("player", ""),
                d.get("gtp", ""),
            )
        )

        valid_moves = []
        for d in sorted_data:
            move_eval = _PatternMoveEval(d)

            # Validate all required fields
            if not _is_valid_move_number(move_eval.move_number):
                _logger.debug(
                    "Skipping invalid move_number=%s in %s",
                    d.get("move_number"), game_name
                )
                skipped_moves_count += 1
                continue

            if not _is_valid_player(move_eval.player):
                _logger.debug(
                    "Skipping invalid player='%s' at move %d in %s",
                    move_eval.player, move_eval.move_number, game_name
                )
                skipped_moves_count += 1
                continue

            if not _is_valid_gtp(move_eval.gtp, board_size):
                _logger.debug(
                    "Skipping invalid gtp='%s' at move %d in %s",
                    move_eval.gtp, move_eval.move_number, game_name
                )
                skipped_moves_count += 1
                continue

            if move_eval.mistake_category is None:
                # Already logged in _PatternMoveEval.__init__
                skipped_moves_count += 1
                continue

            valid_moves.append(move_eval)

        if valid_moves:
            games.append((game_name, _FakeSnapshot(valid_moves)))

    if skipped_moves_count > 0:
        _logger.warning(
            "Skipped %d invalid move(s) during pattern mining input reconstruction.",
            skipped_moves_count
        )

    return games


def _mine_patterns_safe(
    games: List[Tuple[str, _FakeSnapshot]],
    board_size: int,
    min_count: int,
    top_n: int,
) -> List["PatternCluster"]:
    """Wrapper for mine_patterns with lazy import."""
    from katrain.core.batch.stats.pattern_miner import mine_patterns
    return mine_patterns(games, board_size=board_size, min_count=min_count, top_n=top_n)  # type: ignore[arg-type]


def _format_game_refs(game_refs: List["GameRef"], max_display: int = 3) -> str:
    """Format game refs with deterministic ordering."""
    sorted_refs = sorted(
        game_refs,
        key=lambda r: (r.game_name, r.move_number, r.player)
    )
    display_refs = sorted_refs[:max_display]
    return ", ".join(
        f"{r.game_name} #{r.move_number}({r.player})"
        for r in display_refs
    )


def _append_recurring_patterns(
    lines: List[str],
    pattern_clusters: List["PatternCluster"],
    focus_player: Optional[str],
) -> None:
    """Append Recurring Patterns section to lines."""
    from katrain.core.lang import i18n

    if not pattern_clusters:
        return

    header = i18n._("pattern:section-header")
    lines.append(f"## {header}" + (f" ({focus_player})" if focus_player else ""))
    lines.append("")
    lines.append(i18n._("pattern:intro"))
    lines.append("")

    # Track unknown values for logging (once per call, not per cluster)
    unknown_phases: set[str] = set()
    unknown_areas: set[str] = set()
    unknown_severities: set[str] = set()
    unknown_players: set[str] = set()

    for idx, cluster in enumerate(pattern_clusters, 1):
        sig = cluster.signature

        # Check for unknown values and log
        if sig.phase not in PHASE_KEYS:
            unknown_phases.add(sig.phase)
        if sig.area not in AREA_KEYS:
            unknown_areas.add(sig.area)
        if sig.severity not in SEVERITY_KEYS:
            unknown_severities.add(sig.severity)
        if sig.player not in PLAYER_KEYS:
            unknown_players.add(sig.player)

        phase_label = i18n._(PHASE_KEYS.get(sig.phase, "pattern:phase-middle"))
        area_label = i18n._(AREA_KEYS.get(sig.area, "pattern:area-center"))
        severity_label = i18n._(SEVERITY_KEYS.get(sig.severity, "pattern:severity-mistake"))
        player_label = i18n._(PLAYER_KEYS.get(sig.player, "pattern:player-unknown"))

        count_loss_text = i18n._("pattern:count-loss").format(
            count=cluster.count,
            loss=cluster.total_loss,
        )

        lines.append(
            f"{idx}. **{phase_label} / {area_label} / {severity_label} "
            f"({sig.primary_tag}) [{player_label}]**: {count_loss_text}"
        )

        refs_text = _format_game_refs(cluster.game_refs, MAX_DISPLAY_REFS)
        lines.append(f"   - {refs_text}")

        # Phase 86: Add reason line if available
        # Phase 111: Safe fallback for lang attribute (current_lang was removed)
        current_lang = getattr(i18n, "current_lang", None) or getattr(i18n, "lang", None) or "en"
        reason = generate_reason_safe(
            sig.primary_tag,
            phase=sig.phase,
            area=sig.area,
            lang=current_lang,
        )
        if reason:
            lines.append(f"   - {reason}")

        lines.append("")

    # Log unknown signature field values (once per call)
    if unknown_phases:
        _logger.debug("Unknown phase value(s) in pattern clusters: %s", unknown_phases)
    if unknown_areas:
        _logger.debug("Unknown area value(s) in pattern clusters: %s", unknown_areas)
    if unknown_severities:
        _logger.debug("Unknown severity value(s) in pattern clusters: %s", unknown_severities)
    if unknown_players:
        _logger.debug("Unknown player value(s) in pattern clusters: %s", unknown_players)


def build_summary_from_stats(
    stats_list: List[StatsDict],
    focus_player: Optional[str],
    config_fn: ConfigFn,
) -> str:
    """統計dictリストからsummaryテキストを生成.

    Args:
        stats_list: 統計データ辞書のリスト
        focus_player: 対象プレイヤー名（None の場合は全プレイヤー）
        config_fn: 設定取得関数 (key) -> value

    Returns:
        Markdown形式のサマリテキスト
    """
    if not stats_list:
        return "# Multi-Game Summary\n\nNo games provided."

    # 集計
    total_games = len(stats_list)
    total_moves = sum(s["total_moves"] for s in stats_list)
    total_loss = sum(s["total_points_lost"] for s in stats_list)
    avg_loss = total_loss / total_moves if total_moves > 0 else 0.0

    # ミス分類の集計
    mistake_totals = {cat: 0 for cat in eval_metrics.MistakeCategory}
    mistake_loss_totals = {cat: 0.0 for cat in eval_metrics.MistakeCategory}
    for stats in stats_list:
        for cat, count in stats["mistake_counts"].items():
            mistake_totals[cat] += count
        for cat, loss in stats.get("mistake_total_loss", {}).items():
            mistake_loss_totals[cat] += loss

    # Freedom の集計
    freedom_totals = {diff: 0 for diff in eval_metrics.PositionDifficulty}
    for stats in stats_list:
        for diff, count in stats["freedom_counts"].items():
            freedom_totals[diff] += count

    # Phase の集計
    phase_moves_total = {"opening": 0, "middle": 0, "yose": 0, "unknown": 0}
    phase_loss_total = {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0}
    for stats in stats_list:
        for phase in phase_moves_total:
            phase_moves_total[phase] += stats["phase_moves"][phase]
            phase_loss_total[phase] += stats["phase_loss"][phase]

    # Phase × Mistake クロス集計
    phase_mistake_counts_total: Dict[Tuple[str, Any], int] = {}
    phase_mistake_loss_total: Dict[Tuple[str, Any], float] = {}
    for stats in stats_list:
        for key, count in stats.get("phase_mistake_counts", {}).items():
            phase_mistake_counts_total[key] = phase_mistake_counts_total.get(key, 0) + count
        for key, loss in stats.get("phase_mistake_loss", {}).items():
            phase_mistake_loss_total[key] = phase_mistake_loss_total.get(key, 0.0) + loss

    # Aggregate reason_tags counts
    reason_tags_totals: Dict[str, int] = {}
    for stats in stats_list:
        for tag, count in stats.get("reason_tags_counts", {}).items():
            reason_tags_totals[tag] = reason_tags_totals.get(tag, 0) + count

    # Worst moves の集計
    all_worst_moves: List[Tuple[str, int, str, str, float, float, MistakeCategory]] = []
    for stats in stats_list:
        game_name = stats["game_name"]
        for move_num, player, gtp, loss, importance, cat in stats["worst_moves"]:
            all_worst_moves.append((game_name, move_num, player, gtp, loss, importance, cat))
    all_worst_moves.sort(key=lambda x: x[5], reverse=True)  # importance でソート
    all_worst_moves = all_worst_moves[:10]

    # 日付範囲
    dates = [s["date"] for s in stats_list if s["date"]]
    date_range = f"{min(dates)} to {max(dates)}" if dates else "Unknown"

    # 段級位情報を収集
    rank_info = collect_rank_info(stats_list, focus_player)

    # Markdown生成
    lines = ["# Multi-Game Summary\n"]
    lines.append("## Meta")
    lines.append(f"- Games analyzed: {total_games}")
    if focus_player:
        lines.append(f"- Focus player: {focus_player}")
        if rank_info:
            lines.append(f"- Rank: {rank_info}")
    lines.append(f"- Date range: {date_range}")
    lines.append("")

    # 相手情報セクション（動的詳細度調整）
    if focus_player:
        opponent_info_mode = (config_fn("mykatrain_settings") or {}).get("opponent_info_mode", "auto")
        if opponent_info_mode == "auto":
            show_individual = total_games <= 5
        elif opponent_info_mode == "always_detailed":
            show_individual = True
        else:  # always_aggregate
            show_individual = False

        if show_individual and total_games >= 1:
            _append_individual_game_overview(lines, stats_list, focus_player)
        elif total_games > 1:
            _append_opponent_aggregate(lines, stats_list, focus_player, total_games)

    # Overall Statistics
    lines.append("## Overall Statistics" + (f" ({focus_player})" if focus_player else ""))
    lines.append(f"- Total games: {total_games}")
    lines.append(f"- Total moves analyzed: {total_moves}")
    lines.append(f"- Total points lost: {total_loss:.1f}")
    lines.append(f"- Average points lost per move: {avg_loss:.2f}\n")

    # Mistake Distribution
    _append_mistake_distribution(lines, mistake_totals, mistake_loss_totals, total_moves, focus_player)

    # Freedom Distribution (skip if 100% UNKNOWN)
    _append_freedom_distribution(lines, freedom_totals, total_moves, focus_player)

    # Phase × Mistake Breakdown
    _append_phase_mistake_breakdown(lines, phase_mistake_counts_total, phase_mistake_loss_total, focus_player)

    # Reason Tags Distribution
    _append_reason_tags(lines, reason_tags_totals, stats_list, focus_player)

    # Time Management (Phase 60)
    time_section = _format_time_management(stats_list, focus_player)
    if time_section:
        lines.append(time_section)

    # Top Worst Moves
    _append_worst_moves(lines, all_worst_moves, config_fn, focus_player)

    # Weakness Hypothesis
    sorted_combos = _append_weakness_hypothesis(
        lines, phase_mistake_loss_total, phase_mistake_counts_total,
        phase_loss_total, phase_moves_total, focus_player
    )

    # Urgent miss patterns in weakness section
    _append_urgent_miss_in_weakness(lines, all_worst_moves, config_fn)

    lines.append("")

    # Recurring Patterns (Phase 85)
    filtered_for_patterns, pattern_board_size = _filter_by_board_size(stats_list)
    if filtered_for_patterns and pattern_board_size:
        games_input = _reconstruct_pattern_input(filtered_for_patterns, pattern_board_size)
        if len(games_input) >= 2:  # min_count=2 requires at least 2 games
            try:
                pattern_clusters = _mine_patterns_safe(
                    games_input,
                    board_size=pattern_board_size,
                    min_count=2,
                    top_n=5,
                )
                _append_recurring_patterns(lines, pattern_clusters, focus_player)
            except Exception as e:
                _logger.warning("Pattern mining failed: %s", e)

    # Practice Priorities
    _append_practice_priorities(lines, sorted_combos, phase_mistake_counts_total, phase_loss_total, total_moves, focus_player)

    return "\n".join(lines)


def _append_individual_game_overview(
    lines: List[str],
    stats_list: List[StatsDict],
    focus_player: str,
) -> None:
    """個別対局テーブルを追加."""
    lines.append("## Individual Game Overview")
    lines.append("")
    lines.append("| Game | Opponent | Result | My Loss | Opp Loss | Ratio |")
    lines.append("|------|----------|--------|---------|----------|-------|")
    for s in stats_list:
        game_short = truncate_game_name(s["game_name"])
        if s["player_black"] == focus_player:
            opp_name = s["player_white"]
            my_loss = s.get("loss_by_player", {}).get("B", 0.0)
            opp_loss = s.get("loss_by_player", {}).get("W", 0.0)
        else:
            opp_name = s["player_black"]
            my_loss = s.get("loss_by_player", {}).get("W", 0.0)
            opp_loss = s.get("loss_by_player", {}).get("B", 0.0)
        ratio = my_loss / opp_loss if opp_loss > 0 else 0.0
        result = "Win?" if ratio < 0.8 else ("Loss?" if ratio > 1.2 else "Close")
        lines.append(f"| {game_short} | {opp_name[:15]} | {result} | {my_loss:.1f} | {opp_loss:.1f} | {ratio:.2f} |")
    lines.append("")


def _append_opponent_aggregate(
    lines: List[str],
    stats_list: List[StatsDict],
    focus_player: str,
    total_games: int,
) -> None:
    """集計情報のみ（6局以上）."""
    lines.append("## Opponent Statistics (Aggregate)")
    opponents = set()
    total_opp_loss = 0.0
    total_my_loss = 0.0
    for s in stats_list:
        if s["player_black"] == focus_player:
            opponents.add(s["player_white"])
            total_my_loss += s.get("loss_by_player", {}).get("B", 0.0)
            total_opp_loss += s.get("loss_by_player", {}).get("W", 0.0)
        else:
            opponents.add(s["player_black"])
            total_my_loss += s.get("loss_by_player", {}).get("W", 0.0)
            total_opp_loss += s.get("loss_by_player", {}).get("B", 0.0)
    avg_opp_loss = total_opp_loss / total_games if total_games > 0 else 0.0
    avg_my_loss = total_my_loss / total_games if total_games > 0 else 0.0
    loss_ratio = avg_my_loss / avg_opp_loss if avg_opp_loss > 0 else 0.0
    lines.append(f"- Opponents faced: {len(opponents)}")
    lines.append(f"- Average opponent loss per game: {avg_opp_loss:.1f}")
    lines.append(f"- Average my loss per game: {avg_my_loss:.1f}")
    lines.append(f"- Loss ratio (me/opponent): {loss_ratio:.2f}")
    lines.append("")


def _append_mistake_distribution(
    lines: List[str],
    mistake_totals: Dict[MistakeCategory, int],
    mistake_loss_totals: Dict[MistakeCategory, float],
    total_moves: int,
    focus_player: Optional[str],
) -> None:
    """Mistake Distributionテーブル."""
    lines.append("## Mistake Distribution" + (f" ({focus_player})" if focus_player else ""))
    lines.append("| Category | Count | Percentage | Avg Loss |")
    lines.append("|----------|-------|------------|----------|")
    cat_names = {"GOOD": "Good", "INACCURACY": "Inaccuracy", "MISTAKE": "Mistake", "BLUNDER": "Blunder"}
    for cat in eval_metrics.MistakeCategory:
        count = mistake_totals[cat]
        pct = (count / total_moves * 100) if total_moves > 0 else 0
        cat_loss = mistake_loss_totals.get(cat, 0.0)
        avg = cat_loss / count if count > 0 else 0.0
        lines.append(f"| {cat_names.get(cat.name, cat.name)} | {count} | {pct:.1f}% | {avg:.2f} |")
    lines.append("")


def _append_freedom_distribution(
    lines: List[str],
    freedom_totals: Dict[PositionDifficulty, int],
    total_moves: int,
    focus_player: Optional[str],
) -> None:
    """Freedom Distribution（非UNKNOWNがある場合のみ）."""
    has_real_freedom_data = any(
        count > 0 for diff, count in freedom_totals.items()
        if diff != eval_metrics.PositionDifficulty.UNKNOWN
    )

    if has_real_freedom_data:
        lines.append("## Freedom Distribution" + (f" ({focus_player})" if focus_player else ""))
        lines.append("| Difficulty | Count | Percentage |")
        lines.append("|------------|-------|------------|")
        diff_names = {"EASY": "Easy (wide)", "NORMAL": "Normal", "HARD": "Hard (narrow)", "ONLY_MOVE": "Only move"}
        for diff in eval_metrics.PositionDifficulty:
            if diff == eval_metrics.PositionDifficulty.UNKNOWN:
                continue
            count = freedom_totals[diff]
            pct = (count / total_moves * 100) if total_moves > 0 else 0
            lines.append(f"| {diff_names.get(diff.name, diff.name)} | {count} | {pct:.1f}% |")
        lines.append("")


def _append_phase_mistake_breakdown(
    lines: List[str],
    phase_mistake_counts_total: Dict[PhaseMistakeKey, int],
    phase_mistake_loss_total: Dict[PhaseMistakeKey, float],
    focus_player: Optional[str],
) -> None:
    """Phase × Mistake クロス集計テーブル."""
    phase_names = {"opening": "Opening", "middle": "Middle game", "yose": "Endgame", "unknown": "Unknown"}
    lines.append("## Phase × Mistake Breakdown" + (f" ({focus_player})" if focus_player else ""))
    lines.append("| Phase | Good | Inaccuracy | Mistake | Blunder | Total Loss |")
    lines.append("|-------|------|------------|---------|---------|------------|")
    for phase in ["opening", "middle", "yose"]:
        row = [phase_names[phase]]
        total_phase_loss = 0.0
        for cat in eval_metrics.MistakeCategory:
            key = (phase, cat)
            count = phase_mistake_counts_total.get(key, 0)
            loss = phase_mistake_loss_total.get(key, 0.0)
            if count > 0 and cat != eval_metrics.MistakeCategory.GOOD:
                total_phase_loss += loss
                row.append(f"{count} ({loss:.1f})")
            else:
                row.append(f"{count}")
        row.append(f"{total_phase_loss:.1f}")
        lines.append(f"| {' | '.join(row)} |")
    lines.append("")


def _append_reason_tags(
    lines: List[str],
    reason_tags_totals: Dict[str, int],
    stats_list: List[StatsDict],
    focus_player: Optional[str],
) -> None:
    """Reason Tags Distribution."""
    if not reason_tags_totals:
        return

    focus_suffix = f" ({focus_player})" if focus_player else ""
    lines.append(f"## ミス理由タグ分布{focus_suffix}")
    lines.append("")

    sorted_tags = sorted(
        reason_tags_totals.items(),
        key=lambda x: x[1],
        reverse=True
    )

    for tag, count in sorted_tags:
        label = eval_metrics.REASON_TAG_LABELS.get(tag, tag)
        lines.append(f"- {label}: {count} 回")

    lines.append("")

    # 棋力推定
    total_important = sum(
        sum(stats.get("reason_tags_counts", {}).values())
        for stats in stats_list
    )
    if total_important >= 5:
        estimation = eval_metrics.estimate_skill_level_from_tags(
            reason_tags_totals,
            total_important
        )

        level_labels = {
            "beginner": "初級〜中級（G0-G1相当）",
            "standard": "有段者（G2-G3相当）",
            "advanced": "高段者（G4相当）",
            "unknown": "不明"
        }

        lines.append(f"## 推定棋力{focus_suffix}")
        lines.append("")
        lines.append(f"- **レベル**: {level_labels.get(estimation.estimated_level, estimation.estimated_level)}")
        lines.append(f"- **確度**: {estimation.confidence:.0%}")
        lines.append(f"- **理由**: {estimation.reason}")

        preset_recommendations = {
            "beginner": "beginner（緩め：5目以上を大悪手判定）",
            "standard": "standard（標準：2目以上を悪手判定）",
            "advanced": "advanced（厳しめ：1目以上を悪手判定）"
        }
        if estimation.estimated_level in preset_recommendations:
            lines.append(f"- **推奨プリセット**: {preset_recommendations[estimation.estimated_level]}")

        lines.append("")


def _append_worst_moves(
    lines: List[str],
    all_worst_moves: List[Tuple[str, int, str, str, float, float, MistakeCategory]],
    config_fn: ConfigFn,
    focus_player: Optional[str],
) -> None:
    """Top Worst Movesセクション."""
    from katrain.core.reports.summary_report import (
        _detect_urgent_miss_sequences,
        _convert_sgf_to_gtp_coord,
    )

    lines.append("## Top Worst Moves" + (f" ({focus_player})" if focus_player else ""))

    if not all_worst_moves:
        lines.append("- No significant mistakes found.")
        lines.append("")
        return

    # TempMoveクラス
    class TempMove:
        def __init__(self, move_num: int, player: str, gtp: str, loss: float, importance: float) -> None:
            self.move_number = move_num
            self.player = player
            self.gtp = gtp
            self.points_lost = loss
            self.score_loss = loss
            self.importance = importance

    moves_for_detection = [
        (game_name, TempMove(move_num, player, gtp, loss, importance))
        for game_name, move_num, player, gtp, loss, importance, cat in all_worst_moves
    ]

    skill_preset = config_fn("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET
    urgent_config = eval_metrics.get_urgent_miss_config(skill_preset)

    sequences, filtered_moves = _detect_urgent_miss_sequences(
        moves_for_detection,
        threshold_loss=urgent_config.threshold_loss,
        min_consecutive=urgent_config.min_consecutive
    )

    # 急場見逃しパターン
    if sequences:
        lines.append("")
        lines.append("**注意**: 以下の区間は双方が急場を見逃した可能性があります（損失20目超が3手以上連続）")
        lines.append("| Game | 手数範囲 | 連続 | 総損失 | 平均損失/手 |")
        lines.append("|------|---------|------|--------|------------|")

        for seq in sequences:
            short_game = truncate_game_name(seq['game'])
            avg_loss = seq['total_loss'] / seq['count']
            lines.append(
                f"| {short_game} | #{seq['start']}-{seq['end']} | "
                f"{seq['count']}手 | {seq['total_loss']:.1f}目 | {avg_loss:.1f}目 |"
            )
        lines.append("")

    # 通常のワースト手
    if filtered_moves:
        filtered_moves.sort(key=lambda x: x[1].points_lost or x[1].score_loss or 0, reverse=True)
        display_moves = filtered_moves[:10]

        if sequences:
            lines.append("通常のワースト手（損失20目以下 or 単発）:")
        lines.append("| Game | # | P | Coord | Loss | Importance | Category |")
        lines.append("|------|---|---|-------|------|------------|----------|")

        for game_name, temp_move in display_moves:
            coord = temp_move.gtp or '-'
            if coord and len(coord) == 2 and coord.isalpha() and coord.islower():
                coord = _convert_sgf_to_gtp_coord(coord, 19)

            cat_name = "UNKNOWN"
            for gn, mn, pl, gt, ls, imp, ct in all_worst_moves:
                if gn == game_name and mn == temp_move.move_number:
                    cat_name = ct.name
                    break

            lines.append(f"| {truncate_game_name(game_name)} | {temp_move.move_number} | {temp_move.player} | {coord} | {temp_move.points_lost:.1f} | {temp_move.importance:.1f} | {cat_name} |")
    elif sequences:
        lines.append("通常のワースト手: なし（すべて急場見逃しパターン）")
    else:
        lines.append("| Game | # | P | Coord | Loss | Importance | Category |")
        lines.append("|------|---|---|-------|------|------------|----------|")
        for game_name, move_num, player, gtp, loss, importance, cat in all_worst_moves:
            coord = gtp or '-'
            if coord and len(coord) == 2 and coord.isalpha() and coord.islower():
                coord = _convert_sgf_to_gtp_coord(coord, 19)
            lines.append(f"| {truncate_game_name(game_name)} | {move_num} | {player} | {coord} | {loss:.1f} | {importance:.1f} | {cat.name} |")

    lines.append("")


def _append_weakness_hypothesis(
    lines: List[str],
    phase_mistake_loss_total: Dict[PhaseMistakeKey, float],
    phase_mistake_counts_total: Dict[PhaseMistakeKey, int],
    phase_loss_total: Dict[str, float],
    phase_moves_total: Dict[str, int],
    focus_player: Optional[str],
) -> List[Tuple[PhaseMistakeKey, float]]:
    """弱点仮説セクション."""
    phase_names = {"opening": "Opening", "middle": "Middle game", "yose": "Endgame", "unknown": "Unknown"}

    lines.append("## Weakness Hypothesis" + (f" ({focus_player})" if focus_player else ""))
    lines.append("\nBased on cross-tabulation analysis:\n")

    hypotheses = []
    cat_names_ja = {
        eval_metrics.MistakeCategory.BLUNDER: "大悪手",
        eval_metrics.MistakeCategory.MISTAKE: "悪手",
        eval_metrics.MistakeCategory.INACCURACY: "軽微なミス",
    }

    sorted_combos: List[Tuple[Tuple[str, MistakeCategory], float]] = []
    if phase_mistake_loss_total:
        sorted_combos = sorted(
            [(k, v) for k, v in phase_mistake_loss_total.items() if k[1] in cat_names_ja and v > 0],
            key=lambda x: x[1],
            reverse=True
        )

        for i, (key, loss) in enumerate(sorted_combos[:3]):
            phase, category = key
            count = phase_mistake_counts_total.get(key, 0)
            hypotheses.append(
                f"{i+1}. **{phase_names.get(phase, phase)}の{cat_names_ja[category]}** "
                f"({count}回、損失{loss:.1f}目)"
            )

    if hypotheses:
        lines.extend(hypotheses)
        lines.append("")
        lines.append("**分析**:")

        if sorted_combos:
            worst_phase, worst_cat = sorted_combos[0][0]
            worst_loss = sorted_combos[0][1]
            worst_count = phase_mistake_counts_total.get((worst_phase, worst_cat), 0)

            phase_total_loss = phase_loss_total.get(worst_phase, 0)
            if phase_total_loss > 0:
                pct = (worst_loss / phase_total_loss) * 100
                lines.append(
                    f"- {phase_names.get(worst_phase, worst_phase)}の損失の{pct:.1f}%が"
                    f"{cat_names_ja[worst_cat]}によるもの"
                )

            phase_total_moves = phase_moves_total.get(worst_phase, 0)
            if phase_total_moves > 0:
                freq_pct = (worst_count / phase_total_moves) * 100
                lines.append(
                    f"- {phase_names.get(worst_phase, worst_phase)}の{freq_pct:.1f}%の手が"
                    f"{cat_names_ja[worst_cat]}と判定されている"
                )
    else:
        lines.append("- 明確な弱点パターンは検出されませんでした。")

    return sorted_combos


def _append_urgent_miss_in_weakness(
    lines: List[str],
    all_worst_moves: List[Tuple[str, int, str, str, float, float, MistakeCategory]],
    config_fn: ConfigFn,
) -> None:
    """弱点仮説セクションに急場見逃しパターンを追加."""
    if not all_worst_moves:
        return

    from katrain.core.reports.summary_report import _detect_urgent_miss_sequences

    class TempMove:
        def __init__(self, move_num: int, player: str, gtp: str, loss: float, importance: float) -> None:
            self.move_number = move_num
            self.player = player
            self.gtp = gtp
            self.points_lost = loss
            self.score_loss = loss
            self.importance = importance

    moves_for_detection = [
        (game_name, TempMove(move_num, player, gtp, loss, importance))
        for game_name, move_num, player, gtp, loss, importance, cat in all_worst_moves
    ]

    skill_preset = config_fn("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET
    urgent_config = eval_metrics.get_urgent_miss_config(skill_preset)

    sequences, _ = _detect_urgent_miss_sequences(
        moves_for_detection,
        threshold_loss=urgent_config.threshold_loss,
        min_consecutive=urgent_config.min_consecutive
    )

    if sequences:
        lines.append("")
        lines.append("**急場見逃しパターン**:")
        for seq in sequences:
            short_game = truncate_game_name(seq['game'])
            avg_loss = seq['total_loss'] / seq['count']
            lines.append(
                f"- {short_game} #{seq['start']}-{seq['end']}: "
                f"{seq['count']}手連続、総損失{seq['total_loss']:.1f}目（平均{avg_loss:.1f}目/手）"
            )

        lines.append("")
        lines.append("**推奨アプローチ**:")
        lines.append("- 詰碁（死活）訓練で読みの精度向上")
        lines.append("- 対局中、戦いの前に「自分の石は安全か？」「相手の弱点はどこか？」を確認")
        lines.append("- 急場見逃し区間のSGFを重点的に復習")


def _format_time_management(
    stats_list: List[StatsDict],
    focus_player: Optional[str],
) -> str:
    """Time Managementセクションを生成.

    Phase 60: Pacing/Tilt統合

    Args:
        stats_list: 統計データ辞書のリスト（各辞書にpacing_statsキーを含む）
        focus_player: 対象プレイヤー名（None の場合は全プレイヤー）

    Returns:
        Markdown形式のTime Managementセクション（時間データなしの場合は空文字列）
    """
    from katrain.core.reports.sections.time_section import (
        TimeStatsData,
        format_time_stats,
        format_tilt_episode,
        get_section_title,
        get_tilt_episodes_label,
        get_player_label,
    )

    # Check if any game has time data
    has_any_time_data = any(
        stats.get("pacing_stats", {}).get("has_time_data", False)
        for stats in stats_list
    )
    if not has_any_time_data:
        return ""

    lines = [f"## {get_section_title()}"]

    def _aggregate_stats(stats_list: List[StatsDict], player_color: str, focus_player: Optional[str] = None) -> Tuple["TimeStatsData", List[Dict[str, Any]]]:
        """Aggregate time stats for a player color."""
        total_blitz = 0
        total_blitz_mistake = 0
        total_long_think = 0
        total_long_think_mistake = 0
        tilt_episodes = []

        for stats in stats_list:
            pacing = stats.get("pacing_stats", {})
            if not pacing.get("has_time_data", False):
                continue

            # If focus_player specified, check if this player is in the game
            if focus_player:
                if stats.get("player_black") == focus_player:
                    color = "B"
                elif stats.get("player_white") == focus_player:
                    color = "W"
                else:
                    continue
                if color != player_color:
                    continue

            ps = pacing.get("player_stats", {}).get(player_color, {})
            total_blitz += ps.get("blitz_count", 0)
            total_blitz_mistake += ps.get("blitz_mistake_count", 0)
            total_long_think += ps.get("long_think_count", 0)
            total_long_think_mistake += ps.get("long_think_mistake_count", 0)

            for ep in pacing.get("tilt_episodes", []):
                if ep.get("player") == player_color:
                    ep_copy = ep.copy()
                    ep_copy["game_name"] = stats.get("game_name", "")
                    tilt_episodes.append(ep_copy)

        return TimeStatsData(
            blitz_count=total_blitz,
            blitz_mistake_count=total_blitz_mistake,
            long_think_count=total_long_think,
            long_think_mistake_count=total_long_think_mistake,
        ), tilt_episodes

    def _format_player_section(label: str, stats_data: "TimeStatsData", tilt_episodes: List[Dict[str, Any]]) -> List[str]:
        """Format a single player's time management section."""
        section_lines = [f"\n### {label}", ""]
        section_lines.extend(format_time_stats(stats_data))

        if tilt_episodes:
            section_lines.append("")
            section_lines.append(f"**{get_tilt_episodes_label()}:**")
            for ep in tilt_episodes:
                section_lines.append(
                    format_tilt_episode(
                        game_name=ep.get("game_name", ""),
                        start_move=ep["start_move"],
                        end_move=ep["end_move"],
                        severity=ep["severity"],
                        cumulative_loss=ep["cumulative_loss"],
                    )
                )
        return section_lines

    if focus_player:
        # Aggregate across all games where focus_player appears (as B or W)
        total_blitz = 0
        total_blitz_mistake = 0
        total_long_think = 0
        total_long_think_mistake = 0
        tilt_episodes = []

        for stats in stats_list:
            pacing = stats.get("pacing_stats", {})
            if not pacing.get("has_time_data", False):
                continue

            if stats.get("player_black") == focus_player:
                player_color = "B"
            elif stats.get("player_white") == focus_player:
                player_color = "W"
            else:
                continue

            ps = pacing.get("player_stats", {}).get(player_color, {})
            total_blitz += ps.get("blitz_count", 0)
            total_blitz_mistake += ps.get("blitz_mistake_count", 0)
            total_long_think += ps.get("long_think_count", 0)
            total_long_think_mistake += ps.get("long_think_mistake_count", 0)

            for ep in pacing.get("tilt_episodes", []):
                if ep.get("player") == player_color:
                    ep_copy = ep.copy()
                    ep_copy["game_name"] = stats.get("game_name", "")
                    tilt_episodes.append(ep_copy)

        stats_data = TimeStatsData(
            blitz_count=total_blitz,
            blitz_mistake_count=total_blitz_mistake,
            long_think_count=total_long_think,
            long_think_mistake_count=total_long_think_mistake,
        )
        lines.extend(_format_player_section(focus_player, stats_data, tilt_episodes))

    else:
        # Show Black and White separately
        for player_color in ["B", "W"]:
            stats_data, tilt_episodes = _aggregate_stats(stats_list, player_color)
            label = get_player_label(player_color)
            lines.extend(_format_player_section(label, stats_data, tilt_episodes))

    lines.append("")
    return "\n".join(lines)


def _append_practice_priorities(
    lines: List[str],
    sorted_combos: List[Tuple[PhaseMistakeKey, float]],
    phase_mistake_counts_total: Dict[PhaseMistakeKey, int],
    phase_loss_total: Dict[str, float],
    total_moves: int,
    focus_player: Optional[str],
) -> None:
    """Practice Prioritiesセクション."""
    phase_names = {"opening": "Opening", "middle": "Middle game", "yose": "Endgame", "unknown": "Unknown"}
    cat_names_ja = {
        eval_metrics.MistakeCategory.BLUNDER: "大悪手",
        eval_metrics.MistakeCategory.MISTAKE: "悪手",
        eval_metrics.MistakeCategory.INACCURACY: "軽微なミス",
    }

    lines.append("## 練習の優先順位" + (f" ({focus_player})" if focus_player else ""))
    lines.append("\nBased on the data above, consider focusing on:\n")

    priorities = []

    # 弱点仮説から上位2つを抽出
    for i, (key, loss) in enumerate(sorted_combos[:2]):
        phase, category = key
        count = phase_mistake_counts_total.get(key, 0)
        priorities.append(
            f"- {i+1}. **{phase_names.get(phase, phase)}の{cat_names_ja[category]}** "
            f"({count}回、損失{loss:.1f}目)"
        )

    # フォールバック
    if not priorities and total_moves > 0:
        worst_phase = max(phase_loss_total.items(), key=lambda x: x[1])
        if worst_phase[1] > 0:
            priorities.append(f"- Improve {phase_names[worst_phase[0]]} play ({worst_phase[1]:.1f} points lost)")

    if priorities:
        lines.extend(priorities)
    else:
        lines.append("- No specific priorities identified. Keep up the good work!")

"""Pattern-mining input helpers for the karte summary (Phase 174 P1-D).

This module extracts the deterministic, pure helpers used by
``build_summary_from_stats`` to feed the pattern miner. These functions
take a list of stats dicts and reconstruct a normalized dataset of moves
plus a few validating guards (board size filter, coordinate validity).

Splitting these out of ``summary_formatter.py`` keeps the Markdown
assembly logic concentrated in one place and makes the data-shaping
helpers individually testable.

Backward compatibility: ``summary_formatter.py`` re-exports every public
symbol via ``from katrain.gui.features.summary_pattern import *`` so the
private-import paths (``from ...summary_formatter import _filter_by_...``)
used by existing tests continue to work.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from katrain.core import eval_metrics
from katrain.core.analysis.reason_generator import generate_reason_safe
from katrain.core.analysis.models import EvalSnapshot
from katrain.core.batch.stats.pattern_miner import GameRef, PatternCluster

# Pattern-mining constants moved verbatim from summary_formatter.
PHASE_KEYS: dict[str, str] = {
    "opening": "pattern:phase-opening",
    "middle": "pattern:phase-middle",
    "endgame": "pattern:phase-endgame",
}
AREA_KEYS: dict[str, str] = {
    "corner": "pattern:area-corner",
    "edge": "pattern:area-edge",
    "center": "pattern:area-center",
}
SEVERITY_KEYS: dict[str, str] = {
    "mistake": "pattern:severity-mistake",
    "blunder": "pattern:severity-blunder",
}
PLAYER_KEYS: dict[str, str] = {
    "B": "pattern:player-black",
    "W": "pattern:player-white",
    "?": "pattern:player-unknown",
}
MAX_DISPLAY_REFS = 3
_GTP_COORD_PATTERN = __import__("re").compile(
    r"^[a-hj-t](?:[1-9]|1[0-9]|2[0-5])$", __import__("re").IGNORECASE
)

_logger = logging.getLogger("katrain.gui.features.summary_pattern")

StatsDict = dict[str, Any]
PhaseMistakeKey = tuple[str, eval_metrics.MistakeCategory]


# =============================================================================
# Duck-typed helpers
# =============================================================================


class _PatternMoveEval:
    """Duck-typed ``MoveEval`` for pattern mining.

    Safely handles invalid/missing data without raising exceptions.
    """

    __slots__ = (
        "move_number",
        "player",
        "gtp",
        "score_loss",
        "points_lost",
        "mistake_category",
        "meaning_tag_id",
    )

    mistake_category: eval_metrics.MistakeCategory | None

    def __init__(self, data: dict[str, Any]) -> None:
        self.move_number = data.get("move_number", 0)
        self.player = data.get("player")
        self.gtp = data.get("gtp")
        self.score_loss = data.get("score_loss")
        self.points_lost = data.get("points_lost")
        self.meaning_tag_id = data.get("meaning_tag_id")

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
    """Duck-typed ``EvalSnapshot`` for pattern mining."""

    __slots__ = ("moves",)

    def __init__(self, moves: list[_PatternMoveEval]) -> None:
        self.moves = moves


# =============================================================================
# Validators
# =============================================================================


def _normalize_board_size(bs: Any) -> tuple[int, int] | None:
    """Normalize board_size to a (w, h) tuple, or None if invalid."""
    if bs is None:
        return None
    if not isinstance(bs, (tuple, list)) or len(bs) < 2:
        return None
    try:
        return (int(bs[0]), int(bs[1]))
    except (ValueError, TypeError):
        return None


def _is_valid_player(player: Any) -> bool:
    """Player color check: 'B' or 'W' only."""
    return player in ("B", "W")


def _is_valid_gtp(gtp: Any, board_size: int = 19) -> bool:
    """Coordinate validity check (GTP convention, 'I' skipped)."""
    if not gtp or not isinstance(gtp, str):
        return False

    gtp_stripped = gtp.strip()
    gtp_lower = gtp_stripped.lower()

    if gtp_lower in ("pass", "resign"):
        return False

    if not _GTP_COORD_PATTERN.match(gtp_stripped):
        return False

    try:
        col_char = gtp_lower[0]
        row_num = int(gtp_stripped[1:])

        col_index = ord(col_char) - ord("a")
        if col_char >= "j":
            col_index -= 1

        if col_index < 0 or col_index >= board_size:
            return False
        return not (row_num < 1 or row_num > board_size)
    except (ValueError, IndexError):
        return False


def _is_valid_move_number(move_number: Any) -> bool:
    """Positive-integer check for move numbers."""
    return isinstance(move_number, int) and move_number > 0


def _stable_sort_key(stats: StatsDict) -> tuple[str, str, int, int]:
    """Composite sort key for deterministic ordering."""
    return (
        stats.get("game_name", ""),
        stats.get("date", "") or "",
        stats.get("total_moves", 0),
        stats.get("source_index", 0),
    )


# =============================================================================
# Aggregators
# =============================================================================

def _filter_by_board_size(stats_list: list[StatsDict]) -> tuple[list[StatsDict], int | None]:
    """Filter to games with a consistent square board size."""
    size_counts: Counter[tuple[int, int]] = Counter()
    non_square_games: list[str] = []
    invalid_games: list[str] = []

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

    if invalid_games:
        _logger.debug(
            "Skipping %d game(s) with missing/invalid board_size: %s",
            len(invalid_games),
            ", ".join(invalid_games[:5]) + ("..." if len(invalid_games) > 5 else ""),
        )

    if non_square_games:
        _logger.warning(
            "Skipping %d non-square board game(s) for pattern mining: %s",
            len(non_square_games),
            ", ".join(non_square_games[:5]) + ("..." if len(non_square_games) > 5 else ""),
        )

    if not size_counts:
        _logger.debug("No games have valid square board_size; skipping pattern mining.")
        return [], None

    most_common_tuple = size_counts.most_common(1)[0][0]
    most_common_size = most_common_tuple[0]

    if len(size_counts) > 1:
        skipped_count = sum(c for t, c in size_counts.items() if t != most_common_tuple)
        _logger.warning(
            "Mixed board sizes detected: %s. Using %dx%d for pattern mining; skipping %d game(s) with other sizes.",
            {f"{t[0]}x{t[1]}": c for t, c in size_counts.items()},
            most_common_size,
            most_common_size,
            skipped_count,
        )

    filtered = [
        s
        for s in stats_list
        if _normalize_board_size(s.get("board_size")) == most_common_tuple
    ]

    return filtered, most_common_size


def _reconstruct_pattern_input(
    stats_list: list[StatsDict], board_size: int
) -> list[tuple[str, _FakeSnapshot]]:
    """Reconstruct (game_name, FakeSnapshot) pairs sorted deterministically."""
    games: list[tuple[str, _FakeSnapshot]] = []
    skipped_moves_count = 0

    sorted_stats = sorted(stats_list, key=_stable_sort_key)

    for stats in sorted_stats:
        pattern_data = stats.get("pattern_data", [])
        if not pattern_data:
            continue

        game_name = stats.get("game_name", "unknown")

        sorted_data = sorted(
            pattern_data,
            key=lambda d: (
                d.get("move_number", 0),
                d.get("player", ""),
                d.get("gtp", ""),
            ),
        )

        valid_moves: list[_PatternMoveEval] = []
        for d in sorted_data:
            move_eval = _PatternMoveEval(d)

            if not _is_valid_move_number(move_eval.move_number):
                skipped_moves_count += 1
                continue
            if not _is_valid_player(move_eval.player):
                skipped_moves_count += 1
                continue
            if not _is_valid_gtp(move_eval.gtp, board_size):
                skipped_moves_count += 1
                continue
            if move_eval.mistake_category is None:
                skipped_moves_count += 1
                continue

            valid_moves.append(move_eval)

        if valid_moves:
            games.append((game_name, _FakeSnapshot(valid_moves)))

    if skipped_moves_count > 0:
        _logger.warning(
            "Skipped %d invalid move(s) during pattern mining input reconstruction.",
            skipped_moves_count,
        )

    return games


def _mine_patterns_safe(
    games: list[tuple[str, _FakeSnapshot]],
    board_size: int,
    min_count: int,
    top_n: int,
) -> list[PatternCluster]:
    """Lazy wrapper for the heavy pattern miner.

    The ``_FakeSnapshot`` here is a duck-typed ``EvalSnapshot``; we cast
    the list to the producer's expected element type so mypy is happy.
    """
    from katrain.core.batch.stats.pattern_miner import mine_patterns

    typed_games: list[tuple[str, EvalSnapshot]] = [
        (name, snapshot)  # type: ignore[misc]
        for name, snapshot in games
    ]
    return mine_patterns(typed_games, board_size=board_size, min_count=min_count, top_n=top_n)


def _format_game_refs(game_refs: list[GameRef], max_display: int = 3) -> str:
    """Format ``GameRef`` objects with deterministic ordering."""
    sorted_refs = sorted(game_refs, key=lambda r: (r.game_name, r.move_number, r.player))
    display_refs = sorted_refs[:max_display]
    return ", ".join(f"{r.game_name} #{r.move_number}({r.player})" for r in display_refs)


__all__ = [
    "StatsDict",
    "PhaseMistakeKey",
    "_PatternMoveEval",
    "_FakeSnapshot",
    "_normalize_board_size",
    "_is_valid_player",
    "_is_valid_gtp",
    "_is_valid_move_number",
    "_stable_sort_key",
    "_filter_by_board_size",
    "_reconstruct_pattern_input",
    "_mine_patterns_safe",
    "_format_game_refs",
    "_append_recurring_patterns",
    "PHASE_KEYS",
    "AREA_KEYS",
    "SEVERITY_KEYS",
    "PLAYER_KEYS",
    "MAX_DISPLAY_REFS",
]

def _append_recurring_patterns(
    lines: list[str],
    pattern_clusters: list[PatternCluster],
    focus_player: str | None,
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

    unknown_phases: set[str] = set()
    unknown_areas: set[str] = set()
    unknown_severities: set[str] = set()
    unknown_players: set[str] = set()

    for idx, cluster in enumerate(pattern_clusters, 1):
        sig = cluster.signature

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

    if unknown_phases:
        _logger.debug("Unknown phase value(s) in pattern clusters: %s", unknown_phases)
    if unknown_areas:
        _logger.debug("Unknown area value(s) in pattern clusters: %s", unknown_areas)
    if unknown_severities:
        _logger.debug("Unknown severity value(s) in pattern clusters: %s", unknown_severities)
    if unknown_players:
        _logger.debug("Unknown player value(s) in pattern clusters: %s", unknown_players)


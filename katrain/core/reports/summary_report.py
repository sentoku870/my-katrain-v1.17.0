"""Summary report generation for multiple game analysis.

PR #116: Phase B2 - summary_report.py extraction from game.py
Refactored (Phase 128): Logic separated into summary_logic.py, constants moved to constants.py.

All functions in this module:
- Are static (no self parameter)
- Do not modify any state
- Do not import from katrain.gui (core layer only)
"""

from __future__ import annotations

from typing import Any

from katrain.core.eval_metrics import GameSummaryData
from katrain.core.reports.summary_logic import detect_urgent_miss_sequences
from katrain.core.sgf_parser import Move


def _convert_sgf_to_gtp_coord(coord: str, board_size: int) -> str:
    """Convert SGF coordinate (e.g. 'pd') to GTP coordinate (e.g. 'D16').

    SGF format: lowercase 2-letter coordinate where the first letter is
    the column (a=0, b=1, ...) and the second letter is the row counted
    from the top of the board (a=top, b=below-top, ...).

    GTP format: uppercase column letter (skipping 'I') followed by the
    row number counted from the bottom (1=bottom).

    Args:
        coord: SGF coordinate (e.g. "pd" → column p, row d from top).
        board_size: Board size used to flip the row index.

    Returns:
        GTP coordinate (e.g. "D16" on a 19x19 board).
    """
    if not isinstance(coord, str) or len(coord) < 2:
        return coord
    try:
        x_idx = Move.SGF_COORD.index(coord[0])
        y_from_top = Move.SGF_COORD.index(coord[1])
    except ValueError:
        return coord
    y_idx = board_size - y_from_top - 1
    if y_idx < 0 or x_idx >= len(Move.GTP_COORD):
        return coord
    return f"{Move.GTP_COORD[x_idx]}{y_idx + 1}"


def _detect_urgent_miss_sequences(
    moves: list[Any],
    threshold_loss: float,
    min_consecutive: int,
) -> tuple[list[dict[str, Any]], list[Any]]:
    """Detect sequences of consecutive urgent mistakes.

    Delegates to :func:`katrain.core.reports.summary_logic.detect_urgent_miss_sequences`,
    which holds the canonical implementation. Kept here as a stable
    import point for ``summary_formatter.py`` (avoids extra imports at
    call sites that already import from this module).

    Args:
        moves: List of ``(game_name, move)`` tuples.
        threshold_loss: Minimum loss (in points) to qualify a move as
            an urgent miss.
        min_consecutive: Minimum number of consecutive urgent-miss
            moves to register as a sequence.

    Returns:
        Tuple of (sequences, filtered_moves) where ``sequences`` is a
        list of sequence dicts and ``filtered_moves`` are the non-
        sequence worst moves.
    """
    return detect_urgent_miss_sequences(moves, threshold_loss, min_consecutive)


def build_summary_report(game_data_list: list[GameSummaryData], focus_player: str | None = None) -> str:
    """
    複数局から統計まとめを生成（JSON形式）

    Phase 171 で KataGo 専用化により Phase 159A の非KataGo gate を削除。

    Args:
        game_data_list: 各対局のデータリスト
        focus_player: 集計対象プレイヤー名（Noneなら全プレイヤー）

    Returns:
        JSON形式のまとめレポート
    """
    if not game_data_list:
        return '{"meta": {"games_analyzed": 0}}'

    import json

    from katrain.core.reports.summary_json_export import build_summary_json

    json_data = build_summary_json(game_data_list, focus_player)
    return json.dumps(json_data, indent=2, ensure_ascii=False)

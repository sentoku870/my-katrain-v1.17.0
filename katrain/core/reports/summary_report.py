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


def _convert_sgf_to_gtp_coord(coord: str, board_size: int) -> str:
    """Convert SGF coordinate (e.g. 'pd') to GTP coordinate (e.g. 'D16').

    SGF uses lowercase letters for both axes (a=1st line).
    GTP uses uppercase letters skipping 'I' for columns + numbers for rows.
    If the input does not look like an SGF coordinate, it is returned unchanged.
    """
    if len(coord) != 2:
        return coord
    col_lower, row_lower = coord[0].lower(), coord[1].lower()
    if not ("a" <= col_lower <= "s") or not ("a" <= row_lower <= "s"):
        return coord
    col_idx = ord(col_lower) - ord("a")  # 0-based
    row_idx = ord(row_lower) - ord("a")  # 0-based
    if col_idx >= board_size or row_idx >= board_size:
        return coord
    # GTP column letters skip 'I': A-H for indices 0-7, J-T for indices 8-18
    gtp_col_idx = col_idx + (1 if col_idx >= 8 else 0)
    gtp_col = chr(ord("A") + gtp_col_idx)
    gtp_row = str(row_idx + 1)
    return gtp_col + gtp_row


def _detect_urgent_miss_sequences(
    moves: list[Any],
    threshold_loss: float,
    min_consecutive: int,
) -> tuple[list[dict[str, Any]], list[Any]]:
    """Detect sequences of consecutive urgent mistakes.

    Delegates to the real implementation in summary_logic.py.
    Kept as a stable import point for callers in summary_formatter.py.
    """
    from katrain.core.reports.summary_logic import detect_urgent_miss_sequences

    return detect_urgent_miss_sequences(moves, threshold_loss, min_consecutive)


def build_summary_report(
    game_data_list: list[GameSummaryData], focus_player: str | None = None
) -> str:
    """
    複数局から統計まとめを生成（JSON形式）

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


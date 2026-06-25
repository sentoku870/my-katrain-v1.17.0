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

    Stub implementation: returns the input unchanged. Kept as a stable
    import point for legacy callers in summary_formatter.py.
    """
    return coord


def _detect_urgent_miss_sequences(
    moves: list[Any],
    threshold_loss: float,
    min_consecutive: int,
) -> tuple[list[dict[str, Any]], list[Any]]:
    """Detect sequences of consecutive urgent mistakes.

    Stub implementation: returns no sequences and the input moves
    unchanged. Kept as a stable import point for legacy callers in
    summary_formatter.py.
    """
    return [], list(moves)


def build_summary_report(
    game_data_list: list["GameSummaryData"], focus_player: str | None = None
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

    from katrain.core.reports.summary_json_export import build_summary_json
    import json

    json_data = build_summary_json(game_data_list, focus_player)
    return json.dumps(json_data, indent=2, ensure_ascii=False)


"""Important moves report generation.

PR #120: Phase B2 - important_moves_report.py抽出

game.pyから抽出された重要手レポート生成機能。
- build_important_moves_report: 重要局面をテキストレポートとして生成

このモジュールはkatrain.guiをインポートしない（core層のみ）。
"""

from typing import Any

from katrain.core import eval_metrics
from katrain.core.analysis.models import (
    MistakeCategory,
    MoveEval,
)


def build_important_moves_report(
    important_moves: list["MoveEval"],
    *,
    level: str = eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL,
    max_lines: int | None = None,
) -> str:
    """
    重要局面をテキストレポートとして返す。

    - 手数 / 手番 / 着手 / 損失(目) / ミス分類 / 難易度 / 形勢差Δ / 勝率Δ
    - eval_metrics.pick_important_moves の結果に基づく

    Args:
        important_moves: get_important_move_evals() の結果
        level:
            重要局面検出のレベル。
            - "easy"   : ゆるめに拾う
            - "normal" : 標準
            - "strict" : より厳しめに大きな局面だけ
        max_lines:
            レポートの最大行数（None の場合は全件）

    Returns:
        重要局面のテキストレポート
    """
    if not important_moves:
        settings = eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
            level,
            eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL[eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL],
        )
        return (
            f"重要局面候補 (level={level}, "
            f"threshold={settings.importance_threshold}, "
            f"max_moves={settings.max_moves}) は見つかりませんでした。"
        )

    # 必要に応じて行数を制限
    if max_lines is not None and max_lines > 0:
        important_moves = important_moves[:max_lines]

    def fmt_score(v: float | None) -> str:
        if v is None:
            return "-"
        return f"{v:+.1f}"

    def fmt_winrate(v: float | None) -> str:
        if v is None:
            return "-"
        return f"{v:+.1f}%"

    def fmt_mistake(mc: MistakeCategory | None) -> str:
        if mc is None:
            return "-"
        mapping = {
            MistakeCategory.GOOD: "良",
            MistakeCategory.INACCURACY: "軽",
            MistakeCategory.MISTAKE: "悪",
            MistakeCategory.BLUNDER: "大悪",
        }
        return mapping.get(mc, "-")

    def fmt_difficulty(difficulty: Any) -> str:
        """
        PositionDifficulty を短い日本語ラベルに変換する。

        EASY      -> "易"
        NORMAL    -> "普"
        HARD      -> "難"
        ONLY_MOVE -> "一手"
        UNKNOWN   -> "-"
        """
        if difficulty is None:
            return "-"
        # Enum を想定し、.value から判定する
        value = getattr(difficulty, "value", None)
        mapping = {
            "easy": "易",
            "normal": "普",
            "hard": "難",
            "only": "一手",
            "unknown": "-",
        }
        if value is None:
            return "-"
        return mapping.get(value, "-")

    # 見出し行
    settings = eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
        level,
        eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL[eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL],
    )
    lines: list[str] = []
    lines.append(
        f"重要局面候補 (level={level}, threshold={settings.importance_threshold}, max_moves={settings.max_moves})"
    )
    lines.append("")  # 空行

    # ヘッダ
    # 手数 / 手番 / 着手 / 損失(目) / ミス分類 / 難易度 / 形勢差Δ / 勝率Δ
    lines.append("手数  手番  着手   損失(目)  ミス   難度   形勢差Δ  勝率Δ")
    lines.append("-" * 52)

    # 各手を 1 行に整形
    for m in important_moves:
        if not isinstance(m, MoveEval):
            continue

        move_no = m.move_number
        player = m.player or "-"
        gtp = m.gtp or "-"

        pl = fmt_score(m.points_lost)
        ds = fmt_score(m.delta_score)
        dw = fmt_winrate(m.delta_winrate)
        mc = fmt_mistake(m.mistake_category)
        df = fmt_difficulty(getattr(m, "position_difficulty", None))

        lines.append(f"{move_no:>3}   {player:>1}   {gtp:>4}   {pl:>7}  {mc:>4}  {df:>4}  {ds:>7}  {dw:>7}")

    return "\n".join(lines)

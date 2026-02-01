from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import eval_metrics

if TYPE_CHECKING:
    # 型チェック専用。実行時には import しないので循環参照を避けられる。
    from .game import Game


# ---------------------------------------------------------------------------
# データ構造
# ---------------------------------------------------------------------------


@dataclass
class YoseImportantMovesReport:
    """重要局面候補だけをまとめたシンプルなレポート。

    Phase2 では「重要局面リスト」を Yose 側から再利用するための受け皿。
    将来、ここにヨセ専用のラベルやコメントを足していく想定。
    """

    level: str
    settings: eval_metrics.ImportantMoveSettings
    moves: list[eval_metrics.MoveEval] = field(default_factory=list)


# ---------------------------------------------------------------------------
# YoseAnalyzer 本体（最小バージョン）
# ---------------------------------------------------------------------------


class YoseAnalyzer:
    """EvalSnapshot を入力にして、Yose 向けの情報を取り出すヘルパー。

    - 現時点では「重要局面リスト＋設定」を返すだけ。
    - KataGo への追加解析（ローカル目数や先手／後手判定）は、
      Phase3 以降でメソッドを拡張していく。
    """

    def __init__(self, snapshot: eval_metrics.EvalSnapshot):
        self.snapshot = snapshot

    # Game オブジェクトから直接作りたい場合用の入口
    @classmethod
    def from_game(cls, game: "Game") -> "YoseAnalyzer":
        snapshot = eval_metrics.snapshot_from_game(game)
        return cls(snapshot)

    # 重要局面 MoveEval のリストを取得
    def important_moves(
        self,
        *,
        level: str = eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL,
        recompute: bool = True,
    ) -> list[eval_metrics.MoveEval]:
        return eval_metrics.pick_important_moves(
            self.snapshot,
            level=level,
            recompute=recompute,
        )

    # 上記をそのままレポート形式にまとめる
    def build_important_moves_report(
        self,
        *,
        level: str = eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL,
        max_moves: int | None = None,
        recompute: bool = True,
    ) -> YoseImportantMovesReport:
        moves = self.important_moves(level=level, recompute=recompute)

        settings = eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
            level,
            eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL[eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL],
        )

        if max_moves is not None:
            moves = moves[:max_moves]

        return YoseImportantMovesReport(level=level, settings=settings, moves=moves)

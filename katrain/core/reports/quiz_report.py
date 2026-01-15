"""Quiz report generation.

PR #117: Phase B2 - quiz_report.py抽出

game.pyから抽出されたクイズ関連機能。
- get_quiz_items: 対局からクイズ用の大きなミス一覧を取得
- build_quiz_questions: ミス一覧からクイズ問題を生成

このモジュールはkatrain.guiをインポートしない（core層のみ）。
"""

from typing import Callable, List, Optional

from katrain.core.analysis.models import (
    DEFAULT_QUIZ_ITEM_LIMIT,
    DEFAULT_QUIZ_LOSS_THRESHOLD,
    EvalSnapshot,
    QuizChoice,
    QuizItem,
    QuizQuestion,
)
from katrain.core.eval_metrics import (
    quiz_items_from_snapshot,
    quiz_points_lost_from_candidate,
)
from katrain.core.game_node import GameNode


def get_quiz_items(
    snapshot: EvalSnapshot,
    *,
    loss_threshold: float = DEFAULT_QUIZ_LOSS_THRESHOLD,
    limit: int = DEFAULT_QUIZ_ITEM_LIMIT,
) -> List[QuizItem]:
    """
    EvalSnapshotからクイズ用の大きなミス一覧を返す。

    Args:
        snapshot: 対局の評価スナップショット
        loss_threshold: ミスと見なす損失の閾値（目）
        limit: 返すクイズ項目の最大数

    Returns:
        クイズ項目のリスト（損失の大きい順）

    Note:
        解析済みの情報だけを使用し、新たな分析は開始しない。
    """
    if not snapshot.moves:
        return []

    return quiz_items_from_snapshot(
        snapshot, loss_threshold=loss_threshold, limit=limit
    )


def build_quiz_questions(
    quiz_items: List[QuizItem],
    get_node_before_move: Callable[[int], Optional[GameNode]],
    *,
    max_choices: int = 3,
) -> List[QuizQuestion]:
    """
    クイズ項目からクイズ問題を生成する。

    Args:
        quiz_items: クイズ項目のリスト
        get_node_before_move: 手数を受け取りその直前局面のノードを返すコールバック
        max_choices: 選択肢の最大数

    Returns:
        クイズ問題のリスト

    Note:
        各局面の候補手情報（candidate_moves）を使用し、
        新たなエンジン解析は開始しない。
    """
    questions: List[QuizQuestion] = []
    for item in quiz_items:
        node_before = get_node_before_move(item.move_number)
        choices: List[QuizChoice] = []
        best_move: Optional[str] = None

        if node_before is not None and getattr(node_before, "analysis_exists", False):
            candidate_moves = node_before.candidate_moves
            if candidate_moves:
                best_move = candidate_moves[0].get("move")
                analysis = getattr(node_before, "analysis", None) or {}
                root_score = None
                if isinstance(analysis, dict):
                    root_score = (analysis.get("root") or {}).get("scoreLead")
                for mv in candidate_moves[:max_choices]:
                    move_id = mv.get("move", "") or ""
                    loss_val = quiz_points_lost_from_candidate(
                        mv,
                        root_score=root_score,
                        next_player=getattr(node_before, "next_player", None),
                    )
                    choices.append(
                        QuizChoice(move=move_id, points_lost=loss_val)
                    )

        questions.append(
            QuizQuestion(
                item=item,
                choices=choices,
                best_move=best_move,
                node_before_move=node_before,
            )
        )
    return questions

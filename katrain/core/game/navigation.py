"""GameNavigator クラス (Phase 141 分割)

重要局面の計算と、メイン分岐上の前後ナビを担当する。
``Game`` インスタンスへの参照を保持し、メイン分岐ノード列挙と重要度計算を行う。

Phase 70 で最適化された単一パス ``_compute_important_moves`` を維持する。
"""

from __future__ import annotations

import heapq
from collections.abc import Iterator
from typing import TYPE_CHECKING

from katrain.core.game_node import GameNode

if TYPE_CHECKING:
    from katrain.core.game.base import BaseGame


class GameNavigator:
    """重要局面ナビゲーション

    責務:
    - メイン分岐ノードの列挙 (``_iter_main_branch_nodes``)
    - 重要局面の重要度スコア計算 (``_compute_important_moves``)
    - 重要局面リストと現在のカーソルに基づく前後ナビ

    Args:
        game: 操作対象の ``BaseGame`` インスタンス。
              ``current_node`` / ``root`` / ``set_current_node`` を利用する。
    """

    def __init__(self, game: "BaseGame") -> None:
        self._game = game

    # ------------------------------------------------------------------
    # 内部実装 (元 ``Game`` クラスの同名メソッド)
    # ------------------------------------------------------------------

    def _iter_main_branch_nodes(self) -> "Iterator[GameNode]":
        """ルートからメイン分岐（ordered_children[0] を辿った一本の線）
        上のノードだけを順に返す。
        """
        game = self._game
        node: GameNode = game.root
        while node.children:
            child = node.ordered_children[0]
            assert isinstance(child, GameNode)
            node = child
            yield node

    def _compute_important_moves(self, max_moves: int = 20) -> list[tuple[int, float, GameNode]]:
        """メイン分岐上のノードから「重要そうな手」を抽出して返す。

        戻り値: [(手数, 重要度スコア, GameNode), ...]  を
                手数昇順に並べたリスト。

        Phase 70: 単一パスアルゴリズムに最適化。
        重複ループを解消し、heapq.nlargest で上位 max_moves 件を効率的に抽出。
        """
        IMPORTANCE_THRESHOLD = 0.5  # 小さい変化をノイズとして除外

        # 単一パスで全ノードを収集
        all_nodes: list[tuple[int, float, GameNode]] = []
        prev_score: float | None = None

        for node in self._iter_main_branch_nodes():
            # 解析が終わっていない手はスキップ
            if not node.analysis_complete or node.score is None:
                continue

            move_no = len(node.nodes_from_root) - 1
            points_lost = node.points_lost or 0.0
            delta_score = 0.0 if prev_score is None else abs(node.score - prev_score)

            # 「ミス or 大きな形勢変化」を重要度とする
            importance = max(points_lost, delta_score)

            all_nodes.append((move_no, importance, node))
            prev_score = node.score

        # 閾値を超える候補を抽出、なければ全ノードをフォールバック
        candidates = [(m, i, n) for m, i, n in all_nodes if i > IMPORTANCE_THRESHOLD]
        if not candidates:
            candidates = all_nodes

        # 重要度の大きい順に上位 max_moves 件を抽出
        top = heapq.nlargest(max_moves, candidates, key=lambda t: t[1])

        # ナビゲーションで扱いやすいように、手数順に並べ直して返す
        top.sort(key=lambda t: t[0])
        return top

    # ------------------------------------------------------------------
    # 公開 API (元 ``Game`` クラスの同名メソッド)
    # ------------------------------------------------------------------

    def get_main_branch_node_before_move(self, move_number: int) -> GameNode | None:
        """メイン分岐上で指定手数の直前局面を返す（なければ None）。
        move_number が 1 以下なら root を返す。
        """
        game = self._game
        if move_number <= 1:
            return game.root

        target = move_number - 1
        for node in self._iter_main_branch_nodes():
            current_move_no = len(node.nodes_from_root) - 1
            if current_move_no == target:
                return node
            if current_move_no > target:
                break
        return None

    def get_important_move_numbers(self, max_moves: int = 20) -> list[int]:
        """「重要局面」と判定された手数のリストだけを返す。
        ScoreGraph などから呼ぶことを想定。
        """
        important = self._compute_important_moves(max_moves=max_moves)
        return [move_no for move_no, _importance, _node in important]

    def get_next_important_node(self, max_moves: int = 20) -> GameNode | None:
        """現在の手より「後ろにある」重要局面ノードを返す。
        なければ None。
        """
        game = self._game
        important = self._compute_important_moves(max_moves=max_moves)
        if not important:
            return None

        current_move_no = len(game.current_node.nodes_from_root) - 1

        for move_no, _importance, node in important:
            if move_no > current_move_no:
                return node

        # すべて現在手より前なら、今回はジャンプしない仕様にしておく
        return None

    def get_prev_important_node(self, max_moves: int = 20) -> GameNode | None:
        """現在の手より「前にある」重要局面ノードを返す。
        なければ None。
        """
        game = self._game
        important = self._compute_important_moves(max_moves=max_moves)
        if not important:
            return None

        current_move_no = len(game.current_node.nodes_from_root) - 1

        prev_node: GameNode | None = None
        for move_no, _importance, node in important:
            if move_no >= current_move_no:
                break
            prev_node = node

        return prev_node

    def jump_to_next_important_move(self, max_moves: int = 20) -> GameNode | None:
        """次の重要局面にジャンプする。
        実際に current_node を変更したノードを返す。なければ None。
        """
        game = self._game
        node = self.get_next_important_node(max_moves=max_moves)
        if node is not None:
            game.set_current_node(node)
        return node

    def jump_to_prev_important_move(self, max_moves: int = 20) -> GameNode | None:
        """前の重要局面にジャンプする。
        実際に current_node を変更したノードを返す。なければ None。
        """
        game = self._game
        node = self.get_prev_important_node(max_moves=max_moves)
        if node is not None:
            game.set_current_node(node)
        return node

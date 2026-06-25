"""InsertModeController クラス (Phase 141 分割)

``Game`` インスタンスの挿入モード管理を集約する。
``set_insert_mode`` / ``set_current_node`` / ``undo`` / ``redo`` の上書き挙動を担当する。

責務:
- 挿入モードの開始・終了 (``set_insert_mode``)
- 挿入モード中の ``set_current_node`` 拒否
- 挿入モード中の ``undo`` (= 削除) 特殊処理
- 挿入モード中の ``redo`` 拒否
- 挿入モード終了時のコピー処理

ロック (``_lock``) は ``Game`` インスタンス側に保持されているため、
排他制御は呼び出し側 (``Game.undo``) で行う。
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from katrain.core.constants import STATUS_ERROR, STATUS_INFO
from katrain.core.game.base import IllegalMoveException
from katrain.core.game_node import GameNode
from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.core.game.facade import Game


class InsertModeController:
    """挿入モード管理

    ``Game`` インスタンスへの参照を保持し、挿入モードのライフサイクルを管理する。
    状態 (``insert_mode`` / ``insert_after``) は ``Game`` 側に保持される。

    Args:
        game: 操作対象の ``Game`` インスタンス。
    """

    def __init__(self, game: "Game") -> None:
        self._game = game

    # ------------------------------------------------------------------
    # 上書きハンドラ (Game の set_current_node/undo/redo から呼ばれる)
    # ------------------------------------------------------------------

    def handle_set_current_node(self, node: GameNode) -> bool:
        """``Game.set_current_node`` 上書き用ヘルパ。

        挿入モード中ならエラーステータスを表示し、 ``True`` を返す
        (呼び出し側は super().set_current_node() をスキップする)。

        Returns:
            True: ナビゲーションを拒否 (super を呼ぶ必要なし)
            False: 通常のナビゲーションを許可
        """
        game = self._game
        if not game.insert_mode:
            return False
        game.katrain.controls.set_status(i18n._("finish inserting before navigating"), STATUS_ERROR)
        return True

    def handle_undo(self, n_times: int | str) -> bool:
        """``Game.undo`` 上書き用ヘルパ (挿入モード中は独自処理)。

        挿入モード中で ``n_times==1`` かつ現在のノードが挿入ルートにない場合、
        現在のノードを親から削除する。

        Returns:
            True: 挿入モード中の特殊処理を実行 (super を呼ぶ必要なし)
            False: 通常の undo を super に任せる
        """
        game = self._game
        if not game.insert_mode:
            return False
        # in insert mode, undo = delete
        cn = game.current_node
        if (
            game.insert_after is not None
            and n_times == 1
            and cn not in game.insert_after.nodes_from_root
        ):
            parent = cn.parent
            if parent is not None:
                parent.children = [c for c in parent.children if c != cn]
                if isinstance(parent, GameNode):
                    game.current_node = parent
                game._calculate_groups()
        return True

    def handle_redo(self) -> bool:
        """``Game.redo`` 上書き用ヘルパ (挿入モード中は no-op)。

        Returns:
            True: 挿入モード中のため何もしない (super を呼ぶ必要なし)
            False: 通常の redo を super に任せる
        """
        return self._game.insert_mode

    # ------------------------------------------------------------------
    # メインエントリ
    # ------------------------------------------------------------------

    def set_insert_mode(self, mode: bool | str) -> None:
        """挿入モードの開始・終了を制御する。

        Args:
            mode: True (開始), False (終了), "toggle" (反転)
        """
        game = self._game
        effective_mode: bool
        if mode == "toggle":
            effective_mode = not game.insert_mode
        else:
            assert isinstance(mode, bool)
            effective_mode = mode
        if effective_mode == game.insert_mode:
            return
        game.insert_mode = effective_mode
        if effective_mode:
            self._start_insert_mode()
        else:
            self._end_insert_mode()
        # UI 更新
        game.katrain.controls.move_tree.insert_node = game.insert_after if game.insert_mode else None
        game.katrain.controls.move_tree.redraw()
        game.katrain.update_state(redraw_board=True)

    # ------------------------------------------------------------------
    # 内部実装
    # ------------------------------------------------------------------

    def _start_insert_mode(self) -> None:
        game = self._game
        children = game.current_node.ordered_children
        if not children:
            game.insert_mode = False
            return
        child = game.current_node.ordered_children[0]
        assert isinstance(child, GameNode)
        game.insert_after = child
        game.katrain.controls.set_status(i18n._("starting insert mode"), STATUS_INFO)

    def _end_insert_mode(self) -> None:
        game = self._game
        if game.insert_after is None:
            return
        copy_from_node: GameNode = game.insert_after
        copy_to_node: GameNode = game.current_node
        num_copied = 0
        insert_parent = game.insert_after.parent
        if copy_to_node != insert_parent:
            assert insert_parent is not None
            above_insertion_root = insert_parent.nodes_from_root
            already_inserted_moves = [
                n.move for n in copy_to_node.nodes_from_root if n not in above_insertion_root and n.move
            ]
            try:
                while True:
                    for m in copy_from_node.move_with_placements:
                        if m not in already_inserted_moves:
                            game._validate_move_and_update_chains(m, True)
                            # this inserts
                            copy_to_node = GameNode(
                                parent=copy_to_node, properties=copy.deepcopy(copy_from_node.properties)
                            )
                            num_copied += 1
                    if not copy_from_node.children:
                        break
                    next_child = copy_from_node.ordered_children[0]
                    assert isinstance(next_child, GameNode)
                    copy_from_node = next_child
            except IllegalMoveException:
                pass  # illegal move = stop
            game._calculate_groups()  # recalculate groups
            game.katrain.controls.set_status(
                i18n._("ending insert mode").format(num_copied=num_copied), STATUS_INFO
            )
            game.analyze_all_nodes(analyze_fast=True, even_if_present=False)
        else:
            game.katrain.controls.set_status("", STATUS_INFO)

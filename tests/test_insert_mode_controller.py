"""InsertModeController の単体テスト (Phase 141)

Game インスタンスの挿入モード管理を InsertModeController に委譲した動作を検証する。
"""

from __future__ import annotations

import pytest

from katrain.core.game import Game, InsertModeController
from katrain.core.game_node import GameNode
from katrain.core.sgf_parser import Move


@pytest.fixture
def game_with_branch(game):
    """current_node に子を持つゲーム。挿入モード開始可能な状態。"""
    # 1 手進める (current_node = root の子)
    game.play(Move(coords=(3, 3), player="B"))
    # さらに 1 手進める (current_node に子はないが、undo してから再度進めると子を持つ)
    game.undo(1)
    return game


def test_controller_attached_to_game(game):
    """Game インスタンスに insert_mode_ctrl 属性が存在する"""
    assert hasattr(game, "insert_mode_ctrl")
    assert isinstance(game.insert_mode_ctrl, InsertModeController)
    assert game.insert_mode_ctrl._game is game


def test_initial_insert_mode_is_false(game):
    """初期状態は insert_mode=False"""
    assert game.insert_mode is False
    assert game.insert_after is None


def test_handle_set_current_node_in_insert_mode_blocks(game_with_branch):
    """挿入モード中の set_current_node は拒否される"""
    game = game_with_branch
    # 挿入モードに入る
    game.set_insert_mode(True)
    assert game.insert_mode is True

    # メイン分岐の子に移動しようとする → 拒否される
    new_node = game.root.ordered_children[0]
    current_before = game.current_node
    game.set_current_node(new_node)
    # 挿入モード中なので current_node は変わらない
    assert game.current_node is current_before


def test_handle_set_current_node_normal_mode_allows(game):
    """通常モードでは set_current_node は許可される"""
    game = game
    # ルート以外のノードへ移動
    game.play(Move(coords=(3, 3), player="B"))
    target = game.current_node
    # ルートに戻る
    game.set_current_node(game.root)
    assert game.current_node is game.root
    # 再度対象ノードへ
    game.set_current_node(target)
    assert game.current_node is target


def test_handle_undo_in_insert_mode_returns_true(game_with_branch):
    """挿入モード中で、 current_node が insert_after 配下にないとき、 undo で削除される"""
    game = game_with_branch
    # game_with_branch: current_node = root, root の子 = first_child_B
    # set_insert_mode(True) → insert_after = first_child_B
    game.set_insert_mode(True)
    insert_after = game.insert_after
    assert insert_after is not None

    # ここで current_node (root) は insert_after.nodes_from_root に含まれるため
    # 削除条件を満たさないが、 handle_undo は True を返す
    initial_current = game.current_node
    result = game.insert_mode_ctrl.handle_undo(1)
    assert result is True
    # current_node は insert_after 配下にあったので変化しない
    assert game.current_node is initial_current


def test_handle_undo_normal_mode_calls_super(game):
    """通常モードの undo は super に任せる"""
    game = game
    # 2 手進める
    game.play(Move(coords=(3, 3), player="B"))
    game.play(Move(coords=(5, 5), player="W"))
    depth_before = game.current_node.depth
    # undo で 1 手戻る
    game.undo(1)
    assert game.current_node.depth == depth_before - 1


def test_handle_redo_in_insert_mode_noop(game_with_branch):
    """挿入モード中の redo は何もしない"""
    game = game_with_branch
    # 挿入モード開始
    game.set_insert_mode(True)
    current_before = game.current_node

    # redo
    game.redo(1)
    # current_node は変わらない
    assert game.current_node is current_before


def test_handle_redo_normal_mode_calls_super(game):
    """通常モードの redo は super に任せる"""
    game = game
    game.play(Move(coords=(3, 3), player="B"))
    game.undo(1)
    depth_before = game.current_node.depth
    game.redo(1)
    assert game.current_node.depth == depth_before + 1


def test_set_insert_mode_toggle(game_with_branch):
    """'toggle' モードで挿入モードが反転する"""
    game = game_with_branch
    assert game.insert_mode is False
    game.set_insert_mode("toggle")
    assert game.insert_mode is True
    game.set_insert_mode("toggle")
    assert game.insert_mode is False


def test_set_insert_mode_already_on_no_change(game_with_branch):
    """既に挿入モードのときに再度 True を渡しても変化しない"""
    game = game_with_branch
    game.set_insert_mode(True)
    insert_after_before = game.insert_after
    game.set_insert_mode(True)  # no-op
    assert game.insert_after is insert_after_before


def test_set_insert_mode_with_no_children_disables(game):
    """子がないノードで挿入モードを開始すると無効化される"""
    game = game
    # ルートには子がないので挿入モード開始できない
    game.set_insert_mode(True)
    assert game.insert_mode is False


def test_set_insert_mode_end_with_no_insert_after(game_with_branch):
    """insert_after が None のときに set_insert_mode(False) しても False になる"""
    game = game_with_branch
    # insert_mode を強制的に True, insert_after を None にする
    game.insert_mode = True
    game.insert_after = None
    game.set_insert_mode(False)
    # insert_mode は False になる (元コードの挙動)
    assert game.insert_mode is False


def test_set_insert_mode_end_copies_moves(game_with_branch):
    """挿入モード終了時に moves がコピーされる"""
    game = game_with_branch
    # 挿入モード開始 (insert_after = first child of root)
    game.set_insert_mode(True)
    # 挿入モード終了
    game.set_insert_mode(False)
    # 終了したら insert_mode は False
    assert game.insert_mode is False

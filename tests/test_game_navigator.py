"""GameNavigator の単体テスト (Phase 141)

Game インスタンスの重要局面ナビ機能を GameNavigator に委譲した動作を検証する。
既存テストを無修正で動作させるため、後方互換性も合わせて確認する。
"""

from __future__ import annotations

import pytest

from katrain.core.game import Game, GameNavigator
from katrain.core.game_node import GameNode
from katrain.core.sgf_parser import Move


@pytest.fixture
def mock_katrain_and_engine(mock_katrain, mock_engine):
    return mock_katrain, mock_engine


def _build_mainline_game(katrain, engine, n_moves: int) -> Game:
    """Build a game with a mainline of n_moves black plays."""
    root = GameNode(properties={"SZ": ["19"], "KM": ["6.5"], "RU": ["Japanese"]})
    node = root
    for i in range(n_moves):
        mv = Move(coords=(3 + i, 3), player="B" if i % 2 == 0 else "W")
        new_node = GameNode(parent=node, move=mv, properties={"B" if i % 2 == 0 else "W": [mv.gtp()]})
        node = new_node
    return Game(katrain, engine, move_tree=root)


def test_navigator_is_attached_to_game(mock_katrain_and_engine):
    """Game インスタンスに navigator 属性が存在する"""
    katrain, engine = mock_katrain_and_engine
    game = _build_mainline_game(katrain, engine, 3)
    assert hasattr(game, "navigator")
    assert isinstance(game.navigator, GameNavigator)
    # Same game reference
    assert game.navigator._game is game


def test_navigator_main_branch_node_before_move(mock_katrain_and_engine):
    """get_main_branch_node_before_move は手数-1 のノードを返す"""
    katrain, engine = mock_katrain_and_engine
    game = _build_mainline_game(katrain, engine, 5)
    nav = game.navigator

    # move_number <= 1 → root
    assert nav.get_main_branch_node_before_move(1) is game.root
    assert nav.get_main_branch_node_before_move(0) is game.root

    # move_number=3 → depth=2 のノード
    node = nav.get_main_branch_node_before_move(3)
    assert node is not None
    assert len(node.nodes_from_root) == 3


def test_iter_main_branch_nodes(mock_katrain_and_engine):
    """_iter_main_branch_nodes はメイン分岐のノードを順に返す"""
    katrain, engine = mock_katrain_and_engine
    game = _build_mainline_game(katrain, engine, 4)
    nodes = list(game.navigator._iter_main_branch_nodes())
    assert len(nodes) == 4
    # メイン分岐上の最初の子から始まる
    assert nodes[0] is game.root.ordered_children[0]


def test_backward_compat_delegation_methods(mock_katrain_and_engine):
    """後方互換性: Game クラスの同名メソッドが navigator へ委譲される"""
    katrain, engine = mock_katrain_and_engine
    game = _build_mainline_game(katrain, engine, 3)
    nav = game.navigator

    # Game クラスにメソッドが存在し、navigator の結果と一致する
    assert game.get_main_branch_node_before_move(2) is nav.get_main_branch_node_before_move(2)
    assert game._iter_main_branch_nodes is not None
    assert game._compute_important_moves is not None
    assert game.get_important_move_numbers is not None
    assert game.get_next_important_node is not None
    assert game.get_prev_important_node is not None
    assert game.jump_to_next_important_move is not None
    assert game.jump_to_prev_important_move is not None


def test_compute_important_moves_empty_when_no_analysis(mock_katrain_and_engine):
    """解析データなしの場合、重要局面は空リスト"""
    katrain, engine = mock_katrain_and_engine
    game = _build_mainline_game(katrain, engine, 10)
    # 解析データなし → 候補なし → 空リスト
    important = game.navigator._compute_important_moves(max_moves=20)
    assert important == []


def test_jump_to_important_returns_none_when_empty(mock_katrain_and_engine):
    """重要局面なしのとき、next/prev ともに None"""
    katrain, engine = mock_katrain_and_engine
    game = _build_mainline_game(katrain, engine, 3)
    assert game.navigator.get_next_important_node() is None
    assert game.navigator.get_prev_important_node() is None
    assert game.navigator.jump_to_next_important_move() is None
    assert game.navigator.jump_to_prev_important_move() is None


def test_important_move_numbers_empty_when_no_analysis(mock_katrain_and_engine):
    """解析データなしのとき、重要手数リストは空"""
    katrain, engine = mock_katrain_and_engine
    game = _build_mainline_game(katrain, engine, 5)
    assert game.navigator.get_important_move_numbers(max_moves=10) == []
    # Game クラス経由でも同じ結果
    assert game.get_important_move_numbers(max_moves=10) == []


def test_compute_important_moves_with_synthetic_analysis(mock_katrain_and_engine):
    """合成した score で重要局面を抽出できる"""
    katrain, engine = mock_katrain_and_engine
    game = _build_mainline_game(katrain, engine, 6)
    nav = game.navigator

    # ノードに合成の analysis を設定
    # node.score は analysis["root"]["scoreLead"] から計算される
    # node.points_lost は parent.score - self.score から計算される (player_sign 考慮)
    # → parent_score を 5.0, self_score を 0.0 にすると points_lost = 5.0 になる
    nodes = list(nav._iter_main_branch_nodes())
    for i, node in enumerate(nodes):
        node.analysis = {
            "completed": True,
            "root": {"scoreLead": 0.0, "visits": 100},
            "moves": {},
        }

    # 親ノードには score=0.0, 1 つの child だけ score=+5.0 (B 視点の大幅リード) →
    # W player の nodes[1] は points_lost=5.0 になる
    parent_for_important = nodes[0]
    parent_for_important.analysis = {
        "completed": True,
        "root": {"scoreLead": 0.0, "visits": 100},
        "moves": {},
    }
    # nodes[1] (W player) は score=+5.0 (B 視点の大幅リード = W 視点の大幅ビハインド)
    nodes[1].analysis = {
        "completed": True,
        "root": {"scoreLead": 5.0, "visits": 100},
        "moves": {},
    }

    # debug
    assert nodes[0].score == 0.0
    assert nodes[1].score == 5.0
    # W player の points_lost = -1 * (0 - 5) = -1 * -5 = 5
    assert nodes[1].points_lost == 5.0

    important = nav._compute_important_moves(max_moves=20)
    assert len(important) >= 1
    # 重要局面の 1 つは move_no=2 (nodes[1])、 importance=5.0
    move_numbers_importances = [(m, i) for m, i, n in important]
    assert (2, 5.0) in move_numbers_importances


def test_mainline_iteration_skips_branches(mock_katrain_and_engine):
    """メイン分岐は分岐を辿らず一本の線を返す"""
    katrain, engine = mock_katrain_and_engine
    root = GameNode(properties={"SZ": ["19"], "KM": ["6.5"], "RU": ["Japanese"]})
    # メイン分岐 3 手
    main_nodes = [root]
    for i in range(3):
        mv = Move(coords=(3, 3 + i), player="B" if i % 2 == 0 else "W")
        new_node = GameNode(parent=main_nodes[-1], move=mv, properties={"B" if i % 2 == 0 else "W": [mv.gtp()]})
        main_nodes.append(new_node)

    # 分岐を追加 (1 手目から別の手)
    mv_branch = Move(coords=(10, 10), player="B")
    GameNode(parent=main_nodes[1], move=mv_branch, properties={"B": [mv_branch.gtp()]})

    game = Game(katrain, engine, move_tree=root)
    nodes = list(game.navigator._iter_main_branch_nodes())
    # メイン分岐は 3 手だけ
    assert len(nodes) == 3
    # 全てメイン分岐上
    for node in nodes:
        assert node in main_nodes

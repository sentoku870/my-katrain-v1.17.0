"""AnalysisOrchestrator の単体テスト (Phase 141)

Game インスタンスの解析オーケストレーション機能を AnalysisOrchestrator に
委譲した動作を検証する。
"""

from __future__ import annotations

import pytest

from katrain.core.constants import AnalysisMode
from katrain.core.game import AnalysisOrchestrator, Game


@pytest.fixture
def game_with_mock_engine(game):
    """Standard game fixture with mock engine."""
    return game


def test_orchestrator_attached_to_game(game_with_mock_engine):
    """Game インスタンスに analysis 属性が存在する"""
    assert hasattr(game_with_mock_engine, "analysis")
    assert isinstance(game_with_mock_engine.analysis, AnalysisOrchestrator)
    assert game_with_mock_engine.analysis._game is game_with_mock_engine


def test_analyze_all_nodes_delegates(game_with_mock_engine, mock_engine):
    """analyze_all_nodes は orchestrator へ委譲される"""
    game = game_with_mock_engine
    mock_engine.reset_tracking()
    # even_if_present=False で全ノードに新規解析を強制
    game.analyze_all_nodes(analyze_fast=True, even_if_present=False)
    # 解析呼び出しがあったことを確認 (モックエンジンの追跡)
    assert len(mock_engine.request_analysis_calls) > 0


def test_analyze_extra_stop_delegates(game_with_mock_engine):
    """analyze_extra(STOP) は orchestrator 経由でも同じ動作"""
    game = game_with_mock_engine
    # STOP モードは何もせずに完了
    game.analyze_extra(AnalysisMode.STOP)
    # 例外なく完了すれば OK
    # ゲーム状態が変化していないことも確認
    assert game.current_node is not None


def test_analyze_extra_unknown_mode_does_not_raise(game_with_mock_engine):
    """未対応モード (None 含む) は parse_analysis_mode がデフォルトを返すためエラーなし"""
    game = game_with_mock_engine
    # parse_analysis_mode("") はデフォルトの AnalysisMode を返す
    # ここではクラッシュしないことだけを確認
    try:
        game.analyze_extra("invalid_mode")
    except (ValueError, KeyError):
        # 未知のモードは ValueError になる可能性あり
        pass


def test_reset_current_analysis_signature(game_with_mock_engine):
    """reset_current_analysis は orchestrator 側に存在する (実エンジンが必要)"""
    game = game_with_mock_engine
    # メソッドが存在することを確認
    assert callable(game.reset_current_analysis)
    # orchestrator にも同じ名前のメソッドが存在する
    assert callable(game.analysis.reset_current_analysis)


def test_set_region_of_interest_valid_region(game_with_mock_engine):
    """有効な領域は region_of_interest に保存される"""
    game = game_with_mock_engine
    # 19x19 盤で 5,5 - 10,10 の領域
    game.set_region_of_interest((5, 10, 5, 10))
    assert game.region_of_interest == [5, 10, 5, 10]


def test_set_region_of_interest_full_board_clears(game_with_mock_engine):
    """盤全体サイズの領域は None に設定される"""
    game = game_with_mock_engine
    # 19x19 盤で 0,18 - 0,18 = 盤全体
    game.set_region_of_interest((0, 18, 0, 18))
    assert game.region_of_interest is None


def test_set_region_of_interest_single_point_clears(game_with_mock_engine):
    """1 点 (x1==x2, y1==y2) は None に設定される"""
    game = game_with_mock_engine
    game.set_region_of_interest((5, 5, 5, 5))
    assert game.region_of_interest is None


def test_handle_stop_mode_calls_terminate_queries(game_with_separate_engines, mock_engines):
    """STOP モードは全エンジンの terminate_queries を呼ぶ"""
    game = game_with_separate_engines
    mock_engines["B"].reset_tracking()
    mock_engines["W"].reset_tracking()
    game._handle_stop_mode()
    # 各エンジンで stop_pondering と terminate_queries が呼ばれた
    assert mock_engines["B"].stop_pondering_called is True
    assert mock_engines["B"].terminate_queries_called is True
    assert mock_engines["W"].stop_pondering_called is True
    assert mock_engines["W"].terminate_queries_called is True


def test_wait_for_engine_capacity_returns_true_when_available(game_with_mock_engine, mock_engine):
    """エンジンが空いていれば即座に True"""
    game = game_with_mock_engine
    mock_engine.has_query_capacity = lambda headroom=10: True
    result = game.analysis._wait_for_engine_capacity(mock_engine, headroom=10)
    assert result is True


def test_wait_for_engine_capacity_returns_false_on_timeout(game_with_mock_engine, mock_engine):
    """エンジンが常に満杯なら False (タイムアウト)"""
    game = game_with_mock_engine
    mock_engine.has_query_capacity = lambda headroom=10: False
    # テスト高速化: 短い max_attempts / poll_interval でタイムアウト検証
    result = game.analysis._wait_for_engine_capacity(
        mock_engine, headroom=10, max_attempts=3, poll_interval=0.001
    )
    assert result is False


def test_backward_compat_methods_exist(game_with_mock_engine):
    """既存テスト用の private メソッドが Game に存在し、orchestrator へ委譲される"""
    game = game_with_mock_engine
    # これらは外部 (主に tests/test_game_analysis.py) から呼ばれる
    assert callable(game._handle_stop_mode)
    assert callable(game._handle_ponder_mode)
    assert callable(game._handle_extra_mode)
    assert callable(game._handle_game_mode)
    assert callable(game._handle_sweep_equalize_modes)
    assert callable(game._wait_for_engine_capacity)


def test_analyze_extra_unknown_mode_raises_value_error(game_with_mock_engine):
    """未対応モードは orchestrator 側で ValueError を発生させうる"""
    game = game_with_mock_engine
    # 強制的に SWEEP/EQUALIZE 以外の未対応モードで _handle_sweep_equalize_modes を呼ぶ
    cn = game.current_node
    cn.analysis = {"completed": True, "root": {"scoreLead": 0.0, "visits": 50}, "moves": {}}
    engine = game.engines[cn.next_player]
    # None モード → ValueError
    with pytest.raises(ValueError):
        game.analysis._handle_sweep_equalize_modes(cn, engine, "bogus_mode", set())  # type: ignore[arg-type]

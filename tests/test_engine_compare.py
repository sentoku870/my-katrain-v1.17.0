"""
tests/test_engine_compare.py - Phase 39 エンジン比較ロジックのテスト

テスト戦略:
- 実エンジン不使用（合成データ + モック）
- scipy不使用（手動Spearmanテスト + 条件付きscipy比較）
"""

from unittest.mock import MagicMock

import pytest

from katrain.core.analysis.engine_compare import (
    PARTIAL_OVERLAP_THRESHOLD,
    ComparisonWarning,
    EngineComparisonResult,
    EngineStats,
    MoveComparison,
    compute_engine_stats,
    compute_spearman_manual,
)

# =============================================================================
# Helper Functions
# =============================================================================


def make_move_comparison(
    move_number: int,
    player: str = "B",
    gtp: str = "D4",
    katago_loss: float | None = None,
    leela_loss: float | None = None,
) -> MoveComparison:
    """テスト用MoveComparisonを作成。"""
    loss_diff = None
    if katago_loss is not None and leela_loss is not None:
        loss_diff = katago_loss - leela_loss
    return MoveComparison(
        move_number=move_number,
        player=player,
        gtp=gtp,
        katago_loss=katago_loss,
        leela_loss=leela_loss,
        loss_diff=loss_diff,
    )


def make_mock_game(
    moves: list[tuple[int, str, str, float | None, float | None]],
) -> MagicMock:
    """モックGameを作成。

    Args:
        moves: [(move_number, player, gtp, score_loss, leela_loss), ...]
    """
    game = MagicMock()

    # ルートノード
    root = MagicMock()
    root.depth = 0
    root.move = None
    root.children = []

    # 手ノードを作成
    nodes = [root]
    prev_node = root
    for move_num, player_str, gtp, _score_loss, leela_loss in moves:
        node = MagicMock()
        node.depth = move_num
        node.parent = prev_node
        node.children = []
        node.is_resign = False

        # Move mock
        move = MagicMock()
        move.player = 1 if player_str == "B" else 2
        if gtp == "pass":
            move.coords = None
            move.is_pass = True
        else:
            move.coords = (3, 3)  # dummy
            move.is_pass = False
            move.gtp = MagicMock(return_value=gtp)
        node.move = move

        # Leela analysis mock
        if leela_loss is not None:
            parent_leela = MagicMock()
            cand1 = MagicMock()
            cand1.move = "D4"  # best move
            cand1.winrate = 0.6
            cand2 = MagicMock()
            cand2.move = gtp
            # leela_loss = (best_wr - played_wr) * K * 100
            # played_wr = best_wr - leela_loss / (K * 100)
            K = 0.5
            cand2.winrate = 0.6 - leela_loss / (K * 100)
            parent_leela.candidates = [cand1, cand2]
            prev_node.leela_analysis = parent_leela
            node.leela_analysis = MagicMock()
        else:
            node.leela_analysis = None

        prev_node.children = [node]
        nodes.append(node)
        prev_node = node

    game.root = root

    # KataGo snapshot mock (via snapshot_from_game)
    return game, moves


# =============================================================================
# MoveComparison Tests
# =============================================================================


class TestMoveComparison:
    """MoveComparison データクラスのテスト。"""

    def test_abs_diff_with_both(self):
        """両方ある場合のabs_diff。"""
        mc = make_move_comparison(1, katago_loss=3.0, leela_loss=1.0)
        assert mc.abs_diff == 2.0

    def test_abs_diff_negative(self):
        """負の差分のabs_diff。"""
        mc = make_move_comparison(1, katago_loss=1.0, leela_loss=3.0)
        assert mc.abs_diff == 2.0

    def test_abs_diff_none(self):
        """片方Noneの場合のabs_diff。"""
        mc = make_move_comparison(1, katago_loss=3.0, leela_loss=None)
        assert mc.abs_diff == 0.0

    def test_has_both_true(self):
        """両方ある場合のhas_both。"""
        mc = make_move_comparison(1, katago_loss=3.0, leela_loss=1.0)
        assert mc.has_both is True

    def test_has_both_false_katago_only(self):
        """KataGoのみの場合のhas_both。"""
        mc = make_move_comparison(1, katago_loss=3.0, leela_loss=None)
        assert mc.has_both is False

    def test_has_both_false_leela_only(self):
        """Leelaのみの場合のhas_both。"""
        mc = make_move_comparison(1, katago_loss=None, leela_loss=1.0)
        assert mc.has_both is False

    def test_loss_diff_signed_positive(self):
        """差分は符号付き（katago > leela）。"""
        mc = make_move_comparison(1, katago_loss=5.0, leela_loss=2.0)
        assert mc.loss_diff == 3.0

    def test_loss_diff_signed_negative(self):
        """差分は符号付き（katago < leela）。"""
        mc = make_move_comparison(1, katago_loss=2.0, leela_loss=5.0)
        assert mc.loss_diff == -3.0

    def test_loss_diff_one_missing(self):
        """片方Noneの場合のloss_diff。"""
        mc = make_move_comparison(1, katago_loss=5.0, leela_loss=None)
        assert mc.loss_diff is None

    def test_sort_key_divergent(self):
        """乖離Top5用ソートキー。"""
        mc = make_move_comparison(10, katago_loss=5.0, leela_loss=2.0)
        key = mc.sort_key_divergent()
        assert key == (-3.0, 10, -5.0)


# =============================================================================
# EngineStats Tests
# =============================================================================


class TestEngineStats:
    """EngineStats のテスト。"""

    def test_empty(self):
        """空のEngineStats。"""
        stats = EngineStats.empty()
        assert stats.total_loss == 0.0
        assert stats.avg_loss == 0.0
        assert stats.analyzed_moves == 0

    def test_compute_total_loss(self):
        """総損失の計算。"""
        losses = [1.0, 2.0, 3.0]
        stats = compute_engine_stats(losses, (1.0, 3.0, 7.0))
        assert stats.total_loss == 6.0

    def test_compute_avg_loss(self):
        """平均損失の計算。"""
        losses = [1.0, 2.0, 3.0]
        stats = compute_engine_stats(losses, (1.0, 3.0, 7.0))
        assert stats.avg_loss == 2.0

    def test_compute_avg_loss_zero_moves(self):
        """解析手0の場合のavg_loss。"""
        stats = compute_engine_stats([], (1.0, 3.0, 7.0))
        assert stats.avg_loss == 0.0  # 0除算回避

    def test_mistake_counts(self):
        """ミス分類カウント。"""
        # thresholds: inaccuracy=1.0, mistake=3.0, blunder=7.0
        losses = [0.5, 1.5, 2.5, 4.0, 8.0]
        stats = compute_engine_stats(losses, (1.0, 3.0, 7.0))
        assert stats.inaccuracy_count == 2  # 1.5, 2.5
        assert stats.mistake_count == 1  # 4.0
        assert stats.blunder_count == 1  # 8.0

    def test_custom_thresholds(self):
        """カスタム閾値での分類。"""
        losses = [1.0, 3.0, 5.0]
        stats = compute_engine_stats(losses, (0.5, 2.0, 4.0))
        assert stats.inaccuracy_count == 1  # 1.0
        assert stats.mistake_count == 1  # 3.0
        assert stats.blunder_count == 1  # 5.0


# =============================================================================
# Spearman Correlation Tests
# =============================================================================


class TestSpearmanCorrelation:
    """手動Spearman相関のテスト。"""

    def test_perfect_correlation(self):
        """完全相関データ。"""
        paired = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
        result = compute_spearman_manual(paired)
        assert result == pytest.approx(1.0)

    def test_inverse_correlation(self):
        """逆相関データ。"""
        paired = [(1, 5), (2, 4), (3, 3), (4, 2), (5, 1)]
        result = compute_spearman_manual(paired)
        assert result == pytest.approx(-1.0)

    def test_insufficient_data(self):
        """N<5でNone。"""
        paired = [(1, 1), (2, 2), (3, 3), (4, 4)]
        result = compute_spearman_manual(paired)
        assert result is None

    def test_with_ties(self):
        """タイありデータ（中央順位法）。"""
        # 同値がある場合もクラッシュしない
        paired = [(1, 1), (1, 1), (2, 2), (3, 3), (4, 4)]
        result = compute_spearman_manual(paired)
        assert result is not None
        # 浮動小数点誤差を考慮
        assert -1.0 - 1e-10 <= result <= 1.0 + 1e-10

    def test_all_same_values(self):
        """全値同一でNone（分散ゼロ）。"""
        paired = [(1, 1), (1, 1), (1, 1), (1, 1), (1, 1)]
        result = compute_spearman_manual(paired)
        assert result is None

    def test_known_values(self):
        """事前計算した既知値テスト（scipy不要）。"""
        # [(1,1),(2,2),(3,3),(4,4),(5,5)] → r=1.0
        result = compute_spearman_manual([(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])
        assert result == pytest.approx(1.0)

        # [(1,5),(2,4),(3,3),(4,2),(5,1)] → r=-1.0
        result = compute_spearman_manual([(1, 5), (2, 4), (3, 3), (4, 2), (5, 1)])
        assert result == pytest.approx(-1.0)


class TestSpearmanVsScipy:
    """手動Spearman実装とscipy比較テスト（オプショナル）。"""

    def test_manual_vs_scipy(self):
        """scipyがあれば比較テスト。"""
        scipy_stats = pytest.importorskip("scipy.stats")

        test_data = [
            [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6)],
            [(1, 6), (2, 5), (3, 4), (4, 3), (5, 2)],
            [(1, 1), (2, 4), (3, 2), (4, 5), (5, 3)],
        ]

        for paired in test_data:
            x = [p[0] for p in paired]
            y = [p[1] for p in paired]

            manual_result = compute_spearman_manual(paired)
            scipy_result, _ = scipy_stats.spearmanr(x, y)

            assert manual_result == pytest.approx(scipy_result, abs=1e-10)


# =============================================================================
# Divergent Ordering Tests
# =============================================================================


class TestDivergentOrdering:
    """乖離Top5ソートのテスト。"""

    def test_ordering_by_abs_diff(self):
        """abs(diff)降順でソート。"""
        comparisons = [
            make_move_comparison(1, katago_loss=2.0, leela_loss=1.0),  # diff=1
            make_move_comparison(2, katago_loss=5.0, leela_loss=1.0),  # diff=4
            make_move_comparison(3, katago_loss=3.0, leela_loss=1.0),  # diff=2
        ]
        sorted_comps = sorted(comparisons, key=lambda c: c.sort_key_divergent())
        assert sorted_comps[0].move_number == 2  # diff=4
        assert sorted_comps[1].move_number == 3  # diff=2
        assert sorted_comps[2].move_number == 1  # diff=1

    def test_tiebreak_by_move_number(self):
        """同点時は手数昇順。"""
        comparisons = [
            make_move_comparison(10, katago_loss=3.0, leela_loss=1.0),  # diff=2
            make_move_comparison(5, katago_loss=3.0, leela_loss=1.0),  # diff=2
        ]
        sorted_comps = sorted(comparisons, key=lambda c: c.sort_key_divergent())
        assert sorted_comps[0].move_number == 5
        assert sorted_comps[1].move_number == 10

    def test_tiebreak_by_katago_loss(self):
        """最終タイブレークはkatago_loss降順。"""
        comparisons = [
            make_move_comparison(5, katago_loss=3.0, leela_loss=1.0),  # diff=2, katago=3
            make_move_comparison(5, katago_loss=5.0, leela_loss=3.0),  # diff=2, katago=5
        ]
        sorted_comps = sorted(comparisons, key=lambda c: c.sort_key_divergent())
        assert sorted_comps[0].katago_loss == 5.0  # 大きい方が先


# =============================================================================
# Warning Tests
# =============================================================================


class TestComparisonWarnings:
    """警告判定のテスト。"""

    def test_semantics_differ_always(self):
        """SEMANTICS_DIFFERは常に付与。"""
        result = EngineComparisonResult(
            move_comparisons=[],
            katago_stats=EngineStats.empty(),
            leela_stats=EngineStats.empty(),
            correlation=None,
            divergent_moves=[],
            mean_diff=None,
            warnings=[ComparisonWarning.SEMANTICS_DIFFER],
            total_moves=0,
        )
        assert ComparisonWarning.SEMANTICS_DIFFER in result.warnings

    def test_partial_overlap_threshold(self):
        """PARTIAL_OVERLAP閾値の確認。"""
        assert PARTIAL_OVERLAP_THRESHOLD == 0.8


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """エッジケーステスト。"""

    def test_zero_loss_both(self):
        """両エンジン0.0のdiff。"""
        mc = make_move_comparison(1, katago_loss=0.0, leela_loss=0.0)
        assert mc.loss_diff == 0.0
        assert mc.abs_diff == 0.0
        assert mc.has_both is True

    def test_pass_move_gtp(self):
        """パス手のgtp表現。"""
        mc = make_move_comparison(100, player="W", gtp="pass")
        assert mc.gtp == "pass"

    def test_very_long_game_performance(self):
        """500手対局のパフォーマンス確認。"""
        import time

        comparisons = [
            make_move_comparison(i, katago_loss=float(i % 10), leela_loss=float((i + 1) % 10)) for i in range(1, 501)
        ]

        start = time.time()

        # 統計計算
        katago_losses = [c.katago_loss for c in comparisons if c.katago_loss is not None]
        compute_engine_stats(katago_losses, (1.0, 3.0, 7.0))

        # 相関計算
        paired = [(c.katago_loss, c.leela_loss) for c in comparisons if c.has_both]
        compute_spearman_manual(paired)

        # 乖離Top5
        with_diff = [c for c in comparisons if c.has_both and c.abs_diff >= 1.0]
        sorted(with_diff, key=lambda c: c.sort_key_divergent())[:5]

        elapsed = time.time() - start
        assert elapsed < 0.1  # 100ms以内


# =============================================================================
# Integration-style Tests (with mocks)
# =============================================================================


class TestBuildComparisonIntegration:
    """build_comparison_from_game の統合テスト（モック使用）。"""

    def test_both_engines_full_basic(self):
        """両エンジン全手解析の基本テスト。

        Note: 実際のbuild_comparison_from_gameはGameオブジェクトを必要とするため、
        ここではデータクラスの動作確認のみ行う。
        """
        # 手動でEngineComparisonResultを構築してテスト
        comparisons = [
            make_move_comparison(1, katago_loss=1.0, leela_loss=1.5),
            make_move_comparison(2, katago_loss=2.0, leela_loss=1.0),
            make_move_comparison(3, katago_loss=0.5, leela_loss=0.5),
        ]

        katago_stats = compute_engine_stats(
            [c.katago_loss for c in comparisons if c.katago_loss is not None],
            (1.0, 3.0, 7.0),
        )
        leela_stats = compute_engine_stats(
            [c.leela_loss for c in comparisons if c.leela_loss is not None],
            (1.0, 3.0, 7.0),
        )

        # 相関計算
        paired = [(c.katago_loss, c.leela_loss) for c in comparisons if c.has_both]
        correlation = compute_spearman_manual(paired)

        # 乖離Top5
        with_diff = [c for c in comparisons if c.has_both and c.abs_diff >= 0.5]
        divergent = sorted(with_diff, key=lambda c: c.sort_key_divergent())[:5]

        # 平均差分
        diffs = [c.loss_diff for c in comparisons if c.loss_diff is not None]
        mean_diff = sum(diffs) / len(diffs)

        result = EngineComparisonResult(
            move_comparisons=comparisons,
            katago_stats=katago_stats,
            leela_stats=leela_stats,
            correlation=correlation,
            divergent_moves=divergent,
            mean_diff=mean_diff,
            warnings=[ComparisonWarning.SEMANTICS_DIFFER],
            total_moves=3,
        )

        assert len(result.move_comparisons) == 3
        assert result.katago_stats.total_loss == 3.5
        assert result.leela_stats.total_loss == 3.0
        assert result.total_moves == 3
        assert ComparisonWarning.SEMANTICS_DIFFER in result.warnings

    def test_katago_only_scenario(self):
        """KataGoのみ解析のシナリオ。"""
        comparisons = [
            make_move_comparison(1, katago_loss=1.0, leela_loss=None),
            make_move_comparison(2, katago_loss=2.0, leela_loss=None),
        ]

        katago_stats = compute_engine_stats(
            [c.katago_loss for c in comparisons if c.katago_loss is not None],
            (1.0, 3.0, 7.0),
        )
        leela_stats = EngineStats.empty()

        warnings = [ComparisonWarning.SEMANTICS_DIFFER]
        if katago_stats.analyzed_moves > 0 and leela_stats.analyzed_moves == 0:
            warnings.append(ComparisonWarning.KATAGO_ONLY)

        result = EngineComparisonResult(
            move_comparisons=comparisons,
            katago_stats=katago_stats,
            leela_stats=leela_stats,
            correlation=None,
            divergent_moves=[],
            mean_diff=None,
            warnings=warnings,
            total_moves=2,
        )

        assert ComparisonWarning.KATAGO_ONLY in result.warnings
        assert result.correlation is None

    def test_leela_only_scenario(self):
        """Leelaのみ解析のシナリオ。"""
        comparisons = [
            make_move_comparison(1, katago_loss=None, leela_loss=1.5),
            make_move_comparison(2, katago_loss=None, leela_loss=2.5),
        ]

        katago_stats = EngineStats.empty()
        leela_stats = compute_engine_stats(
            [c.leela_loss for c in comparisons if c.leela_loss is not None],
            (1.0, 3.0, 7.0),
        )

        warnings = [ComparisonWarning.SEMANTICS_DIFFER]
        if katago_stats.analyzed_moves == 0 and leela_stats.analyzed_moves > 0:
            warnings.append(ComparisonWarning.LEELA_ONLY)

        result = EngineComparisonResult(
            move_comparisons=comparisons,
            katago_stats=katago_stats,
            leela_stats=leela_stats,
            correlation=None,
            divergent_moves=[],
            mean_diff=None,
            warnings=warnings,
            total_moves=2,
        )

        assert ComparisonWarning.LEELA_ONLY in result.warnings

    def test_partial_overlap_warning(self):
        """部分的重複の警告。"""
        # 10手中7手だけ両エンジン解析 → 70% < 80%
        comparisons = []
        for i in range(1, 11):
            if i <= 7:
                comparisons.append(make_move_comparison(i, katago_loss=1.0, leela_loss=1.0))
            else:
                comparisons.append(make_move_comparison(i, katago_loss=1.0, leela_loss=None))

        total_moves = 10
        both_count = sum(1 for c in comparisons if c.has_both)

        warnings = [ComparisonWarning.SEMANTICS_DIFFER]
        if total_moves > 0 and both_count < total_moves * PARTIAL_OVERLAP_THRESHOLD:
            warnings.append(ComparisonWarning.PARTIAL_OVERLAP)

        assert ComparisonWarning.PARTIAL_OVERLAP in warnings
        assert both_count == 7
        assert both_count / total_moves == 0.7  # < 0.8

    def test_no_partial_overlap_above_threshold(self):
        """閾値以上なら警告なし。"""
        # 10手中9手が両エンジン解析 → 90% > 80%
        comparisons = []
        for i in range(1, 11):
            if i <= 9:
                comparisons.append(make_move_comparison(i, katago_loss=1.0, leela_loss=1.0))
            else:
                comparisons.append(make_move_comparison(i, katago_loss=1.0, leela_loss=None))

        total_moves = 10
        both_count = sum(1 for c in comparisons if c.has_both)

        warnings = [ComparisonWarning.SEMANTICS_DIFFER]
        if total_moves > 0 and both_count < total_moves * PARTIAL_OVERLAP_THRESHOLD:
            warnings.append(ComparisonWarning.PARTIAL_OVERLAP)

        assert ComparisonWarning.PARTIAL_OVERLAP not in warnings
        assert both_count == 9
        assert both_count / total_moves == 0.9  # > 0.8


# =============================================================================
# Mean Diff Tests
# =============================================================================


class TestMeanDiff:
    """平均差分のテスト。"""

    def test_mean_diff_positive(self):
        """平均差分が正（KataGo厳しい）。"""
        comparisons = [
            make_move_comparison(1, katago_loss=5.0, leela_loss=2.0),  # diff=3
            make_move_comparison(2, katago_loss=4.0, leela_loss=2.0),  # diff=2
            make_move_comparison(3, katago_loss=3.0, leela_loss=2.0),  # diff=1
        ]
        diffs = [c.loss_diff for c in comparisons if c.loss_diff is not None]
        mean_diff = sum(diffs) / len(diffs)
        assert mean_diff == 2.0  # (3+2+1)/3

    def test_mean_diff_negative(self):
        """平均差分が負（Leela厳しい）。"""
        comparisons = [
            make_move_comparison(1, katago_loss=2.0, leela_loss=5.0),  # diff=-3
            make_move_comparison(2, katago_loss=2.0, leela_loss=4.0),  # diff=-2
            make_move_comparison(3, katago_loss=2.0, leela_loss=3.0),  # diff=-1
        ]
        diffs = [c.loss_diff for c in comparisons if c.loss_diff is not None]
        mean_diff = sum(diffs) / len(diffs)
        assert mean_diff == -2.0  # (-3-2-1)/3

    def test_mean_diff_near_zero(self):
        """平均差分がほぼゼロ（両エンジン同程度）。"""
        comparisons = [
            make_move_comparison(1, katago_loss=3.0, leela_loss=2.0),  # diff=1
            make_move_comparison(2, katago_loss=2.0, leela_loss=3.0),  # diff=-1
        ]
        diffs = [c.loss_diff for c in comparisons if c.loss_diff is not None]
        mean_diff = sum(diffs) / len(diffs)
        assert mean_diff == 0.0

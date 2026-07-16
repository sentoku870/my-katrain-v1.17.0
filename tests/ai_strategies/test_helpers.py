"""Cross-cutting AI helper tests (Phase F-1).

Extracted from tests/test_ai_strategies.py. Covers
:func:`ai_rank_estimation`, :func:`game_report`, the interpolation
helpers (:func:`interp1d`, :func:`interp2d`, :func:`interp_ix`), the
weight generators, and the :func:`generate_ai_move` / request-analysis
guards.
"""

from __future__ import annotations

from katrain.core.ai import (
    STRATEGY_REGISTRY,
    ai_rank_estimation,
    game_report,
)
from katrain.core.ai.constants import (
    AI_DEFAULT,
    AI_HANDICAP,
    AI_HUMAN,
    AI_INFLUENCE,
    AI_JIGO,
    AI_LOCAL,
    AI_PICK,
    AI_PRO,
    AI_RANK,
    AI_SCORELOSS,
    AI_STRENGTH,
    AI_TENUKI,
    AI_TERRITORY,
    AI_WEIGHTED,
)
from katrain.core.ai_strategies_base import (
    AIStrategy,
    generate_influence_territory_weights,
    generate_local_tenuki_weights,
    interp1d,
    interp2d,
    interp_ix,
    register_strategy,
)
from katrain.core.game import Move
from tests.ai_strategies._helpers import (
    ai_test_context,
)


class TestAiRankEstimation:
    def test_default_strategies_return_9(self):
        """AI_DEFAULT, AI_HANDICAP, AI_JIGO, AI_PRO all return 9.0."""
        for s in [AI_DEFAULT, AI_HANDICAP, AI_JIGO, AI_PRO]:
            assert ai_rank_estimation(s, {}) == 9.0

    def test_rank_strategy(self):
        """AI_RANK: 1 - kyu_rank."""
        assert ai_rank_estimation(AI_RANK, {"kyu_rank": 5}) == 1 - 5

    def test_human_strategy(self):
        """AI_HUMAN: 1 - human_kyu_rank."""
        assert ai_rank_estimation(AI_HUMAN, {"human_kyu_rank": 8}) == 1 - 8

    def test_weighted_uses_weaken_fac(self):
        """AI_WEIGHTED: interpolate from AI_WEIGHTED_ELO using weaken_fac."""
        result = ai_rank_estimation(AI_WEIGHTED, {"weaken_fac": 1.0})
        assert isinstance(result, float)
        assert -30 <= result <= 9

    def test_scoreloss_uses_strength(self):
        """AI_SCORELOSS: interpolate from AI_SCORELOSS_ELO using strength."""
        result = ai_rank_estimation(AI_SCORELOSS, {"strength": 5.0})
        assert isinstance(result, float)
        assert -30 <= result <= 9

    def test_pick_uses_pick_frac_pick_n(self):
        """AI_PICK: 2D interpolation from AI_PICK_ELO_GRID."""
        result = ai_rank_estimation(AI_PICK, {"pick_frac": 0.5, "pick_n": 3})
        assert isinstance(result, float)
        assert -30 <= result <= 9

    def test_local_tenuki_territory_influence(self):
        """2D interpolation strategies all return a float."""
        for s in [AI_LOCAL, AI_TENUKI, AI_TERRITORY, AI_INFLUENCE]:
            result = ai_rank_estimation(s, {"pick_frac": 0.5, "pick_n": 3})
            assert isinstance(result, float)
            assert -30 <= result <= 9

    def test_unknown_uses_ai_strength(self):
        """Unknown strategy falls back to AI_STRENGTH dict."""
        AI_STRENGTH["custom_xyz"] = 5.0
        try:
            result = ai_rank_estimation("custom_xyz", {})
            assert result == 5.0
        finally:
            AI_STRENGTH.pop("custom_xyz", None)


# ---------------------------------------------------------------------------
# game_report
# ---------------------------------------------------------------------------


class TestGameReport:
    def test_game_report_empty_game(self):
        """game_report on empty game returns empty stats."""
        with ai_test_context() as (game, cn):
            sum_stats, histogram, ptloss = game_report(game, [0, 1, 2, 5])
            for bw in "BW":
                assert sum_stats[bw] == {} or "mean_ptloss" not in sum_stats.get(bw, {})

    def test_game_report_with_no_points_lost(self):
        """game_report handles nodes with no points_lost gracefully."""
        with ai_test_context() as (game, cn):
            sum_stats, histogram, ptloss = game_report(game, [0, 1, 2, 5])
            assert ptloss == {"B": [], "W": []}

    def test_game_report_depth_filter_no_passes(self):
        """depth_filter restricts but no moves are analyzed."""
        with ai_test_context(depth=1) as (game, cn):
            sum_stats, histogram, ptloss = game_report(game, [0, 1, 2, 5], depth_filter=(0, 0.1))
            assert isinstance(sum_stats, dict)


# ---------------------------------------------------------------------------
# DefaultStrategy
# ---------------------------------------------------------------------------


class TestInterpolationUtils:
    def test_interp_ix_basic(self):
        result = interp_ix([1.0, 2.0, 3.0, 4.0], 2.5)
        i, t = result
        assert i == 1
        assert t == 0.5

    def test_interp_ix_at_boundary(self):
        result = interp_ix([1.0, 2.0, 3.0], 1.0)
        i, t = result
        assert t == 0.0

    def test_interp1d(self):
        result = interp1d([(1.0, 10.0), (2.0, 20.0), (3.0, 30.0)], 1.5)
        assert abs(result - 15.0) < 0.01

    def test_interp2d_bilinear(self):
        gridspec = ([1.0, 2.0, 3.0], [10.0, 20.0], [[100.0, 200.0, 300.0], [400.0, 500.0, 600.0]])
        # x=2.0 is at index 1 exactly (t=0), y=15.0 is between 10 and 20 (s=0.5)
        # (1-t)(1-s)*m[0][1] + t(1-s)*m[0][2] + (1-t)s*m[1][1] + t*s*m[1][2]
        # = 1*0.5*200 + 0*0.5*300 + 1*0.5*500 + 0*0.5*600 = 100 + 0 + 250 + 0 = 350
        result = interp2d(gridspec, 2.0, 15.0)
        assert result == 350.0


class TestGenerateWeights:
    def test_generate_influence_territory_weights_influence(self):
        """Influence weights higher for positions far from edge."""
        grid = [[0.1, 0.2, 0.3], [0.05, 0.5, 0.05], [0.0, 0.0, 0.0]]
        coords, thoughts = generate_influence_territory_weights(
            AI_INFLUENCE, {"threshold": 1, "line_weight": 0.5}, grid, (3, 3)
        )
        assert len(coords) >= 1

    def test_generate_influence_territory_weights_territory(self):
        """Territory weights higher for positions near center/edge."""
        grid = [[0.1, 0.2, 0.3], [0.05, 0.5, 0.05], [0.0, 0.0, 0.0]]
        coords, thoughts = generate_influence_territory_weights(
            AI_TERRITORY, {"threshold": 1, "line_weight": 0.5}, grid, (3, 3)
        )
        assert len(coords) >= 1

    def test_generate_local_tenuki_weights(self):
        """Local/Tenuki weights based on distance from previous move."""
        grid = [[0.5, 0.3, 0.1], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        prev_move = Move.from_gtp("A19", player="B")
        with ai_test_context(move=prev_move) as (game, cn):
            coords, thoughts = generate_local_tenuki_weights(AI_LOCAL, {"stddev": 2.0}, grid, cn, (3, 3))
            assert len(coords) >= 1


# ---------------------------------------------------------------------------
# register_strategy decorator
# ---------------------------------------------------------------------------


class TestRegisterStrategy:
    def test_register_strategy_adds_to_registry(self):
        """register_strategy adds a class to the registry under the given name."""

        @register_strategy("test:custom_strategy")
        class CustomTestStrategy(AIStrategy):
            def generate_move(self):
                return Move(None, player="B"), "test"

        assert "test:custom_strategy" in STRATEGY_REGISTRY
        assert STRATEGY_REGISTRY["test:custom_strategy"] is CustomTestStrategy
        del STRATEGY_REGISTRY["test:custom_strategy"]

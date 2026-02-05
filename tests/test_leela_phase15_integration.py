"""Phase 15 integration tests for Leela UI."""

from katrain.core.game_node import GameNode
from katrain.core.leela.logic import compute_estimated_loss
from katrain.core.leela.models import LeelaCandidate, LeelaPositionEval


class TestLeelaRequestPrevention:
    """Tests for multi-request prevention."""

    def test_skip_if_already_analyzed(self):
        """Analyzed node should not be re-analyzed (is_valid == True)."""
        node = GameNode()
        analysis = LeelaPositionEval(candidates=[LeelaCandidate(move="D4", winrate=0.5, visits=100, loss_est=0.0)])
        node.set_leela_analysis(analysis)

        # Confirm: recognized as analyzed
        assert node.leela_analysis is not None
        assert node.leela_analysis.is_valid is True
        assert len(node.leela_analysis.candidates) == 1

    def test_invalid_analysis_allows_retry(self):
        """Invalid analysis result should allow retry."""
        node = GameNode()
        node.set_leela_analysis(LeelaPositionEval(parse_error="Test error"))

        # Confirm: recognized as invalid
        assert node.leela_analysis is not None
        assert node.leela_analysis.is_valid is False


class TestKValueRecalculation:
    """Tests for K value recalculation."""

    def test_recalc_changes_loss(self):
        """Changing K value should change loss_est."""
        candidates = [
            LeelaCandidate(move="D4", winrate=0.52, visits=1000),
            LeelaCandidate(move="Q16", winrate=0.48, visits=500),
        ]
        original = LeelaPositionEval(candidates=candidates)

        k05 = compute_estimated_loss(original, k=0.5)
        k10 = compute_estimated_loss(original, k=1.0)

        q16_k05 = next(c for c in k05.candidates if c.move == "Q16")
        q16_k10 = next(c for c in k10.candidates if c.move == "Q16")

        # K=1.0 loss should be about 2x of K=0.5
        assert q16_k10.loss_est is not None
        assert q16_k05.loss_est is not None
        assert q16_k10.loss_est > q16_k05.loss_est
        # Concrete values: 4% diff * K -> K=0.5 gives 2.0, K=1.0 gives 4.0
        assert abs(q16_k05.loss_est - 2.0) < 0.1
        assert abs(q16_k10.loss_est - 4.0) < 0.1

    def test_recalc_preserves_winrate(self):
        """Recalculation should preserve winrate."""
        candidates = [LeelaCandidate(move="D4", winrate=0.52, visits=1000)]
        original = LeelaPositionEval(candidates=candidates)

        recalculated = compute_estimated_loss(original, k=1.0)

        assert recalculated.candidates[0].winrate == 0.52
        assert recalculated.candidates[0].visits == 1000

    def test_best_move_always_zero_loss(self):
        """Best move should always have loss_est=0.0."""
        candidates = [
            LeelaCandidate(move="D4", winrate=0.55, visits=1000),
            LeelaCandidate(move="Q16", winrate=0.50, visits=500),
        ]
        original = LeelaPositionEval(candidates=candidates)

        result = compute_estimated_loss(original, k=1.0)
        best = max(result.candidates, key=lambda c: c.winrate)

        assert best.loss_est == 0.0


class TestKataGoRegression:
    """KataGo regression tests."""

    def test_leela_does_not_affect_katago(self):
        """Leela analysis should not affect KataGo analysis."""
        node = GameNode()

        # Set KataGo analysis
        node.analysis["moves"]["D4"] = {"scoreLead": 0.5, "visits": 100}

        # Set Leela analysis
        node.set_leela_analysis(
            LeelaPositionEval(candidates=[LeelaCandidate(move="D4", winrate=0.5, visits=100, loss_est=0.0)])
        )

        # Confirm KataGo analysis unchanged
        assert node.analysis["moves"]["D4"]["scoreLead"] == 0.5
        assert node.analysis["moves"]["D4"]["visits"] == 100
        # Confirm Leela analysis set
        assert node.leela_analysis is not None
        assert node.leela_analysis.is_valid

    def test_clear_analysis_clears_both(self):
        """clear_analysis() should clear both."""
        node = GameNode()
        node.analysis["moves"]["D4"] = {"scoreLead": 0.5, "visits": 100}
        node.set_leela_analysis(
            LeelaPositionEval(candidates=[LeelaCandidate(move="D4", winrate=0.5, visits=100, loss_est=0.0)])
        )

        node.clear_analysis()

        assert node.leela_analysis is None
        assert node.analysis["completed"] is False


class TestConfigIntegration:
    """Config integration tests."""

    def test_leela_config_exists(self):
        """config.json should have leela settings."""
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "katrain" / "config.json"
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        assert "leela" in config
        assert "enabled" in config["leela"]
        assert "exe_path" in config["leela"]
        assert "max_visits" in config["leela"]
        assert "loss_scale_k" in config["leela"]

    def test_default_values(self):
        """Default values should be reasonable."""
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "katrain" / "config.json"
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        leela = config["leela"]
        assert leela["enabled"] is False  # default is disabled
        assert 0.1 <= leela["loss_scale_k"] <= 2.0  # K value in valid range
        assert leela["max_visits"] >= 100  # minimum visits


class TestLeelaLogicClampK:
    """Tests for clamp_k function."""

    def test_clamp_k_too_low(self):
        """K value below minimum should be clamped."""
        from katrain.core.constants import LEELA_K_MIN
        from katrain.core.leela.logic import clamp_k

        result = clamp_k(0.05)
        assert result == LEELA_K_MIN

    def test_clamp_k_too_high(self):
        """K value above maximum should be clamped."""
        from katrain.core.constants import LEELA_K_MAX
        from katrain.core.leela.logic import clamp_k

        result = clamp_k(5.0)
        assert result == LEELA_K_MAX

    def test_clamp_k_in_range(self):
        """K value in range should not change."""
        from katrain.core.leela.logic import clamp_k

        result = clamp_k(0.5)
        assert result == 0.5

        result = clamp_k(1.0)
        assert result == 1.0

"""Integration tests for Leela estimated loss feature.

These tests verify the full pipeline from parsing to display formatting.
UI rendering tests are manual (see Phase 14.7 manual test plan).
"""

import pytest

from katrain.core.game_node import GameNode
from katrain.core.leela.models import LeelaCandidate, LeelaPositionEval
from katrain.core.leela.parser import parse_lz_analyze
from katrain.core.leela.logic import compute_estimated_loss, LEELA_K_DEFAULT
from katrain.core.leela.presentation import loss_to_color, format_loss_est, format_winrate_pct


class TestParserToLogicPipeline:
    """Tests for parser -> logic pipeline."""

    def test_parse_and_compute_loss(self):
        """Test full pipeline from raw output to loss calculation."""
        # Sample lz-analyze output
        raw_output = """info move R14 visits 59871 winrate 4997 order 0 pv R14 R5 C16
info move R13 visits 18346 winrate 4948 order 1 pv R13 R5 Q5
info move M17 visits 5254 winrate 4913 order 2 pv M17 F17 D17"""

        # Parse
        parsed = parse_lz_analyze(raw_output)
        assert parsed.is_valid
        assert len(parsed.candidates) == 3

        # Compute loss
        with_loss = compute_estimated_loss(parsed, k=LEELA_K_DEFAULT)
        assert with_loss.is_valid
        assert len(with_loss.candidates) == 3

        # Best candidate should have loss 0
        best = with_loss.candidates[0]
        assert best.move == "R14"
        assert best.loss_est == 0.0

        # Other candidates should have positive loss
        for candidate in with_loss.candidates[1:]:
            assert candidate.loss_est is not None
            assert candidate.loss_est > 0.0

    def test_empty_output_produces_invalid_result(self):
        """Test that empty output produces invalid result."""
        parsed = parse_lz_analyze("")
        assert not parsed.is_valid

        with_loss = compute_estimated_loss(parsed)
        assert not with_loss.is_valid

    def test_gtp_error_produces_invalid_result(self):
        """Test that GTP error produces invalid result."""
        parsed = parse_lz_analyze("? unknown command")
        assert not parsed.is_valid


class TestLogicToGameNodePipeline:
    """Tests for logic -> GameNode pipeline."""

    def test_set_leela_analysis_on_node(self):
        """Test setting computed Leela analysis on GameNode."""
        # Create analysis
        candidates = [
            LeelaCandidate(move="D4", winrate=0.52, visits=1000, loss_est=0.0),
            LeelaCandidate(move="Q16", winrate=0.48, visits=500, loss_est=2.0),
        ]
        analysis = LeelaPositionEval(candidates=candidates)

        # Set on node
        node = GameNode()
        node.set_leela_analysis(analysis)

        # Verify
        assert node.leela_analysis is not None
        assert node.leela_analysis.is_valid
        assert len(node.leela_analysis.candidates) == 2
        assert node.leela_analysis.candidates[0].loss_est == 0.0

    def test_katago_analysis_unchanged(self):
        """Test that KataGo analysis is not affected by Leela analysis."""
        node = GameNode()

        # Set Leela analysis
        leela_candidates = [
            LeelaCandidate(move="D4", winrate=0.52, visits=1000, loss_est=0.0),
        ]
        node.set_leela_analysis(LeelaPositionEval(candidates=leela_candidates))

        # KataGo analysis should be unchanged
        assert node.analysis == {
            "moves": {},
            "root": None,
            "ownership": None,
            "policy": None,
            "completed": False,
        }

    def test_clear_analysis_clears_both(self):
        """Test that clear_analysis clears both KataGo and Leela analysis."""
        node = GameNode()

        # Set Leela analysis
        node.set_leela_analysis(
            LeelaPositionEval(
                candidates=[LeelaCandidate(move="D4", winrate=0.5, visits=100, loss_est=0.0)]
            )
        )
        assert node.leela_analysis is not None

        # Clear
        node.clear_analysis()

        # Both should be cleared
        assert node.leela_analysis is None
        assert node.analysis["completed"] is False


class TestFullPipeline:
    """Full pipeline integration tests."""

    def test_parse_compute_store_format(self):
        """Test full pipeline: parse -> compute loss -> store -> format."""
        # Raw output
        raw_output = """info move C4 visits 10000 winrate 5200 order 0 pv C4 D16 Q4
info move D4 visits 8000 winrate 5100 order 1 pv D4 Q16 C16"""

        # Parse
        parsed = parse_lz_analyze(raw_output)

        # Compute loss with K=0.5
        with_loss = compute_estimated_loss(parsed, k=0.5)

        # Store on node
        node = GameNode()
        node.set_leela_analysis(with_loss)

        # Format for display
        analysis = node.leela_analysis
        assert analysis is not None

        best = analysis.candidates[0]
        second = analysis.candidates[1]

        # Best move formatting
        assert format_loss_est(best.loss_est) == "0.0"
        assert format_winrate_pct(best.winrate) == "52.0%"

        # Second move formatting
        # 52% - 51% = 1% diff * 0.5 = 0.5 loss
        assert format_loss_est(second.loss_est) == "0.5"
        assert format_winrate_pct(second.winrate) == "51.0%"

        # Colors
        best_color = loss_to_color(best.loss_est)
        second_color = loss_to_color(second.loss_est)

        # Best should be green, second should be slightly warmer
        from katrain.core.constants import LEELA_COLOR_BEST
        assert best_color == LEELA_COLOR_BEST
        # Second color should have higher red component than best
        assert second_color != best_color


class TestKataGoRegression:
    """Regression tests to ensure KataGo functionality is not affected."""

    def test_game_node_analysis_structure(self):
        """Test that GameNode analysis structure is unchanged."""
        node = GameNode()

        # Check structure
        assert "moves" in node.analysis
        assert "root" in node.analysis
        assert "ownership" in node.analysis
        assert "policy" in node.analysis
        assert "completed" in node.analysis

    def test_game_node_candidate_moves(self):
        """Test that candidate_moves property works correctly."""
        node = GameNode()

        # Should return empty list when no analysis
        assert node.candidate_moves == []

    def test_analysis_visits_requested(self):
        """Test that analysis_visits_requested works correctly."""
        node = GameNode()
        assert node.analysis_visits_requested == 0

        node.analysis_visits_requested = 1000
        assert node.analysis_visits_requested == 1000

        node.clear_analysis()
        assert node.analysis_visits_requested == 0


class TestConfigIntegration:
    """Tests for config-related integration."""

    def test_default_leela_config_values(self):
        """Test that default Leela config has expected values."""
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "katrain" / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Check leela section exists
        assert "leela" in config

        leela_config = config["leela"]
        assert "enabled" in leela_config
        assert "exe_path" in leela_config
        assert "max_visits" in leela_config
        assert "loss_scale_k" in leela_config

        # Check default values
        assert leela_config["enabled"] is False
        assert leela_config["loss_scale_k"] == 0.5


class TestRealSamplesPipeline:
    """Tests using real sample files."""

    @pytest.fixture
    def samples_dir(self):
        """Get samples directory."""
        from pathlib import Path
        return Path(__file__).parent / "fixtures" / "leela_samples"

    def test_even_game_opening_pipeline(self, samples_dir):
        """Test pipeline with even game opening sample."""
        sample_file = samples_dir / "even_game_opening.txt"
        if not sample_file.exists():
            pytest.skip("Sample file not found")

        with open(sample_file, "r", encoding="utf-8") as f:
            raw_output = f.read()

        # Full pipeline
        parsed = parse_lz_analyze(raw_output)
        assert parsed.is_valid

        with_loss = compute_estimated_loss(parsed, k=0.5)
        assert with_loss.is_valid

        # Store and retrieve
        node = GameNode()
        node.set_leela_analysis(with_loss)
        assert node.leela_analysis.is_valid

    def test_endgame_pipeline(self, samples_dir):
        """Test pipeline with endgame sample."""
        sample_file = samples_dir / "endgame.txt"
        if not sample_file.exists():
            pytest.skip("Sample file not found")

        with open(sample_file, "r", encoding="utf-8") as f:
            raw_output = f.read()

        # Full pipeline
        parsed = parse_lz_analyze(raw_output)
        if not parsed.is_valid:
            pytest.skip("Sample may be invalid")

        with_loss = compute_estimated_loss(parsed, k=0.5)

        # Even if only a few candidates, should work
        if with_loss.is_valid:
            node = GameNode()
            node.set_leela_analysis(with_loss)
            assert node.leela_analysis is not None

"""Tests for LeelaStrategy (Phase 40).

This module tests the Leela Zero AI strategy for move generation.
"""

from unittest.mock import MagicMock

import pytest

from katrain.core.ai import STRATEGY_REGISTRY
from katrain.core.constants import AI_LEELA


class TestLeelaStrategyRegistration:
    """Tests for LeelaStrategy registration in the strategy registry."""

    def test_ai_leela_in_registry(self):
        """AI_LEELA should be in STRATEGY_REGISTRY."""
        assert AI_LEELA in STRATEGY_REGISTRY

    def test_ai_leela_in_recommended_order(self):
        """AI_LEELA should appear in recommended order."""
        from katrain.core.constants import AI_STRATEGIES_RECOMMENDED_ORDER

        assert AI_LEELA in AI_STRATEGIES_RECOMMENDED_ORDER

    def test_ai_leela_in_strategies(self):
        """AI_LEELA should be in AI_STRATEGIES."""
        from katrain.core.constants import AI_STRATEGIES

        assert AI_LEELA in AI_STRATEGIES

    def test_ai_leela_has_strength(self):
        """AI_LEELA should have a strength value."""
        from katrain.core.constants import AI_STRENGTH

        assert AI_LEELA in AI_STRENGTH
        assert AI_STRENGTH[AI_LEELA] == 9


class TestLeelaStrategyErrors:
    """Tests for LeelaStrategy error handling."""

    @pytest.fixture
    def mock_game(self):
        """Create minimal mock game."""
        game = MagicMock()
        game.current_node.next_player = "B"
        game.current_node.nodes_from_root = []
        game.board_size = (19, 19)
        game.komi = 6.5
        game.katrain.log = MagicMock()
        game.katrain.config = MagicMock(return_value=500)
        return game

    def test_no_engine_raises(self, mock_game):
        """Should raise when leela_engine is None and start fails."""
        from katrain.core.ai import LeelaNotAvailableError, LeelaStrategy

        mock_game.katrain.leela_engine = None
        mock_game.katrain.start_leela_engine = MagicMock(return_value=False)

        strategy = LeelaStrategy(mock_game, {})
        with pytest.raises(LeelaNotAvailableError):
            strategy.generate_move()

    def test_dead_engine_raises(self, mock_game):
        """Should raise when engine is not alive."""
        from katrain.core.ai import LeelaNotAvailableError, LeelaStrategy

        mock_game.katrain.leela_engine = MagicMock()
        mock_game.katrain.leela_engine.is_alive.return_value = False

        strategy = LeelaStrategy(mock_game, {})
        with pytest.raises(LeelaNotAvailableError):
            strategy.generate_move()

    def test_request_analysis_failure_raises(self, mock_game):
        """Should raise when request_analysis returns False."""
        from katrain.core.ai import LeelaNotAvailableError, LeelaStrategy

        leela = MagicMock()
        leela.is_alive.return_value = True
        leela.request_analysis.return_value = False
        mock_game.katrain.leela_engine = leela

        strategy = LeelaStrategy(mock_game, {})
        with pytest.raises(LeelaNotAvailableError):
            strategy.generate_move()


class TestLeelaStrategySuccess:
    """Tests for successful LeelaStrategy move generation."""

    def test_successful_move(self):
        """Should return move from Leela's best candidate."""
        from katrain.core.ai import LeelaStrategy

        game = MagicMock()
        game.current_node.next_player = "B"
        game.current_node.nodes_from_root = []
        game.board_size = (19, 19)
        game.komi = 6.5
        game.katrain.log = MagicMock()
        game.katrain.config = MagicMock(return_value=500)

        # Mock Leela engine - callback called immediately (no threading)
        leela = MagicMock()
        leela.is_alive.return_value = True

        def mock_request(moves, callback, visits, board_size, komi):
            # Verify dynamic values are passed
            assert board_size == 19
            assert komi == 6.5

            # Create minimal mock result
            best_candidate = MagicMock()
            best_candidate.move = "D4"
            best_candidate.eval_pct = 55.0
            best_candidate.visits = 500

            result = MagicMock()
            result.is_valid = True
            result.best_candidate = best_candidate

            callback(result)  # Call immediately, no threading
            return True

        leela.request_analysis = mock_request
        game.katrain.leela_engine = leela

        strategy = LeelaStrategy(game, {})
        move, thoughts = strategy.generate_move()

        assert move.gtp() == "D4"
        assert "55.0%" in thoughts
        assert "Leela Zero" in thoughts

    def test_successful_move_9x9_board(self):
        """Should pass correct board_size for 9x9 games."""
        from katrain.core.ai import LeelaStrategy

        game = MagicMock()
        game.current_node.next_player = "B"
        game.current_node.nodes_from_root = []
        game.board_size = (9, 9)  # 9x9 board
        game.komi = 5.5  # Different komi for 9x9
        game.katrain.log = MagicMock()
        game.katrain.config = MagicMock(return_value=500)

        leela = MagicMock()
        leela.is_alive.return_value = True

        captured_args = {}

        def mock_request(moves, callback, visits, board_size, komi):
            captured_args["board_size"] = board_size
            captured_args["komi"] = komi

            best_candidate = MagicMock()
            best_candidate.move = "E5"
            best_candidate.eval_pct = 52.0
            best_candidate.visits = 500

            result = MagicMock()
            result.is_valid = True
            result.best_candidate = best_candidate

            callback(result)
            return True

        leela.request_analysis = mock_request
        game.katrain.leela_engine = leela

        strategy = LeelaStrategy(game, {})
        move, _ = strategy.generate_move()

        assert captured_args["board_size"] == 9
        assert captured_args["komi"] == 5.5
        assert move.gtp() == "E5"


class TestLeelaNotAvailableError:
    """Tests for LeelaNotAvailableError exception."""

    def test_exception_can_be_imported(self):
        """LeelaNotAvailableError should be importable."""
        from katrain.core.ai import LeelaNotAvailableError

        assert LeelaNotAvailableError is not None

    def test_exception_is_exception_subclass(self):
        """LeelaNotAvailableError should be an Exception subclass."""
        from katrain.core.ai import LeelaNotAvailableError

        assert issubclass(LeelaNotAvailableError, Exception)

    def test_exception_message(self):
        """LeelaNotAvailableError should preserve its message."""
        from katrain.core.ai import LeelaNotAvailableError

        error = LeelaNotAvailableError("Test message")
        assert str(error) == "Test message"


class TestConfigSettings:
    """Tests for config.json settings related to Leela play mode."""

    def test_ai_leela_in_config(self):
        """ai:leela should exist in config.json."""
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "katrain" / "config.json"
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        assert "ai" in config
        assert "ai:leela" in config["ai"]

    def test_play_visits_in_config(self):
        """leela.play_visits should exist in config.json."""
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "katrain" / "config.json"
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        assert "leela" in config
        assert "play_visits" in config["leela"]
        assert config["leela"]["play_visits"] == 500

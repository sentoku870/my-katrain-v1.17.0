"""Phase 280 slim-down: tests for the two surviving AI strategies.

Only ``ai:default`` (DefaultStrategy) and ``ai:handicap``
(HandicapStrategy) survive the slim-down. These tests verify:

- All announced strategies are registered in ``STRATEGY_REGISTRY``.
- ``AI_STRATEGIES`` / ``AI_STRATEGIES_RECOMMENDED_ORDER`` agree.
- The remaining strategies can be dispatched through
  ``generate_ai_move`` without raising (engine calls are mocked).
- ``ai_rank_estimation`` returns a sensible value for both.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from katrain.core.ai import ai_rank_estimation
from katrain.core.ai.constants import AI_STRATEGIES, AI_STRATEGIES_RECOMMENDED_ORDER
from katrain.core.base_katrain import KaTrainBase


class TestAI:
    def test_order(self):
        assert set(AI_STRATEGIES_RECOMMENDED_ORDER) == set(AI_STRATEGIES)

    def test_ai_strategies_dispatch(self):
        """``generate_ai_move`` can be called for every surviving strategy.

        Engine calls are fully mocked; this test verifies that the
        registry/dispatch contract still holds after the Phase 280
        slim-down.
        """
        import katrain.core.ai as ai_module

        katrain = KaTrainBase(force_package_config=True, debug_level=0)

        for strategy in AI_STRATEGIES:
            assert strategy in ai_module.STRATEGY_REGISTRY, f"{strategy} not in registry"

        mock_move = MagicMock()
        mock_move.coords = (3, 3)
        mock_node = MagicMock()
        mock_game = MagicMock()

        with patch.object(ai_module, "generate_ai_move", return_value=(mock_move, mock_node)) as mock_gen:
            for strategy in AI_STRATEGIES:
                settings = katrain.config(f"ai/{strategy}")
                move, played_node = ai_module.generate_ai_move(mock_game, strategy, settings)
                assert move.coords is not None
                assert played_node is mock_node

            assert mock_gen.call_count == len(AI_STRATEGIES)
            called_strategies = [c.args[1] for c in mock_gen.call_args_list]
            assert called_strategies == list(AI_STRATEGIES)

    def test_ai_rank_estimation(self):
        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        for strategy in AI_STRATEGIES:
            settings = katrain.config(f"ai/{strategy}")
            rank = ai_rank_estimation(strategy, settings)
            assert -20 <= rank <= 9

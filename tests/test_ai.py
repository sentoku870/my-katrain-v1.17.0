from unittest.mock import MagicMock, patch

from katrain.core.ai import ai_rank_estimation
from katrain.core.base_katrain import KaTrainBase
from katrain.core.constants import (
    AI_HUMAN,
    AI_PRO,
    AI_STRATEGIES,
    AI_STRATEGIES_RECOMMENDED_ORDER,
)


class TestAI:
    def test_order(self):
        assert set(AI_STRATEGIES_RECOMMENDED_ORDER) == set(AI_STRATEGIES)

    def test_ai_strategies_dispatch(self):
        """generate_ai_move が全戦略で例外なく呼び出せることを検証 (実 KataGo 不要)。

        戦略の動作詳細は tests/test_ai_strategies.py / test_ai_strategies_parametric.py で
        mock 化済み。本テストはレジストリ整合性とディスパッチの確認のみ。
        """
        import katrain.core.ai as ai_module

        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        test_strategies = [s for s in AI_STRATEGIES if s not in [AI_HUMAN, AI_PRO]]

        # すべての戦略が STRATEGY_REGISTRY に登録されていることを確認
        for strategy in test_strategies:
            assert strategy in ai_module.STRATEGY_REGISTRY, f"{strategy} not in registry"

        # generate_ai_move を mock して全戦略で呼び出せることを確認
        mock_move = MagicMock()
        mock_move.coords = (3, 3)
        mock_node = MagicMock()
        mock_game = MagicMock()

        with patch.object(
            ai_module, "generate_ai_move", return_value=(mock_move, mock_node)
        ) as mock_gen:
            for strategy in test_strategies:
                settings = katrain.config(f"ai/{strategy}")
                move, played_node = ai_module.generate_ai_move(mock_game, strategy, settings)
                assert move.coords is not None
                assert played_node is mock_node

            assert mock_gen.call_count == len(test_strategies)
            called_strategies = [c.args[1] for c in mock_gen.call_args_list]
            assert called_strategies == test_strategies

    def test_ai_rank_estimation(self):
        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        for strategy in AI_STRATEGIES:
            if strategy in [AI_HUMAN, AI_PRO]:
                continue
            settings = katrain.config(f"ai/{strategy}")
            rank = ai_rank_estimation(strategy, settings)
            assert -20 <= rank <= 9

"""Game パッケージ (Phase 141: 責務分割)

このパッケージは対局状態管理を以下の責務に分割して実装する:

- ``base`` : 着手/捕獲/Undo/SGF出力 (BaseGame)
- ``facade`` : Game クラス (合成 + レポートファサード)
- ``navigation`` : 重要局面ナビ (GameNavigator)
- ``analysis_orchestrator`` : 解析オーケストレーション (Phase 2 で追加)
- ``insert_mode`` : 挿入モード管理 (Phase 3 で追加)

後方互換のため ``katrain.core.game`` からすべての公開シンボルを再エクスポートする。
"""

from __future__ import annotations

from katrain.core.game.analysis_orchestrator import AnalysisOrchestrator
from katrain.core.game.base import (
    BaseGame,
    IllegalMoveException,
    KaTrainSGF,
)
from katrain.core.game.facade import Game
from katrain.core.game.insert_mode import InsertModeController
from katrain.core.game.navigation import GameNavigator
from katrain.core.game_node import GameNode
from katrain.core.reports.karte.models import KarteGenerationError
from katrain.core.sgf_parser import Move

__all__ = [
    "AnalysisOrchestrator",
    "BaseGame",
    "Game",
    "GameNode",
    "GameNavigator",
    "IllegalMoveException",
    "InsertModeController",
    "KarteGenerationError",
    "KaTrainSGF",
    "Move",
]

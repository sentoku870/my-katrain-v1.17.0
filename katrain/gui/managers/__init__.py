"""GUI managers package.

Phase 73: KeyboardManager抽出
Phase 74: ConfigManager抽出
Phase 75: PopupManager抽出
Phase 76: GameStateManager抽出
Phase 96: SummaryManager抽出
Phase 97: ActiveReviewController抽出
Phase 98: QuizManager抽出

Note: PEP 562 lazy imports を使用。
各マネージャーは初めてアクセスされた時のみインポートされる。
これにより、GameStateManagerの単体テスト時に他のマネージャー（GUI依存あり）を
読み込まずに済む。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "KeyboardManager",
    "ConfigManager",
    "PopupManager",
    "GameStateManager",
    "SummaryManager",
    "ActiveReviewController",
    "QuizManager",
]

if TYPE_CHECKING:
    from katrain.gui.managers.active_review_controller import (
        ActiveReviewController as ActiveReviewController,
    )
    from katrain.gui.managers.config_manager import ConfigManager as ConfigManager
    from katrain.gui.managers.game_state_manager import GameStateManager as GameStateManager
    from katrain.gui.managers.keyboard_manager import KeyboardManager as KeyboardManager
    from katrain.gui.managers.popup_manager import PopupManager as PopupManager
    from katrain.gui.managers.quiz_manager import QuizManager as QuizManager
    from katrain.gui.managers.summary_manager import SummaryManager as SummaryManager


def __getattr__(name: str) -> Any:
    """PEP 562: Lazy module attribute access."""
    if name == "KeyboardManager":
        from katrain.gui.managers.keyboard_manager import KeyboardManager

        return KeyboardManager
    if name == "ConfigManager":
        from katrain.gui.managers.config_manager import ConfigManager

        return ConfigManager
    if name == "PopupManager":
        from katrain.gui.managers.popup_manager import PopupManager

        return PopupManager
    if name == "GameStateManager":
        from katrain.gui.managers.game_state_manager import GameStateManager

        return GameStateManager
    if name == "SummaryManager":
        from katrain.gui.managers.summary_manager import SummaryManager

        return SummaryManager
    if name == "ActiveReviewController":
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        return ActiveReviewController
    if name == "QuizManager":
        from katrain.gui.managers.quiz_manager import QuizManager

        return QuizManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

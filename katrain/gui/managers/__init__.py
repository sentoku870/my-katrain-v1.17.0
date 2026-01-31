"""GUI managers package.

Phase 73: KeyboardManager抽出
Phase 74: ConfigManager抽出
Phase 75: PopupManager抽出
Phase 76: GameStateManager抽出

Note: PEP 562 lazy imports を使用。
各マネージャーは初めてアクセスされた時のみインポートされる。
これにより、GameStateManagerの単体テスト時に他のマネージャー（GUI依存あり）を
読み込まずに済む。
"""
from typing import TYPE_CHECKING

__all__ = ["KeyboardManager", "ConfigManager", "PopupManager", "GameStateManager", "SummaryManager"]

if TYPE_CHECKING:
    from katrain.gui.managers.config_manager import ConfigManager as ConfigManager
    from katrain.gui.managers.game_state_manager import GameStateManager as GameStateManager
    from katrain.gui.managers.keyboard_manager import KeyboardManager as KeyboardManager
    from katrain.gui.managers.popup_manager import PopupManager as PopupManager
    from katrain.gui.managers.summary_manager import SummaryManager as SummaryManager


def __getattr__(name: str):
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

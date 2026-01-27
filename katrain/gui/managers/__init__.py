"""GUI managers package.

Phase 73: KeyboardManager抽出
Phase 74: ConfigManager抽出
Phase 75: PopupManager抽出
"""
from katrain.gui.managers.config_manager import ConfigManager
from katrain.gui.managers.keyboard_manager import KeyboardManager
from katrain.gui.managers.popup_manager import PopupManager

__all__ = ["KeyboardManager", "ConfigManager", "PopupManager"]

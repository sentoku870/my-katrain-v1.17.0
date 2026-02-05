"""Dialog Factory (Phase 120)

Encapsulates the creation of application popups to decouple KaTrainGui from specific popup classes.
Works in conjunction with PopupManager which handles the state and caching.
"""

from typing import Any

from kivy.metrics import dp

from katrain.gui.popups import (
    ConfigAIPopup,
    ConfigTeacherPopup,
    ConfigTimerPopup,
    EngineRecoveryPopup,
    I18NPopup,
    NewGamePopup,
)


class DialogFactory:
    """Factory for creating application dialogs/popups."""

    def __init__(self, gui: Any):
        """Initialize with reference to main GUI."""
        self.gui = gui

    def create_new_game_popup(self) -> Any:
        """Create NewGamePopup."""
        raw = I18NPopup(
            title_key="New Game title",
            size=[dp(800), dp(900)],
            content=NewGamePopup(self.gui),
        )
        popup: Any = getattr(raw, "__self__", raw)
        popup.content.popup = popup
        return popup

    def create_timer_popup(self) -> Any:
        """Create TimerPopup."""
        raw = I18NPopup(
            title_key="timer settings",
            size=[dp(600), dp(500)],
            content=ConfigTimerPopup(self.gui),
        )
        popup: Any = getattr(raw, "__self__", raw)
        popup.content.popup = popup
        return popup

    def create_teacher_popup(self) -> Any:
        """Create TeacherPopup."""
        raw = I18NPopup(
            title_key="teacher settings",
            size=[dp(800), dp(825)],
            content=ConfigTeacherPopup(self.gui),
        )
        popup: Any = getattr(raw, "__self__", raw)
        popup.content.popup = popup
        return popup

    def create_ai_popup(self) -> Any:
        """Create AIPopup."""
        raw = I18NPopup(
            title_key="ai settings",
            size=[dp(750), dp(750)],
            content=ConfigAIPopup(self.gui),
        )
        popup: Any = getattr(raw, "__self__", raw)
        popup.content.popup = popup
        return popup

    def create_engine_recovery_popup(self, error_message: str, code: Any) -> Any:
        """Create EngineRecoveryPopup."""
        raw = I18NPopup(
            title_key="engine recovery",
            size=[dp(600), dp(700)],
            content=EngineRecoveryPopup(self.gui, error_message=error_message, code=code),
        )
        popup: Any = getattr(raw, "__self__", raw)
        popup.content.popup = popup
        return popup

    def is_engine_recovery_popup(self, popup: Any) -> bool:
        """Check if popup is EngineRecoveryPopup."""
        if not popup or not hasattr(popup, "content"):
            return False
        return isinstance(popup.content, EngineRecoveryPopup)

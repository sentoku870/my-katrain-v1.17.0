"""Quiz Manager (Phase 98).

Manages Quiz popup and session lifecycle.
Extracted from KaTrainGui for improved testability.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.core.eval_metrics import QuizItem
    from katrain.gui.features.context import FeatureContext
    from katrain.gui.managers.active_review_controller import ActiveReviewController


class QuizManager:
    """Quiz functionality manager (Phase 98).

    Responsibilities:
    - Quiz popup display
    - Quiz session start
    - Active Review coordination (disable when starting quiz)

    Design:
    - Import/instantiation: Kivy-free (unit testable)
    - UI execution requires Kivy (quiz_popup.py, quiz_session.py)
    - Dependency injection pattern (like ActiveReviewController)

    Kivy-free boundary:
    - Top-level imports: typing + TYPE_CHECKING only
    - Kivy/UI imports: local imports inside methods only
    """

    def __init__(
        self,
        get_ctx: Callable[[], FeatureContext],
        get_active_review_controller: Callable[[], ActiveReviewController | None],
        update_state_fn: Callable[[], None],
        logger: Callable[[str, int], None],
    ) -> None:
        """Initialize with dependency injection.

        Args:
            get_ctx: Returns FeatureContext (KaTrainGui instance)
            get_active_review_controller: Returns ActiveReviewController or None
            update_state_fn: UI state update callback (redraw_board=True)
            logger: Logging callback (logger(message, level) format)
        """
        self._get_ctx = get_ctx
        self._get_active_review_controller = get_active_review_controller
        self._update_state_fn = update_state_fn
        self._logger = logger

    def do_quiz_popup(self) -> None:
        """Show quiz selection popup. Requires Kivy."""
        from katrain.gui.features.quiz_popup import do_quiz_popup as _do_quiz_popup

        _do_quiz_popup(
            self._get_ctx(),
            self.start_quiz_session,
            self._update_state_fn,
        )

    def start_quiz_session(self, quiz_items: list[QuizItem]) -> None:
        """Start quiz session. Disables Active Review if active.

        Args:
            quiz_items: List of QuizItem to include in the session

        Active Review coordination:
        - If controller exists: calls disable_if_needed()
        - If controller is None: logs warning, quiz continues
        - disable_if_needed() is idempotent (safe to call multiple times)
        """
        # Disable Active Review (robust implementation)
        controller = self._get_active_review_controller()
        if controller is not None:
            try:
                controller.disable_if_needed()
            except Exception as e:
                self._logger(f"Warning: Failed to disable Active Review: {e}", 1)
                # Quiz continues
        else:
            self._logger("Active Review controller not available, skipping disable", 0)

        # Start session (local import)
        from katrain.gui.features.quiz_session import (
            start_quiz_session as _start_quiz_session,
        )

        _start_quiz_session(
            self._get_ctx(),
            quiz_items,
            self.format_points_loss,
            self._update_state_fn,
        )

    def format_points_loss(self, loss: float | None) -> str:
        """Format points loss for display.

        Args:
            loss: Points lost value or None

        Returns:
            Formatted string for display
        """
        from katrain.gui.features.quiz_popup import (
            format_points_loss as _format_points_loss,
        )

        return _format_points_loss(loss)

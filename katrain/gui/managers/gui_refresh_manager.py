"""GUI refresh manager (Phase 158+: extracted from KaTrainGui).

Phase 158+: Manages GUI-wide refresh operations that were previously
inline in ``KaTrainGui``:

- ``update_gui(cn, redraw_board)`` - refresh prisoners, board, timer
- ``log(message, level)`` - log + status update
- ``_on_engine_status(event_type, message)`` - engine status string mapping
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class GUIRefreshManager:
    """Centralizes full-GUI refresh operations.

    These operations used to be split across ``KaTrainGui.update_gui`` and
    the base class ``log``. They're gathered here so the GUI class stays
    thin and the refresh logic is testable.
    """

    def __init__(
        self,
        *,
        get_game: Callable[[], Any],
        get_board_gui: Callable[[], Any],
        get_board_controls: Callable[[], Any],
        get_controls: Callable[[], Any],
        get_gui: Callable[[], Any],  # for BadukPanControls.update_controls(gui)
        # Optional status setter for engine events / error display
        set_status: Callable[[str, int], None] | None = None,
    ) -> None:
        self._get_game = get_game
        self._get_board_gui = get_board_gui
        self._get_board_controls = get_board_controls
        self._get_controls = get_controls
        self._get_gui = get_gui
        self._set_status = set_status

    def update_gui(self, cn: Any, redraw_board: bool = False) -> None:
        """Full GUI refresh: prisoners, board, timer, move tree.

        Equivalent to ``KaTrainGui.update_gui``.
        """
        game = self._get_game()
        if not game:
            return

        # Delegate to BadukPanControls for prisoners + next player display
        board_controls = self._get_board_controls()
        if board_controls:
            board_controls.update_controls(self._get_gui())

        # Redraw board (full) and contents (stones/hints)
        board_gui = self._get_board_gui()
        if board_gui:
            if redraw_board:
                board_gui.draw_board()
            board_gui.redraw_board_contents_trigger()

        controls = self._get_controls()
        if controls:
            controls.update_evaluation()
            controls.update_timer(1)
            if game:
                controls.move_tree.current_node = game.current_node

    def update_status_for_error(self, message: str, level: int) -> None:  # type: ignore[type-arg]
        """Update the status bar if the log line is an error.

        Called by ``KaTrainGui.log`` AFTER it has forwarded the message to
        ``super().log()``. Errors and KataGo stderr lines that contain
        'error' trigger a status bar update.
        """
        from katrain.core.constants import OUTPUT_ERROR, OUTPUT_KATAGO_STDERR, STATUS_ERROR

        if self._set_status is None:
            return
        if (
            level == OUTPUT_ERROR
            or (level == OUTPUT_KATAGO_STDERR and "error" in message.lower() and "tuning" not in message.lower())
        ):
            self._set_status(f"ERROR: {message}", STATUS_ERROR)  # type: ignore[arg-type]

    def on_engine_status(self, event_type: str, message: str) -> None:
        """Map engine status events to user-facing status messages."""
        from katrain.core.constants import STATUS_INFO

        if self._set_status is None:
            return
        if event_type == "starting":
            self._set_status("KataGo engine starting...", STATUS_INFO)  # type: ignore[arg-type]
        elif event_type == "tuning":
            self._set_status(
                f"KataGo is tuning settings for first startup, please wait.{message}", STATUS_INFO  # type: ignore[arg-type]
            )
        elif event_type == "ready":
            self._set_status("KataGo engine ready.", STATUS_INFO)  # type: ignore[arg-type]

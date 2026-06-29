"""Scroll handler manager (Phase 158+: extracted from KaTrainGui).

Phase 158+: Handles mouse scroll events on the board/control area. Was
previously inline in ``KaTrainGui.on_touch_up`` (~20 lines).

The handler distinguishes three behaviors:

1. Scroll while PV is animating -> adjust PV animation index
2. Scroll while board/control is touched -> move forward/back (undo/redo)
3. Otherwise -> defer to Kivy's default touch handling
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ScrollHandler:
    """Mouse scroll dispatcher for the board area.

    The original ``on_touch_up`` differentiates between:
    - ``is_mouse_scrolling`` events (mouse wheel)
    - touches that happen to land on the board vs. the controls panel
    - whether the PV animation is currently active
    """

    def __init__(
        self,
        *,
        get_board_gui: Callable[[], Any],
        get_board_controls: Callable[[], Any],
        get_controls: Callable[[], Any],
        action_dispatcher: Callable[[str], None],
    ) -> None:
        self._get_board_gui = get_board_gui
        self._get_board_controls = get_board_controls
        self._get_controls = get_controls
        self._action_dispatcher = action_dispatcher

    def handle_touch_up(self, touch: Any) -> bool:
        """Return True to consume the event, False to let Kivy handle it."""
        if not touch.is_mouse_scrolling:
            return False  # not our concern

        board_gui = self._get_board_gui()
        board_controls = self._get_board_controls()
        controls = self._get_controls()

        touching_board = bool(
            board_gui and board_gui.collide_point(*touch.pos)
        ) or bool(
            board_controls and board_controls.collide_point(*touch.pos)
        )
        touching_control_nonscroll = bool(
            controls
            and controls.collide_point(*touch.pos)
            and not controls.notes_panel.collide_point(*touch.pos)
        )

        # Scroll while PV is animating -> adjust animation index
        if board_gui and board_gui.animating_pv is not None and touching_board:
            if touch.button == "scrollup":
                board_gui.adjust_animate_pv_index(1)
            elif touch.button == "scrolldown":
                board_gui.adjust_animate_pv_index(-1)
            return True

        # Otherwise scroll through moves (undo/redo)
        if touching_board or touching_control_nonscroll:
            if touch.button == "scrollup":
                self._action_dispatcher("redo")
            elif touch.button == "scrolldown":
                self._action_dispatcher("undo")
            return True

        return False

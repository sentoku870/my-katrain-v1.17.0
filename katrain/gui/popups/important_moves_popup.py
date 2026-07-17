"""Phase 248-γ-D1: Kivy-side re-export shim for the important-moves popup.

The Kivy-free core lives in
:mod:`katrain.core.analysis.important_moves_popup` so it can be
unit-tested without triggering Kivy's window-init. This module
re-exports the public names so ``from katrain.gui.popups.important_moves_popup
import ...`` keeps working for the future popup widget.

The actual ``I18NPopup`` widget implementation is tracked in
``docs/archive/specs-planned/phase248-important-moves-popup.md``
and will land in a follow-up phase.
"""

from __future__ import annotations

# Phase 248-γ-D1: re-export from the Kivy-free core so test code can
# import either path. Once the actual Kivy widget lands, this
# module will host the ``I18NPopup`` subclass.
from katrain.core.analysis.important_moves_popup import (
    get_important_moves_for_game,
    show_important_moves_popup,
)

__all__ = [
    "get_important_moves_for_game",
    "show_important_moves_popup",
]

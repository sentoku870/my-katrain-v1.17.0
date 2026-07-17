"""Phase 248-γ-D1: Important-moves list popup (Kivy-free core logic).

This module provides the *Kivy-free* core for the important-moves
popup. It lives under :mod:`katrain.core.analysis` so tests can
import it without triggering Kivy's window-init code path; the
Kivy popup widget itself is in
:mod:`katrain.gui.popups.important_moves_popup` (re-export shim).

The full implementation is tracked in
``docs/archive/specs-planned/phase248-important-moves-popup.md``
and will land in a follow-up phase.

Public surface:
- :func:`show_important_moves_popup` — entry point; pure-logic
  side returns ``None`` until the GUI widget is wired up.
- :func:`get_important_moves_for_game` — pure helper that collects
  the critical_3 candidates for both players (used by the
  popup and by tests).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from katrain.core.analysis import (
    DEFAULT_IMPORTANT_MOVE_LEVEL,
    select_critical_moves,
)
from katrain.core.constants import (
    DEFAULT_CRITICAL_3_MAX_MOVES,
    OUTPUT_DEBUG,
)

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui
    from katrain.core.analysis import CriticalMove

_log = logging.getLogger(__name__)


# Phase 248-γ-D1: the upper bound for the popup's "show all" mode.
# (The user-configurable ``critical_3_max_moves`` clamps the per-player
# list; the popup itself shows all available candidates up to this
# internal ceiling so a user can still jump to a less-important move
# via the scrollable list.)
_POPUP_INTERNAL_MAX_MOVES = 10


def get_important_moves_for_game(
    game: Any,
    *,
    level: str = DEFAULT_IMPORTANT_MOVE_LEVEL,
    max_moves: int = DEFAULT_CRITICAL_3_MAX_MOVES,
) -> dict[str, list[CriticalMove]]:
    """Collect the critical_3 candidates for both players of a game.

    Pure function: no GUI side effects. The popup uses this to populate
    the list view, and tests use it to verify the popup's data source.

    Args:
        game: The ``Game`` object (duck-typed to avoid circular import).
        level: Important-moves level (Phase 248-B1: easy/normal/strict).
        max_moves: How many critical moves to collect per player
            (Phase 248-B2: 1-10, default 3).

    Returns:
        A dict ``{"black": [...], "white": [...]}`` of
        :class:`~katrain.core.analysis.CriticalMove` instances,
        sorted by ``critical_score`` descending. The list may be
        shorter than ``max_moves`` if the candidate pool is empty.
    """
    if game is None:
        return {"black": [], "white": []}

    result: dict[str, list[CriticalMove]] = {"black": [], "white": []}
    for player in ("B", "W"):
        try:
            moves = select_critical_moves(
                game,
                max_moves=max_moves,
                lang="ja",
                level=level,
                player_filter=player,
            )
            result["black" if player == "B" else "white"] = list(moves)
        except Exception as exc:  # noqa: BLE001 — broad to keep the popup alive
            _log.log(
                OUTPUT_DEBUG,
                "get_important_moves_for_game: player=%s, level=%s failed: %s",
                player,
                level,
                exc,
            )
            # Leave the list empty for this player; the popup will
            # still render the other player's moves.
    return result


def show_important_moves_popup(
    katrain: KaTrainGui,
    *,
    level: str = DEFAULT_IMPORTANT_MOVE_LEVEL,
    max_moves: int = DEFAULT_CRITICAL_3_MAX_MOVES,
) -> None:
    """Open the important-moves list popup for the current game.

    Phase 248-γ-D1 SKELETON: the function is defined and returns
    ``None`` but the actual Kivy popup widget is not yet wired up.
    See ``docs/archive/specs-planned/phase248-important-moves-popup.md``
    for the design and TODO list.

    Args:
        katrain: The :class:`KaTrainGui` instance (entry point).
        level: Important-moves level (easy/normal/strict).
        max_moves: Number of moves per player to show (1-10).
    """
    if katrain is None or getattr(katrain, "game", None) is None:
        _log.warning("show_important_moves_popup: no active game")
        return

    moves = get_important_moves_for_game(
        katrain.game,
        level=level,
        max_moves=max_moves,
    )
    total = sum(len(v) for v in moves.values())
    _log.info(
        "Important-moves popup: %d moves (B=%d, W=%d) at level=%s, max=%d",
        total,
        len(moves["black"]),
        len(moves["white"]),
        level,
        max_moves,
    )

    # TODO(γ-D1 follow-up): instantiate the Kivy popup widget here.
    # The widget is expected to:
    # 1. Render a scrollable list of moves (black + white) with
    #    move number, player, loss, and meaning-tag label.
    # 2. Highlight moves flagged ``complexity_discounted``.
    # 3. Provide a "Jump to this move" button that calls
    #    ``katrain.game.set_current_node(node)`` and refreshes the
    #    board view.
    # 4. Provide "Copy" + "Close" buttons (clipboard + dismiss).
    # 5. Be re-runnable (re-opening the popup refreshes the data
    #    rather than stacking copies).
    return None


__all__ = [
    "get_important_moves_for_game",
    "show_important_moves_popup",
]

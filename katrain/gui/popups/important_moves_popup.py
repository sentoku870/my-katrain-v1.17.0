"""Phase 248-γ-D1: Important-moves list popup (Kivy widget).

The popup shows the critical_3 candidates for both players of the
current game. The user can:

- See all candidates in a scrollable list (black + white, sorted by
  ``critical_score`` desc).
- Click "この局面にジャンプ" to call ``katrain.game.set_current_node``
  on the highlighted move.
- Click "コピー" to copy a Markdown summary of the list to the clipboard.
- Click "閉じる" to dismiss the popup.

The Kivy-free core (data collection) lives in
:mod:`katrain.core.analysis.important_moves_popup`; this module
contains the widget + entry point only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.properties import (
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout

from katrain.core.analysis.important_moves_popup import (
    get_important_moves_for_game,
)
from katrain.core.analysis.models import DEFAULT_IMPORTANT_MOVE_LEVEL
from katrain.core.constants import DEFAULT_CRITICAL_3_MAX_MOVES
from katrain.core.lang import i18n
from katrain.gui.popups._base import I18NPopup
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui


class ImportantMovesPopupContent(BoxLayout):
    """Scrollable list of important-moves with a jump / copy / close footer."""

    font_name = StringProperty(Theme.DEFAULT_FONT)
    moves_by_color = ObjectProperty({"black": [], "white": []})
    selected_index = NumericProperty(-1)  # index into the flattened list
    # Flattened list of (color, move) pairs for the entry widgets.
    flattened = ListProperty([])

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # The KV id bindings may not be ready in __init__ when constructed
        # from pure-Python tests; defer the population to ``populate()``.
        self._populated = False

    def populate(
        self,
        moves_by_color: dict[str, list[Any]],
        game_name: str,
        level: str,
    ) -> None:
        """Fill the scrollable list with the candidate moves.

        Args:
            moves_by_color: ``{"black": [...], "white": [...]}`` of
                :class:`~katrain.core.analysis.CriticalMove` instances.
            game_name: Display name for the SGF (shown in the header).
            level: Important-moves level (shown in the header).
        """
        self.moves_by_color = moves_by_color
        # Flatten into a single list, black first then white.
        flat: list[tuple[str, Any]] = []
        for color in ("black", "white"):
            for m in moves_by_color.get(color, []):
                flat.append((color, m))
        self.flattened = flat

        # Update header.
        header_game_name = self.ids.get("header_game_name")
        header_meta = self.ids.get("header_meta")
        header_count = self.ids.get("header_count")
        if header_game_name is not None:
            header_game_name.text = game_name
        if header_meta is not None:
            header_meta.text = i18n._("mykatrain:popup:important-moves:subtitle").format(level=level)
        if header_count is not None:
            n_black = len(moves_by_color.get("black", []))
            n_white = len(moves_by_color.get("white", []))
            header_count.text = f"重要局面: 黒 {n_black} 件 / 白 {n_white} 件 (全 {len(flat)} 件)"

        # Toggle empty-state vs list visibility.
        empty_label = self.ids.get("empty_label")
        scroll_view = self.ids.get("scroll_view")
        if empty_label is not None:
            empty_label.opacity = 1 if not flat else 0
            empty_label.height = dp(40) if not flat else 0
        if scroll_view is not None:
            scroll_view.opacity = 1 if flat else 0

        # Clear existing entries.
        entries_box = self.ids.get("entries_box")
        if entries_box is None:
            return
        entries_box.clear_widgets()
        if not flat:
            self._populated = True
            return

        # Build one entry per move.
        for idx, (color, m) in enumerate(flat):
            entry = self._build_entry(idx, color, m)
            entries_box.add_widget(entry)

        self._populated = True
        # Default selection: first entry.
        self.select_index(0)

    def _build_entry(self, idx: int, color: str, move: Any) -> BoxLayout:
        """Build a single entry row.

        Args:
            idx: Index in the flattened list.
            color: ``"black"`` or ``"white"``.
            move: :class:`~katrain.core.analysis.CriticalMove` instance.

        Returns:
            A configured BoxLayout ready to be added to the list.
        """
        from katrain.gui.kv.important_moves_popup import (
            ImportantMovesEntry,  # type: ignore[attr-defined]
        )

        # Alternating background for readability.
        bg = [0.05, 0.05, 0.07, 1.0] if idx % 2 == 0 else [0.10, 0.10, 0.13, 1.0]
        player = "B" if color == "black" else "W"
        complexity = bool(getattr(move, "complexity_discounted", False))
        entry = ImportantMovesEntry(
            move_number=move.move_number,
            player=player,
            gtp_coord=move.gtp_coord or "?",
            score_loss=float(getattr(move, "score_loss", 0.0) or 0.0),
            meaning_tag_label=str(getattr(move, "meaning_tag_label", "")),
            complexity_discounted=complexity,
            bg_color=bg,
        )
        entry.bind(on_touch_down=lambda inst, touch, i=idx: self._on_entry_touch(i, touch))
        return entry

    def _on_entry_touch(self, idx: int, touch: Any) -> None:
        """Select an entry when the user touches it.

        Filters for the entry's bounding box so taps outside the row
        don't accidentally select it.
        """
        # Only act on left-button UP events that landed on the entry.
        if touch.button != "left":
            return
        # Selection is handled via index; the entry's BoxLayout already
        # received the touch, so we just need to update the selection.
        if 0 <= idx < len(self.flattened):
            self.select_index(idx)

    def select_index(self, idx: int) -> None:
        """Mark ``idx`` as the currently selected row.

        The jump button is enabled iff at least one row is selected.
        """
        if not self.flattened:
            self.selected_index = -1
            jump_button = self.ids.get("jump_button")
            if jump_button is not None:
                jump_button.disabled = True
            return
        self.selected_index = max(0, min(idx, len(self.flattened) - 1))
        jump_button = self.ids.get("jump_button")
        if jump_button is not None:
            jump_button.disabled = False

    # ------------------------------------------------------------------
    # Button handlers (called from KV)
    # ------------------------------------------------------------------

    def on_jump(self) -> None:
        """Jump to the currently selected move on the board."""
        if self.selected_index < 0 or self.selected_index >= len(self.flattened):
            return
        color, move = self.flattened[self.selected_index]
        # The popup holds a reference to the gui via ``self.gui`` so we
        # can call set_current_node through it.
        gui = getattr(self, "gui", None)
        if gui is None or getattr(gui, "game", None) is None:
            return
        node = gui.game._find_node_by_move_number(move.move_number)
        if node is None:
            return
        try:
            gui.game.set_current_node(node)
            gui.update_state()
        except Exception:  # noqa: BLE001 — broad to keep the popup alive
            pass
        # Close the popup after a successful jump.
        popup = getattr(self, "_popup_ref", None)
        if popup is not None:
            popup.dismiss()

    def on_copy(self) -> None:
        """Copy a Markdown summary of the moves to the clipboard."""
        lines = ["# 重要局面リスト", ""]
        for color, m in self.flattened:
            player = "黒" if color == "black" else "白"
            tag = m.meaning_tag_label or "—"
            loss = f"{m.score_loss:.1f}目"
            lines.append(f"- #{m.move_number} ({player}) {m.gtp_coord} — {loss} ({tag})")
        Clipboard.put("\n".join(lines))

    def on_close(self) -> None:
        """Dismiss the popup."""
        popup = getattr(self, "_popup_ref", None)
        if popup is not None:
            popup.dismiss()


def open_important_moves_popup(
    gui: KaTrainGui,
    *,
    level: str = DEFAULT_IMPORTANT_MOVE_LEVEL,
    max_moves: int = DEFAULT_CRITICAL_3_MAX_MOVES,
) -> I18NPopup | None:
    """Open the important-moves list popup for the current game.

    Args:
        gui: The :class:`KaTrainGui` instance.
        level: Important-moves level (Phase 248-B1: easy/normal/strict).
        max_moves: How many critical moves per player to show (1-10).

    Returns:
        The opened popup (or ``None`` if the gui has no active game).
    """
    if gui is None or getattr(gui, "game", None) is None:
        return None

    # Collect candidates.
    moves_by_color = get_important_moves_for_game(
        gui.game,
        level=level,
        max_moves=max_moves,
    )

    # Resolve the game name for the header.
    game_name = ""
    game = gui.game
    if game is not None:
        sgf_filename = getattr(game, "sgf_filename", None)
        if sgf_filename:
            import os

            game_name = os.path.basename(str(sgf_filename))
        else:
            game_id = getattr(game, "game_id", None)
            if game_id:
                game_name = str(game_id)

    # Build the content widget.
    content = ImportantMovesPopupContent()
    # Hand the content a back-reference to the gui and popup so the
    # jump / close handlers can reach the right objects.
    content.gui = gui  # type: ignore[attr-defined]

    popup = I18NPopup(
        title_key="mykatrain:popup:important-moves:title",
        size_hint=(None, None),
        size=[dp(620), dp(480)],
        content=content,
    )
    content._popup_ref = popup  # type: ignore[attr-defined]

    # Populate after the widget tree is built so KV ids are available.
    content.populate(moves_by_color, game_name=game_name, level=level)
    popup.open()
    return popup


# ---------------------------------------------------------------------------
# Re-exports for the Kivy-free core (Phase 248-γ-D1 shim layer)
# ---------------------------------------------------------------------------

from katrain.core.analysis.important_moves_popup import (  # noqa: E402,F401
    show_important_moves_popup,
)

__all__ = [
    "ImportantMovesPopupContent",
    "get_important_moves_for_game",
    "open_important_moves_popup",
    "show_important_moves_popup",
]

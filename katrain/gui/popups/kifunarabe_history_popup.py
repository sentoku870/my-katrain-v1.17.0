"""Phase 249-β: history popup for kifunarabe (棋譜並べ) sessions.

Lists the most-recent entries from :class:`KifunarabeHistoryStore` so
the user can revisit past results. The popup is read-only in this
Phase — editing / deleting entries can be a follow-up.
"""

from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING, Any

from kivy.metrics import dp
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

from katrain.gui.popups._base import I18NPopup

if TYPE_CHECKING:
    from katrain.core.study.kifunarabe_history import KifunarabeHistoryStore


#: How many entries to show in the popup. A scrollview handles overflow
#: but we still cap to keep the initial render cheap.
_MAX_ENTRIES = 50


def _format_entry_line(entry: Any) -> str:
    """Render a single entry as a single multi-line string.

    Layout:
        2026-07-18 09:30:14   D4
        total 38, correct 30, wrong 6, auto 2, skip 0
        correct rate 83.3%   critical_3 2/3 (66.7%)
    """
    s = entry.summary or {}
    total = s.get("total_positions", 0)
    correct = s.get("correct_count", 0)
    wrong = s.get("wrong_count", 0)
    auto = s.get("auto_advance_count", 0)
    skipped = s.get("skipped_count", 0)
    attempted = correct + wrong
    correct_rate = (correct / attempted * 100.0) if attempted else 0.0

    crit_total = s.get("critical_3_total", 0)
    crit_correct = s.get("critical_3_correct", 0)
    crit_rate = (crit_correct / crit_total * 100.0) if crit_total else 0.0
    crit_text = f"   critical_3 {crit_correct}/{crit_total} ({crit_rate:.1f}%)" if crit_total else ""

    sgf_name = ""
    if entry.sgf_path:
        sgf_name = os.path.basename(entry.sgf_path)

    return (
        f"{entry.timestamp}   {sgf_name}\n"
        f"  total {total}, correct {correct}, wrong {wrong}, auto {auto}, skip {skipped}\n"
        f"  correct rate {correct_rate:.1f}%{crit_text}"
    )


def show_kifunarabe_history(
    ctx: Any,
    history_store: "KifunarabeHistoryStore | None",
) -> None:
    """Display the kifunarabe history popup.

    Args:
        ctx: KaTrainGui instance (used for the close action).
        history_store: The store to read from. ``None`` shows an
            "history not configured" message.
    """
    from kivy.uix.label import Label

    from katrain.core.lang import i18n
    from katrain.gui.theme import Theme
    from katrain.gui.widgets.factory import Button

    if history_store is None:
        body_text = i18n._("kifunarabe:history:not_configured")
    else:
        entries = history_store.list_entries(limit=_MAX_ENTRIES)
        if not entries:
            body_text = i18n._("kifunarabe:history:empty")
        else:
            body_text = "\n\n".join(_format_entry_line(e) for e in entries)

    content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))

    headline = Label(
        text=i18n._("kifunarabe:history:title"),
        size_hint_y=None,
        height=dp(36),
        halign="center",
        valign="middle",
        bold=True,
        font_name=Theme.DEFAULT_FONT,
    )
    headline.bind(size=lambda _w, _s: setattr(headline, "text_size", headline.size))
    content.add_widget(headline)

    body = Label(
        text=body_text,
        size_hint_y=None,
        halign="left",
        valign="top",
        font_name=Theme.DEFAULT_FONT,
    )
    body.bind(size=lambda _w, _s: setattr(body, "text_size", body.size))
    # Make the body grow with its text.
    body.bind(texture_size=lambda _lbl, tex: setattr(_lbl, "height", tex[1]))
    # Wrap the body in a ScrollView so a long history stays usable.
    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, bar_width=dp(8))
    scroll.add_widget(body)
    content.add_widget(scroll)

    close_btn = Button(
        text=i18n._("kifunarabe:history:close"),
        size_hint_y=None,
        height=dp(40),
        font_name=Theme.DEFAULT_FONT,
    )
    close_btn.bind(on_release=lambda _b: _close_popup(content))
    content.add_widget(close_btn)

    popup = I18NPopup(
        title_key="kifunarabe:history:title",
        size=[dp(560), dp(540)],
        content=content,
    ).__self__
    popup.size_hint = (None, None)
    popup.pos_hint = {"center_x": 0.5, "center_y": 0.5}
    # Stash for the close button.
    content.popup = popup  # type: ignore[attr-defined]
    popup.open()


def _close_popup(content: Any) -> None:
    popup = getattr(content, "popup", None)
    if popup is not None:
        with contextlib.suppress(Exception):
            popup.dismiss()

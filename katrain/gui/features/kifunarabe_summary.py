"""Summary popup for Kifunarabe (棋譜並べ) sessions.

Displays the final tally (correct / wrong / auto-advance / skipped) when a
session ends, whether explicitly by the user, by reaching the end of the
mainline, or by hitting the configured ``max_moves`` cap.

Phase 177-G: provides two follow-up actions after the summary:
- "Next game" — reopen the kifunarabe SGF selector so the user can study
  another record without leaving kifunarabe mode.
- "Abort Kifu Narabe" — end kifunarabe mode entirely (returns to normal
  KataGo analysis). The mode property is preserved until the user picks
  this option.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from kivy.metrics import dp
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout

from katrain.gui.popups._base import I18NPopup

if TYPE_CHECKING:
    from katrain.core.study.kifunarabe import KifunarabeSummary


class KifunarabeSummaryContent(BoxLayout):
    """Body widget of the kifunarabe summary popup (Phase 177-G)."""

    popup = ObjectProperty(None)
    katrain = ObjectProperty(None)
    controller = ObjectProperty(None)

    def __init__(
        self,
        summary: KifunarabeSummary,
        katrain: Any = None,
        controller: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.summary = summary
        self.katrain = katrain
        self.controller = controller

    def on_next_sgf(self) -> None:
        """User picks 'Next game': reopen the SGF selector."""
        if self.popup is not None:
            self.popup.dismiss()
        if self.katrain is None:
            return
        from kivy.clock import Clock

        from katrain.gui.popups.kifunarabe_setup_popup import (
            open_kifunarabe_sgf_selector,
        )

        # Defer so this popup fully dismisses before the next one opens.
        Clock.schedule_once(
            lambda _dt: open_kifunarabe_sgf_selector(self.katrain),
            0.05,
        )

    def on_abort(self) -> None:
        """User picks 'Abort Kifu Narabe': end kifunarabe cleanly."""
        if self.popup is not None:
            self.popup.dismiss()
        if self.controller is not None:
            self.controller.abort_session()

    def on_ok(self) -> None:
        """Legacy OK button: behaves like abort."""
        self.on_abort()

    def on_show_history(self) -> None:
        """Phase 249-β: open the persistent history popup.

        The history store is read from the controller (which received
        it via DI in ``__main__.py``). If the controller is missing
        or has no store wired up, the history popup shows its
        "not configured" message.
        """
        if self.popup is not None:
            self.popup.dismiss()
        if self.controller is None:
            return
        from kivy.clock import Clock

        from katrain.gui.popups.kifunarabe_history_popup import (
            show_kifunarabe_history,
        )

        # Defer so this popup fully dismisses before the next one opens.
        Clock.schedule_once(
            lambda _dt: show_kifunarabe_history(self.katrain, self._get_history_store()),
            0.05,
        )

    def on_show_important_moves(self) -> None:
        """Phase 250: 重要局面リスト popup は廃止。

        棋譜並べサマリーから「重要局面を表示」ボタンを押した時の挙動は
        4 ボタン (黒前/黒次/白前/白次) で代替できるため、何もしない。
        Kept as a stub for back-compat with KV bindings — silent no-op.
        """
        if self.popup is not None:
            self.popup.dismiss()
        # Phase 250: no-op (重要局面リスト popup 廃止)

    def _get_history_store(self) -> Any:
        """Phase 249-β: resolve the history store from the controller.

        The controller stores the store in ``_history_store``; we
        access it through a public read so tests can swap the store
        without poking at private attributes.
        """
        if self.controller is None:
            return None
        return getattr(self.controller, "_history_store", None)


def _format_rate(value: float) -> str:
    """Return ``"75.0%"`` for ``75.0`` (one decimal place)."""
    return f"{value:.1f}%"


def show_kifunarabe_summary(
    ctx: Any,
    summary: KifunarabeSummary,
    on_popup_opened: Any = None,
) -> None:
    """Display the kifunarabe summary popup.

    Args:
        ctx: KaTrainGui instance (used to look up the controller and to
            re-open the SGF selector after the user picks 'Next game').
        summary: :class:`KifunarabeSummary` with the session totals.
        on_popup_opened: Phase 181-B. Optional callable invoked with the
            ``popup`` instance right after ``popup.open()``. The controller
            uses this to track the popup for later dismissal from the
            panel "Abort" button. Exceptions raised by the callback are
            swallowed so a tracking bug never blocks the UI.
    """
    from kivy.uix.label import Label

    from katrain.core.lang import i18n
    from katrain.gui.theme import Theme
    from katrain.gui.widgets.factory import Button

    controller = getattr(ctx, "_kifunarabe_controller", None)

    content = KifunarabeSummaryContent(
        summary=summary,
        katrain=ctx,
        controller=controller,
        orientation="vertical",
        spacing=dp(8),
        padding=dp(10),
    )

    # Headline: total positions vs correct guesses
    headline = Label(
        text=i18n._("kifunarabe:summary:headline").format(
            correct=summary.correct_count,
            total=summary.total_positions,
            attempted=summary.attempted_count,
        ),
        size_hint_y=None,
        height=dp(44),
        halign="center",
        valign="middle",
        bold=True,
        font_name=Theme.DEFAULT_FONT,
    )
    headline.bind(size=lambda _w, _s: setattr(headline, "text_size", headline.size))
    content.add_widget(headline)

    # Body: tall enough for two lines plus the helper note (``limit_reached``)
    # plus the button row, so the text never visually collides with the
    # button row at the bottom. (Phase 177-I.)
    body_height = dp(180) + (dp(28) if summary.max_moves_reached else 0)

    # Body: tally + rates
    correct_rate = _format_rate(summary.correct_rate)
    wrong_rate = _format_rate(summary.wrong_rate)

    body_text = i18n._("kifunarabe:summary:body").format(
        correct=summary.correct_count,
        wrong=summary.wrong_count,
        auto=summary.auto_advance_count,
        skipped=summary.skipped_count,
        correct_rate=correct_rate,
        wrong_rate=wrong_rate,
    )
    # Phase 249-β: also surface the "overall rate" (treats auto-advance
    # as correct) so the user can disambiguate the two percentages.
    # Without this, a 30%(correct_rate) vs 60%(overall_rate) gap is
    # confusing when many of the 50 positions were auto-advanced.
    if summary.total_positions > 0:
        overall_rate = _format_rate(summary.overall_rate)
        body_text += "\n" + i18n._("kifunarabe:summary:overall_rate").format(
            overall_rate=overall_rate,
        )
    # Phase 179-B2: append Critical 3 hit-rate line when a Critical 3 set
    # was supplied to the session. We never show 0/0 because the user
    # would see "0.0% / 0" which is just confusing.
    if summary.critical_3_total > 0:
        crit_text = i18n._("kifunarabe:summary:critical3").format(
            correct=summary.critical_3_correct,
            total=summary.critical_3_total,
            rate=_format_rate(summary.critical_3_hit_rate),
        )
        body_text += "\n" + crit_text
    body = Label(
        text=body_text,
        size_hint_y=None,
        height=body_height,
        halign="center",
        valign="top",
        font_name=Theme.DEFAULT_FONT,
    )
    body.bind(size=lambda _w, _s: setattr(body, "text_size", body.size))
    content.add_widget(body)

    # Optional: max_moves notice
    if summary.max_moves_reached:
        cap_label = Label(
            text=i18n._("kifunarabe:summary:limit_reached"),
            size_hint_y=None,
            height=dp(28),
            halign="center",
            valign="middle",
            italic=True,
            font_name=Theme.DEFAULT_FONT,
        )
        cap_label.bind(size=lambda _w, _s: setattr(cap_label, "text_size", cap_label.size))
        content.add_widget(cap_label)

    # Phase 177-G: action row with three buttons, side-by-side.
    # Phase 249-β: added a "History" button that opens the persistent
    # history popup. The history store is resolved through the
    # controller (which received it via DI in __main__.py).
    # Phase 249-γ: added an "Important moves" button that opens the
    # Phase 248-γ-D1 list popup so the user can jump to any of the
    # Critical 3 positions from the session.
    # Phase 290-B: each button now gets ``size_hint_x=1`` and the row
    # uses ``dp(4)`` spacing so the 4 buttons share equal width inside
    # a 480dp popup — the previous dp(8) + 440dp combo clipped the
    # Japanese "中断して棋譜並べ終了" label. The label has also been
    # shortened to "中断して終了" (and "Abort" in English) so each
    # button has comfortable headroom even on smaller screens.
    button_row = BoxLayout(
        orientation="horizontal",
        spacing=dp(4),
        size_hint_y=None,
        height=dp(40),
    )
    next_btn = Button(
        text=i18n._("kifunarabe:summary:next_sgf"),
        font_name=Theme.DEFAULT_FONT,
        size_hint_x=1,
    )
    next_btn.bind(on_release=lambda _b: content.on_next_sgf())
    history_btn = Button(
        text=i18n._("kifunarabe:summary:history"),
        font_name=Theme.DEFAULT_FONT,
        size_hint_x=1,
    )
    history_btn.bind(on_release=lambda _b: content.on_show_history())
    important_btn = Button(
        text=i18n._("kifunarabe:summary:important_moves"),
        font_name=Theme.DEFAULT_FONT,
        size_hint_x=1,
    )
    important_btn.bind(on_release=lambda _b: content.on_show_important_moves())
    abort_btn = Button(
        text=i18n._("kifunarabe:summary:abort"),
        font_name=Theme.DEFAULT_FONT,
        size_hint_x=1,
    )
    abort_btn.bind(on_release=lambda _b: content.on_abort())
    button_row.add_widget(next_btn)
    button_row.add_widget(history_btn)
    button_row.add_widget(important_btn)
    button_row.add_widget(abort_btn)
    content.add_widget(button_row)

    popup = I18NPopup(
        title_key="kifunarabe:summary:title",
        size=[dp(480), dp(420)],
        content=content,
    ).__self__
    popup.size_hint = (None, None)
    popup.pos_hint = {"center_x": 0.5, "center_y": 0.5}
    content.popup = popup
    popup.open()
    # Phase 181-B: notify the controller that the popup is now visible.
    # Used by the panel "Abort" button to dismiss it on a single click
    # even after the natural end has already cleared the session.
    if on_popup_opened is not None:
        with contextlib.suppress(Exception):
            on_popup_opened(popup)

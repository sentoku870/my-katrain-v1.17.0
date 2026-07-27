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

Phase 292-B: adds a "Replay" / "もう一度並べる" button that re-opens
the setup popup on the *same* SGF with the previous session's settings
pre-filled, replacing the now no-op "重要局面" button. The 4-button row
layout is preserved unchanged.
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

    def _brutal_close_summary(self) -> None:
        """Phase 292-B (rev3): multi-layer close of the current popup.

        Used by every button on this row (next_sgf / replay / abort /
        show_history) to guarantee the popup disappears, regardless of
        what Kivy's closing transition or modal-layer caching does
        behind the scenes. Order of operations, most-intrusive last:

        1. ``popup.dismiss()`` — standard Kivy dismissal.
        2. ``popup._window_dismiss()`` — bypasses the ``_is_open``
           short-circuit (the most common silent-no-op cause).
        3. ``parent.remove_widget(popup)`` — strips the widget from
           the modal window's children list.
        4. ``controller._summary_popup = None`` — clears the controller's
           sticky reference so subsequent ``_dismiss_summary_popup_if_open``
           calls are real no-ops rather than re-firing.

        Errors at every layer are swallowed because a failed close is
        always preferable to a crash mid-flow.
        """
        popup = self.popup
        if popup is None:
            return
        with contextlib.suppress(Exception):
            popup.dismiss()
        with contextlib.suppress(Exception):
            popup._window_dismiss()
        with contextlib.suppress(Exception):
            parent = getattr(popup, "parent", None)
            if parent is not None:
                parent.remove_widget(popup)
        with contextlib.suppress(Exception):
            if self.controller is not None:
                self.controller._summary_popup = None

    def on_next_sgf(self) -> None:
        """User picks 'Next game': reopen the SGF selector.

        Phase 292-B (Bug 1 + rev3 fix): triple-dismiss the OLD summary
        popup (standard ``dismiss()``, controller's tracker, and a
        direct ``parent.remove_widget``) before opening the SGF
        selector. The user reported that without this the OLD summary
        stayed visible after they selected a new SGF.
        """
        self._brutal_close_summary()
        if self.katrain is None:
            return
        from kivy.clock import Clock

        from katrain.gui.popups.kifunarabe_setup_popup import (
            open_kifunarabe_sgf_selector,
        )

        # 0.25s gives the Kivy closing transition AND the brutal
        # close (above) a comfortable buffer.
        Clock.schedule_once(
            lambda _dt: open_kifunarabe_sgf_selector(self.katrain),
            0.25,
        )

    def on_abort(self) -> None:
        """User picks 'Abort Kifu Narabe': end kifunarabe cleanly.

        Phase 292-B (Bug 1 + rev3 fix): same triple-dismiss as
        :meth:`on_replay` / :meth:`on_next_sgf`.

        Phase 292-B (Bug 2 fix): route through ``disable_if_needed``
        rather than ``abort_session``. ``abort_session`` opens a fresh
        summary popup, which the user perceived as "I have to press
        the button twice — the screen brightens and only on the second
        press does the popup actually disappear".

        The panel "Abort" button (``do_kifunarabe_abort`` →
        ``abort_session``) still shows the summary popup because the
        user opens it from outside the popup window.
        """
        self._brutal_close_summary()
        if self.controller is not None:
            self.controller.disable_if_needed()

    def on_ok(self) -> None:
        """Legacy OK button: behaves like abort."""
        self.on_abort()

    def on_show_history(self) -> None:
        """Phase 249-β: open the persistent history popup.

        The history store is read from the controller (which received
        it via DI in ``__main__.py``). If the controller is missing
        or has no store wired up, the history popup shows its
        "not configured" message.

        Phase 292-B (rev3): the OLD summary popup gets the
        multi-layer close treatment (``_brutal_close_summary``)
        because the original double-dismiss left the OLD popup
        visible long enough for the history popup to be obscured.
        """
        self._brutal_close_summary()
        if self.controller is None:
            return
        from kivy.clock import Clock

        from katrain.gui.popups.kifunarabe_history_popup import (
            show_kifunarabe_history,
        )

        Clock.schedule_once(
            lambda _dt: show_kifunarabe_history(self.katrain, self._get_history_store()),
            0.25,
        )

    def on_show_important_moves(self) -> None:
        """Phase 250 + Phase 292-B: 重要局面リスト popup は廃止。

        棋譜並べサマリーから「重要局面を表示」ボタンを押した時の挙動は
        4 ボタン (黒前/黒次/白前/白次) で代替できるため、何もしない。
        Kept as a stub for back-compat with KV bindings — silent no-op.

        Note: as of Phase 292-B, this slot is reused for the "Replay"
        handler (``on_replay``) in the button-row layout; callers that
        still bind this method continue to get the no-op behaviour.

        Phase 292-B (rev3): even this stub gets a brutal close —
        it costs nothing and keeps the row layout consistent.
        """
        self._brutal_close_summary()
        # Phase 250: no-op (重要局面リスト popup 廃止)

    def on_replay(self) -> None:
        """Phase 292-B: replay the same game record with new settings.

        Dismisses the summary popup, **rewinds the game state to the
        root of the SGF**, and re-opens the setup popup so the user
        can change conditions (turn / max_hints / max_moves) before
        starting a new session on the *same* SGF.

        Phase 292-B (rev3): the dismissal is escalated to a
        multi-layer attack. The original double-dismiss
        (``self.popup.dismiss()`` + ``controller._dismiss_summary_popup_if_open()``)
        still runs as the first line of defence, followed by a
        scheduled brutal-close pass after 0.05s. The second pass
        actually removes the widget from its parent using
        ``parent.remove_widget`` and clears the controller's sticky
        ``_summary_popup`` reference. This is necessary because
        several users still report the OLD summary window staying
        visible after clicking 開始 even though both standard
        dismissal calls fire — the widget tree appears to keep a
        stale modal layer reference.

        The setup popup is scheduled with a 0.25s delay so BOTH
        the Kivy closing transition AND the brutal-close pass have
        a comfortable buffer before the new widget is opened.
        """
        last_config: Any = None
        if self.controller is not None:
            last_config = getattr(self.controller, "_last_config", None)

        # 1. Standard dismissal via the content-bound widget.
        if self.popup is not None:
            with contextlib.suppress(Exception):
                self.popup.dismiss()
        # 2. Standard dismissal via the controller's tracker.
        if self.controller is not None:
            with contextlib.suppress(Exception):
                self.controller._dismiss_summary_popup_if_open()

        # 3. Belt-and-braces: a SECOND cleanup pass scheduled after
        # 0.05s. If the standard ``dismiss()`` somehow leaves a stale
        # widget reference attached to the modal layer (Kivy's modal
        # layer caches ``self._window`` for every open Popup), this
        # pass forcibly strips the widget from its parent and clears
        # the controller's tracking. We deliberately run this from
        # the main Kivy clock so the widget tree mutations land on
        # the same thread as ``open_kifunarabe_setup_popup`` will run
        # on, avoiding a raced mutation.
        from kivy.clock import Clock

        def _brutal_close(_dt: float) -> None:
            popup = self.popup
            if popup is None:
                return
            with contextlib.suppress(Exception):
                popup.dismiss()
            with contextlib.suppress(Exception):
                popup._window_dismiss()
            with contextlib.suppress(Exception):
                parent = getattr(popup, "parent", None)
                if parent is not None:
                    parent.remove_widget(popup)
            with contextlib.suppress(Exception):
                if self.controller is not None:
                    self.controller._summary_popup = None

        Clock.schedule_once(_brutal_close, 0.05)

        # 4. Rewind the game state to root (visual confirmation +
        # safety net for the new session).
        if self.controller is not None:
            self._rewind_game_for_replay()

        if self.katrain is None:
            return

        from katrain.gui.popups.kifunarabe_setup_popup import (
            open_kifunarabe_setup_popup,
        )

        # 0.25s — covers both the Kivy closing transition (typical
        # ~150ms) and the brutal-close pass (0.05s + processing
        # margin) before the new popup opens.
        Clock.schedule_once(
            lambda _dt: open_kifunarabe_setup_popup(
                self.katrain,
                prefill_config=last_config,
            ),
            0.25,
        )

    def _rewind_game_for_replay(self) -> None:
        """Phase 292-B (rev2): rewind the game to ``game.root`` for
        replay. Used both by :meth:`on_replay` (visual reset before
        the setup popup opens) and as a defensive pre-emptive
        clean-up.

        Implementation: direct ``set_current_node(game.root)`` first
        because it is O(1). We then belt-and-braces call
        ``undo(10000)`` so that if some downstream mixin (e.g.
        InsertModeController) consumed the direct call or if a
        ``shortcut_from`` chain exists, the undo loop walks any
        remaining nodes. The inner ``undo`` loop breaks at ``root``
        so the bound is only a safety net for cyclic SGFs.

        On any failure (missing game, missing root, exceptions in
        kivy/insertion-mode paths) we silently swallow because the
        controller-side rewind in
        :meth:`KifunarabeSessionMixin._rewind_if_at_end_of_mainline`
        runs again at ``start_session`` time as a final fallback.
        """
        if self.controller is None:
            return
        game_getter = getattr(self.controller, "_get_game", None)
        ctx_getter = getattr(self.controller, "_get_ctx", None)
        if game_getter is None:
            return
        game = game_getter()
        if game is None:
            return
        root = getattr(game, "root", None)
        node = getattr(game, "current_node", None)
        if root is None:
            return
        if node is root:
            return  # already at root
        with contextlib.suppress(Exception):
            set_node = getattr(game, "set_current_node", None)
            if callable(set_node):
                set_node(root)
        with contextlib.suppress(Exception):
            undo = getattr(game, "undo", None)
            if callable(undo):
                undo(10000)
        # Refresh the board / engine state so the user sees the
        # empty board immediately when the setup popup opens.
        with contextlib.suppress(Exception):
            ctx = ctx_getter() if ctx_getter else None
            if ctx is not None and hasattr(ctx, "update_state"):
                ctx.update_state(redraw_board=True)

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
    # Phase 292-B: replaced the (now no-op) "重要局面" button with a
    # "もう一度並べる" / "Replay" button that re-opens the setup popup
    # on the same SGF with the previous session's settings pre-filled.
    # The 4-button layout (next_sgf / history / replay / abort) is
    # preserved so existing width-1 / spacing-dp(4) math still works.
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
    replay_btn = Button(
        text=i18n._("kifunarabe:summary:replay"),
        font_name=Theme.DEFAULT_FONT,
        size_hint_x=1,
    )
    replay_btn.bind(on_release=lambda _b: content.on_replay())
    abort_btn = Button(
        text=i18n._("kifunarabe:summary:abort"),
        font_name=Theme.DEFAULT_FONT,
        size_hint_x=1,
    )
    abort_btn.bind(on_release=lambda _b: content.on_abort())
    button_row.add_widget(next_btn)
    button_row.add_widget(history_btn)
    button_row.add_widget(replay_btn)
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

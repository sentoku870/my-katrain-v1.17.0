"""Kifunarabe Controller — Session lifecycle mixin.

Phase A3: extracted from the original 800-line KifunarabeController.
Owns the *when* of a session: start / end / abort / disable_if_needed /
finish_position / check_session_ended.

Cross-mixin attributes
----------------------

- ``_session`` (``KifunarabeSession | None``): the active session, or
  ``None`` when kifunarabe mode is off.
- ``_source_sgf_path`` (``str | None``): path of the SGF that started the
  most recent session (set/cleared by start_session / _end_session,
  used by sgf_manager exit paths).

This mixin assumes the facade satisfies ``_ControllerDeps`` and
``_SessionState`` (see :mod:`katrain.gui.managers.kifunarabe_state`).
"""

from contextlib import suppress
from typing import TYPE_CHECKING, Any

from katrain.core.study.kifunarabe import (
    get_critical_3_move_numbers,
)

if TYPE_CHECKING:
    from katrain.core.study.kifunarabe import KifunarabeSession


class KifunarabeSessionMixin:
    """Session lifecycle: start, end, abort, disable_if_needed.

    Helpers from other mixins (``_restore_analysis_toggles``,
    ``_dismiss_summary_popup_if_open``, ``_auto_advance_until_user_turn``,
    ``_apply_hint_toggle``, ``_schedule_redraw``) are resolved at runtime
    via the facade's MRO.
    """

    # Instance attributes managed by this mixin (declared as class
    # annotations so mypy can see the wider ``Optional`` types that
    # both the mixin and the facade manipulate). Quoted forward
    # references keep KifunarabeSession as a TYPE_CHECKING-only name.
    #
    # Phase 249-α: ``_source_sgf_path`` removed (no caller wrote to it).
    _session: "KifunarabeSession | None"
    _last_critical_3_highlight: int

    # -- public lifecycle entry points ---------------------------------------

    def disable_if_needed(self: Any) -> None:
        """Disable kifunarabe mode if currently active (no summary popup).

        Called when switching to PLAY mode, loading SGF, or other
        interrupting transitions.
        """
        # Phase 181-B: dismiss any visible summary popup first so the
        # user can always exit with one button press.
        self._dismiss_summary_popup_if_open()
        # Phase 177-H: put the saved toggle mask back where it was
        # before kifunarabe started.
        self._restore_analysis_toggles()
        self._end_session(show_summary=False)

    def start_session(self: Any, config: Any) -> None:
        """Start a new session with the given config and turn on the mode.

        Behaviour:
        - Clears any existing kifunarabe session first
          (``disable_if_needed``).
        - Phase 179-B1: fetches Critical 3 move numbers from the current
          game so the per-position highlight and summary hit-rate can
          use them.
        - Ensures the on-board ``Top Moves`` toggle reflects
          ``config.max_hints > 0``.
        - Schedules a board redraw on the main thread so the candidate
          markers appear without the user clicking the toggle manually.
        """
        from katrain.core.study.kifunarabe import KifunarabeSession

        # B3: clear any lingering session/state first.
        self.disable_if_needed()

        # Phase 179-B1: fetch the Critical 3 set (max 6 entries).
        critical_3: list[int] = []
        game_for_c3 = self._get_game()
        if game_for_c3 is not None:
            try:
                critical_3 = get_critical_3_move_numbers(game_for_c3)
            except Exception:
                critical_3 = []

        self._session = KifunarabeSession(
            config,
            critical_3_move_numbers=critical_3,
        )
        # Reset the highlight guard so each critical 3 position fires
        # its badge.
        self._last_critical_3_highlight = 0
        self._set_mode(True)

        # Phase 177-H: save then mask ``show_children`` / ``eval`` so
        # the actual move isn't visually revealed during this session.
        if self._is_auto_toggle_enabled():
            self._save_analysis_toggles()
            self._apply_kifu_toggle_mask()

        # A2: enable board "Top Moves" candidate markers if user asked
        # for them, and trigger a redraw so the markers actually render.
        self._apply_hint_toggle(max_hints=config.max_hints)
        self._schedule_redraw()

        # Belt-and-braces: even if ``analysis_controls`` wasn't ready
        # at the first schedule, retry on a slightly later main-thread
        # tick.
        from kivy.clock import Clock

        def _resync(_dt: float) -> None:
            self._apply_hint_toggle(max_hints=config.max_hints)
            self._schedule_redraw()

        Clock.schedule_once(_resync, 0.15)

        self._auto_advance_until_user_turn()

    def abort_session(self: Any) -> None:
        """User-requested abort of the kifunarabe session.

        Ends the session cleanly, shows the summary popup if there were
        results, and returns ``kifunarabe_mode`` to False.

        Phase 181-B: also dismisses any visible summary popup
        regardless of mode. Previously, after a natural session end
        (e.g. max_moves cap), the panel "Abort" button would call
        ``abort_session``, bail out at the ``if not self._get_mode():
        return`` guard, and leave the user staring at the popup. Now
        the popup is dismissed first so a single button press is enough
        to fully exit.
        """
        # Phase 181-B: dismiss any visible summary popup first. This
        # is a no-op when no popup is open, and runs even when mode is
        # already False.
        self._dismiss_summary_popup_if_open()
        if not self._get_mode():
            return
        summary_data: Any = None
        if self._session and self._session.results:
            summary_data = self._session.get_summary()
            with __import__("contextlib").suppress(Exception):
                self._get_show_summary()(self._get_ctx(), summary_data)
        # Phase 177-H: restore the user's ``show_children`` / ``eval``
        # toggles that were masked at session start.
        self._restore_analysis_toggles()
        self._session = None
        self._set_mode(False)

    def on_mode_change(self: Any, value: bool) -> None:
        """React to ``kifunarabe_mode`` property changes from the GUI.

        Note: Does NOT call ``_end_session`` (recursion guard).
        """
        if not value:
            # OFF: drop session; UI drove the change.
            self._session = None

    # -- internal helpers ----------------------------------------------------

    def _finish_position(self: Any, move_number: int) -> None:
        """End the session and show the summary popup (if results exist)."""
        if self._session is not None:
            self._session.record_skipped_no_move(move_number)
        self._end_session(show_summary=True)

    def _check_session_ended(self: Any) -> None:
        """If the session was finalised elsewhere, surface the summary popup.

        Used so ``handle_guess``'s end-of-mainline / max_moves-cap paths
        can show results without going through ``_end_session`` again.
        """
        if self._session is None:
            return
        if self._session.is_active:
            return
        # The session was already finalized elsewhere; just display.
        self._show_session_summary()

    def _end_session(self: Any, show_summary: bool) -> None:
        """End the session (internal).

        Args:
            show_summary: True to display summary popup if there were
                results.
        """
        if not self._get_mode():
            return
        summary_data: Any = None
        if show_summary and self._session and self._session.results:
            summary_data = self._session.get_summary()
            try:
                self._get_show_summary()(self._get_ctx(), summary_data)
            except Exception:
                self._logger("kifunarabe: show_summary callback raised", level=0)
        # Phase 177-H: every "end" path must put the user's analysis
        # toggles back where they were before kifunarabe started.
        self._restore_analysis_toggles()
        self._session = None
        self._set_mode(False)
        # Phase 249-α: ``_source_sgf_path = None`` removed (no caller
        # ever set the attribute, so there is nothing to clear).


__all__ = ["KifunarabeSessionMixin"]

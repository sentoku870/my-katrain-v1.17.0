"""Kifunarabe Controller — Session lifecycle mixin.

Phase A3: extracted from the original 800-line KifunarabeController.
Owns the *when* of a session: start / end / abort / disable_if_needed /
finish_position / check_session_ended.

Cross-mixin attributes
----------------------

- ``_session`` (``KifunarabeSession | None``): the active session, or
  ``None`` when kifunarabe mode is off.
- ``_last_critical_3_highlight`` (``int``): guard so the Critical 3
  badge fires at most once per position.
- ``_history_store`` (Phase 249-β, facade-injected): JSON-backed
  persistent history store.
- ``_weakness_exporter`` (Phase 249-γ, facade-injected): opt-in
  WRONG_GUESS exporter for Karte 連携.
"""

import contextlib
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
    # Phase 292-B: ``_last_config`` added — the previous-session
    # ``KifunarabeConfig`` snapshot, written just before ``_session``
    # is cleared on every exit path and read by the summary popup's
    # "Replay" handler so the re-opened setup popup can pre-fill the
    # turn / max_hints / max_moves fields.
    _session: "KifunarabeSession | None"
    _last_critical_3_highlight: int
    _last_config: Any

    # -- public lifecycle entry points ---------------------------------------

    def disable_if_needed(self: Any) -> None:
        """Disable kifunarabe mode if currently active (no summary popup).

        Called when switching to PLAY mode, loading SGF, or other
        interrupting transitions.

        Phase 292-B (Bug 2 fix): if kifunarabe was actively running
        (mode was True at entry), also rewind the game to ``game.root``
        so the board is left in a clean state. The mid-game cursor is
        only preserved when kifunarabe was already inactive — i.e.
        users navigating around their own SGF are not bothered.
        """
        # Phase 181-B: dismiss any visible summary popup first so
        # the user can always exit with one button press.
        self._dismiss_summary_popup_if_open()
        # Phase 177-H: put the saved toggle mask back where it was
        # before kifunarabe started.
        self._restore_analysis_toggles()
        was_active = self._get_mode()
        self._end_session(show_summary=False)
        # Bug 2 fix: when kifunarabe was actively running, leave
        # the board in the empty / root state so Analyze / Play /
        # もう一度並べる all start from a clean slate.
        if was_active:
            self._rewind_to_root()

    def start_session(self: Any, config: Any) -> None:
        """Start a new session with the given config and turn on the mode.

        Behaviour:
        - Clears any existing kifunarabe session first
          (``disable_if_needed``).
        - Phase 292-B (rev): if the game state is parked at the end
          of the SGF (``current_node`` has no ordered children),
          rewind to ``game.root`` so the new session has positions to
          play through. This happens whenever the *previous* session
          ran to its configured ``max_moves`` cap and is most visible
          in the "もう一度並べる" (Replay) flow.
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

        # Phase 292-B (rev): rewind game state to ``root`` when the
        # game is parked at the end of the mainline. We deliberately
        # limit the check to "current node has no ordered children"
        # so we do not disturb the user if they manually navigated
        # mid-game before starting a fresh session.
        self._rewind_if_at_end_of_mainline()

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

        # Belt-and-braces: even if ``analysis_controls`` wasn't ready
        # at the first schedule, retry on a slightly later main-thread
        # tick. The deferred redraw subsumes the immediate one above.
        from kivy.clock import Clock

        def _resync(_dt: float) -> None:
            self._apply_hint_toggle(max_hints=config.max_hints)
            self._schedule_redraw()

        Clock.schedule_once(_resync, 0.15)

        self._auto_advance_until_user_turn()

    def _rewind_if_at_end_of_mainline(self: Any) -> None:
        """Phase 292-B (rev): rewind ``game.current_node`` to ``game.root``
        when the current node has no ordered children (i.e. we are
        parked at the end of the SGF mainline).

        Why only-when-at-end? After the previous kifunarabe session
        ran to its ``max_moves`` cap the game cursor is parked on the
        final move of the mainline; without this guard
        ``_auto_advance_until_user_turn`` would immediately fire
        ``_finish_position`` and the user would see the summary popup
        re-appear without playing a single move. We avoid touching
        the cursor when the user navigated mid-game (``root`` has
        children and we are not at the very end) — that case is
        rare in practice but the asymmetry is intentional.

        Implementation: direct ``set_current_node(root)`` jumps in
        O(1) (via the public API, which honors ``InsertModeController``
        but only blocks when ``game.insert_mode`` is True — never the
        case here). As a belt-and-braces fallback we also call
        ``undo(10000)`` so any ``shortcut_from`` chains or downstream
        mixin overrides don't strand the cursor short of root.
        """
        # Phase 292-B (Bug 2 fix): _rewind_to_root is the unconditional
        # wrapper used by the "session just ended → reset board" paths.
        # This conditional helper is a narrower variant that only fires
        # when the cursor is parked at the SGF end; it intentionally
        # leaves mid-game cursors alone so the "Re-watch from current
        # position, but with new conditions" use case still works.
        self._maybe_rewind_to_root(require_at_end=True)

    def _rewind_to_root(self: Any) -> None:
        """Phase 292-B (Bug 2 fix): unconditionally rewind the game to
        ``game.root``. Used right after the kifunarabe session ends
        (abort or natural max_moves) so the board is left in the same
        clean state as a fresh app launch — Analyze/Play can resume
        from the empty board, and a subsequent ``Open SGF`` /
        ``もう一度並べる`` does not see ghosts of the kifunarabe game.

        Errors are swallowed because a failed rewind is always better
        than blocking the UI cleanup.
        """
        self._maybe_rewind_to_root(require_at_end=False)

    def _maybe_rewind_to_root(self: Any, *, require_at_end: bool) -> None:
        """Shared helper for the two rewind variants.

        When ``require_at_end`` is True the rewind only fires if
        ``current_node.ordered_children`` is empty (i.e. the cursor is
        parked at the SGF mainline end). When False it rewinds in all
        cases — used by the "session just ended" paths so the board
        always resets.

        The rewind itself uses the O(1) ``set_current_node(root)`` first
        and a defensive ``undo(10000)`` second so any ``shortcut_from``
        chains don't strand the cursor short of root.
        """
        game = self._get_game()
        if game is None:
            return
        node = getattr(game, "current_node", None)
        root = getattr(game, "root", None)
        if node is None or root is None:
            return
        if node is root:
            return
        if require_at_end:
            children = getattr(node, "ordered_children", None) or []
            if children:
                return  # mid-game: leave the cursor alone
        with contextlib.suppress(Exception):
            set_node = getattr(game, "set_current_node", None)
            if callable(set_node):
                set_node(root)
        with contextlib.suppress(Exception):
            undo = getattr(game, "undo", None)
            if callable(undo):
                undo(10000)
        # Force a board redraw so the user sees the empty board.
        with contextlib.suppress(Exception):
            ctx = self._get_ctx()
            if ctx is not None and hasattr(ctx, "update_state"):
                ctx.update_state(redraw_board=True)

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

        Phase 249-β / 249-γ: also write to the persistent history
        store and (opt-in) the weakness exporter, mirroring the
        natural end path so an aborted session still feeds the
        history and the Karte 連携 pipeline.

        Phase 292-B (Bug 2 fix): rewinds the game to ``game.root``
        after the session cleanup so the board is left in a clean
        state. The user no longer has to load a fresh SGF to discard
        the kifunarabe end-position; either a normal Analyze / Play
        session or a fresh ``Open SGF`` picker can be entered
        immediately without seeing the kifunarabe ghost stones.
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
            # Phase 249-β / 249-γ: persist before showing the popup
            # so a user who immediately clicks "Abort" still gets the
            # data on disk.
            self._persist_history(summary_data)
            with contextlib.suppress(Exception):
                self._get_show_summary()(self._get_ctx(), summary_data)
        # Phase 177-H: restore the user's ``show_children`` / ``eval``
        # toggles that were masked at session start.
        self._restore_analysis_toggles()
        # Phase 292-B: snapshot the config before clearing ``_session``
        # so the summary popup's "Replay" handler can pre-fill the
        # setup popup with the previous turn / max_hints / max_moves.
        if self._session is not None:
            self._last_config = self._session.config
        self._session = None
        self._set_mode(False)
        # Phase 292-B (Bug 2 fix): rewind the game to root. Done last
        # so ``mode = False`` is committed before the GUI redraws.
        self._rewind_to_root()

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
            # Phase 249-β: persist the finished session to the
            # history store (no-op when ``_history_store`` is None).
            self._persist_history(summary_data)
            try:
                self._get_show_summary()(self._get_ctx(), summary_data)
            except Exception:
                self._logger("kifunarabe: show_summary callback raised", level=0)
        # Phase 177-H: every "end" path must put the user's analysis
        # toggles back where they were before kifunarabe started.
        self._restore_analysis_toggles()
        # Phase 292-B: snapshot the config before clearing ``_session``
        # so the summary popup's "Replay" handler can pre-fill the
        # setup popup with the previous turn / max_hints / max_moves.
        if self._session is not None:
            self._last_config = self._session.config
        self._session = None
        self._set_mode(False)
        # Phase 292-B (Bug 2 fix): rewind to the SGF root when the
        # session ENDS (show_summary=True). The ``disable_if_needed``
        # path passes show_summary=False and is left untouched so
        # transitioning from one kifunarabe to the next (or just
        # backing out without finishing) keeps the user's manual
        # cursor position. The ``abort_session`` path is handled by
        # its own ``_rewind_to_root()`` call below.
        if show_summary:
            self._rewind_to_root()
        # Phase 249-α: ``_source_sgf_path = None`` removed (no caller
        # ever set the attribute, so there is nothing to clear).

    # -- Phase 249-β: persistent history / Phase 249-γ: weakness export ----

    def _persist_history(self: Any, summary_data: Any) -> None:
        """Phase 249-β: append the finished session to the history store,
        then (Phase 249-γ) optionally export the WRONG_GUESS results.

        Both writes are best-effort: any failure is logged at level 0
        and swallowed so a broken history file on disk can never block
        a session end. The store / exporter are resolved through the
        facade (injected in __init__).
        """
        if self._session is None:
            return
        # We need the source SGF path. ``game.current_node`` knows
        # the SGF via ``game.root.properties.get("SGFLocation", ...)``
        # but that is engine-specific; the controller already keeps
        # a snapshot through the game-tree.
        game = self._get_game()
        sgf_path: str | None = None
        if game is not None:
            try:
                root = game.root
                sgf_path = getattr(root, "sgf_path", None) or None
            except Exception:  # noqa: BLE001
                sgf_path = None

        # Phase 249-β: history store.
        store = getattr(self, "_history_store", None)
        if store is not None:
            try:
                store.append(
                    summary=summary_data,
                    config=self._session.config,
                    sgf_path=sgf_path,
                    critical_3_set=list(self._session.critical_3_set),
                )
            except Exception as e:  # noqa: BLE001
                with contextlib.suppress(Exception):
                    self._logger(f"kifunarabe: history append failed: {e}", level=0)

        # Phase 249-γ: opt-in weakness export.
        self._export_weaknesses(sgf_path)

    def _export_weaknesses(self: Any, sgf_path: str | None) -> None:
        """Phase 249-γ: opt-in export of WRONG_GUESS results.

        Best-effort: any failure is logged and swallowed so a broken
        export can never block the session end. The exporter is
        resolved through the facade (injected in __init__).
        """
        exporter = getattr(self, "_weakness_exporter", None)
        if exporter is None:
            return
        if self._session is None:
            return
        if not getattr(self._session.config, "auto_export_weaknesses", False):
            return
        try:
            path = exporter.export(self._session, sgf_path)
            if path is not None:
                with contextlib.suppress(Exception):
                    self._logger(f"kifunarabe: weaknesses exported to {path}", 0)
        except Exception as e:  # noqa: BLE001
            with contextlib.suppress(Exception):
                self._logger(f"kifunarabe: weakness export failed: {e}", level=0)


__all__ = ["KifunarabeSessionMixin"]

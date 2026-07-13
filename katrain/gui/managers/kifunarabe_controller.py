"""Kifunarabe (棋譜並べ) Controller.

Manages kifunarabe mode lifecycle and board-click interactions:

- ON: user clicks on the board; if click matches the recorded move, the engine
  plays it as the user's guess and advances; if not, nothing happens.
- With ``turn="B"|"W"``, the opposite side is auto-advanced by playing the
  recorded move automatically.
- The session ends either by reaching the end of the mainline tree or by an
  explicit abort.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from katrain.core.constants import (
    KIFUNARABE_AUTO_TOGGLE_MARKERS_DEFAULT,
    KIFUNARABE_AUTO_TOGGLE_MARKERS_KEY,
)
from katrain.core.study.kifunarabe import (
    get_critical_3_move_numbers,
)

if TYPE_CHECKING:
    from katrain.core.game import Game
    from katrain.core.study.kifunarabe import KifunarabeSession, KifunarabeSummary
    from katrain.gui.controlspanel import ControlsPanel


# Callback signatures (UI callbacks injected via DI for testability)
OnGuessResolvedFn = Callable[
    [Any, bool, str | None, str | None],
    None,
]
"""
Signature: ``on_guess_resolved(ctx, correct, expected_gtp, guessed_gtp)``.

Called after every click so the GUI can play a sound / show a status hint.
"""

ShowSummaryFn = Callable[[Any, "KifunarabeSummary"], None]
"""Signature: ``show_summary(ctx, summary)``. Called when the session ends with results."""


class KifunarabeController:
    """Controller for kifunarabe (棋譜並べ) mode.

    Responsibilities:
    - Session lifecycle (start, advance, end)
    - User guess evaluation via ``evaluate_guess``
    - Auto-advance the opponent's moves when ``turn="B"|"W"``
    - Drive ``game.play()`` for both user-guessed and auto-advanced moves
    - Coordinate summary popup on end

    Design:
    - Import/instantiation: Kivy-free (testable with mocks)
    - UI callbacks injected for testability
    - Dependency-injection pattern (mirrors ActiveReviewController)

    Lifecycle invariants:
    - session is None <=> mode is False
    - on_mode_change(True) creates a new session only if session is None
    - on_mode_change(False) clears the session without showing summary
    """

    def __init__(
        self,
        get_ctx: Callable[[], Any],
        get_config: Callable[..., Any],
        get_game: Callable[[], Game | None],
        get_controls: Callable[[], ControlsPanel | None],
        get_mode: Callable[[], bool],
        set_mode: Callable[[bool], None],
        logger: Callable[..., None],
        show_summary_fn: ShowSummaryFn | None = None,
        on_guess_resolved_fn: OnGuessResolvedFn | None = None,
    ) -> None:
        """Initialize with dependency injection.

        Args:
            get_ctx: Returns KaTrainGui instance (for UI callbacks).
            get_config: ``config(setting, default=None)`` accessor.
            get_game: Returns current Game or None.
            get_controls: Returns ControlsPanel or None.
            get_mode: Returns ``kifunarabe_mode`` value.
            set_mode: Sets ``kifunarabe_mode`` value.
            logger: ``log(message, level)`` function.
            show_summary_fn: UI callback for end-of-session summary.
            on_guess_resolved_fn: UI callback for guess resolution events.
        """
        self._get_ctx = get_ctx
        self._get_config = get_config
        self._get_game = get_game
        self._get_controls = get_controls
        self._get_mode = get_mode
        self._set_mode = set_mode
        self._logger = logger

        self._show_summary_fn = show_summary_fn
        self._on_guess_resolved_fn = on_guess_resolved_fn

        self._session: KifunarabeSession | None = None
        # Phase 181-B: tracks the currently-visible summary popup so the
        # panel "Abort" button can dismiss it even after the natural end
        # has already cleared ``_session`` and toggled mode off. Without
        # this, the user has to click the popup's own "abort" button to
        # dismiss it after a max_moves cap run.
        self._summary_popup: Any = None

    # -- accessors ------------------------------------------------------------

    @property
    def session(self) -> KifunarabeSession | None:
        """Current session, or None if mode is off."""
        return self._session

    def is_active(self) -> bool:
        """True iff the mode is currently on (UI-level state)."""
        return self._get_mode()

    def is_fog_active(self) -> bool:
        """KV compatibility shim - mirrors ActiveReviewController.

        Returns True if kifunarabe mode is ON.
        """
        return self._get_mode()

    # -- Phase 177-H: auto-toggle save / restore ---------------------------

    def _is_auto_toggle_enabled(self) -> bool:
        """Whether the user opted into automatic toggle masking for kifu.

        Reads ``kifunarabe/auto_toggle_markers`` from the gui config and
        defaults to True (Phase 177-H default behaviour).
        """
        ctx = self._get_ctx()
        if ctx is None:
            return True
        try:
            return bool(
                ctx.config(
                    KIFUNARABE_AUTO_TOGGLE_MARKERS_KEY,
                    KIFUNARABE_AUTO_TOGGLE_MARKERS_DEFAULT,
                )
            )
        except Exception:  # noqa: BLE001
            return KIFUNARABE_AUTO_TOGGLE_MARKERS_DEFAULT

    def _save_analysis_toggles(self) -> None:
        """Snapshot the user's ``show_children`` / ``eval`` flag state.

        Called by ``start_session`` *before* applying the mask so we can
        restore on every exit path (abort, end-of-mainline, SGF load).
        """
        ctx = self._get_ctx()
        ac = getattr(ctx, "analysis_controls", None) if ctx is not None else None
        if ac is None:
            self._saved_analysis_toggles = None
            return
        try:
            self._saved_analysis_toggles = (
                bool(ac.show_children.active),
                bool(ac.eval.active),
            )
        except Exception:  # noqa: BLE001
            self._saved_analysis_toggles = None

    def _apply_kifu_toggle_mask(self) -> None:
        """Force ``show_children`` / ``eval`` OFF so the actual move is
        not visually revealed during the kifunarabe session.
        """
        ctx = self._get_ctx()
        ac = getattr(ctx, "analysis_controls", None) if ctx is not None else None
        if ac is None:
            return
        with contextlib.suppress(Exception):
            ac.show_children.active = False
        with contextlib.suppress(Exception):
            ac.eval.active = False

    def _restore_analysis_toggles(self) -> None:
        """Restore the original ``show_children`` / ``eval`` flag state.

        Idempotent: a second call after the saved state has been cleared
        is a no-op.
        """
        saved = getattr(self, "_saved_analysis_toggles", None)
        if saved is None:
            return
        self._saved_analysis_toggles = None
        ctx = self._get_ctx()
        ac = getattr(ctx, "analysis_controls", None) if ctx is not None else None
        if ac is None:
            return
        show_children, eval_dot = saved
        with contextlib.suppress(Exception):
            ac.show_children.active = show_children
        with contextlib.suppress(Exception):
            ac.eval.active = eval_dot

    # -- callbacks ------------------------------------------------------------

    def _get_show_summary(self) -> ShowSummaryFn:
        """Get summary UI function (lazy import if not injected)."""
        if self._show_summary_fn is not None:
            return self._show_summary_fn

        # Phase 181-B: wrap the default impl so the controller can track
        # the popup instance for later dismissal from the panel button.
        def _tracked_show_summary(ctx: Any, summary: Any) -> None:
            from katrain.gui.features.kifunarabe_summary import (
                show_kifunarabe_summary as _impl,
            )

            _impl(
                ctx,
                summary,
                on_popup_opened=lambda p: setattr(self, "_summary_popup", p),
            )

        return _tracked_show_summary

    def _dismiss_summary_popup_if_open(self) -> None:
        """Phase 181-B: dismiss any visible summary popup and clear tracking.

        Called from ``abort_session`` so that a single panel-button press
        closes the popup regardless of whether the session is still
        active. Also called from ``disable_if_needed`` to keep the
        controller's state consistent.
        """
        popup = self._summary_popup
        if popup is None:
            return
        with contextlib.suppress(Exception):
            popup.dismiss()
        self._summary_popup = None

    def _get_on_guess_resolved(self) -> OnGuessResolvedFn:
        """Get guess-resolved UI function (lazy import if not injected)."""
        if self._on_guess_resolved_fn is not None:
            return self._on_guess_resolved_fn
        return _default_on_guess_resolved

    # -- lifecycle ------------------------------------------------------------

    def disable_if_needed(self) -> None:
        """Disable kifunarabe mode if currently active (no summary popup).

        Called when switching to PLAY mode, loading SGF, or other interrupting
        transitions.
        """
        # Phase 181-B: also dismiss any visible summary popup so the user
        # does not get stranded with a popup and no exit path.
        self._dismiss_summary_popup_if_open()
        # Phase 177-H: whenever the session is interrupted (SGF load,
        # mode switch, manual disable), the saved toggle mask must come
        # off so the user's analysis settings come back.
        self._restore_analysis_toggles()
        self._end_session(show_summary=False)

    def start_session(self, config: Any) -> None:
        """Start a new session with the given config and turn on the mode.

        Behaviour:
        - Clears any existing kifunarabe session first (``disable_if_needed``).
        - Phase 179-B1: fetches the Critical 3 move numbers from the current
          game and stores them on the new session so per-position
          highlights and the summary hit-rate can use them.
        - Ensures the on-board ``Top Moves`` (hints) toggle reflects
          ``config.max_hints > 0`` so candidates are visible on the board.
        - Schedules a board redraw on the main thread so the candidate
          markers appear without the user clicking the toggle manually.

        Args:
            config: A ``KifunarabeConfig`` instance.
        """
        from katrain.core.study.kifunarabe import KifunarabeSession

        # B3: clear any lingering session/state first. ``disable_if_needed``
        # restores any saved toggle state from a previous session.
        self.disable_if_needed()

        # Phase 179-B1: fetch the Critical 3 set (max 6 entries: B/W each 3).
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
        # Reset the highlight guard so each critical 3 position fires its badge.
        self._last_critical_3_highlight = 0
        self._set_mode(True)

        # Phase 177-H: save then mask ``show_children`` / ``eval`` so the
        # actual move isn't visually revealed during this session.
        if self._is_auto_toggle_enabled():
            self._save_analysis_toggles()
            self._apply_kifu_toggle_mask()

        # A2: enable board "Top Moves" candidate markers if user asked for
        # them, and trigger a redraw so the markers actually render.
        self._apply_hint_toggle(max_hints=config.max_hints)
        self._schedule_redraw()

        # Belt-and-braces: even if ``analysis_controls`` wasn't ready at the
        # first schedule, retry on a slightly later main-thread tick.
        from kivy.clock import Clock

        def _resync(_dt: float) -> None:
            self._apply_hint_toggle(max_hints=config.max_hints)
            self._schedule_redraw()

        Clock.schedule_once(_resync, 0.15)

        self._auto_advance_until_user_turn()

    def _apply_hint_toggle(self, max_hints: int) -> None:
        """Reflect ``max_hints`` in the existing analysis-controls toggle.

        The popup does not own the "Top Moves" toggle widget; the controller
        is the single point that decides whether candidate markers show.

        Args:
            max_hints: Number of hint markers requested (0 = no hints).
        """
        from kivy.clock import Clock

        # Kivy widget property writes must happen on the main thread.
        # The popup ``on_submit`` already runs on the main thread, but we
        # schedule defensively in case this is invoked from elsewhere.
        Clock.schedule_once(lambda _dt: self._do_apply_hint_toggle(max_hints), 0)

    def _do_apply_hint_toggle(self, max_hints: int) -> None:
        ctx = self._get_ctx()
        if ctx is None:
            return
        ac = getattr(ctx, "analysis_controls", None)
        if ac is None:
            # The KaTrainGui still hasn't finished wiring up the controls.
            # Retry shortly - the analysis_controls widget is created during
            # KV loading in ``build()`` which may not have completed yet.
            from kivy.clock import Clock

            Clock.schedule_once(lambda _dt: self._do_apply_hint_toggle(max_hints), 0.05)
            return

        # 1) Force the policy toggle's underlying checkbox to False. The
        #    ``panels.kv:435`` binding ``disabled: policy.checkbox.active``
        #    reads the *checkbox*, so we must write through that path.
        policy = getattr(ac, "policy", None)
        policy_checkbox = getattr(policy, "checkbox", None) if policy is not None else None
        if policy_checkbox is not None and getattr(policy_checkbox, "active", False):
            with contextlib.suppress(Exception):
                policy_checkbox.active = False

        # 2) Set the hints toggle to whatever the session asks for.
        hints = getattr(ac, "hints", None)
        if hints is None:
            with contextlib.suppress(Exception):
                self._logger("kifunarabe: analysis_controls.hints not found", level=0)
            return

        hints_checkbox = getattr(hints, "checkbox", None)
        target_active = max_hints > 0
        try:
            if hints_checkbox is not None:
                if bool(hints_checkbox.active) != target_active:
                    hints_checkbox.active = target_active
            else:
                # Fallback: ``AnalysisToggle.active`` setter is now in place
                if bool(hints.active) != target_active:
                    hints.active = target_active
        except Exception as e:  # noqa: BLE001
            with contextlib.suppress(Exception):
                self._logger(f"kifunarabe: failed to set hints={target_active}: {e}", level=0)

    def _schedule_redraw(self) -> None:
        """Trigger a board redraw on the main thread.

        Candidate markers become visible only after ``BadukPanWidget.redraw``
        runs (or its hover-contents trigger). We can't safely call draw
        routines off the main thread, so we schedule it.
        """
        ctx = self._get_ctx()
        board_gui = getattr(ctx, "board_gui", None) if ctx is not None else None
        if board_gui is None:
            return
        try:
            from kivy.clock import Clock

            Clock.schedule_once(lambda _dt: self._safe_redraw_board(ctx, board_gui), 0)
        except Exception:  # noqa: BLE001
            with contextlib.suppress(Exception):
                self._logger("kifunarabe: failed to schedule redraw", level=0)

    @staticmethod
    def _safe_redraw_board(ctx: Any, board_gui: Any) -> None:
        """Safely invoke BadukPanWidget redraw hooks from the main thread."""
        for name in ("redraw_hover_contents_trigger", "draw_board_contents", "redraw"):
            fn = getattr(board_gui, name, None)
            if not callable(fn):
                continue
            with contextlib.suppress(Exception):
                fn()
                return

    def on_mode_change(self, value: bool) -> None:
        """React to ``kifunarabe_mode`` property changes from the GUI.

        Note: Does NOT call ``_end_session`` (recursion guard).
        """
        if not value:
            # OFF: drop session; UI drove the change
            self._session = None

    # -- click handling -------------------------------------------------------

    def handle_guess(self, coords: tuple[int, int]) -> None:
        """Handle a board click from the user.

        Behaviour:
        - If mode is off or no game/no session: do nothing.
        - Call ``evaluate_guess`` against the current node.
        - If ``True``: record the result, play the move, advance.
        - If ``False``: record WRONG_GUESS (Phase 177-F), do NOT play,
          but still notify the UI so the click feels acknowledged.
        - If ``None``: end the session if the game is over.

        Args:
            coords: Click coordinates (col, row) zero-based.
        """
        from katrain.core.study.kifunarabe import evaluate_guess

        if not self._get_mode() or self._session is None:
            return

        game = self._get_game()
        if not game:
            return

        node = game.current_node
        move_number = node.move_number

        result = evaluate_guess(coords, node)
        if result is None:
            # No continuation: end of mainline
            self._finish_position(move_number)
            return

        if result:
            # User guessed correctly: play that move and advance
            self._play_guessed(coords, node)
            self._advance_after_user_turn()
        else:
            # Phase 177-F (fix): the click landed somewhere - either on a
            # marker that didn't match the actual move, or completely off
            # the marker set. Both count as a WRONG_GUESS so the summary
            # stats are accurate.
            self._record_wrong_guess(coords, node)
            # Spec: 間違えなら何も起こりません (no move played).
            self._notify_guess(coords, node, correct=False)

        # Phase 179-B1: if the user has just landed on a Critical 3
        # position, surface a small "Critical 3" badge popup.
        self._highlight_critical_3_if_reached(node)

        # Phase 177-G: surface the summary popup if the move cap or end of
        # mainline just closed the session. Mode property is preserved.
        self._check_session_ended()

    # -- Phase 179-B1: Critical 3 badge hook ----------------------------------

    def _highlight_critical_3_if_reached(self, node: Any) -> None:
        """Show a short Critical 3 toast when the user lands on a tracked node.

        Phase 179-B1: the session stores ``critical_3_set`` (Phase 179-B1)
        and a ``_last_critical_3_highlight`` move-number guard to ensure
        each position fires its badge at most once.
        """
        if self._session is None:
            return
        critical_3_set = getattr(self._session, "critical_3_set", None)
        if not critical_3_set:
            return
        move_number = getattr(node, "move_number", None)
        if not isinstance(move_number, int) or move_number not in critical_3_set:
            return
        if move_number == getattr(self, "_last_critical_3_highlight", None):
            return
        self._last_critical_3_highlight = move_number
        ctx = self._get_ctx()
        if ctx is None:
            return
        from kivy.clock import Clock

        from katrain.gui.popups.kifunarabe_critical3_popup import (
            show_critical_3_badge,
        )

        try:
            Clock.schedule_once(lambda _dt: show_critical_3_badge(ctx, move_number), 0)
        except Exception:
            self._logger("kifunarabe: failed to schedule critical_3 badge", level=0)

    def _record_wrong_guess(self, coords: tuple[int, int], node: Any) -> None:
        """Phase 177-F (fix): persist a non-matching click as WRONG_GUESS.

        Called from :meth:`handle_guess` when ``evaluate_guess`` returns
        ``False`` (the click landed somewhere that did not match the
        actual move - either on a wrong marker or off the marker set
        entirely). Recording this lets the summary popup report an
        accurate failure count.
        """
        from katrain.core.sgf_parser import Move

        if self._session is None:
            return
        expected_gtp = self._expected_gtp_from_node(node)
        self._session.record_guess(
            move_number=node.move_number,
            expected_gtp=expected_gtp,
            guessed_gtp=Move(coords, player=node.next_player).gtp(),
        )

    def _play_guessed(self, coords: tuple[int, int], node: Any) -> None:
        """Record a correct guess and play the move.

        Args:
            coords: User click coordinates.
            node: Current GameNode before playing.
        """
        from katrain.core.sgf_parser import Move

        assert self._session is not None  # guarded by handle_guess()
        expected_gtp = self._expected_gtp_from_node(node)
        self._session.record_guess(
            move_number=node.move_number,
            expected_gtp=expected_gtp,
            guessed_gtp=Move(coords, player=node.next_player).gtp(),
        )
        self._notify_guess(coords, node, correct=True)
        self._play_move(coords, node.next_player)

    def _advance_after_user_turn(self) -> None:
        """After the user's turn, auto-advance as required by config.

        Advances to the next user turn or ends the session if mainline ends.
        """
        self._auto_advance_until_user_turn()

    def _auto_advance_until_user_turn(self) -> None:
        """Auto-play opponent moves until it's the user's turn (or end)."""
        from katrain.core.study.kifunarabe import should_auto_advance

        if self._session is None or not self._session.is_active:
            self._check_session_ended()
            return
        game = self._get_game()
        if not game:
            return

        cfg = self._session.config
        while True:
            # Phase 177-G: stop the loop if the session was just ended
            # by ``_finalize_at_limit`` between iterations.
            if not self._session.is_active:
                self._check_session_ended()
                return
            node = game.current_node
            ordered = node.ordered_children
            if not ordered or not ordered[0].move:
                # End of mainline: finalize position
                self._finish_position(node.move_number)
                return

            next_player = node.next_player
            if not should_auto_advance(cfg, next_player):
                return

            # Auto-play: pick the recorded move
            child = ordered[0]
            child_move = child.move
            assert child_move is not None
            coords = child_move.coords
            player = child_move.player

            assert self._session is not None  # guard set by handle_guess
            self._session.record_auto_advance(node.move_number)
            self._play_move(coords, player)

    def _finish_position(self, move_number: int) -> None:
        """End the session and show the summary popup (if results exist)."""
        if self._session is not None:
            self._session.record_skipped_no_move(move_number)
        self._end_session(show_summary=True)

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _expected_gtp_from_node(node: Any) -> str | None:
        """Return the GTP coord of the mainline child of ``node``, or None."""
        ordered = node.ordered_children
        if not ordered:
            return None
        child = ordered[0]
        child_move = getattr(child, "move", None)
        if child_move is None:
            return None
        gtp = getattr(child_move, "gtp", None)
        if callable(gtp):
            result = gtp()
            return result if isinstance(result, str) else None
        return None

    def _play_move(self, coords: tuple[int, int] | None, player: str) -> None:
        """Invoke ``game.play(Move(...))`` without triggering analysis.

        We pass ``analyze=False`` to keep engine load light while the user is
        clicking. The candidate-marker display in Phase 2 only relies on
        already-present analysis.

        Args:
            coords: Move coordinates (None for pass).
            player: "B" or "W".
        """
        from katrain.core.game import IllegalMoveException
        from katrain.core.sgf_parser import Move

        game = self._get_game()
        if not game:
            return
        try:
            game.play(Move(coords, player=player))
            ctx = self._get_ctx()
            if hasattr(ctx, "update_state"):
                ctx.update_state(redraw_board=True)
        except IllegalMoveException as e:
            self._logger(f"kifunarabe: illegal move ({coords}, {player}): {e}", level=0)

    def _notify_guess(
        self,
        coords: tuple[int, int],
        node: Any,
        correct: bool,
    ) -> None:
        """Notify the UI that a guess was resolved."""
        expected = self._expected_gtp_from_node(node)
        guessed = node_move_gtp(coords, node.next_player)
        cb = self._get_on_guess_resolved()
        try:
            cb(self._get_ctx(), correct, expected, guessed)
        except Exception:
            # UI callback failures must not crash the session
            self._logger("kifunarabe: on_guess_resolved callback raised", level=0)

    def _end_session(self, show_summary: bool) -> None:
        """End the session (internal).

        Args:
            show_summary: True to display summary popup if there were results.
        """
        if not self._get_mode():
            return
        summary_data: KifunarabeSummary | None = None
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
        # Phase 181-B: clear the source path so the next session does
        # not accidentally inherit a stale value.
        self._source_sgf_path = None

    # Phase 177-G: split the previous "end session + mode off" path into
    # two so the max_moves-cap flow can show the summary popup while
    # leaving the kifunarabe mode intact for the user to choose the
    # next step ("Next SGF" or "Abort").

    def _show_session_summary(self) -> None:
        """Show the summary popup without changing the kifunarabe mode.

        Called when the session ended (e.g. via ``_finalize_at_limit``).
        The mode property remains True so the user can pick another SGF
        from the summary popup.
        """
        if self._session is None or self._session.results is None:
            return
        if not self._session.results:
            return
        with contextlib.suppress(Exception):
            summary = self._session.get_summary()
            self._get_show_summary()(self._get_ctx(), summary)

    def _check_session_ended(self) -> None:
        """If ``KifunarabeSession.end()`` was invoked (max_moves reached or
        end of mainline auto-advanced through ``_finish_position``),
        surface the summary popup while keeping the mode intact.
        """
        if self._session is None:
            return
        if self._session.is_active:
            return
        # The session was already finalized elsewhere; just display.
        self._show_session_summary()

    def abort_session(self) -> None:
        """User-requested abort of the kifunarabe session.

        Ends the session cleanly, shows the summary popup if there were
        results, and returns ``kifunarabe_mode`` to False.

        Phase 181-B: also dismisses any visible summary popup regardless
        of mode. Previously, after a natural session end (e.g. max_moves
        cap), the panel "Abort" button would call ``abort_session``,
        bail out at the ``if not self._get_mode(): return`` guard, and
        leave the user staring at the popup. Now the popup is dismissed
        first so a single button press is enough to fully exit.
        """
        # Phase 181-B: dismiss any visible summary popup first. This is
        # a no-op when no popup is open, and runs even when mode is
        # already False (which is the common case after a natural end).
        self._dismiss_summary_popup_if_open()
        if not self._get_mode():
            return
        summary_data: KifunarabeSummary | None = None
        if self._session and self._session.results:
            summary_data = self._session.get_summary()
            with contextlib.suppress(Exception):
                self._get_show_summary()(self._get_ctx(), summary_data)
        # Phase 177-H: restore the user's ``show_children`` / ``eval``
        # toggles that were masked at session start.
        self._restore_analysis_toggles()
        self._session = None
        self._set_mode(False)


def disable_kifunarabe_if_active(katrain: Any) -> None:
    """Phase 178: centralised helper to disable kifunarabe from any exit path.

    Looks up the kifunarabe controller on ``katrain`` and calls
    ``disable_if_needed()``. Errors are swallowed because this helper
    is used from "cleanup" call sites (regular SGF load, future
    popup-manager dismissals, save-game-as-after-kifunarabe, etc.)
    where a kifunarabe failure must never block the main flow.

    Callers should use this function instead of repeating the
    ``getattr(katrain, "_kifunarabe_controller", None)`` lookup + nested
    ``if`` + try/except dance.
    """
    controller = getattr(katrain, "_kifunarabe_controller", None)
    if controller is None:
        return
    with contextlib.suppress(Exception):
        controller.disable_if_needed()


def node_move_gtp(coords: tuple[int, int], player: str) -> str | None:
    """Return the GTP representation of a (coords, player) click.

    Args:
        coords: Board coordinates (col, row) zero-based.
        player: "B" or "W".

    Returns:
        GTP coordinate string (``"D4"``) or "pass" for None coords.
    """
    from katrain.core.sgf_parser import Move

    if coords is None:
        return "pass"
    return Move(coords, player=player).gtp()


def _default_on_guess_resolved(
    ctx: Any,
    correct: bool,
    expected_gtp: str | None,
    guessed_gtp: str | None,
) -> None:
    """Default guess-resolved callback (plays a stone sound on correct)."""
    import contextlib

    if correct and hasattr(ctx, "_play_stone_sound"):
        with contextlib.suppress(Exception):
            ctx._play_stone_sound()

"""Kifunarabe Controller — Guess progression mixin.

Phase A3: extracted from the original 800-line KifunarabeController.
Owns the *what-happens-on-click* logic: evaluating a click, recording a
correct or wrong guess, advancing the opponent's moves, and surfacing
the Critical 3 badge.

Cross-mixin attributes
----------------------

- ``_session`` (read): the active kifunarabe session, ``None`` when
  mode is off.
- ``_last_critical_3_highlight``: int set/checked by the Critical 3
  highlight guard.

Helper methods from other mixins (``_save_*`` from the toggle mixin,
``_record_*`` methods on the session, ``_play_move``, ``_notify_guess``,
``_finish_position``, ``_check_session_ended``, ``_highlight_critical_3``
if/when it splits) are resolved via the facade's MRO.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core.study.kifunarabe import should_auto_advance

if TYPE_CHECKING:
    pass


class KifunarabeGuessMixin:
    """Guess progression: ``handle_guess`` and supporting helpers."""

    def handle_guess(self: Any, coords: tuple[int, int]) -> None:
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
            # No continuation: end of mainline.
            self._finish_position(move_number)
            return

        if result:
            # User guessed correctly: play that move and advance.
            self._play_guessed(coords, node)
            self._advance_after_user_turn()
        else:
            # Phase 177-F (fix): the click landed somewhere - either
            # on a marker that didn't match the actual move, or
            # completely off the marker set. Both count as a
            # WRONG_GUESS so the summary stats are accurate.
            self._record_wrong_guess(coords, node)
            # Spec: 間違えなら何も起こりません (no move played).
            self._notify_guess(coords, node, correct=False)

        # Phase 179-B1: if the user has just landed on a Critical 3
        # position, surface a small "Critical 3" badge popup.
        self._highlight_critical_3_if_reached(node)

        # Phase 177-G: surface the summary popup if the move cap or
        # end of mainline just closed the session. Mode property is
        # preserved.
        self._check_session_ended()

    # -- guess outcome helpers -----------------------------------------------

    def _record_wrong_guess(self: Any, coords: tuple[int, int], node: Any) -> None:
        """Phase 177-F (fix): persist a non-matching click as WRONG_GUESS.

        Called when ``evaluate_guess`` returns ``False``. Recording this
        lets the summary popup report an accurate failure count.

        Phase 249-α: uses the consolidated core helper
        ``_expected_move_gtp`` instead of the local
        ``_expected_gtp_from_node`` (removed). The two implementations
        are equivalent after the hardening in :func:`_expected_move_gtp`.
        """
        from katrain.core.sgf_parser import Move
        from katrain.core.study.kifunarabe import _expected_move_gtp

        if self._session is None:
            return
        expected_gtp = _expected_move_gtp(node)
        self._session.record_guess(
            move_number=node.move_number,
            expected_gtp=expected_gtp,
            guessed_gtp=Move(coords, player=node.next_player).gtp(),
        )

    def _play_guessed(self: Any, coords: tuple[int, int], node: Any) -> None:
        """Record a correct guess and play the move.

        Args:
            coords: User click coordinates.
            node: Current GameNode before playing.

        Phase 249-α: delegates expected-GTP resolution to the core
        helper ``_expected_move_gtp`` (single source of truth).
        """
        from katrain.core.sgf_parser import Move
        from katrain.core.study.kifunarabe import _expected_move_gtp

        assert self._session is not None  # guarded by handle_guess()
        expected_gtp = _expected_move_gtp(node)
        self._session.record_guess(
            move_number=node.move_number,
            expected_gtp=expected_gtp,
            guessed_gtp=Move(coords, player=node.next_player).gtp(),
        )
        self._notify_guess(coords, node, correct=True)
        self._play_move(coords, node.next_player)

    def _advance_after_user_turn(self: Any) -> None:
        """After the user's turn, auto-advance as required by config.

        Advances to the next user turn or ends the session if the
        mainline ends.
        """
        self._auto_advance_until_user_turn()

    def _auto_advance_until_user_turn(self: Any) -> None:
        """Auto-play opponent moves until it's the user's turn (or end)."""
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
                # End of mainline: finalize position.
                self._finish_position(node.move_number)
                return

            next_player = node.next_player
            if not should_auto_advance(cfg, next_player):
                return

            # Auto-play: pick the recorded move.
            child = ordered[0]
            child_move = child.move
            assert child_move is not None
            coords = child_move.coords
            player = child_move.player

            assert self._session is not None  # guard set by handle_guess
            self._session.record_auto_advance(node.move_number)
            self._play_move(coords, player)

    # -- internal helpers -----------------------------------------------------

    # Phase 249-α: ``_expected_gtp_from_node`` removed. Use
    # :func:`katrain.core.study.kifunarabe._expected_move_gtp` instead.
    # The two implementations are now consolidated; the core helper
    # has been hardened to swallow malformed GTP returns.

    def _play_move(self: Any, coords: tuple[int, int] | None, player: str) -> None:
        """Invoke ``game.play(Move(...))`` without triggering analysis.

        We pass ``analyze=False`` to keep engine load light while the
        user is clicking. The candidate-marker display in Phase 2 only
        relies on already-present analysis.

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

    def _notify_guess(self: Any, coords: tuple[int, int], node: Any, correct: bool) -> None:
        """Notify the UI that a guess was resolved.

        Phase 249-α: expected-GTP resolution delegates to the core
        helper ``_expected_move_gtp``.
        """
        from katrain.core.study.kifunarabe import _expected_move_gtp

        expected = _expected_move_gtp(node)
        # Lazy import to avoid kivy / module-level coupling: the helper
        # ``node_move_gtp`` lives in the facade module.
        from katrain.gui.managers.kifunarabe_controller import node_move_gtp

        guessed = node_move_gtp(coords, node.next_player)
        cb = self._get_on_guess_resolved()
        try:
            cb(self._get_ctx(), correct, expected, guessed)
        except Exception:
            # UI callback failures must not crash the session.
            self._logger("kifunarabe: on_guess_resolved callback raised", level=0)

    # -- Phase 179-B1: Critical 3 badge hook --------------------------------

    def _highlight_critical_3_if_reached(self: Any, node: Any) -> None:
        """Show a short Critical 3 toast when the user lands on a tracked node.

        Phase 179-B1: the session stores ``critical_3_set`` and a
        ``_last_critical_3_highlight`` move-number guard to ensure each
        position fires its badge at most once.
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


__all__ = ["KifunarabeGuessMixin"]

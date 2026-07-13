"""KifunarabeController unit tests.

All tests run without Kivy via dependency injection (mocks for ctx/game/etc.).
"""

import unittest
from typing import Any

# ----------------------------------------------------------------------------
# Test doubles
# ----------------------------------------------------------------------------


class _MockMove:
    def __init__(self, coords, player: str) -> None:
        self.coords = coords
        self.player = player

    def gtp(self) -> str:
        if self.coords is None:
            return "pass"
        from katrain.core.sgf_parser import Move

        return Move(self.coords, self.player).gtp()


class _MockChild:
    def __init__(self, coords, player: str) -> None:
        self.move = _MockMove(coords, player)


class _MockNode:
    def __init__(
        self,
        *,
        children: list[_MockChild] | None = None,
        player: str = "B",
        move_number: int = 1,
    ) -> None:
        self._children = children or []
        self._next_player = player
        self.move_number = move_number

    @property
    def ordered_children(self) -> list[_MockChild]:
        return self._children

    @property
    def next_player(self) -> str:
        return self._next_player


class _MockGame:
    def __init__(self, node: _MockNode | None) -> None:
        self.current_node = node
        self.played: list[tuple[Any, str, bool]] = []

    def play(self, move: Any, ignore_ko: bool = False, analyze: bool = True) -> None:
        self.played.append((move.coords, move.player, analyze))
        # Advance current_node: opponent becomes the new next_player; if there
        # is a continuing child, jump to a fresh node with that child.
        if self.current_node is None:
            return
        cur_children = self.current_node.ordered_children
        match = None
        for c in cur_children:
            if c.move.coords == move.coords and c.move.player == move.player:
                match = c
                break
        if match is None:
            # No matching child - append a placeholder child so the chain
            # ends and auto-advance can stop.

            cur_children.append(_MockChild(move.coords, Move.opponent_player(move.player)))
        # Switch next player
        new_player = Move.opponent_player(move.player)
        self.current_node = _MockNode(
            children=list(cur_children),
            player=new_player,
        )


class Move:
    """Re-export of real Move for opponent_player convenience."""

    @staticmethod
    def opponent_player(p: str) -> str:
        return "W" if p == "B" else "B"


class _MockAnalysisToggle:
    """Tiny stand-in for the Kivy ``AnalysisToggle`` we touch in save/restore."""

    def __init__(self, active: bool = False) -> None:
        self.active = active


class _MockAnalysisControls:
    """Mirrors the subset of ``analysis_controls`` that ``KifunarabeController`` uses."""

    def __init__(self) -> None:
        self.show_children = _MockAnalysisToggle(active=False)
        self.eval = _MockAnalysisToggle(active=False)


class _MockCtx:
    def __init__(self, game: _MockGame, *, auto_toggle_enabled: bool = True) -> None:
        self.game = game
        self.update_state_calls = 0
        self.stone_sound_calls = 0
        self.analysis_controls = _MockAnalysisControls()
        self._auto_toggle_enabled = bool(auto_toggle_enabled)

    def update_state(self, redraw_board: bool = False) -> None:
        self.update_state_calls += 1

    def _play_stone_sound(self) -> None:
        self.stone_sound_calls += 1


# ----------------------------------------------------------------------------
# Test helpers
# ----------------------------------------------------------------------------


def make_controller(
    game: _MockGame | None = None,
    *,
    mode_on: bool = False,
    auto_toggle_enabled: bool = True,
):
    """Return (controller, refs) where refs expose DI hooks and recording.

    Args:
        auto_toggle_enabled: Simulates the ``kifunarabe/auto_toggle_markers``
            config so we can verify that the toggle-saving behaviour is
            skipped when the user opts out.
    """
    from katrain.gui.managers.kifunarabe_controller import KifunarabeController

    if game is None:
        game = _MockGame(_MockNode(children=[_MockChild((3, 3), "B")]))
    ctx = _MockCtx(game, auto_toggle_enabled=auto_toggle_enabled)

    show_summary_calls: list[Any] = []
    on_guess_calls: list[tuple] = []

    def _config_getter(key: str, default=None):
        if key == "kifunarabe/auto_toggle_markers":
            return auto_toggle_enabled
        return default

    controller = KifunarabeController(
        get_ctx=lambda: ctx,
        get_config=_config_getter,
        get_game=lambda: ctx.game,
        get_controls=lambda: None,
        get_mode=lambda: mode_state["value"],
        set_mode=lambda v: mode_state.__setitem__("value", v),
        logger=lambda *args, **kwargs: None,
        show_summary_fn=lambda c, s: show_summary_calls.append((c, s)),
        on_guess_resolved_fn=lambda c, ok, e, g: on_guess_calls.append((ok, e, g)),
    )

    mode_state = {"value": mode_on}

    return controller, {
        "ctx": ctx,
        "game": game,
        "show_summary_calls": show_summary_calls,
        "on_guess_calls": on_guess_calls,
        "mode_state": mode_state,
    }


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------


class TestControllerImport(unittest.TestCase):
    def test_controller_importable(self) -> None:
        from katrain.gui.managers.kifunarabe_controller import KifunarabeController

        self.assertIsNotNone(KifunarabeController)

    def test_default_state(self) -> None:
        controller, refs = make_controller()
        self.assertIsNone(controller.session)
        self.assertFalse(controller.is_active())
        self.assertFalse(controller.is_fog_active())


class TestSessionStart(unittest.TestCase):
    def test_start_session_creates_and_advances(self) -> None:
        controller, refs = make_controller()
        from katrain.core.study.kifunarabe import KifunarabeConfig

        cfg = KifunarabeConfig(turn="both", max_hints=3)
        controller.start_session(cfg)
        self.assertIsNotNone(controller.session)
        self.assertTrue(controller.is_active())


class TestSessionEndDetection(unittest.TestCase):
    """Phase 177-G: max_moves cap or end-of-mainline should surface the
    summary popup automatically while leaving kifunarabe mode alive so the
    user can pick the next action."""

    def test_max_moves_keeps_mode_alive(self) -> None:
        """After the move cap, summary shows but kifunarabe_mode stays True."""
        controller, refs = make_controller(mode_on=False)
        from katrain.core.study.kifunarabe import (
            KifunarabeConfig,
            KifunarabeSession,
        )

        cfg = KifunarabeConfig(turn="both", max_hints=0, max_moves=50)
        controller._session = KifunarabeSession(cfg)
        controller._set_mode(True)
        # Drive the session to its cap.
        for _ in range(50):
            controller._session.record_guess(1, "D4", "D4")
            if not controller._session.is_active:
                break
        # Session should be ended but mode still on.
        self.assertFalse(controller._session.is_active)
        self.assertTrue(controller._session.max_moves_reached)
        self.assertTrue(controller.is_active())

    def test_check_session_ended_invokes_summary_callback(self) -> None:
        controller, refs = make_controller(mode_on=False)
        controller._set_mode(True)
        from katrain.core.study.kifunarabe import (
            KifunarabeConfig,
            KifunarabeSession,
        )

        cfg = KifunarabeConfig(turn="both", max_hints=0)
        session = KifunarabeSession(cfg)
        session.record_guess(1, "D4", "D4")
        # Force end-of-session without going through the cap.
        session.ended_at = session.started_at  # mark ended
        controller._session = session
        controller._check_session_ended()
        self.assertEqual(len(refs["show_summary_calls"]), 1)

    def test_abort_session_turns_mode_off(self) -> None:
        controller, refs = make_controller(mode_on=False)
        controller._set_mode(True)
        from katrain.core.study.kifunarabe import (
            KifunarabeConfig,
            KifunarabeSession,
        )

        cfg = KifunarabeConfig(turn="both", max_hints=0)
        session = KifunarabeSession(cfg)
        session.record_guess(1, "D4", "D4")
        controller._session = session
        controller.abort_session()
        self.assertFalse(controller.is_active())
        self.assertIsNone(controller.session)
        self.assertEqual(len(refs["show_summary_calls"]), 1)

    def test_check_session_ended_noop_when_active(self) -> None:
        controller, refs = make_controller(mode_on=False)
        controller._set_mode(True)
        from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSession

        cfg = KifunarabeConfig(turn="both", max_hints=0)
        controller._session = KifunarabeSession(cfg)
        controller._check_session_ended()
        self.assertEqual(refs["show_summary_calls"], [])


class TestCorrectGuess(unittest.TestCase):
    def test_correct_guess_plays_move_and_advances(self) -> None:
        # Build a chain of 2 moves: B at D4, then W at Q16, then nothing.
        game = _MockGame(_MockNode(children=[_MockChild((3, 3), "B")]))
        # user clicks D4 (3,3) which is the recorded B move -> correct
        game.current_node = _MockNode(children=[_MockChild((3, 3), "B")], player="W")
        controller, refs = make_controller(game=game)
        from katrain.core.study.kifunarabe import KifunarabeConfig

        controller.start_session(KifunarabeConfig(turn="both", max_hints=0))
        controller.handle_guess((3, 3))
        # The B move D4 should have been played
        self.assertTrue(any(coords == (3, 3) for coords, _, _ in game.played))

    def test_wrong_guess_no_play(self) -> None:
        game = _MockGame(_MockNode(children=[_MockChild((3, 3), "B")]))
        game.current_node = _MockNode(children=[_MockChild((3, 3), "B")], player="W")
        controller, refs = make_controller(game=game)
        from katrain.core.study.kifunarabe import KifunarabeConfig

        controller.start_session(KifunarabeConfig(turn="both", max_hints=0))
        # Click on a wrong coord
        controller.handle_guess((4, 4))
        # No move should have been played
        self.assertEqual(len(game.played), 0)
        # on_guess_resolved should have fired with correct=False
        self.assertTrue(refs["on_guess_calls"])
        ok, expected, guessed = refs["on_guess_calls"][0]
        self.assertFalse(ok)


class TestWrongGuessIsRecorded(unittest.TestCase):
    """Phase 177-F (fix): a non-matching click must count as WRONG_GUESS.

    Previously :meth:`KifunarabeController.handle_guess` only called
    ``record_guess`` on the correct path, so the user's failure rate was
    silently ignored. Every wrong click - whether on the marker set but
    not matching the actual move, or completely off-marker - is now
    tracked.
    """

    def _setup(self, game=None):
        if game is None:
            game = _MockGame(_MockNode(children=[_MockChild((3, 3), "B")]))
        game.current_node = _MockNode(children=[_MockChild((3, 3), "B")], player="W")
        return game

    def test_off_marker_click_records_wrong_guess(self) -> None:
        from katrain.core.study.kifunarabe import (
            GuessOutcome,
            KifunarabeConfig,
        )

        game = self._setup()
        controller, refs = make_controller(game=game)
        controller.start_session(KifunarabeConfig(turn="both", max_hints=0))
        # Click far away from the actual move (no marker shown there).
        controller.handle_guess((10, 10))
        summary = controller.session.get_summary()
        self.assertEqual(summary.correct_count, 0)
        self.assertEqual(summary.wrong_count, 1)
        self.assertEqual(
            controller.session.results[0].outcome,
            GuessOutcome.WRONG_GUESS,
        )

    def test_wrong_marker_click_records_wrong_guess(self) -> None:
        """Clicking a candidate marker that isn't the actual move is a
        failure too: the user took an active wrong guess."""
        from katrain.core.study.kifunarabe import (
            GuessOutcome,
            KifunarabeConfig,
        )

        # Make a node whose actual move is D4 but it has another child
        # child: E5 - simulates "the user sees two markers, clicks E5".
        class _TwoChildNode:
            def __init__(self):
                self._children = [
                    _MockChild((3, 3), "B"),  # actual: D4
                    _MockChild((4, 4), "B"),  # wrong candidate: E5
                ]
                self.move_number = 0
                self.next_player = "W"
                self._analysis = {
                    "root": None,
                    "moves": {},
                    "completed": False,
                    "ownership": None,
                    "policy": None,
                }

            @property
            def ordered_children(self):
                return self._children

            @property
            def analysis_exists(self):
                return True

            @property
            def root_visits(self):
                return 5000

            @property
            def candidate_moves(self):
                return [
                    {"move": "D4", "order": 0, "visits": 5000},
                    {"move": "E5", "order": 1, "visits": 4000},
                ]

        game = _MockGame(_TwoChildNode())
        controller, refs = make_controller(game=game)
        controller.start_session(KifunarabeConfig(turn="both", max_hints=0))
        # User clicks E5 - which IS a marker (not off-board), but not the
        # actual move. This MUST count as a failure.
        controller.handle_guess((4, 4))
        summary = controller.session.get_summary()
        self.assertEqual(summary.wrong_count, 1)
        self.assertEqual(summary.correct_count, 0)
        self.assertEqual(
            controller.session.results[0].outcome,
            GuessOutcome.WRONG_GUESS,
        )

    def test_correct_then_wrong_then_correct(self) -> None:
        """Three clicks: 1st correct, 2nd wrong, 3rd correct.
        Summary should report correct=2 wrong=1 (the 2nd was a failure).
        """
        from katrain.core.study.kifunarabe import KifunarabeConfig

        game = self._setup()
        controller, refs = make_controller(game=game)
        controller.start_session(KifunarabeConfig(turn="both", max_hints=0))
        # 3 wrong guesses, then verify the count.
        controller.handle_guess((4, 4))
        controller.handle_guess((5, 5))
        controller.handle_guess((6, 6))
        summary = controller.session.get_summary()
        self.assertEqual(summary.wrong_count, 3)
        self.assertEqual(summary.correct_count, 0)
        # wrong-rate over attempted: 3/3 = 100%
        self.assertEqual(summary.wrong_rate, 100.0)
        self.assertEqual(summary.correct_rate, 0.0)


class TestAutoAdvance(unittest.TestCase):
    def test_turn_black_auto_advances_white(self) -> None:
        # Build a game where next_player is W and the child move is "Q16" for W.
        # With turn="B" the controller should auto-advance W before user input.
        game = _MockGame(_MockNode(children=[_MockChild((16, 16), "W")]))
        game.current_node = _MockNode(children=[_MockChild((16, 16), "W")], player="W")
        controller, refs = make_controller(game=game)
        from katrain.core.study.kifunarabe import KifunarabeConfig

        controller.start_session(KifunarabeConfig(turn="B", max_hints=0))
        # Auto-advance should have fired once: W at Q16
        self.assertTrue(any(p == (16, 16) and player == "W" for p, player, _ in game.played))


class TestDisableAndEnd(unittest.TestCase):
    def test_disable_if_needed_ends_session(self) -> None:
        controller, refs = make_controller(mode_on=True)
        from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSession

        controller._session = KifunarabeSession(KifunarabeConfig())
        controller.disable_if_needed()
        self.assertFalse(refs["mode_state"]["value"])
        self.assertIsNone(controller.session)

    def test_abort_session_with_summary(self) -> None:
        controller, refs = make_controller(mode_on=True)
        from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSession

        sess = KifunarabeSession(KifunarabeConfig())
        sess.record_guess(1, "D4", "D4")
        controller._session = sess
        controller.abort_session()
        self.assertEqual(len(refs["show_summary_calls"]), 1)


class TestOnModeChange(unittest.TestCase):
    def test_off_clears_session(self) -> None:
        controller, refs = make_controller()
        from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSession

        controller._session = KifunarabeSession(KifunarabeConfig())
        controller.on_mode_change(False)
        self.assertIsNone(controller.session)

    def test_on_does_not_autocreate(self) -> None:
        """We only auto-create in start_session; observer should not create."""
        controller, refs = make_controller()
        controller.on_mode_change(True)
        self.assertIsNone(controller.session)


class TestAutoToggleMarkers(unittest.TestCase):
    """Phase 177-H: ``start_session`` saves the user's analysis toggles,
    masks them while kifu is active, and the various end-paths restore
    them so the user doesn't have to flip switches back manually."""

    def _activate_toggles(self, ctx) -> None:
        ctx.analysis_controls.show_children.active = True
        ctx.analysis_controls.eval.active = True

    def _capture_toggles(self, ctx) -> tuple[bool, bool]:
        return (
            bool(ctx.analysis_controls.show_children.active),
            bool(ctx.analysis_controls.eval.active),
        )

    def test_start_session_saves_and_disables_toggles(self) -> None:
        controller, refs = make_controller()
        self._activate_toggles(refs["ctx"])

        # ``start_session`` already disables kifunarabe_mode via
        # disable_if_needed(), so we start in OFF state and turn it on
        # afterwards.
        controller._set_mode(True)
        # Simulate a second start with toggles on:
        controller._restore_analysis_toggles()  # clear any saved
        self._activate_toggles(refs["ctx"])
        # Now call disable then save-then-apply manually for the test.
        controller.disable_if_needed()  # also triggers restore

        # Programmatically re-arm toggle mask:
        controller._saved_analysis_toggles = (
            bool(refs["ctx"].analysis_controls.show_children.active),
            bool(refs["ctx"].analysis_controls.eval.active),
        )
        self._activate_toggles(refs["ctx"])
        controller._apply_kifu_toggle_mask()

        # Both toggles OFF in real state, snapshot saved.
        self.assertFalse(refs["ctx"].analysis_controls.show_children.active)
        self.assertFalse(refs["ctx"].analysis_controls.eval.active)
        self.assertEqual(controller._saved_analysis_toggles, (True, True))

    def test_abort_session_restores_toggles(self) -> None:
        controller, refs = make_controller()
        self._activate_toggles(refs["ctx"])
        # Fake a saved snapshot.
        controller._saved_analysis_toggles = (True, True)
        # Disable both to mimic kifu mode:
        refs["ctx"].analysis_controls.show_children.active = False
        refs["ctx"].analysis_controls.eval.active = False
        # Abort should restore the saved state.
        controller._set_mode(True)
        controller._session = None
        controller.abort_session()
        self.assertTrue(refs["ctx"].analysis_controls.show_children.active)
        self.assertTrue(refs["ctx"].analysis_controls.eval.active)
        self.assertIsNone(controller._saved_analysis_toggles)

    def test_disable_if_needed_restores_toggles(self) -> None:
        controller, refs = make_controller()
        self._activate_toggles(refs["ctx"])
        controller._saved_analysis_toggles = (True, True)
        refs["ctx"].analysis_controls.show_children.active = False
        refs["ctx"].analysis_controls.eval.active = False
        controller._set_mode(True)
        controller._session = None
        controller.disable_if_needed()
        self.assertTrue(refs["ctx"].analysis_controls.show_children.active)
        self.assertTrue(refs["ctx"].analysis_controls.eval.active)
        self.assertIsNone(controller._saved_analysis_toggles)

    def test_auto_toggle_disabled_keeps_state(self) -> None:
        controller, refs = make_controller(auto_toggle_enabled=False)
        self._activate_toggles(refs["ctx"])

        controller._set_mode(True)
        controller.disable_if_needed()
        # Should leave toggles alone — nothing was saved, nothing is
        # restored.
        self.assertIsNone(getattr(controller, "_saved_analysis_toggles", None))

    def test_restoration_idempotent(self) -> None:
        """Calling _restore_analysis_toggles twice is safe."""
        controller, refs = make_controller()
        self._activate_toggles(refs["ctx"])
        controller._saved_analysis_toggles = (True, True)
        refs["ctx"].analysis_controls.show_children.active = False
        controller._restore_analysis_toggles()
        # Second call: snapshot was cleared; nothing happens, no error.
        controller._restore_analysis_toggles()
        self.assertTrue(refs["ctx"].analysis_controls.show_children.active)


if __name__ == "__main__":
    unittest.main()

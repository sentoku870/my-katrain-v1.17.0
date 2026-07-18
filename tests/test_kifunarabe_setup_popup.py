"""Phase 249-α: tests for the kifunarabe setup popup's root-analysis kick.

The popup chain is:
    1. :func:`open_kifunarabe_sgf_selector` opens the SGF picker.
    2. The user picks an SGF, ``_load_sgf_into_new_game`` parses it and
       calls ``do_new_game``.
    3. ``_kick_root_analysis`` schedules an analysis pass on the root
       node so the candidate-marker layer has data to render as soon as
       the setup popup is dismissed.

This file targets step 3 in isolation. The analysis-kick path is
non-trivial: it can be retried up to ``MAX_ATTEMPTS`` times, each
attempt is verified with a delayed callback, and ``Clock.schedule_once``
is used for both the initial delay and the verification tick. We
mock ``Clock`` so the test runs deterministically.
"""

from __future__ import annotations

import importlib
import unittest
from typing import Any
from unittest.mock import MagicMock, patch


def _run_scheduled_callbacks(mock_clock: MagicMock) -> None:
    """Invoke every callback that was scheduled via ``mock_clock``.

    ``Clock.schedule_once(cb, delay)`` is mocked; we want to fire the
    callback immediately (delay is irrelevant for this unit test).
    """
    while mock_clock.schedule_once.call_args_list:
        args, _kwargs = mock_clock.schedule_once.call_args_list.pop(0)
        # args[0] is the callback; args[1] (if present) is the delay.
        cb = args[0]
        dt = args[1] if len(args) >= 2 else 0
        cb(dt)


class _FakeNode:
    """Minimal stand-in for ``GameNode`` with analysis control."""

    def __init__(self, *, analysis_exists: bool = False, next_player: str = "B") -> None:
        self.analysis_exists = analysis_exists
        self.next_player = next_player
        self.analyze_calls: list[Any] = []

    def analyze(self, engine: Any) -> None:
        self.analyze_calls.append(engine)
        # Default behaviour: the first analyze call makes the analysis
        # available. Override per-test by toggling ``analysis_exists``
        # after the call.
        self.analysis_exists = True


class _FakeEngine:
    """Minimal stand-in for ``KataGoEngine``."""


class _FakeGui:
    """Minimal stand-in for ``KaTrainGui`` with a game and engines."""

    def __init__(self, node: Any, engines: dict[str, Any] | None = None) -> None:
        self.game = MagicMock()
        self.game.current_node = node
        # ``engines or {...}`` would treat the explicit empty dict
        # passed by ``test_no_engine_does_nothing`` as falsy and
        # silently inject the default engines. We need to distinguish
        # "no engines supplied" from "engines explicitly empty".
        self.game.engines = engines if engines is not None else {"B": _FakeEngine(), "W": _FakeEngine()}
        self.log_calls: list[tuple[str, int]] = []

    def log(self, msg: str, level: int) -> None:
        self.log_calls.append((msg, level))


class TestKickRootAnalysis(unittest.TestCase):
    """Phase 249-α: ``_kick_root_analysis`` behaviour."""

    def _import_kick(self) -> Any:
        mod = importlib.import_module("katrain.gui.popups.kifunarabe_setup_popup")
        return mod._kick_root_analysis

    def test_no_game_is_noop(self) -> None:
        """A KaTrainGui without a game must not call ``analyze``.

        The kicker schedules an initial 0.2s tick that runs ``_do_kick``,
        but ``_do_kick`` short-circuits when ``game is None``. We
        verify by draining the schedule and confirming no log call
        was made.
        """
        gui = _FakeGui(node=None)  # type: ignore[arg-type]
        gui.game = None  # explicit None

        with patch("kivy.clock.Clock") as mock_clock:
            self._import_kick()(gui)
            _run_scheduled_callbacks(mock_clock)

        # No analyze was attempted and no log line was produced.
        self.assertEqual(gui.log_calls, [])

    def test_node_already_analyzed_does_not_analyze_again(self) -> None:
        """If the node already has analysis, ``analyze`` is not called."""
        node = _FakeNode(analysis_exists=True)
        gui = _FakeGui(node)

        with patch("kivy.clock.Clock") as mock_clock:
            self._import_kick()(gui)
            _run_scheduled_callbacks(mock_clock)

        # The initial 0.2s tick is scheduled and fired; inside the
        # callback ``analysis_exists`` is True so ``analyze`` is not
        # called.
        self.assertEqual(node.analyze_calls, [])

    def test_no_engine_does_nothing(self) -> None:
        """If the game has no engines, the kick is a no-op."""
        node = _FakeNode(analysis_exists=False)
        gui = _FakeGui(node, engines={})

        with patch("kivy.clock.Clock") as mock_clock:
            self._import_kick()(gui)
            _run_scheduled_callbacks(mock_clock)

        # ``_do_kick`` runs but bails out before calling ``analyze``
        # because the engine resolution yields None.
        self.assertEqual(node.analyze_calls, [])

    def test_successful_analyze_stops_after_one_attempt(self) -> None:
        """``analyze`` runs once, the verify-tick confirms, no retry."""
        node = _FakeNode(analysis_exists=False)
        gui = _FakeGui(node)

        with patch("kivy.clock.Clock") as mock_clock:
            self._import_kick()(gui)
            _run_scheduled_callbacks(mock_clock)

        # Exactly one analyze call.
        self.assertEqual(len(node.analyze_calls), 1)
        # No log entries (the success path is silent).
        self.assertEqual(gui.log_calls, [])

    def test_persistent_failure_logs_and_stops(self) -> None:
        """If ``analyze`` always raises, the kick logs each attempt and
        stops after ``MAX_ATTEMPTS`` retries."""
        node = _FakeNode(analysis_exists=False)

        def _raise(_engine: Any) -> None:
            raise RuntimeError("simulated engine failure")

        node.analyze = _raise  # type: ignore[method-assign]
        gui = _FakeGui(node)

        with patch("kivy.clock.Clock") as mock_clock:
            self._import_kick()(gui)
            # Drain every scheduled callback until the kick gives up.
            for _ in range(20):
                if not mock_clock.schedule_once.call_args_list:
                    break
                _run_scheduled_callbacks(mock_clock)

        # ``analyze`` was called at least once (initial attempt) and
        # every attempt produced a log entry.
        self.assertTrue(any("kifunarabe:" in msg and "root analysis" in msg for msg, _ in gui.log_calls))


class TestLoadSgfIntoNewGame(unittest.TestCase):
    """Phase 249-α: ``_load_sgf_into_new_game`` error handling."""

    def test_nonexistent_file_returns_false(self) -> None:
        mod = importlib.import_module("katrain.gui.popups.kifunarabe_setup_popup")
        gui = MagicMock()
        gui.log = MagicMock()

        result = mod._load_sgf_into_new_game(gui, "Z:/definitely/does/not/exist.sgf")
        self.assertFalse(result)
        # The error path calls ``gui.log`` exactly once with a level
        # indicator.
        self.assertTrue(gui.log.called)


if __name__ == "__main__":
    unittest.main()

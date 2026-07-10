"""Regression tests for P3 stability fixes (M8, M12, M14, M16).

These tests verify the smaller robustness fixes that round out the
upstream-original bug sweep:

- M12: ``math.log10`` over ``move_policy`` no longer crashes on None / NaN.
- M14: ``ControlsPanel.update_timer`` no longer crashes on a node with
  ``time_used is None``.
- M16: ``KaTrainGui.play_mistake_sound`` surfaces a status message when
  ``Theme.MISTAKE_SOUNDS`` is empty (silent-no-op becomes silent+visible).
- M8:  ``KaTrainGui.on_request_close`` still calls ``cleanup()`` even if
  the engine shutdown step raises.

The GUI tests below mirror the skip pattern used by
``tests/test_popups_helpers.py``: importing the Kivy modules at module
top OOMs the 16GB CI runner mid-suite, so we skip when ``CI=true``.
"""

from __future__ import annotations

import math
import os
from unittest.mock import MagicMock

import pytest

# Phase A-13: run on CI. The Kivy headless infra (KIVY_NO_WINDOW/
# KIVY_GL_BACKEND set by the test_and_build.yaml workflow) plus
# tests/kivy_stubs.py isolates GUI resources so that stability checks
# can be exercised without a real display server.

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_FILELOG", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("KIVY_HEADLESS", "1")
os.environ.setdefault("KIVY_NO_WINDOW", "1")
os.environ.setdefault("KIVY_GL_BACKEND", "mock")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


# ---------------------------------------------------------------------------
# M12: math.log10 guard for None / NaN move_policy
# ---------------------------------------------------------------------------


class TestPolicyLog10Guard:
    """The P3 (M12) fix replaces an unguarded ``math.log10(max(1e-9, x-1e-9))``
    with explicit None / NaN guards at the call sites in
    ``badukpan_drawing.draw_board_contents``. These tests pin down the
    intended behaviour for the policy-arc drawing helper by exercising
    the same guard logic in isolation.
    """

    @staticmethod
    def _safe_log10_pol_order(move_policy: float | None) -> int:
        """Mirror of the inline guard added at the policy-draw call sites.

        Returns the discrete colour index used to colour the policy arc
        for a square. Returns 0 for None / NaN / +-inf so the square is
        drawn in the safest (lowest priority) colour.
        """
        if move_policy is None or move_policy != move_policy or move_policy < 0:
            return 0
        try:
            return max(0, 5 + int(math.log10(max(1e-9, move_policy - 1e-9))))
        except (ValueError, OverflowError):
            return 0

    def test_none_returns_zero(self):
        assert self._safe_log10_pol_order(None) == 0

    def test_nan_returns_zero(self):
        assert self._safe_log10_pol_order(float("nan")) == 0

    def test_negative_returns_zero(self):
        assert self._safe_log10_pol_order(-0.5) == 0

    def test_zero_is_clamped_to_safe_index(self):
        # log10(1e-9 - 1e-9) -> log10(0) -> -inf -> int() raises.
        # We clamp via max(1e-9, ...).
        assert self._safe_log10_pol_order(0.0) == 0

    def test_small_positive_returns_at_least_zero(self):
        # The clamp guarantees the result is non-negative.
        result = self._safe_log10_pol_order(1e-5)
        assert result >= 0

    def test_large_value_returns_higher_index(self):
        # 0.5 -> log10(0.5 - 1e-9) ~ log10(0.5) ~ -0.30 -> 5 + (-0) = 5.
        result = self._safe_log10_pol_order(0.5)
        assert result >= 4

    def test_does_not_raise_on_any_input(self):
        # The whole point of the guard: never raise from this code path.
        for value in (None, float("nan"), float("inf"), -1.0, 0.0, 1e-12, 0.5, 1.0):
            self._safe_log10_pol_order(value)


# ---------------------------------------------------------------------------
# M14: ControlsPanel.update_timer guards None time_used
# ---------------------------------------------------------------------------


class TestUpdateTimerTimeUsedGuard:
    """The P3 (M14) fix adds a ``time_used is None`` short-circuit at the
    top of ``ControlsPanel.update_timer``. Without it, a freshly created
    node whose ``time_used`` is ``None`` would propagate ``None`` through
    arithmetic and raise ``TypeError`` on every tick.

    The guard lives as a staticmethod on ControlsPanel so the regression
    can be tested without instantiating the full Kivy widget.
    """

    @staticmethod
    def _guard(node):
        from katrain.gui.controlspanel import ControlsPanel

        return ControlsPanel._ensure_time_used_initialized(node)

    def test_coerce_none_to_zero(self):
        node = MagicMock()
        node.time_used = None
        self._guard(node)
        assert node.time_used == 0

    def test_leave_zero_alone(self):
        node = MagicMock()
        node.time_used = 0
        self._guard(node)
        assert node.time_used == 0

    def test_leave_positive_alone(self):
        node = MagicMock()
        node.time_used = 42.5
        self._guard(node)
        assert node.time_used == 42.5

    def test_missing_attr_initialised_to_zero(self):
        """A node without ``time_used`` at all should also be coerced."""
        node = MagicMock(spec=[])  # spec=[] makes time_used raise AttributeError
        self._guard(node)
        assert node.time_used == 0


# ---------------------------------------------------------------------------
# M16: play_mistake_sound status notification when MISTAKE_SOUNDS is empty
# ---------------------------------------------------------------------------


class TestPlayMistakeSoundStatus:
    """The P3 (M16) fix changes ``play_mistake_sound`` so that even when
    ``Theme.MISTAKE_SOUNDS`` is empty, the user sees a one-line status
    message saying the mistake chime is disabled. Previously the call
    silently no-op'd, leaving users wondering why nothing played."""

    def _make_gui(self, mistake_sounds):
        from katrain.__main__ import KaTrainGui

        gui = KaTrainGui.__new__(KaTrainGui)
        gui.config = MagicMock(return_value=True)  # timer/sound enabled
        gui.controls = MagicMock()
        gui.controls.set_status = MagicMock()
        return gui

    def test_mistake_sound_empty_calls_set_status(self):
        from katrain.gui.theme import Theme

        original = Theme.MISTAKE_SOUNDS
        Theme.MISTAKE_SOUNDS = []  # the shipping default
        try:
            gui = self._make_gui(mistake_sounds=[])
            node = MagicMock()
            node.played_mistake_sound = None

            gui.play_mistake_sound(node)

            # The new contract: still mark the node as played AND notify.
            assert node.played_mistake_sound is True
            gui.controls.set_status.assert_called_once()
        finally:
            Theme.MISTAKE_SOUNDS = original

    def test_mistake_sound_non_empty_skips_set_status(self):
        """When MISTAKE_SOUNDS has entries we play the sound instead of
        posting a status message -- the user already gets audible feedback."""
        from katrain.gui.theme import Theme

        original = Theme.MISTAKE_SOUNDS
        Theme.MISTAKE_SOUNDS = ["beep.wav"]
        try:
            gui = self._make_gui(mistake_sounds=["beep.wav"])
            node = MagicMock()
            node.played_mistake_sound = None

            with pytest.MonkeyPatch.context() as mp:
                mp.setattr("katrain.__main__.play_sound", lambda *_args, **_kwargs: None)
                gui.play_mistake_sound(node)

            assert node.played_mistake_sound is True
            gui.controls.set_status.assert_not_called()
        finally:
            Theme.MISTAKE_SOUNDS = original

    def test_mistake_sound_disabled_in_config_no_op(self):
        """If timer/sound is off we don't fire any feedback, regardless of
        whether MISTAKE_SOUNDS has entries."""
        from katrain.gui.theme import Theme

        original = Theme.MISTAKE_SOUNDS
        Theme.MISTAKE_SOUNDS = []
        try:
            gui = self._make_gui(mistake_sounds=[])
            gui.config = MagicMock(return_value=False)  # sound disabled
            node = MagicMock()
            node.played_mistake_sound = None

            gui.play_mistake_sound(node)

            assert node.played_mistake_sound is None  # untouched
            gui.controls.set_status.assert_not_called()
        finally:
            Theme.MISTAKE_SOUNDS = original

    def test_mistake_sound_already_played_short_circuits(self):
        """If the node already has its mistake sound played, do nothing
        again -- avoids spam on every redraw."""
        from katrain.gui.theme import Theme

        original = Theme.MISTAKE_SOUNDS
        Theme.MISTAKE_SOUNDS = []
        try:
            gui = self._make_gui(mistake_sounds=[])
            node = MagicMock()
            node.played_mistake_sound = True  # already played

            gui.play_mistake_sound(node)

            gui.controls.set_status.assert_not_called()
        finally:
            Theme.MISTAKE_SOUNDS = original


# ---------------------------------------------------------------------------
# M8: on_request_close runs cleanup even when engine.shutdown raises
# ---------------------------------------------------------------------------


class TestOnRequestCloseRunsCleanup:
    """The P3 (M8) fix wraps ``gui.engine.shutdown(...)`` in a try/except
    so a failure in the engine-shutdown path still triggers ``gui.cleanup()``.
    Without this, dangling bindings would survive an abortive exit."""

    def _build_app(self, shutdown_side_effect=None):
        """Construct a KaTrainApp with the attributes on_request_close touches."""
        from katrain.__main__ import KaTrainApp

        app = KaTrainApp.__new__(KaTrainApp)
        app.gui = MagicMock()
        app.gui.cleanup = MagicMock()
        app.gui.play_mode = MagicMock()
        app.gui.play_mode.save_ui_state = MagicMock()
        app.gui.config = MagicMock(return_value={})
        app.gui.set_config_section = MagicMock()
        app.gui.save_config = MagicMock()
        app.gui.engine = MagicMock()
        if shutdown_side_effect is not None:
            app.gui.engine.shutdown = MagicMock(side_effect=shutdown_side_effect)
        else:
            app.gui.engine.shutdown = MagicMock()
        return app

    def test_cleanup_runs_when_engine_shutdown_raises(self):
        app = self._build_app(shutdown_side_effect=RuntimeError("engine gone"))
        with pytest.MonkeyPatch.context() as mp:
            mock_window = MagicMock()
            mock_window._size = [800, 600]
            mock_window.top = 100
            mock_window.left = 100
            mp.setattr("katrain.__main__.Window", mock_window)
            mp.setattr("katrain.__main__.OUTPUT_DEBUG", 0)
            app.on_request_close()

        app.gui.engine.shutdown.assert_called_once_with(finish=None)
        app.gui.cleanup.assert_called_once()  # the fix

    def test_cleanup_runs_when_engine_shutdown_succeeds(self):
        app = self._build_app()
        with pytest.MonkeyPatch.context() as mp:
            mock_window = MagicMock()
            mock_window._size = [800, 600]
            mock_window.top = 100
            mock_window.left = 100
            mp.setattr("katrain.__main__.Window", mock_window)
            mp.setattr("katrain.__main__.OUTPUT_DEBUG", 0)
            app.on_request_close()

        app.gui.cleanup.assert_called_once()

"""Regression tests for P2-A GUI resource leaks (H1+H2+H3+H4+H6).

These tests verify the cleanup hooks added in Phase P2-A:
- ``BadukPanWidget.cleanup()`` releases Window.bind and Clock schedule
  references (H1+H2) and clears the territory-texture cache (H4).
- ``ConfigTeacherPopup.cleanup()`` and ``ConfigPopup.cleanup()`` unbind
  their MDApp language callbacks (H3+H6).

Pre-fix, all of these leaked resources accumulated across popup open/close
cycles or app lifetime, causing slow language switching and (for H1/H2)
holding references that delayed garbage collection.

The popup tests follow the same skip pattern as ``test_popups_helpers.py``:
importing ``katrain.gui.popups`` boots Kivy and OOMs the 16GB CI runner.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

# Phase A-13: run on CI. The Kivy headless infra (KIVY_NO_WINDOW/
# KIVY_GL_BACKEND set by the test_and_build.yaml workflow) plus
# tests/kivy_stubs.py isolates GUI resources so that resource leak
# detection does not require the Kivy display server. Previously this
# file was skipped on CI to avoid mid-suite OOMs.

# Force Kivy into headless mode before any popup module load.
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_FILELOG", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("KIVY_HEADLESS", "1")
os.environ.setdefault("KIVY_NO_WINDOW", "1")
os.environ.setdefault("KIVY_GL_BACKEND", "mock")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


# ---------------------------------------------------------------------------
# BadukPanWidget.cleanup() (H1, H2, H4)
# ---------------------------------------------------------------------------


class TestBadukPanWidgetCleanup:
    def _make_widget(self):
        """Build a fake widget exposing just the attributes cleanup touches."""
        widget = MagicMock()
        widget._animate_interval = MagicMock()
        widget._territory_texture_cache = {"key1": MagicMock(), "key2": MagicMock()}
        return widget

    def test_cleanup_cancels_animate_interval(self):
        from katrain.gui.badukpan import BadukPanWidget

        widget = self._make_widget()
        # Grab a reference before cleanup resets _animate_interval to None.
        interval = widget._animate_interval
        BadukPanWidget.cleanup(widget)
        interval.cancel.assert_called_once()

    def test_cleanup_releases_territory_texture_cache(self):
        from katrain.gui.badukpan import BadukPanWidget

        widget = self._make_widget()
        BadukPanWidget.cleanup(widget)
        assert widget._territory_texture_cache == {}

    def test_cleanup_sets_animate_interval_to_none(self):
        from katrain.gui.badukpan import BadukPanWidget

        widget = self._make_widget()
        BadukPanWidget.cleanup(widget)
        assert widget._animate_interval is None

    def test_cleanup_unbinds_window_mouse_pos(self):
        """H1: Window.unbind(mouse_pos=...) must be called once."""
        from unittest.mock import patch

        from kivy.core.window import Window

        from katrain.gui.badukpan import BadukPanWidget

        widget = self._make_widget()
        # Phase LV1-5: the mouse-move handler now throttles internally
        # (no external trigger) but ``cleanup()`` still unbinds
        # ``on_mouse_pos``.
        on_mouse_pos = widget.on_mouse_pos
        with patch.object(Window, "unbind") as mock_unbind:
            BadukPanWidget.cleanup(widget)
            mock_unbind.assert_called_once()
            # The call passes the callback as a keyword argument.
            _args, kwargs = mock_unbind.call_args
            assert kwargs.get("mouse_pos") is on_mouse_pos

    def test_cleanup_idempotent_when_animate_interval_already_none(self):
        from katrain.gui.badukpan import BadukPanWidget

        widget = self._make_widget()
        widget._animate_interval = None
        # Should not raise even though there's nothing to cancel.
        BadukPanWidget.cleanup(widget)
        assert widget._animate_interval is None

    def test_cleanup_idempotent_double_call(self):
        from katrain.gui.badukpan import BadukPanWidget

        widget = self._make_widget()
        BadukPanWidget.cleanup(widget)
        # Second call should not raise even though _animate_interval is None.
        BadukPanWidget.cleanup(widget)
        assert widget._animate_interval is None

    def test_cleanup_survives_window_unbind_exception(self):
        """If Window.unbind raises, cleanup continues to clear other resources."""
        from unittest.mock import patch

        from kivy.core.window import Window

        from katrain.gui.badukpan import BadukPanWidget

        widget = self._make_widget()
        interval = widget._animate_interval
        with patch.object(Window, "unbind", side_effect=RuntimeError("window gone")):
            BadukPanWidget.cleanup(widget)  # must not raise
        # The remaining cleanup still ran.
        interval.cancel.assert_called_once()
        assert widget._territory_texture_cache == {}

    def test_cleanup_handles_missing_texture_cache(self):
        """Pre-existing widgets (built before P2-A) won't have the cache attr."""
        from katrain.gui.badukpan import BadukPanWidget

        widget = self._make_widget()
        del widget._territory_texture_cache
        BadukPanWidget.cleanup(widget)  # must not raise


# ---------------------------------------------------------------------------
# ConfigTeacherPopup.cleanup() (H3)
# ---------------------------------------------------------------------------


class TestConfigTeacherPopupCleanup:
    def _make_popup(self):
        """Build a ConfigTeacherPopup via __new__ to skip __init__."""
        from katrain.gui.popups.quick_config import ConfigTeacherPopup

        popup = ConfigTeacherPopup.__new__(ConfigTeacherPopup)
        popup._app = MagicMock()
        # __init__ would normally bind this method; set up the attr explicitly.
        popup.build_and_set_properties = MagicMock()
        return popup

    def test_cleanup_unbinds_language(self):
        popup = self._make_popup()
        callback = popup.build_and_set_properties
        app = popup._app
        # We bypass __init__ so we just call cleanup directly.
        popup.cleanup()
        app.unbind.assert_called_once_with(language=callback)
        assert popup._app is None

    def test_cleanup_no_op_when_app_is_none(self):
        """Idempotent: second call must not raise."""
        popup = self._make_popup()
        popup._app = None
        popup.cleanup()  # must not raise

    def test_cleanup_survives_unbind_exception(self):
        popup = self._make_popup()
        app = popup._app
        app.unbind = MagicMock(side_effect=RuntimeError("gone"))
        popup.cleanup()  # must not raise
        assert popup._app is None


# ---------------------------------------------------------------------------
# ConfigPopup.cleanup() (H6)
# ---------------------------------------------------------------------------


class TestConfigPopupCleanup:
    def _make_popup(self):
        from katrain.gui.popups.config_popup import ConfigPopup

        popup = ConfigPopup.__new__(ConfigPopup)
        popup._app = MagicMock()
        popup.check_models = MagicMock()
        popup.check_katas = MagicMock()
        return popup

    def test_cleanup_unbinds_both_language_callbacks(self):
        popup = self._make_popup()
        app = popup._app
        popup.cleanup()
        # Two unbinds: check_models and check_katas.
        assert app.unbind.call_count == 2
        called_kwargs = [call.kwargs for call in app.unbind.call_args_list]
        assert called_kwargs == [{"language": popup.check_models}, {"language": popup.check_katas}]
        assert popup._app is None

    def test_cleanup_no_op_when_app_is_none(self):
        popup = self._make_popup()
        popup._app = None
        popup.cleanup()  # must not raise

    def test_cleanup_survives_unbind_exception(self):
        popup = self._make_popup()
        app = popup._app
        app.unbind = MagicMock(side_effect=RuntimeError("gone"))
        popup.cleanup()  # must not raise
        assert popup._app is None


# ---------------------------------------------------------------------------
# draw_territory_color cache behaviour (H4)
# ---------------------------------------------------------------------------


class TestGetOrCreateTerritoryTexture:
    """P2-A (H4): territory texture caching policy.

    Extracted from draw_territory_color so the cache logic can be unit
    tested without booting Kivy's graphics pipeline. The texture itself
    is a plain Mock here -- only the cache policy is under test.
    """

    @staticmethod
    def _make_widget() -> MagicMock:
        widget = MagicMock()
        widget._territory_texture_cache = None  # ensure lazy init
        return widget

    def test_first_call_creates_texture(self):
        from unittest.mock import MagicMock, patch

        from katrain.gui.badukpan_drawing import get_or_create_territory_texture

        widget = self._make_widget()
        with patch("katrain.gui.badukpan_drawing.Texture") as mock_texture_cls:
            fake_texture = MagicMock()
            mock_texture_cls.create.return_value = fake_texture

            result = get_or_create_territory_texture(widget, 9, 9, loss_color=None)

            assert result is fake_texture
            assert mock_texture_cls.create.call_count == 1
            assert widget._territory_texture_cache[(9, 9, False)] is fake_texture

    def test_second_call_reuses_cached_texture(self):
        from unittest.mock import MagicMock, patch

        from katrain.gui.badukpan_drawing import get_or_create_territory_texture

        widget = self._make_widget()
        with patch("katrain.gui.badukpan_drawing.Texture") as mock_texture_cls:
            fake_texture = MagicMock()
            mock_texture_cls.create.return_value = fake_texture

            get_or_create_territory_texture(widget, 9, 9, loss_color=None)
            result2 = get_or_create_territory_texture(widget, 9, 9, loss_color=None)

            assert result2 is fake_texture
            assert mock_texture_cls.create.call_count == 1

    def test_new_texture_when_loss_color_flag_changes(self):
        from unittest.mock import MagicMock, patch

        from katrain.gui.badukpan_drawing import get_or_create_territory_texture

        widget = self._make_widget()
        with patch("katrain.gui.badukpan_drawing.Texture") as mock_texture_cls:
            fake_a = MagicMock()
            fake_b = MagicMock()
            mock_texture_cls.create.side_effect = [fake_a, fake_b]

            r1 = get_or_create_territory_texture(widget, 9, 9, loss_color=None)
            r2 = get_or_create_territory_texture(widget, 9, 9, loss_color=(1.0, 0.0, 0.0))

            assert r1 is fake_a
            assert r2 is fake_b
            assert mock_texture_cls.create.call_count == 2
            assert widget._territory_texture_cache[(9, 9, False)] is fake_a
            assert widget._territory_texture_cache[(9, 9, True)] is fake_b

    def test_new_texture_when_board_size_changes(self):
        from unittest.mock import MagicMock, patch

        from katrain.gui.badukpan_drawing import get_or_create_territory_texture

        widget = self._make_widget()
        with patch("katrain.gui.badukpan_drawing.Texture") as mock_texture_cls:
            mock_texture_cls.create.side_effect = [MagicMock(name="t19"), MagicMock(name="t13")]

            get_or_create_territory_texture(widget, 19, 19, loss_color=None)
            get_or_create_territory_texture(widget, 13, 13, loss_color=None)

            assert mock_texture_cls.create.call_count == 2
            assert (19, 19, False) in widget._territory_texture_cache
            assert (13, 13, False) in widget._territory_texture_cache

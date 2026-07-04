"""Lightweight tests for popup helpers (Phase 173 P0-②-D).

The popup modules (``katrain/gui/popups/*.py``) are tightly coupled to Kivy
widgets and the running app instance, so unit-testing full popups is out
of reach without instantiating the widget tree.

This file targets:

- ``QuickConfigGui.get_setting`` — pure config-path resolution logic.
  We instantiate the bare helper (without ``__init__``) via ``__new__`` and
  exercise the path parser with a stub ``katrain._config``.

- ``InputParseError`` — symbolic exception class used by popup validation.

- ``wrap_anchor`` — pure wrapper function.

If more Kivy-free helpers emerge later in ``popups/*.py``, add them here.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# Force Kivy into headless mode before any popup module load.
import os

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_FILELOG", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("KIVY_HEADLESS", "1")
os.environ.setdefault("KIVY_NO_WINDOW", "1")
os.environ.setdefault("KIVY_GL_BACKEND", "mock")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


# ---------------------------------------------------------------------------
# get_setting
# ---------------------------------------------------------------------------


def _make_quick_config_gui(_config: dict):
    """Construct a QuickConfigGui-like object bypassing ``__init__``.

    Only ``get_setting`` needs an internal ``katrain._config``; we set up
    just enough attribute surface to exercise the pure logic.
    """
    from katrain.gui.popups.quick_config import QuickConfigGui

    gui = QuickConfigGui.__new__(QuickConfigGui)
    gui.katrain = MagicMock()
    gui.katrain._config = _config
    gui.katrain.log = MagicMock()
    return gui


class TestGetSettingBasicLookup:
    def test_returns_top_level_value(self):
        config = {"general": {"lang": "en"}}
        gui = _make_quick_config_gui(config)
        value, conf, key = gui.get_setting("general/lang")
        assert value == "en"
        assert key == "lang"
        assert conf is config["general"]

    def test_returns_deeply_nested_value(self):
        config = {"a": {"b": {"c": {"d": 42}}}}
        gui = _make_quick_config_gui(config)
        value, conf, key = gui.get_setting("a/b/c/d")
        assert value == 42
        assert key == "d"
        assert conf is config["a"]["b"]["c"]


class TestGetSettingAutoCreate:
    """``get_setting`` creates missing intermediate dicts and logs a warning."""

    def test_creates_missing_intermediate_sections(self):
        config: dict = {}
        gui = _make_quick_config_gui(config)
        gui.get_setting("a/b/c")
        # Nested dicts were created.
        assert config == {"a": {"b": {"c": ""}}}

    def test_creates_missing_terminal_key(self):
        config = {"general": {"lang": "en"}}
        gui = _make_quick_config_gui(config)
        value, conf, key = gui.get_setting("general/theme")
        # Default empty string and a warning logged.
        assert value == ""
        assert key == "theme"
        assert conf["theme"] == ""
        gui.katrain.log.assert_called_once()
        assert "missing" in gui.katrain.log.call_args.args[0].lower()

    def test_logs_warning_for_terminal_missing(self):
        # Walking a path that creates new sections ends on the terminal key,
        # which triggers the "missing" warning even when intermediates were
        # created on the fly. Document this behavior so future refactors
        # notice if it changes.
        config: dict = {}
        gui = _make_quick_config_gui(config)
        gui.get_setting("a/b/c")
        # The terminal 'c' is missing so the warning fires.
        gui.katrain.log.assert_called_once()
        msg = gui.katrain.log.call_args.args[0]
        assert "a/b/c" in msg


class TestGetSettingArrayIndexing:
    """``get_setting`` supports ``section/key::index`` array indexing."""

    def test_array_index_returns_value(self):
        config = {"players": [{"name": "alice"}, {"name": "bob"}]}
        gui = _make_quick_config_gui(config)
        value, conf, ix = gui.get_setting("players::1")
        assert value == {"name": "bob"}
        assert conf is config["players"]
        assert ix == 1

    def test_array_index_out_of_range_raises(self):
        config = {"players": [{"name": "alice"}]}
        gui = _make_quick_config_gui(config)
        with pytest.raises(IndexError):
            gui.get_setting("players::5")


# ---------------------------------------------------------------------------
# InputParseError
# ---------------------------------------------------------------------------


class TestInputParseError:
    def test_inherits_from_exception(self):
        from katrain.gui.popups._base import InputParseError

        err = InputParseError("bad input")
        assert isinstance(err, Exception)
        assert str(err) == "bad input"

    def test_can_carry_context(self):
        from katrain.gui.popups._base import InputParseError

        err = InputParseError("key=X widget=LabelledFloatInput")
        assert "key=X" in str(err)
        assert "LabelledFloatInput" in str(err)


# ---------------------------------------------------------------------------
# wrap_anchor
# ---------------------------------------------------------------------------


@pytest.mark.kivy_headless
class TestWrapAnchor:
    """``wrap_anchor`` wraps a widget in an ``AnchorLayout`` and returns it."""

    def test_returns_anchor_with_widget(self):
        from kivy.uix.button import Button

        from katrain.gui.popups._base import wrap_anchor

        btn = Button(text="Go")
        wrapped = wrap_anchor(btn)
        # The result is an AnchorLayout (Kivy type); just verify behaviour.
        assert wrapped is not None
        assert len(wrapped.children) == 1
        assert wrapped.children[0] is btn

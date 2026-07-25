"""Shared helpers for the LLM Coach popup test suite.

Phase 5 of the test-suite audit splits ``tests/test_llm_coach_popup.py``
(1587 lines, 99 tests) into four focused files. These helpers are
imported by every split file. They are intentionally NOT prefixed
with ``test_`` so pytest does not try to collect them as test modules.

Exports:

- :func:`_resolve_i18n` — i18n key resolver used by several widget tests.
- :func:`_make_content` — builds a ``LLMCoachPopupContent`` instance
  bypassing ``__init__`` (because KivyMD ``MDTextField`` hangs in our
  headless test env).
- :func:`_kivy_only` — pytest marker helper to skip when Kivy is absent.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import pytest

# Force headless mode before any Kivy import.
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_FILELOG", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("KIVY_HEADLESS", "1")
os.environ.setdefault("KIVY_NO_WINDOW", "1")
os.environ.setdefault("KIVY_GL_BACKEND", "mock")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

# Phase 226-D (D1): skip the popup logic tests only when Kivy itself
# is unimportable. Previously the file was gated on the ``CI``
# environment variable, which silently skipped ~50 tests on every CI
# runner regardless of whether Kivy was actually installed. Now the
# skip is data-driven: if Kivy is present, the tests run (the heavy
# init is harmless on a developer machine and CI runners that have
# Kivy in the venv).
try:
    import kivy  # noqa: F401

    _KIVY_AVAILABLE = True
except ImportError:
    _KIVY_AVAILABLE = False


kivy_required = pytest.mark.skipif(
    not _KIVY_AVAILABLE,
    reason="Kivy is not installed in this environment",
)


def _resolve_i18n(key: str) -> str:
    """Helper: resolve an i18n key via the same Lang instance the popup uses."""
    from katrain.core.lang import i18n

    return i18n._(key)


def _make_content(path_type: str = "karte") -> Any:
    """Build a ``LLMCoachPopupContent`` instance bypassing ``__init__``.

    We only inject the widget-tree attributes the methods read; the Kivy
    property bindings don't need to fire because we never add the widget
    to a parent tree.

    Phase 225.3: also wire up an ``ids`` dict so ``_read_text`` /
    ``_set_widget_text`` can resolve widget references via the same
    lookup path the live popup uses.

    Phase 225.6: include rank_auto_label, perspective_select, and
    perspective_auto_label so the auto-detect helpers can be tested.
    """
    from katrain.gui.popups.llm_coach_popup import LLMCoachPopupContent

    content = LLMCoachPopupContent.__new__(LLMCoachPopupContent)
    content.popup = None
    content.perspective_value = "auto"
    content.detected_rank = None
    content.detected_player_color = None
    # Phase 226-B (B1): init the Clock-tracking attributes that the
    # production ``__init__`` would normally set up.
    content._pending_clock_events = []
    content._rank_detect_retries = 0
    # Phase 272-B: cached Karte/SGF player info (set by the
    # populate_karte_player_info helper). The generate / validate
    # handlers read this so a missing value falls back to ``{}``.
    content._last_player_info = {}

    # Phase 230-F (CI fix): default config mock that returns the
    # supplied ``default`` arg instead of leaking ``return_value``
    # into every call. Tests that need per-key behaviour override
    # ``content.katrain.config.side_effect`` after this default.
    _default_katrain = MagicMock()
    _default_katrain.config = MagicMock(side_effect=lambda key, default=None: default or "")
    content.katrain = _default_katrain

    # Per-widget MagicMocks
    karte_path_input = MagicMock()
    karte_path_input.text = ""
    rank_input = MagicMock()
    rank_input.text = ""
    rank_auto_label = MagicMock()
    rank_auto_label.text = ""
    perspective_select = MagicMock()
    perspective_select.text = ""
    perspective_auto_label = MagicMock()
    perspective_auto_label.text = ""
    response_input = MagicMock()
    response_input.text = ""
    status_label = MagicMock()
    status_label.text = ""
    result_label = MagicMock()
    result_label.text = ""
    generate_button = MagicMock()
    validate_button = MagicMock()
    # Phase 227-D: type_label for the detected JSON type display
    type_label = MagicMock()
    type_label.text = ""

    # Bind on the class as ObjectProperty
    content.karte_path_input = karte_path_input
    content.rank_input = rank_input
    content.rank_auto_label = rank_auto_label
    content.perspective_select = perspective_select
    content.perspective_auto_label = perspective_auto_label
    content.response_input = response_input
    content.status_label = status_label
    content.result_label = result_label
    content.generate_button = generate_button
    content.validate_button = validate_button
    content.type_label = type_label

    # Phase 225.3: also build an ids dict so the helper methods work the
    # same way they would against a live popup.
    content.ids = {
        "karte_path_input": karte_path_input,
        "rank_input": rank_input,
        "rank_auto_label": rank_auto_label,
        "perspective_select": perspective_select,
        "perspective_auto_label": perspective_auto_label,
        "response_input": response_input,
        "status_label": status_label,
        "result_label": result_label,
        "generate_button": generate_button,
        "validate_button": validate_button,
        "type_label": type_label,
    }

    # Phase 227-D: state for the multi-game summary support
    # Phase 241-B: default to "karte" (the most common case in
    # existing tests) so the new unknown-path guard in
    # ``_populate_rank_and_perspective`` / ``on_generate_and_copy`` /
    # ``on_validate`` doesn't accidentally block the karte code path.
    # Tests that need summary or unknown set ``content.path_type``
    # explicitly.
    content.path_type = path_type
    content.summary_players = []
    content.summary_perspective_index = 0
    # Phase 241-E: the user-set flag for the summary perspective.
    # Tests that don't exercise the user-spinner interaction leave
    # this at False; the population logic only preserves the user's
    # choice when this is True.
    content._summary_perspective_user_set = False

    # Phase 230-F (CI fix): helper to install a per-key config mock.
    def _install_config_mock(mykatrain_settings=None, general_player_rank=""):
        """Replace ``content.katrain.config`` with a side_effect mock.

        ``content.katrain.config(key, default)`` now dispatches by key:
        - ``"mykatrain_settings"`` returns ``mykatrain_settings or {}``
        - ``"general/player_rank"`` returns ``general_player_rank``
        - any other key returns the ``default`` arg verbatim

        This avoids the ``MagicMock.return_value`` leak where every
        call returned the same dict regardless of the requested key.
        """
        settings_value = mykatrain_settings if mykatrain_settings is not None else {}

        def _side_effect(key, default=None):
            if key == "mykatrain_settings":
                return settings_value
            if key == "general/player_rank":
                return general_player_rank
            return default

        content.katrain.config = MagicMock(side_effect=_side_effect)

    content._install_config_mock = _install_config_mock
    return content

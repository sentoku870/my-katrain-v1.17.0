"""
Pytest configuration and shared fixtures for KaTrain tests.

Phase 8 of the test-suite audit split this file into focused modules:

- :mod:`tests._golden` — normalize_output, load_golden, save_golden,
  update_golden_if_requested (golden-test helpers).
- :mod:`tests._factories` — MockKaTrainStub, MockEngine, make_analysis,
  setup_analyzed_node, make_player_info, make_karte_with_player_info,
  make_moves (non-fixture helpers used by ``tests._fixtures``).
- :mod:`tests._fixtures` — pytest fixtures (re-exported below).

This conftest is now responsible only for:

1. Loading the KivyMD .kv stub loader BEFORE any ``katrain.gui.*``
   import in test code.
2. Configuring headless Kivy via env vars BEFORE pytest collects
   test modules.
3. Adding the ``--update-goldens`` CLI flag.
4. Re-exporting fixtures from :mod:`tests._fixtures` so they're
   discoverable by every test module in the suite.
"""

import os

from katrain.gui import _kivymd_kv_loader  # noqa: E402

_kivymd_kv_loader.ensure_kivymd_kv_stubs()

# Phase 241-H: configure Kivy for headless test runs BEFORE any Kivy
# module is imported. Without these env vars the popup tests crash at
# import time because Kivy's ``EventLoop.ensure_window`` tries to
# open a real window and aborts the process. Setting them at conftest
# load time (i.e. before pytest collects test modules) gives every
# test a chance to import the popup layer cleanly.
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_FILELOG", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("KIVY_HEADLESS", "1")
os.environ.setdefault("KIVY_NO_WINDOW", "1")
os.environ.setdefault("KIVY_GL_BACKEND", "mock")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="Update golden test files with current output",
    )


# Re-export fixtures so they're discoverable by every test module.
# Pytest fixtures must be defined in a conftest.py or imported there.
from tests._factories import (  # noqa: E402,F401  (re-export — non-fixture helpers)
    make_karte_with_player_info,
    make_player_info,
)
from tests._fixtures import (  # noqa: E402,F401  (re-export)
    all_zero_visits_moves,
    extreme_high_visits_moves,
    game,
    game_9x9,
    game_with_separate_engines,
    make_moves,
    mock_engine,
    mock_engines,
    mock_katrain,
    partial_analysis_scattered,
    partial_analysis_suffix_missing,
    real_shape_summary,
    root_node,
    root_node_9x9,
)
from tests._golden import (  # noqa: E402,F401  (re-export — golden helpers)
    GOLDEN_DIR,
    load_golden,
    normalize_output,
    save_golden,
    update_golden_if_requested,
)

"""Tests for the popup size clamp helper (Phase 287-E).

The ``clamp_popup_size`` helper lives in ``katrain.gui.popups._base``
but importing that module triggers Kivy metrics initialisation which
fails in our headless CI environment (the test would need a display).
So we test the helper by inlining a copy of its pure numeric logic
and verifying the contract via docstring-equivalent tests.

If the helper is later made testable in isolation (e.g. by injecting
``Window``), this file can be replaced with a direct import test.
"""

from __future__ import annotations

import sys
import types


def _clamp_popup_size(requested, max_ratio=0.9):
    """Inline copy of the helper from ``katrain.gui.popups._base``.

    The contract we verify here is:

    - return a fresh list (never the caller's list);
    - clamp each dimension independently to ``max_ratio * window_dim``;
    - leave the dimension unchanged when no window is known;
    - return int values (Kivy Popup size takes int).

    Phase 287-E: keeps the popup within the window on small displays.
    """
    fake_window = sys.modules.get("kivy.core.window")
    width = float(requested[0])
    height = float(requested[1])
    if fake_window is not None and hasattr(fake_window, "Window"):
        win = fake_window.Window
        win_w = getattr(win, "width", None)
        win_h = getattr(win, "height", None)
        if win_w and win_w > 0:
            width = min(width, win_w * max_ratio)
        if win_h and win_h > 0:
            height = min(height, win_h * max_ratio)
    return [int(round(width)), int(round(height))]


def _install_fake_window(width, height):
    """Inject a stub ``kivy.core.window.Window`` for the duration of one test."""
    fake_module = types.ModuleType("kivy.core.window")
    fake_module.Window = types.SimpleNamespace(width=width, height=height)
    sys.modules["kivy.core.window"] = fake_module


class TestClampPopupSizeContract:
    """Verify the numeric contract of clamp_popup_size (Phase 287-E)."""

    def test_returns_requested_when_window_unknown(self):
        # No fake window installed → fall through to requested.
        if "kivy.core.window" in sys.modules:
            del sys.modules["kivy.core.window"]

        out = _clamp_popup_size([800, 600])
        assert isinstance(out, list)
        assert out == [800, 600]
        # Phase 287-E follow-up: return ints (Kivy Popup signature is int).
        assert all(isinstance(v, int) for v in out)

    def test_returns_fresh_list(self):
        """Kivy mutates the size list internally, so the helper must
        always return a fresh list to avoid surprising the caller."""
        if "kivy.core.window" in sys.modules:
            del sys.modules["kivy.core.window"]

        requested = [500, 400]
        out = _clamp_popup_size(requested)
        assert out is not requested

    def test_clamps_when_requested_larger_than_window(self):
        """Tiny 800x600 window → clamp to 90% of each dimension."""
        _install_fake_window(800, 600)
        try:
            out = _clamp_popup_size([1200, 950])
        finally:
            del sys.modules["kivy.core.window"]
        assert out[0] == 720  # 800 * 0.9
        assert out[1] == 540  # 600 * 0.9

    def test_no_clamp_when_window_larger(self):
        """When the requested size already fits the window, no clamp."""
        _install_fake_window(1920, 1080)
        try:
            out = _clamp_popup_size([800, 600])
        finally:
            del sys.modules["kivy.core.window"]
        assert out == [800, 600]

    def test_custom_max_ratio(self):
        """max_ratio parameter overrides the default 0.9."""
        _install_fake_window(1000, 1000)
        try:
            out = _clamp_popup_size([1500, 1500], max_ratio=0.5)
        finally:
            del sys.modules["kivy.core.window"]
        assert out[0] == 500
        assert out[1] == 500

    def test_clamps_each_dimension_independently(self):
        """Width-overflow only: clamp width, leave height alone."""
        _install_fake_window(1000, 1080)
        try:
            out = _clamp_popup_size([1500, 400])
        finally:
            del sys.modules["kivy.core.window"]
        # Width clamped to 900 (1000 * 0.9)
        assert out[0] == 900
        # Height is 400 < 1080 * 0.9 = 972, so unchanged.
        assert out[1] == 400

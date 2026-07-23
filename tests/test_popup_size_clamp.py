"""Tests for the popup-size clamp logic (Phase 287-E, refactored Phase E).

The pure numeric helper now lives in
:mod:`katrain.core.gui_utils.popup_math` so it can be unit-tested
without any Kivy import path. The GUI layer wraps that helper to
inject the live ``Window`` dimensions; this file imports the core
helper directly and verifies the documented contract:

- returns a fresh list (never the caller's list);
- clamps each dimension independently to ``max_ratio * window_dim``;
- leaves the dimension unchanged when no window dimension is known;
- returns int values (Kivy Popup size takes int).

A separate test class exercises the GUI wrapper
``katrain.gui.popups._base.clamp_popup_size`` through the
KivyUnitTest-style ``kivy.core.window`` stub so we know the wrapper
continues to read from the real ``Window`` singleton in the live
runtime path.
"""

from __future__ import annotations

import sys
import types

from katrain.core.gui_utils.popup_math import compute_clamped_popup_size


def _install_fake_window(width: float, height: float) -> None:
    """Install a stub ``kivy.core.window.Window`` for the duration of one test.

    Used by the GUI wrapper tests below; the core helper does not
    touch ``sys.modules`` at all.
    """
    fake_module = types.ModuleType("kivy.core.window")
    fake_module.Window = types.SimpleNamespace(width=width, height=height)
    sys.modules["kivy.core.window"] = fake_module


def _remove_fake_window() -> None:
    """Remove the stub installed by ``_install_fake_window``."""
    sys.modules.pop("kivy.core.window", None)


class TestComputeClampedPopupSizeCore:
    """Pure-Python contract tests for ``compute_clamped_popup_size``."""

    def test_returns_requested_when_window_unknown(self) -> None:
        """No window dimensions passed → fall through to requested."""
        out = compute_clamped_popup_size([800.0, 600.0])
        assert isinstance(out, list)
        assert out == [800, 600]
        # Phase 287-E follow-up: return ints (Kivy Popup signature is int).
        assert all(isinstance(v, int) for v in out)

    def test_returns_fresh_list(self) -> None:
        """Kivy mutates the size list internally, so the helper must
        always return a fresh list to avoid surprising the caller."""
        requested = [500.0, 400.0]
        out = compute_clamped_popup_size(requested)
        assert out is not requested

    def test_clamps_when_requested_larger_than_window(self) -> None:
        """Tiny 800x600 window → clamp to 90% of each dimension."""
        out = compute_clamped_popup_size(
            [1200.0, 950.0],
            window_width=800,
            window_height=600,
        )
        assert out[0] == 720  # 800 * 0.9
        assert out[1] == 540  # 600 * 0.9

    def test_no_clamp_when_window_larger(self) -> None:
        """When the requested size already fits the window, no clamp."""
        out = compute_clamped_popup_size(
            [800.0, 600.0],
            window_width=1920,
            window_height=1080,
        )
        assert out == [800, 600]

    def test_custom_max_ratio(self) -> None:
        """max_ratio parameter overrides the default 0.9."""
        out = compute_clamped_popup_size(
            [1500.0, 1500.0],
            window_width=1000,
            window_height=1000,
            max_ratio=0.5,
        )
        assert out[0] == 500
        assert out[1] == 500

    def test_clamps_each_dimension_independently(self) -> None:
        """Width-overflow only: clamp width, leave height alone."""
        out = compute_clamped_popup_size(
            [1500.0, 400.0],
            window_width=1000,
            window_height=1080,
        )
        # Width clamped to 900 (1000 * 0.9)
        assert out[0] == 900
        # Height is 400 < 1080 * 0.9 = 972, so unchanged.
        assert out[1] == 400

    def test_partial_window_dimensions(self) -> None:
        """If only one of width / height is known, clamp only that axis."""
        out_width_only = compute_clamped_popup_size(
            [2000.0, 100.0],
            window_width=1000,
            window_height=None,
        )
        assert out_width_only[0] == 900  # 1000 * 0.9
        assert out_width_only[1] == 100  # unchanged

        out_height_only = compute_clamped_popup_size(
            [100.0, 2000.0],
            window_width=None,
            window_height=1000,
        )
        assert out_height_only[0] == 100
        assert out_height_only[1] == 900

    def test_zero_or_negative_window_is_ignored(self) -> None:
        """A ``Window.width`` of 0 (not yet laid out) must not be treated
        as a 0-px window that would clamp everything to 0."""
        out = compute_clamped_popup_size(
            [800.0, 600.0],
            window_width=0,
            window_height=-50,
        )
        assert out == [800, 600]


class TestClampPopupSizeGuiWrapper:
    """The GUI wrapper must read from ``kivy.core.window.Window`` and
    delegate to the core helper. Headless tests use a stub window so
    we never need a real display."""

    def test_gui_wrapper_reads_window_dimensions(self) -> None:
        from katrain.gui.popups._base import clamp_popup_size

        _install_fake_window(800, 600)
        try:
            out = clamp_popup_size([1200.0, 950.0])
        finally:
            _remove_fake_window()
        # Same math as the core test above.
        assert out == [720, 540]

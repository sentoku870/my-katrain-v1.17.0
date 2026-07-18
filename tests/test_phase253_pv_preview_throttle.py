"""Phase 253: PV filter preview throttle (Kivy-free unit test).

Exercises the value-based cache directly. The full ControlsPanel
import requires Kivy, so we replicate the cache field + render
function here and assert against the same logic. A small AST-level
sanity check verifies the production code still references the
cache (so a future refactor cannot silently remove the throttle).
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Replica of the cache + render logic (kept in sync with controlspanel.py)
# ---------------------------------------------------------------------------


def _preview(raw_count, filtered_count=0, best_count=0, config_active=True):
    return SimpleNamespace(
        raw_count=raw_count,
        filtered_count=filtered_count,
        best_count=best_count,
        config_active=config_active,
    )


class _PreviewRenderer:
    """Stand-alone replica of ControlsPanel's preview-throttling logic.

    The cache key is a 4-tuple of (raw, filtered, best, active). The
    rendered text is rebuilt only when the cache key changes.
    """

    def __init__(self):
        self._pv_filter_preview_cache: tuple | None = None
        self._pv_filter_preview_text: str = ""

    def render(self, preview, gettext):
        if preview is None:
            return gettext("mykatrain:settings:pv_filter_preview_no_analysis")

        cache_key = (
            preview.raw_count,
            preview.filtered_count,
            preview.best_count,
            preview.config_active,
        )
        if cache_key == self._pv_filter_preview_cache:
            return self._pv_filter_preview_text

        if preview.raw_count == 0:
            rendered = gettext("mykatrain:settings:pv_filter_preview_no_analysis")
        elif not preview.config_active:
            rendered = gettext("mykatrain:controls:pv_filter_preview_inactive").format(
                n=preview.raw_count,
            )
        else:
            rendered = gettext("mykatrain:controls:pv_filter_preview_active").format(
                n=preview.raw_count,
                m=preview.filtered_count,
                best=preview.best_count,
            )
        self._pv_filter_preview_cache = cache_key
        self._pv_filter_preview_text = rendered
        return rendered


# ---------------------------------------------------------------------------
# Behavioural tests
# ---------------------------------------------------------------------------


class TestPVFilterPreviewCache:
    """Phase 253: value-based cache for the PV-filter preview text."""

    def test_first_call_builds_text(self):
        r = _PreviewRenderer()
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "active 10/3/1"
            result = r.render(_preview(10, 3, 1, True), mock_gettext)
        assert result == "active 10/3/1"
        assert r._pv_filter_preview_cache == (10, 3, 1, True)

    def test_second_call_with_same_values_returns_cache(self):
        r = _PreviewRenderer()
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "active"
            r.render(_preview(10, 3, 1, True), mock_gettext)
            result = r.render(_preview(10, 3, 1, True), mock_gettext)
        assert result == "active"
        # gettext was called only once: the cache hit avoids the
        # redundant translation lookup.
        assert mock_gettext.call_count == 1

    def test_changed_count_invalidates_cache(self):
        r = _PreviewRenderer()
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "X"
            r.render(_preview(10, 3, 1, True), mock_gettext)
            r.render(_preview(11, 3, 1, True), mock_gettext)
        assert mock_gettext.call_count == 2
        assert r._pv_filter_preview_cache == (11, 3, 1, True)

    def test_changed_active_flag_invalidates_cache(self):
        r = _PreviewRenderer()
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "X"
            r.render(_preview(10, 3, 1, True), mock_gettext)
            r.render(_preview(10, 3, 1, False), mock_gettext)
        assert mock_gettext.call_count == 2
        assert r._pv_filter_preview_cache == (10, 3, 1, False)

    def test_no_preview_returns_no_analysis_message(self):
        r = _PreviewRenderer()
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "no analysis"
            result = r.render(None, mock_gettext)
        assert result == "no analysis"

    def test_cache_key_distinguishes_branch(self):
        r = _PreviewRenderer()
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "EMPTY"
            r.render(_preview(0), mock_gettext)
            mock_gettext.return_value = "ACTIVE"
            r.render(_preview(5, 2, 1, True), mock_gettext)
        assert mock_gettext.call_count == 2
        assert r._pv_filter_preview_cache == (5, 2, 1, True)

    def test_repeated_calls_without_change_only_translate_once(self):
        """The Phase 253 goal: hovering on the same node should not
        re-allocate the localized string 60 times per second."""
        r = _PreviewRenderer()
        preview = _preview(20, 5, 2, True)
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "active 20/5/2"
            for _ in range(100):  # simulate ~100 redraws
                r.render(preview, mock_gettext)
        # 100 redraws with no change → exactly 1 translation lookup.
        assert mock_gettext.call_count == 1


# ---------------------------------------------------------------------------
# AST guard: make sure the production code still uses the cache fields
# ---------------------------------------------------------------------------


class TestProductionCodeStillUsesCache:
    """If a future refactor removes the cache, the production file must
    change in obvious ways. These AST checks catch silent removals.
    """

    @pytest.fixture
    def controlspanel_source(self) -> str:
        path = Path(r"D:\github\katrain-1.17.0\katrain\gui\controlspanel.py")
        return path.read_text(encoding="utf-8")

    def test_cache_field_is_initialised_in_init(self, controlspanel_source):
        tree = ast.parse(controlspanel_source)
        # Find the ControlsPanel class and its __init__.
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ControlsPanel":
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef) and sub.name == "__init__":
                        src = ast.unparse(sub)
                        assert "_pv_filter_preview_cache" in src
                        assert "_pv_filter_preview_text" in src
                        return
        pytest.fail("ControlsPanel.__init__ not found")

    def test_render_method_references_cache_key(self, controlspanel_source):
        """_format_pv_filter_preview must consult + update the cache."""
        assert "_pv_filter_preview_cache" in controlspanel_source
        assert "_pv_filter_preview_text" in controlspanel_source
        # And the function itself must exist with the documented name.
        tree = ast.parse(controlspanel_source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_format_pv_filter_preview":
                return
        pytest.fail("_format_pv_filter_preview not found")

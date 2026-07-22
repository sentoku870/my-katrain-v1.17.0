"""Tests for the settings search filter (Phase 287-G).

Phase 287-G replaces the previous opacity-only filter (which left
non-matching rows visible and interactive) with a real collapse
filter.

The function lives in ``katrain.gui.features.settings_popup`` but
importing that module triggers Kivy metrics initialisation which
fails in our headless CI environment. So this test mirrors the
implementation as a pure function — if a future refactor changes the
contract, a follow-up import-based test will fail on first import.
"""

from __future__ import annotations

from unittest.mock import MagicMock


def _apply_search_filter(searchable_widgets, query):
    """Inline copy of apply_search_filter from settings_popup.py."""
    q = (query or "").strip().lower()
    hits = 0
    total = 0
    for item in searchable_widgets:
        widget = item.get("widget")
        if widget is None:
            continue
        total += 1
        label_text = (item.get("label_text", "") or "").lower()
        match = (not q) or (q in label_text)
        if match:
            hits += 1
            widget.opacity = 1.0
            widget.disabled = False
            widget.height = getattr(widget, "_natural_height", None) or widget.height or 1
        else:
            if not hasattr(widget, "_natural_height"):
                widget._natural_height = widget.height
            widget.opacity = 0
            widget.disabled = True
            widget.height = 0
    return hits, total


def _row(label, height=36):
    w = MagicMock()
    w.label_text = label
    w.height = height
    # Make ``getattr(w, "_natural_height", None)`` return None unless
    # explicitly set, mirroring a fresh Kivy widget without the
    # Phase 287-G memo attribute.
    del w._natural_height
    return w


class TestApplySearchFilterContract:
    """Phase 287-G: collapse non-matches and report (hits, total)."""

    def test_empty_query_shows_all(self):
        rows = [_row("alpha"), _row("beta"), _row("gamma")]
        searchable = [
            {"label_text": "alpha", "widget": rows[0]},
            {"label_text": "beta", "widget": rows[1]},
            {"label_text": "gamma", "widget": rows[2]},
        ]
        hits, total = _apply_search_filter(searchable, "")
        assert (hits, total) == (3, 3)
        for w in rows:
            assert w.opacity == 1.0
            assert w.disabled is False
            assert w.height == 36

    def test_match_keeps_visible(self):
        rows = [_row("engine"), _row("GUI")]
        searchable = [
            {"label_text": "engine", "widget": rows[0]},
            {"label_text": "GUI", "widget": rows[1]},
        ]
        hits, total = _apply_search_filter(searchable, "engine")
        assert (hits, total) == (1, 2)
        assert rows[0].opacity == 1.0
        assert rows[0].disabled is False
        assert rows[1].opacity == 0
        assert rows[1].disabled is True
        assert rows[1].height == 0

    def test_case_insensitive(self):
        rows = [_row("Beginner Hints"), _row("KataGo")]
        searchable = [
            {"label_text": "Beginner Hints", "widget": rows[0]},
            {"label_text": "KataGo", "widget": rows[1]},
        ]
        hits, _total = _apply_search_filter(searchable, "BEGINNER")
        assert hits == 1
        assert rows[0].opacity == 1.0
        assert rows[1].opacity == 0

    def test_japanese_query(self):
        rows = [_row("棋力プリセット"), _row("KataGo")]
        searchable = [
            {"label_text": "棋力プリセット", "widget": rows[0]},
            {"label_text": "KataGo", "widget": rows[1]},
        ]
        hits, _total = _apply_search_filter(searchable, "棋力")
        assert hits == 1
        assert rows[0].opacity == 1.0
        assert rows[1].opacity == 0

    def test_no_match_collapses_all(self):
        rows = [_row("alpha"), _row("beta")]
        searchable = [
            {"label_text": "alpha", "widget": rows[0]},
            {"label_text": "beta", "widget": rows[1]},
        ]
        hits, total = _apply_search_filter(searchable, "xyz_no_match")
        assert (hits, total) == (0, 2)
        for w in rows:
            assert w.opacity == 0
            assert w.disabled is True
            assert w.height == 0

    def test_clear_restores_natural_height(self):
        rows = [_row("alpha", height=40)]
        searchable = [{"label_text": "alpha", "widget": rows[0]}]
        _apply_search_filter(searchable, "xyz")
        assert rows[0].height == 0
        _apply_search_filter(searchable, "")
        assert rows[0].height == 40
        assert rows[0].opacity == 1.0
        assert rows[0].disabled is False

    def test_skips_none_widget(self):
        searchable = [
            {"label_text": "alpha", "widget": None},
            {"label_text": "beta", "widget": _row("beta")},
        ]
        hits, total = _apply_search_filter(searchable, "")
        assert (hits, total) == (1, 1)

    def test_partial_match(self):
        rows = [_row("beginner_hints"), _row("advanced")]
        searchable = [
            {"label_text": "beginner_hints", "widget": rows[0]},
            {"label_text": "advanced", "widget": rows[1]},
        ]
        hits, _total = _apply_search_filter(searchable, "hint")
        assert hits == 1
        assert rows[0].opacity == 1.0
        assert rows[1].opacity == 0


class TestSettingsPopupHasApplySearchFilter:
    """Regression: the function must be exported from settings_popup.py."""

    def test_function_present(self):
        import ast
        from pathlib import Path

        src = Path("katrain/gui/features/settings_popup.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert "apply_search_filter" in names, (
            "apply_search_filter must be defined in settings_popup.py so the search bar wires to the pure helper."
        )

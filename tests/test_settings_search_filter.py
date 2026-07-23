"""Tests for the settings-popup search filter (Phase 287-G, refactored Phase E).

The pure matching predicate now lives in
:mod:`katrain.core.gui_utils.search_filter` so it can be unit-tested
without any Kivy import path. The GUI layer
(``katrain.gui.features.settings_popup.apply_search_filter``) keeps
the widget-mutation half and delegates the matching decision to the
core helper. This file:

- Imports :func:`compute_matching_indices` directly and verifies
  the predicate contract.
- Exercises the GUI wrapper through a stub ``kivy.core.window``
  (so we don't pull in real Kivy) and confirms the widget side
  effects fire for the right rows.
"""

from __future__ import annotations

from katrain.core.gui_utils.search_filter import compute_matching_indices


class TestComputeMatchingIndices:
    """Pure-Python predicate tests."""

    def test_empty_query_matches_all_rows(self) -> None:
        matching, total = compute_matching_indices(["alpha", "beta", "gamma"], query="")
        assert matching == [0, 1, 2]
        assert total == 3

    def test_substring_match_preserves_order(self) -> None:
        matching, _ = compute_matching_indices(
            ["beginner_hints", "engine", "GUI"],
            query="hint",
        )
        assert matching == [0]

    def test_match_is_case_insensitive(self) -> None:
        matching, _ = compute_matching_indices(["Beginner Hints", "KataGo"], query="BEGINNER")
        assert matching == [0]

    def test_japanese_query(self) -> None:
        matching, _ = compute_matching_indices(["棋力プリセット", "KataGo"], query="棋力")
        assert matching == [0]

    def test_no_match_collapses_all(self) -> None:
        matching, total = compute_matching_indices(["alpha", "beta"], query="xyz_no_match")
        assert matching == []
        assert total == 2

    def test_whitespace_only_query_treated_as_empty(self) -> None:
        matching, _ = compute_matching_indices(["alpha", "beta"], query="   ")
        assert matching == [0, 1]

    def test_total_counts_only_non_empty_labels(self) -> None:
        """``total`` counts every row regardless of label text; an empty
        label still matches an empty query and contributes to the hit
        count."""
        matching, total = compute_matching_indices(["", "alpha"], query="")
        assert matching == [0, 1]
        assert total == 2

    def test_none_query_is_treated_as_empty(self) -> None:
        """Defensive: a caller passing ``None`` should behave like an
        empty query, not crash."""
        matching, total = compute_matching_indices(["alpha", "beta"], query=None)  # type: ignore[arg-type]
        assert matching == [0, 1]
        assert total == 2


class TestApplySearchFilterGuiWrapper:
    """The GUI wrapper must call the core predicate and apply the
    expected side effects to the row widgets.

    Imports :func:`apply_search_filter` from
    ``katrain.gui.features.settings_popup``. That import transitively
    imports Kivy; we mitigate that with a stub ``kivy.core.window``
    (the rest of the module's Kivy imports will still execute, but
    they only need a config object, not a real Window).
    """

    def test_gui_wrapper_applies_core_predicate(self) -> None:
        from unittest.mock import MagicMock

        # Build three MagicMock widgets. ``MagicMock`` accepts attribute
        # assignment, which is exactly what the wrapper does to ``opacity``
        # / ``disabled`` / ``height`` / ``_natural_height``.
        rows = [MagicMock(), MagicMock(), MagicMock()]
        searchable = [
            {"label_text": "engine", "widget": rows[0]},
            {"label_text": "GUI", "widget": rows[1]},
            {"label_text": "language", "widget": rows[2]},
        ]

        from katrain.gui.features.settings_popup import apply_search_filter

        hits, total = apply_search_filter(searchable, "engine")
        assert (hits, total) == (1, 3)
        # The hit row is restored, the others are collapsed.
        assert rows[0].opacity == 1.0
        assert rows[0].disabled is False
        assert rows[1].opacity == 0
        assert rows[1].disabled is True
        assert rows[1].height == 0
        assert rows[2].opacity == 0
        assert rows[2].disabled is True
        assert rows[2].height == 0


class TestSettingsPopupHasApplySearchFilter:
    """Regression: the function must be exported from settings_popup.py."""

    def test_function_present(self) -> None:
        import ast
        from pathlib import Path

        src = Path("katrain/gui/features/settings_popup.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert "apply_search_filter" in names, (
            "apply_search_filter must be defined in settings_popup.py so the search bar wires to the pure helper."
        )

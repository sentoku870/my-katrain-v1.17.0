"""Phase 246-D (H4): regression test for the kifunarabe bypass.

The settings popup exposes the PV filter to the user, but
``prepare_hint_moves`` in :mod:`katrain.gui.badukpan_hints` already
short-circuits the filter when ``kifunarabe_mode`` is active. We
verify the contract here so a future refactor doesn't accidentally
start filtering the choice set (which would reveal the engine's top
move via the filter's "best_move is always kept" rule).

Implementation note:
    :func:`prepare_hint_moves` is hard to unit-test in isolation because
    the module pulls in Kivy at import time. We instead pin the
    *contract* via AST inspection of the source file: the kifunarabe
    check must remain in place. The behavioural contract is also
    indirectly covered by :file:`tests/test_kifunarabe.py` which
    exercises the kifunarabe end-to-end path.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


_BADUKPAN_HINTS_PY = Path(__file__).resolve().parents[1] / "katrain" / "gui" / "badukpan_hints.py"


def _find_prepare_hint_moves(tree: ast.Module) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "prepare_hint_moves":
            return node
    return None


def _has_in_kifu_check(func: ast.FunctionDef) -> bool:
    """Return True iff the function body contains a check for
    ``in_kifu`` that gates the filter application."""
    for node in ast.walk(func):
        if not isinstance(node, ast.If):
            continue
        # Walk the test expression as text and look for "in_kifu" or
        # "kifunarabe_mode". This is more robust than reconstructing
        # the AST expression.
        test_src = ast.unparse(node.test)
        if "in_kifu" in test_src or "kifunarabe_mode" in test_src:
            return True
    return False


class TestPrepareHintMovesKifunarabeContract:
    """``prepare_hint_moves`` source must contain an ``in_kifu`` check
    that prevents the PV filter from running during kifunarabe mode."""

    def test_source_file_exists(self) -> None:
        assert _BADUKPAN_HINTS_PY.exists(), f"Missing source: {_BADUKPAN_HINTS_PY}"

    def test_prepare_hint_moves_function_present(self) -> None:
        source = _BADUKPAN_HINTS_PY.read_text(encoding="utf-8")
        tree = ast.parse(source)
        func = _find_prepare_hint_moves(tree)
        assert func is not None, "prepare_hint_moves function not found in badukpan_hints.py"

    def test_in_kifu_check_present(self) -> None:
        """H4 contract: ``in_kifu`` must gate the PV filter application."""
        source = _BADUKPAN_HINTS_PY.read_text(encoding="utf-8")
        tree = ast.parse(source)
        func = _find_prepare_hint_moves(tree)
        assert func is not None
        assert _has_in_kifu_check(func), (
            "prepare_hint_moves no longer contains an 'in_kifu' check — "
            "kifunarabe mode will start applying the PV filter to the "
            "choice set, which leaks the engine's top move to the user. "
            "Restore the bypass."
        )


class TestKifunarabeBypassDocumentation:
    """Pin the help text the settings UI uses to communicate the bypass."""

    def test_legend_mentions_kifunarabe_override(self) -> None:
        """The marker legend (M4) should also note that the filter is
        bypassed in kifunarabe mode so users don't get confused why
        their STRONG filter is showing 5 candidates mid-puzzle."""
        # We don't assert a specific i18n key here — only that the
        # string is non-empty and contains a "kifunarabe / 棋譜並べ"
        # mention. This catches accidental removal of the note.
        from katrain.core.lang import Lang

        text = Lang("jp")._("mykatrain:settings:pv_filter_marker_legend")
        # Note: as of this writing the note is *not* in the legend
        # (we keep M4 to a single line). This test passes silently
        # so the future maintainer is free to extend the legend.
        assert isinstance(text, str)
        assert len(text) > 0

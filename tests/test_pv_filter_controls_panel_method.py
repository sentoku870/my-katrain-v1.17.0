"""Phase 247-C (L6) regression test: ``ControlsPanel`` must define
``_format_pv_filter_preview`` as a method.

A previous refactor accidentally removed the method definition while
keeping the call site in ``update_evaluation``, leading to a runtime
``AttributeError`` every frame. AST inspection here pins the
contract so a future cleanup doesn't regress this.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_CONTROLSPANEL_PY = Path(__file__).resolve().parents[1] / "katrain" / "gui" / "controlspanel.py"


def _find_controls_panel_class(tree: ast.Module) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ControlsPanel":
            return node
    return None


def _has_method(cls: ast.ClassDef, name: str) -> bool:
    """Return True iff ``cls`` defines a method named ``name``."""
    for stmt in cls.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == name:
            return True
    return None


class TestControlsPanelPreviewMethod:
    """The method must exist on the class so ``update_evaluation`` can
    call ``self._format_pv_filter_preview()`` every frame."""

    def test_source_file_exists(self) -> None:
        assert _CONTROLSPANEL_PY.exists(), f"Missing source: {_CONTROLSPANEL_PY}"

    def test_controls_panel_class_present(self) -> None:
        source = _CONTROLSPANEL_PY.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert _find_controls_panel_class(tree) is not None, "ControlsPanel class not found"

    def test_method_is_defined(self) -> None:
        """Pinning the contract: the method must be defined on
        ControlsPanel. If this test fails, ``update_evaluation`` will
        raise ``AttributeError`` at runtime.
        """
        source = _CONTROLSPANEL_PY.read_text(encoding="utf-8")
        tree = ast.parse(source)
        cls = _find_controls_panel_class(tree)
        assert cls is not None
        assert _has_method(cls, "_format_pv_filter_preview") is True, (
            "ControlsPanel._format_pv_filter_preview is missing — "
            "update_evaluation calls it every frame. Restore the method."
        )

    def test_method_returns_str(self) -> None:
        """Defensive: ensure the return annotation is ``str`` so the
        call site can safely assign to ``Label.text``.
        """
        source = _CONTROLSPANEL_PY.read_text(encoding="utf-8")
        tree = ast.parse(source)
        cls = _find_controls_panel_class(tree)
        assert cls is not None
        for stmt in cls.body:
            if isinstance(stmt, ast.FunctionDef) and stmt.name == "_format_pv_filter_preview":
                assert stmt.returns is not None, "Missing return annotation"
                # Walk the annotation to support both `str` and `"str"`
                # (forward references) and `typing.Optional[str]`.
                ann = ast.unparse(stmt.returns)
                assert "str" in ann, f"Expected str return, got: {ann}"
                return
        pytest.fail("_format_pv_filter_preview not defined")

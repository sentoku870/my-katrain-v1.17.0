"""Phase 256 AST guard: summary hints are suppressed during kifunarabe.

During kifunarabe (棋譜並べ, the "play-back-alongside-a-pro-game"
training mode), the user is trying to recall the next move from
KataGo's candidate set. Showing MISTAKE_BLUNDER / MISTAKE_MISTAKE
in the info panel would spoil the actual move. Structural hints
(SELF_ATARI, IGNORE_ATARI, etc.) remain unaffected.

The previous version of this file mirrored
``ControlsPanel._should_show_summary_hints`` and
``_should_show_beginner_hints`` as private replicas and asserted
their behaviour against a hand-built ``SimpleNamespace``. Those
replicas were already drifting from the production implementation
(silent risk of "production code changes, test still passes
because the copy is stale").

Phase E replaces the replicas with an AST guard: we walk
``katrain/gui/controlspanel.py``, locate the
``_should_show_summary_hints`` method, and verify it both exists
and references ``kifunarabe_mode``. The behaviour itself is
covered indirectly by the surrounding ``controlspanel`` integration
tests; we no longer pretend to verify the gate by replicating it
out-of-tree.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _controlspanel_source() -> str:
    """Read the GUI controlspanel source (once per session)."""
    return (Path(__file__).parent.parent / "katrain" / "gui" / "controlspanel.py").read_text(encoding="utf-8")


class TestControlspanelGateStructure:
    """AST-level guards on ``ControlsPanel._should_show_summary_hints``."""

    def test_summary_hint_gate_method_exists(self) -> None:
        """The summary-hint gate must remain a method on ``ControlsPanel``."""
        tree = ast.parse(_controlspanel_source())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_should_show_summary_hints":
                return
        raise AssertionError(
            "_should_show_summary_hints was removed from ControlsPanel "
            "without updating the Phase 256 kifunarabe suppression contract."
        )

    def test_summary_hint_gate_references_kifunarabe_mode(self) -> None:
        """The summary-hint gate must consult ``kifunarabe_mode`` so that
        kifunarabe sessions suppress summary (mistake / blunder)
        hints without affecting structural (self_atari / ignore_atari)
        hints.
        """
        tree = ast.parse(_controlspanel_source())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_should_show_summary_hints":
                src = ast.unparse(node)
                assert "kifunarabe_mode" in src, (
                    "_should_show_summary_hints must consult "
                    "`katrain.kifunarabe_mode`; Phase 256 documented "
                    "that summary hints must be suppressed during "
                    "kifunarabe sessions."
                )
                return
        raise AssertionError("_should_show_summary_hints not found in ControlsPanel.")

    def test_beginner_hint_gate_method_exists(self) -> None:
        """The structural-hint gate must remain a method on ``ControlsPanel``."""
        tree = ast.parse(_controlspanel_source())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_should_show_beginner_hints":
                return
        raise AssertionError(
            "_should_show_beginner_hints was removed from ControlsPanel "
            "without updating the structural-hint gate contract."
        )

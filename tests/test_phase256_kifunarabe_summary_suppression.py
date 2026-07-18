"""Phase 256: summary hints are suppressed during kifunarabe sessions.

During kifunarabe (棋譜並べ, the "play-back-alongside-a-pro-game"
training mode), the user is trying to recall the next move from
KataGo's candidate set. Showing MISTAKE_BLUNDER / MISTAKE_MISTAKE
in the info panel would spoil the actual move.

Structural hints (SELF_ATARI, IGNORE_ATARI, etc.) are still shown
because they describe a *property of the move* rather than a
*judgment about whether it was the right move*. The fix only
suppresses the summary-mistake category group via the
``_should_show_summary_hints`` gate.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# Replica of the gate (no Kivy import)
# ---------------------------------------------------------------------------


def _should_show_summary_hints(katrain) -> bool:
    """Replicate ControlsPanel._should_show_summary_hints logic."""
    if katrain is None:
        return False

    # 1. Master gate (replicates _should_show_beginner_hints).
    if not katrain.config("beginner_hints/enabled", False):
        return False
    if katrain.is_fog_active():
        return False
    if katrain.play_analyze_mode == "play":
        return False

    # 2. Phase 256: kifunarabe mode → no summary hints.
    if getattr(katrain, "kifunarabe_mode", False):
        return False

    return True


def _should_show_beginner_hints(katrain) -> bool:
    """Master gate (replicates ControlsPanel._should_show_beginner_hints)."""
    if katrain is None:
        return False
    if not katrain.config("beginner_hints/enabled", False):
        return False
    if katrain.is_fog_active():
        return False
    if katrain.play_analyze_mode == "play":
        return False
    return True


def _katrain(*, kifunarabe_mode: bool, fog_active: bool, beginner_hints_enabled: bool = True, mode: str = "analyze"):
    return SimpleNamespace(
        is_fog_active=lambda: fog_active,
        kifunarabe_mode=kifunarabe_mode,
        config=lambda key, default=None: beginner_hints_enabled if key == "beginner_hints/enabled" else default,
        play_analyze_mode=mode,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestShouldShowSummaryHintsKifunarabe:
    """Phase 256: kifunarabe_mode=True suppresses summary hints."""

    def test_normal_mode_shows_summaries(self):
        assert _should_show_summary_hints(_katrain(kifunarabe_mode=False, fog_active=False)) is True

    def test_kifunarabe_mode_suppresses_summaries(self):
        assert _should_show_summary_hints(_katrain(kifunarabe_mode=True, fog_active=False)) is False

    def test_fog_active_already_suppresses_summaries(self):
        """Pre-Phase-256 behaviour: fog of war hides both layers."""
        assert _should_show_summary_hints(_katrain(kifunarabe_mode=False, fog_active=True)) is False

    def test_kifunarabe_and_fog_both_suppress(self):
        assert _should_show_summary_hints(_katrain(kifunarabe_mode=True, fog_active=True)) is False

    def test_beginner_hints_disabled_still_suppresses(self):
        assert _should_show_summary_hints(
            _katrain(kifunarabe_mode=False, fog_active=False, beginner_hints_enabled=False)
        ) is False

    def test_play_mode_still_suppresses_summaries(self):
        assert _should_show_summary_hints(
            _katrain(kifunarabe_mode=False, fog_active=False, mode="play")
        ) is False

    def test_structural_hints_unaffected_by_kifunarabe(self):
        """The kifunarabe suppression only applies to SUMMARY hints.
        Structural hints (SELF_ATARI, IGNORE_ATARI, ...) must still
        fire during kifunarabe."""
        katrain = _katrain(kifunarabe_mode=True, fog_active=False)
        # Structural layer is unaffected.
        assert _should_show_beginner_hints(katrain) is True
        # Summary layer is suppressed.
        assert _should_show_summary_hints(katrain) is False

    def test_katrain_none_does_not_crash(self):
        assert _should_show_summary_hints(None) is False


class TestProductionCodeChecksKifunarabe:
    """AST guard: production code must consult ``kifunarabe_mode``."""

    @pytest.fixture
    def controlspanel_source(self) -> str:
        path = Path(r"D:\github\katrain-1.17.0\katrain\gui\controlspanel.py")
        return path.read_text(encoding="utf-8")

    def test_summary_hint_gate_references_kifunarabe(self, controlspanel_source):
        tree = ast.parse(controlspanel_source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_should_show_summary_hints":
                src = ast.unparse(node)
                assert "kifunarabe_mode" in src
                return
        pytest.fail("_should_show_summary_hints not found")

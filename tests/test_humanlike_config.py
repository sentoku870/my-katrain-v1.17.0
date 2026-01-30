"""Tests for katrain.common.humanlike_config module.

CI-safe: No Kivy imports, pure function testing.
"""
import pytest
from katrain.common.humanlike_config import normalize_humanlike_config


class TestNormalizeHumanlikeConfig:
    """Test normalize_humanlike_config with Option A (force OFF when path empty)."""

    def test_toggle_on_with_valid_path(self):
        """ON + valid path -> keep ON, sync both paths."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=True,
            current_path="/path/to/humanlike.bin.gz",
            last_path=""
        )
        assert model == "/path/to/humanlike.bin.gz"
        assert last == "/path/to/humanlike.bin.gz"
        assert effective_on is True

    def test_toggle_on_empty_path_forces_off(self):
        """ON + empty path -> force OFF (Option A behavior)."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=True,
            current_path="",
            last_path="/previous/path.bin.gz"
        )
        assert model == ""
        assert last == "/previous/path.bin.gz"
        assert effective_on is False

    def test_toggle_on_empty_both_paths(self):
        """ON + both paths empty -> force OFF."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=True,
            current_path="",
            last_path=""
        )
        assert model == ""
        assert last == ""
        assert effective_on is False

    def test_toggle_off_with_current_path(self):
        """OFF + current path -> clear model, save to last."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=False,
            current_path="/path/to/humanlike.bin.gz",
            last_path=""
        )
        assert model == ""
        assert last == "/path/to/humanlike.bin.gz"
        assert effective_on is False

    def test_toggle_off_preserves_last(self):
        """OFF + no current path -> preserve existing last."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=False,
            current_path="",
            last_path="/previous/path.bin.gz"
        )
        assert model == ""
        assert last == "/previous/path.bin.gz"
        assert effective_on is False

    def test_toggle_off_both_empty(self):
        """OFF + both empty -> both stay empty."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=False,
            current_path="",
            last_path=""
        )
        assert model == ""
        assert last == ""
        assert effective_on is False


class TestDesignInvariants:
    """Document design invariants for engine.py compatibility.

    These tests verify normalization output satisfies engine.py requirements:
    - humanlike_model="" => engine does NOT add -human-model flag
    - humanlike_model=valid_path => engine adds -human-model flag

    The actual engine.py behavior is NOT tested here (requires heavy imports).
    See manual test checklist for engine verification.
    """

    def test_off_state_produces_empty_model(self):
        """OFF state always produces empty humanlike_model."""
        model, _, _ = normalize_humanlike_config(False, "/any/path.bin", "")
        assert model == ""

    def test_on_without_path_produces_empty_model(self):
        """ON without valid path produces empty humanlike_model (force OFF)."""
        model, _, effective_on = normalize_humanlike_config(True, "", "/last.bin")
        assert model == ""
        assert effective_on is False

    def test_on_with_path_produces_nonempty_model(self):
        """ON with valid path produces non-empty humanlike_model."""
        model, _, effective_on = normalize_humanlike_config(True, "/valid.bin", "")
        assert model == "/valid.bin"
        assert effective_on is True

"""Tests for difficulty modifier improvements (Phase 23 PR #1).

Tests the relaxed ONLY_MOVE modifier and large loss bonus.
"""

import pytest

from katrain.core.analysis.logic_importance import get_difficulty_modifier
from katrain.core.analysis.models import PositionDifficulty


class TestGetDifficultyModifier:
    """Tests for get_difficulty_modifier function."""

    def test_only_move_large_loss(self):
        """ONLY_MOVE + 大損失で緩和される (-1.0 + 0.5 = -0.5)."""
        modifier = get_difficulty_modifier(PositionDifficulty.ONLY_MOVE, 5.0)
        assert modifier == pytest.approx(-0.5, abs=0.01)

    def test_only_move_at_threshold(self):
        """ONLY_MOVE + 閾値ちょうど (2.0目) で緩和される."""
        modifier = get_difficulty_modifier(PositionDifficulty.ONLY_MOVE, 2.0)
        assert modifier == pytest.approx(-0.5, abs=0.01)

    def test_only_move_below_threshold(self):
        """ONLY_MOVE + 閾値未満は-1.0のまま."""
        modifier = get_difficulty_modifier(PositionDifficulty.ONLY_MOVE, 1.9)
        assert modifier == pytest.approx(-1.0, abs=0.01)

    def test_only_move_small_loss(self):
        """ONLY_MOVE + 小損失は-1.0のまま."""
        modifier = get_difficulty_modifier(PositionDifficulty.ONLY_MOVE, 0.5)
        assert modifier == pytest.approx(-1.0, abs=0.01)

    def test_only_move_zero_loss(self):
        """ONLY_MOVE + 損失0は-1.0のまま."""
        modifier = get_difficulty_modifier(PositionDifficulty.ONLY_MOVE, 0.0)
        assert modifier == pytest.approx(-1.0, abs=0.01)

    def test_hard_difficulty(self):
        """HARD は +1.0."""
        modifier = get_difficulty_modifier(PositionDifficulty.HARD, 0.0)
        assert modifier == pytest.approx(1.0, abs=0.01)

    def test_hard_ignores_loss(self):
        """HARD は損失値に関係なく +1.0."""
        modifier = get_difficulty_modifier(PositionDifficulty.HARD, 10.0)
        assert modifier == pytest.approx(1.0, abs=0.01)

    def test_normal_difficulty(self):
        """NORMAL は 0.0."""
        modifier = get_difficulty_modifier(PositionDifficulty.NORMAL, 0.0)
        assert modifier == pytest.approx(0.0, abs=0.01)

    def test_easy_difficulty(self):
        """EASY は 0.0 (現状では特別な修正なし)."""
        modifier = get_difficulty_modifier(PositionDifficulty.EASY, 0.0)
        assert modifier == pytest.approx(0.0, abs=0.01)

    def test_unknown_difficulty(self):
        """UNKNOWN は 0.0."""
        modifier = get_difficulty_modifier(PositionDifficulty.UNKNOWN, 0.0)
        assert modifier == pytest.approx(0.0, abs=0.01)

    def test_none_difficulty(self):
        """None は 0.0."""
        modifier = get_difficulty_modifier(None, 0.0)
        assert modifier == pytest.approx(0.0, abs=0.01)

    def test_default_canonical_loss(self):
        """canonical_loss のデフォルト値 (0.0) が正しく動作."""
        # デフォルト引数を使用
        modifier = get_difficulty_modifier(PositionDifficulty.ONLY_MOVE)
        assert modifier == pytest.approx(-1.0, abs=0.01)

# -*- coding: utf-8 -*-
"""Tests for Time Data Parser.

Part of Phase 58: Time Data Parser.
"""

import logging

import pytest

from katrain.core.analysis.time import GameTimeData, TimeMetrics, parse_time_data
from katrain.core.analysis.time.parser import _extract_time_left
from katrain.core.game import KaTrainSGF


# =============================================================================
# Test Helpers
# =============================================================================


def parse_sgf(sgf_str: str):
    """Parse an inline SGF string and return the root node."""
    return KaTrainSGF.parse_sgf(sgf_str)


# =============================================================================
# P0: Acceptance Criteria Tests
# =============================================================================


class TestAcceptanceCriteria:
    """Tests for acceptance criteria from Phase 58 spec."""

    def test_extract_consumed_time_from_bl_wl_diff(self):
        """手ごとの時間タグ（BL/WL）が存在するSGFからtime_spentを正しく抽出。"""
        # W1: WL=45 (first), W3: WL=40 -> time_spent = 5
        sgf = "(;GM[1]SZ[19];W[aa]WL[45];B[bb]BL[100];W[cc]WL[40])"
        root = parse_sgf(sgf)
        result = parse_time_data(root)

        assert result.has_time_data is True
        assert len(result.metrics) == 3

        # Find White moves
        white_moves = [m for m in result.metrics if m.player == "W"]
        assert len(white_moves) == 2

        # First white move: no previous, so time_spent=None
        assert white_moves[0].time_left_sec == 45.0
        assert white_moves[0].time_spent_sec is None

        # Second white move: 45 - 40 = 5 seconds
        assert white_moves[1].time_left_sec == 40.0
        assert white_moves[1].time_spent_sec == 5.0

    def test_no_time_tags_returns_empty_metrics(self):
        """時間タグなしSGFで GameTimeData(has_time_data=False, metrics=()) を返却。"""
        sgf = "(;GM[1]SZ[19];B[aa];W[bb];B[cc])"
        root = parse_sgf(sgf)
        result = parse_time_data(root)

        assert result.has_time_data is False
        assert result.metrics == ()
        assert result.black_moves_with_time == 0
        assert result.white_moves_with_time == 0

    def test_integer_format_igs_style(self):
        """整数形式（IGS）でテストパス。"""
        sgf = "(;GM[1]SZ[19];B[aa]BL[100];W[bb]WL[200])"
        root = parse_sgf(sgf)
        result = parse_time_data(root)

        assert result.has_time_data is True
        assert result.metrics[0].time_left_sec == 100.0
        assert result.metrics[1].time_left_sec == 200.0

    def test_decimal_format_kgs_style(self):
        """小数形式（KGS）でテストパス。"""
        sgf = "(;GM[1]SZ[19];B[aa]BL[123.456];W[bb]WL[78.9])"
        root = parse_sgf(sgf)
        result = parse_time_data(root)

        assert result.has_time_data is True
        assert result.metrics[0].time_left_sec == 123.456
        assert result.metrics[1].time_left_sec == 78.9

    def test_all_mainline_moves_included_with_alignment(self):
        """時間データありの場合、全メインライン手を含む（move_number アライメント維持）。"""
        # Move 1, 2, 3 - all should be in metrics
        sgf = "(;GM[1]SZ[19];B[aa]BL[100];W[bb]WL[100];B[cc]BL[90])"
        root = parse_sgf(sgf)
        result = parse_time_data(root)

        assert len(result.metrics) == 3
        assert result.metrics[0].move_number == 1
        assert result.metrics[1].move_number == 2
        assert result.metrics[2].move_number == 3


class TestPartialMissingTags:
    """Tests for partial missing tags."""

    def test_partial_missing_tag_is_none(self):
        """部分的にタグ欠損があるSGFで、該当手は time_left_sec=None。"""
        # B1 has BL, B3 has no BL
        sgf = "(;GM[1]SZ[19];B[aa]BL[100];W[bb]WL[100];B[cc])"
        root = parse_sgf(sgf)
        result = parse_time_data(root)

        assert result.has_time_data is True
        black_moves = [m for m in result.metrics if m.player == "B"]

        assert black_moves[0].time_left_sec == 100.0  # B1 has tag
        assert black_moves[1].time_left_sec is None  # B3 missing tag
        assert black_moves[1].time_spent_sec is None


class TestMissingTagGap:
    """Tests for gap in time tags (CRITICAL)."""

    def test_same_player_missing_tag_gap(self):
        """タグ欠損後の有効タグで time_spent_sec=None（ギャップ越しの差分計算防止）。

        Scenario (Black moves only, interleaved with White):
        - Move 1 (B): BL=100 -> time_spent=None (first)
        - Move 3 (B): BL missing -> time_left=None, time_spent=None
        - Move 5 (B): BL=80 -> time_left=80, time_spent=None (NOT 20!)
        """
        sgf = "(;GM[1]SZ[19];B[aa]BL[100];W[bb]WL[100];B[cc];W[dd]WL[90];B[ee]BL[80])"
        root = parse_sgf(sgf)
        result = parse_time_data(root)

        assert result.has_time_data is True

        # Find Black moves
        black_moves = [m for m in result.metrics if m.player == "B"]
        assert len(black_moves) == 3

        # B1: first move, time_spent=None
        assert black_moves[0].move_number == 1
        assert black_moves[0].time_left_sec == 100.0
        assert black_moves[0].time_spent_sec is None

        # B3: missing tag, both None
        assert black_moves[1].move_number == 3
        assert black_moves[1].time_left_sec is None
        assert black_moves[1].time_spent_sec is None

        # B5: valid tag, but prev was None, so time_spent=None (NOT 20!)
        assert black_moves[2].move_number == 5
        assert black_moves[2].time_left_sec == 80.0
        assert black_moves[2].time_spent_sec is None


class TestFloatingPointTolerance:
    """Tests for floating point tolerance."""

    def test_tiny_negative_delta_treated_as_zero(self):
        """微小負値（delta >= -EPS）は 0.0 として処理。"""
        # delta = 100.002 - 100.001 = 0.001, which is positive, time_spent = 0.001
        sgf = "(;GM[1]SZ[19];B[aa]BL[100.002];W[bb]WL[100];B[cc]BL[100.001])"
        root = parse_sgf(sgf)
        result = parse_time_data(root)

        black_moves = [m for m in result.metrics if m.player == "B"]
        assert black_moves[1].time_spent_sec is not None
        assert black_moves[1].time_spent_sec >= 0.0

    def test_significant_negative_delta_is_none(self, caplog):
        """負の差分（delta < -EPS、秒読みリセット等）で time_spent_sec=None + 警告ログ。"""
        # 10 -> 600 = byoyomi reset
        sgf = "(;GM[1]SZ[19];B[aa]BL[10];W[bb]WL[100];B[cc]BL[600])"
        root = parse_sgf(sgf)

        with caplog.at_level(logging.WARNING):
            result = parse_time_data(root)

        black_moves = [m for m in result.metrics if m.player == "B"]
        assert black_moves[1].time_spent_sec is None  # Byoyomi reset
        assert "time increased" in caplog.text


class TestTimeSemantics:
    """Tests for BL/WL semantics (off-by-one prevention)."""

    def test_time_left_is_after_move(self):
        """BL/WL は「着手後の残り時間」であることをテストで検証。

        Verification using inline SGF:
        - Move 1: W[aa]WL[45] -> After playing, White has 45s left
        - Move 3: W[cc]WL[40] -> After playing, White has 40s left
        - time_spent = 45 - 40 = 5 seconds
        """
        sgf = "(;GM[1]SZ[19];W[aa]WL[45];B[bb]BL[100];W[cc]WL[40])"
        root = parse_sgf(sgf)
        result = parse_time_data(root)

        white_moves = [
            m for m in result.metrics if m.player == "W" and m.time_left_sec is not None
        ]

        assert white_moves[0].time_left_sec == 45.0  # After move 1
        assert white_moves[1].time_left_sec == 40.0  # After move 3
        assert white_moves[1].time_spent_sec == 5.0  # 45 - 40


# =============================================================================
# P1: _extract_time_left() Tests
# =============================================================================


class TestExtractTimeLeft:
    """Tests for _extract_time_left() function."""

    def test_black_reads_bl_not_wl(self):
        """Black は BL を読む（WL ではない）。"""
        root = parse_sgf("(;GM[1]SZ[19];B[aa]BL[45]WL[60])")
        node = root.children[0]
        assert _extract_time_left(node, "B") == 45.0

    def test_white_reads_wl_not_bl(self):
        """White は WL を読む（BL ではない）。"""
        root = parse_sgf("(;GM[1]SZ[19];W[aa]BL[45]WL[60])")
        node = root.children[0]
        assert _extract_time_left(node, "W") == 60.0

    def test_integer_format(self):
        """IGS-style integer value."""
        root = parse_sgf("(;GM[1]SZ[19];B[aa]BL[45])")
        node = root.children[0]
        assert _extract_time_left(node, "B") == 45.0

    def test_decimal_format(self):
        """KGS-style decimal value."""
        root = parse_sgf("(;GM[1]SZ[19];W[aa]WL[123.456])")
        node = root.children[0]
        assert _extract_time_left(node, "W") == 123.456

    def test_missing_property_returns_none(self):
        """Missing property returns None (no warning)."""
        root = parse_sgf("(;GM[1]SZ[19];B[aa])")  # No BL
        node = root.children[0]
        assert _extract_time_left(node, "B") is None

    def test_invalid_value_returns_none_with_warning(self, caplog):
        """Non-numeric value returns None with warning."""
        root = parse_sgf("(;GM[1]SZ[19];B[aa]BL[abc])")
        node = root.children[0]

        with caplog.at_level(logging.WARNING):
            result = _extract_time_left(node, "B")

        assert result is None
        assert "Invalid BL value" in caplog.text

    def test_negative_value_returns_none_with_warning(self, caplog):
        """Negative value returns None with warning."""
        root = parse_sgf("(;GM[1]SZ[19];B[aa]BL[-10])")
        node = root.children[0]

        with caplog.at_level(logging.WARNING):
            result = _extract_time_left(node, "B")

        assert result is None
        assert "Negative time value" in caplog.text


# =============================================================================
# P1: Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for various edge cases."""

    def test_empty_game_returns_empty(self):
        """Empty game (root only) returns empty GameTimeData."""
        root = parse_sgf("(;GM[1]SZ[19])")
        result = parse_time_data(root)

        assert result.has_time_data is False
        assert result.metrics == ()

    def test_first_move_has_none_time_spent(self):
        """各プレイヤーの最初の手は time_spent=None。"""
        sgf = "(;GM[1]SZ[19];B[aa]BL[100];W[bb]WL[100])"
        root = parse_sgf(sgf)
        result = parse_time_data(root)

        for m in result.metrics:
            assert m.time_spent_sec is None  # Both are first moves

    def test_move_number_increments_only_for_moves(self):
        """move_number は実際の着手のみカウント。"""
        # This SGF has comment nodes that should be skipped
        sgf = "(;GM[1]SZ[19];B[aa]BL[100];W[bb]WL[100];B[cc]BL[90])"
        root = parse_sgf(sgf)
        result = parse_time_data(root)

        assert result.metrics[0].move_number == 1
        assert result.metrics[1].move_number == 2
        assert result.metrics[2].move_number == 3

    def test_dataclass_is_frozen(self):
        """TimeMetrics and GameTimeData are immutable."""
        m = TimeMetrics(
            move_number=1, player="B", time_left_sec=100.0, time_spent_sec=5.0
        )
        with pytest.raises(Exception):
            m.move_number = 2  # type: ignore

        g = GameTimeData(
            metrics=(m,), has_time_data=True, black_moves_with_time=1, white_moves_with_time=0
        )
        with pytest.raises(Exception):
            g.has_time_data = False  # type: ignore


# =============================================================================
# P2: Real SGF Integration Tests
# =============================================================================


class TestRealSGFFiles:
    """Tests using actual SGF files from tests/data/."""

    def test_panda1_sgf_has_time_data(self):
        """panda1.sgf（IGS形式）から時間データを抽出。"""
        root = KaTrainSGF.parse_file("tests/data/panda1.sgf")
        result = parse_time_data(root)

        assert result.has_time_data is True
        assert result.black_moves_with_time > 0
        assert result.white_moves_with_time > 0

        # Verify first White move has WL=45 (from panda1.sgf)
        white_moves = [
            m for m in result.metrics if m.player == "W" and m.time_left_sec is not None
        ]
        assert white_moves[0].time_left_sec == 45.0

        # Verify second White move (W[ce]) has WL=40, time_spent=5
        assert white_moves[1].time_left_sec == 40.0
        assert white_moves[1].time_spent_sec == 5.0

"""Tests for Phase 154-A SGF RE string parser.

Covers:
- Standard formats: B+R, W+T, B+5.5, W+12.5
- Draw formats: 0, Draw, Jigo
- Case insensitivity and whitespace tolerance
- Unknown / empty / None inputs
- outcome_for_player helper
"""
from __future__ import annotations

import pytest

from katrain.core.reports.utils.result_parser import (
    GameOutcome,
    PlayerOutcome,
    outcome_for_player,
    parse_result,
)


class TestParseResultStandard:
    """Standard RE strings (Phase 154-A)."""

    @pytest.mark.parametrize(
        "result_str,expected_winner",
        [
            ("B+R", "B"),
            ("W+R", "W"),
            ("B+T", "B"),
            ("W+T", "W"),
            ("B+5.5", "B"),
            ("W+12.5", "W"),
            ("B+0.5", "B"),
            ("W+100", "W"),
        ],
    )
    def test_score_or_resignation(self, result_str: str, expected_winner: str):
        outcome = parse_result(result_str)
        if expected_winner == "B":
            assert outcome.black == PlayerOutcome.WIN
            assert outcome.white == PlayerOutcome.LOSS
        else:
            assert outcome.black == PlayerOutcome.LOSS
            assert outcome.white == PlayerOutcome.WIN

    @pytest.mark.parametrize("result_str", ["B+R", "b+r", "B + R", "  B+R  "])
    def test_case_insensitive_and_whitespace(self, result_str: str):
        outcome = parse_result(result_str)
        assert outcome.black == PlayerOutcome.WIN
        assert outcome.white == PlayerOutcome.LOSS

    def test_score_diff_sign(self):
        """Score diff is signed: positive = black winning."""
        black_win = parse_result("B+5.5")
        assert black_win.score_diff == 5.5
        white_win = parse_result("W+5.5")
        assert white_win.score_diff == -5.5

    def test_resign_no_score_diff(self):
        """Resignation / time forfeit: score_diff is None."""
        outcome = parse_result("B+R")
        assert outcome.score_diff is None


class TestParseResultDraw:
    """Draw / jigo formats."""

    @pytest.mark.parametrize("result_str", ["0", "Draw", "Jigo", "draw", "JIGO"])
    def test_draw_formats(self, result_str: str):
        outcome = parse_result(result_str)
        assert outcome.black == PlayerOutcome.DRAW
        assert outcome.white == PlayerOutcome.DRAW
        assert outcome.score_diff == 0.0


class TestParseResultUnknown:
    """Unrecognized / empty / None inputs."""

    @pytest.mark.parametrize("result_str", [None, "", "  ", "?", "unknown", "abc"])
    def test_unknown(self, result_str: str):
        outcome = parse_result(result_str)
        assert outcome.black == PlayerOutcome.UNKNOWN
        assert outcome.white == PlayerOutcome.UNKNOWN
        assert outcome.score_diff is None


class TestOutcomeForPlayer:
    """outcome_for_player helper."""

    def test_black(self):
        outcome = parse_result("B+5.5")
        assert outcome_for_player(outcome, "B") == PlayerOutcome.WIN

    def test_white(self):
        outcome = parse_result("W+5.5")
        assert outcome_for_player(outcome, "W") == PlayerOutcome.WIN

    def test_invalid_player_returns_unknown(self):
        outcome = parse_result("B+5.5")
        assert outcome_for_player(outcome, "X") == PlayerOutcome.UNKNOWN
        assert outcome_for_player(outcome, "") == PlayerOutcome.UNKNOWN


class TestRawPreservation:
    """Original RE string is preserved in the outcome."""

    def test_raw_preserved(self):
        outcome = parse_result("B+R")
        assert outcome.raw == "B+R"

    def test_raw_preserved_unknown(self):
        outcome = parse_result("???")
        assert outcome.raw == "???"
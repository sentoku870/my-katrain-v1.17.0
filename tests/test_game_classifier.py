"""Tests for Phase 157-C game-type classifier."""
from __future__ import annotations

import pytest

from katrain.core.analysis.models import EvalSnapshot, MoveEval, MistakeCategory
from katrain.core.analysis.models.skill import GameSummaryData
from katrain.core.reports.utils.game_classifier import (
    EVEN_KOMI_FLOOR,
    classify_game,
    classify_games,
)


def _make_gd(name: str, handicap: int = 0, komi: float = 6.5) -> GameSummaryData:
    """Build a minimal GameSummaryData with the given handicap / komi."""
    snapshot = EvalSnapshot(moves=[
        MoveEval(
            move_number=1,
            player="B",
            gtp="D4",
            score_before=0.0,
            score_after=0.0,
            delta_score=0.0,
            winrate_before=0.5,
            winrate_after=0.5,
            delta_winrate=0.0,
            points_lost=0.0,
            realized_points_lost=None,
            root_visits=200,
        )
    ])
    move = snapshot.moves[0]
    move.score_loss = 0.0
    move.mistake_category = MistakeCategory.GOOD
    return GameSummaryData(
        game_name=name,
        player_black="Alice",
        player_white="Bob",
        snapshot=snapshot,
        board_size=(19, 19),
        handicap=handicap,
        komi=komi,
    )


class TestClassifyGameEven:
    """Even game detection."""

    def test_default_is_even(self):
        """GameSummaryData defaults: HA=0, KM=6.5 -> even."""
        gd = _make_gd("default.sgf")
        assert classify_game(gd) == "even"

    def test_chinese_komi_seven_and_a_half_is_even(self):
        gd = _make_gd("cjk.sgf", handicap=0, komi=7.5)
        assert classify_game(gd) == "even"

    def test_japanese_komi_six_and_a_half_is_even(self):
        gd = _make_gd("jp.sgf", handicap=0, komi=6.5)
        assert classify_game(gd) == "even"

    def test_komi_exactly_floor_is_even(self):
        """Boundary: komi == EVEN_KOMI_FLOOR is even."""
        gd = _make_gd("boundary.sgf", handicap=0, komi=EVEN_KOMI_FLOOR)
        assert classify_game(gd) == "even"


class TestClassifyGameHandicapped:
    """Handicap-game detection."""

    def test_two_stone_handicap(self):
        gd = _make_gd("ha2.sgf", handicap=2, komi=0.5)
        assert classify_game(gd) == "handicapped"

    def test_nine_stone_handicap(self):
        gd = _make_gd("ha9.sgf", handicap=9, komi=0.5)
        assert classify_game(gd) == "handicapped"

    def test_zero_komi_no_handicap(self):
        """No-komi games with HA=0 are still handicaps (reduced komi)."""
        gd = _make_gd("nokomi.sgf", handicap=0, komi=0.0)
        assert classify_game(gd) == "handicapped"

    def test_low_komi_is_handicap(self):
        gd = _make_gd("low.sgf", handicap=0, komi=5.5)
        assert classify_game(gd) == "handicapped"

    def test_handicap_takes_priority_over_komi(self):
        """HA>=2 with normal komi is still handicapped."""
        gd = _make_gd("ha2_komi7.sgf", handicap=2, komi=7.5)
        assert classify_game(gd) == "handicapped"


class TestClassifyGames:
    """Bulk split into the three buckets."""

    def test_mixed_split(self):
        games = [
            _make_gd("e1.sgf", handicap=0, komi=6.5),
            _make_gd("e2.sgf", handicap=0, komi=7.5),
            _make_gd("h1.sgf", handicap=2, komi=0.5),
            _make_gd("h2.sgf", handicap=0, komi=0.0),
        ]
        buckets = classify_games(games)
        assert [g.game_name for g in buckets["even"]] == ["e1.sgf", "e2.sgf"]
        assert [g.game_name for g in buckets["handicapped"]] == ["h1.sgf", "h2.sgf"]
        assert buckets["unknown"] == []

    def test_unknown_bucket_always_present(self):
        """The ``unknown`` key must always exist (possibly empty)."""
        buckets = classify_games([])
        assert set(buckets.keys()) == {"even", "handicapped", "unknown"}
        assert buckets == {"even": [], "handicapped": [], "unknown": []}

    def test_single_even_run(self):
        games = [_make_gd("only.sgf", handicap=0, komi=6.5)]
        buckets = classify_games(games)
        assert len(buckets["even"]) == 1
        assert buckets["handicapped"] == []
        assert buckets["unknown"] == []

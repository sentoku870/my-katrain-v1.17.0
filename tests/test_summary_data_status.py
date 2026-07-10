"""Regression tests for Phase H-4 data_status field.

Phase H-4 added a 3-state ``meta.data_status`` field to the Summary
JSON output so the LLM can distinguish between:
- "not_applicable_no_games" -- empty batch
- "insufficient_data" -- single game (need >= 2 for meaningful
  per-player aggregates)
- "computed" -- the normal 2+ game case

This test pins the contract on :func:`_data_status_for` and the
``MetaData`` TypedDict field, and verifies the empty-batch path emits
the correct status.
"""

from __future__ import annotations

import pytest

from katrain.core.analysis.models import EvalSnapshot, GameSummaryData
from katrain.core.reports.schema import MetaData
from katrain.core.reports.summary_json_export import _data_status_for


class TestDataStatusHelper:
    @pytest.mark.parametrize(
        "count,expected",
        [
            (0, "not_applicable_no_games"),
            (1, "insufficient_data"),
            (2, "computed"),
            (5, "computed"),
            (100, "computed"),
        ],
    )
    def test_three_state_mapping(self, count: int, expected: str) -> None:
        assert _data_status_for(count) == expected


class TestMetaDataTypedDict:
    def test_data_status_field_declared(self) -> None:
        """The ``data_status`` field must be on the TypedDict."""
        annotations = getattr(MetaData, "__annotations__", {})
        assert "data_status" in annotations


class TestBuildSummaryJsonEmptyBatch:
    """End-to-end: build_summary_json with an empty batch must emit
    ``data_status == "not_applicable_no_games"`` and the per-player
    block must still be a structurally valid empty dict."""

    def test_empty_batch_emits_no_games_status(self) -> None:
        from katrain.core.reports.summary_json_export import build_summary_json

        result = build_summary_json([])
        assert result["meta"]["data_status"] == "not_applicable_no_games"
        assert result["meta"]["games_analyzed"] == 0
        assert result["meta"]["games_by_type"] == {
            "even": 0,
            "handicapped": 0,
            "unknown": 0,
        }
        assert result["players"] == {}
        assert result["loss_progression"] == {"all": []}

    def test_single_game_emits_insufficient_data(self) -> None:
        from katrain.core.reports.summary_json_export import build_summary_json

        result = build_summary_json([_make_gd()])
        assert result["meta"]["data_status"] == "insufficient_data"
        assert result["meta"]["games_analyzed"] == 1

    def test_two_game_batch_emits_computed(self) -> None:
        from katrain.core.reports.summary_json_export import build_summary_json

        result = build_summary_json([_make_gd(), _make_gd()])
        assert result["meta"]["data_status"] == "computed"
        assert result["meta"]["games_analyzed"] == 2


def _make_gd() -> GameSummaryData:
    """Minimal ``GameSummaryData`` for empty/single-game tests."""
    return GameSummaryData(
        game_name="g",
        player_black="P1",
        player_white="P2",
        snapshot=EvalSnapshot(moves=[]),
        board_size=(19, 19),
    )

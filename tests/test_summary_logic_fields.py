"""Regression tests for Phase H-2 GameSummaryData aggregation.

Phase H-2 fixed a dead-code path in
:mod:`katrain.core.reports.summary_logic` where
``hasattr(game_data, "reason_tags_by_player")`` was always ``False``
because :class:`GameSummaryData` did not declare those fields. The
aggregation was silently skipped, leading to reason-tag counts of 0
in the Summary JSON for every batch.

This test pins the contract:
- :class:`GameSummaryData` has both new fields with empty-dict defaults
- ``extraction.py`` populates them from the raw stats dict
- ``summary_logic.SummaryAnalyzer`` reads them without a ``hasattr``
  guard
"""

from __future__ import annotations

from dataclasses import fields

from katrain.core.analysis.models import GameSummaryData


class TestGameSummaryDataFields:
    def test_has_reason_tags_by_player_field(self) -> None:
        """The reason-tags aggregate must be a first-class field."""
        field_names = {f.name for f in fields(GameSummaryData)}
        assert "reason_tags_by_player" in field_names, (
            "GameSummaryData must declare reason_tags_by_player; "
            "Phase H-2 fixed the dead-code hasattr path in summary_logic."
        )

    def test_has_important_moves_stats_by_player_field(self) -> None:
        """The important-moves-stats aggregate must be a first-class field."""
        field_names = {f.name for f in fields(GameSummaryData)}
        assert "important_moves_stats_by_player" in field_names, (
            "GameSummaryData must declare important_moves_stats_by_player; "
            "Phase H-2 fixed the dead-code hasattr path in summary_logic."
        )

    def test_default_is_empty_dict(self) -> None:
        """Empty dicts are the safe default when no batch aggregation ran."""
        gd = GameSummaryData(
            game_name="g",
            player_black="B",
            player_white="W",
            snapshot=None,  # type: ignore[arg-type]
            board_size=(19, 19),
        )
        assert gd.reason_tags_by_player == {}
        assert gd.important_moves_stats_by_player == {}


class TestSummaryAnalyzerNoHasattr:
    """``summary_logic.py`` must use direct attribute access, not
    :func:`hasattr`, for the reason-tag / important-move aggregates."""

    def test_no_hasattr_check_on_game_summary_data(self) -> None:
        import inspect

        from katrain.core.reports import summary_logic

        source = inspect.getsource(summary_logic)
        # The dead ``hasattr(game_data, "reason_tags_by_player")`` and
        # ``hasattr(game_data, "important_moves_stats_by_player")``
        # guards must NOT appear any more (Phase H-2 removed them).
        for literal in (
            'hasattr(game_data, "reason_tags_by_player")',
            'hasattr(game_data, "important_moves_stats_by_player")',
        ):
            assert literal not in source, (
                f"summary_logic still has defensive hasattr check {literal!r}; "
                f"GameSummaryData now declares these fields directly."
            )

    def test_summary_analyzer_aggregates_reason_tags(self) -> None:
        """End-to-end: when reason_tags_by_player is populated, the
        summary must reflect it (the Phase H-2 fix)."""
        from katrain.core.analysis.models import (
            EvalSnapshot,
        )
        from katrain.core.reports.summary_logic import SummaryAnalyzer

        snapshot = EvalSnapshot(moves=[])
        gd = GameSummaryData(
            game_name="g",
            player_black="P1",
            player_white="P2",
            snapshot=snapshot,
            board_size=(19, 19),
            reason_tags_by_player={"B": {"heavy_loss": 2, "endgame_hint": 1}},
        )
        analyzer = SummaryAnalyzer([gd])
        stats = analyzer.get_all_player_stats()["P1"]
        # The fix makes the aggregation actually fire; the previous
        # dead-code path left reason_tags_counts empty.
        assert stats.reason_tags_counts.get("heavy_loss") == 2
        assert stats.reason_tags_counts.get("endgame_hint") == 1

    def test_summary_analyzer_aggregates_important_moves_stats(self) -> None:
        """The important-moves-stats aggregate path must also fire."""
        from katrain.core.analysis.models import (
            EvalSnapshot,
        )
        from katrain.core.reports.summary_logic import SummaryAnalyzer

        snapshot = EvalSnapshot(moves=[])
        gd = GameSummaryData(
            game_name="g",
            player_black="P1",
            player_white="P2",
            snapshot=snapshot,
            board_size=(19, 19),
            important_moves_stats_by_player={
                "B": {"important_count": 7, "tagged_count": 3, "tag_occurrences": 5},
            },
        )
        analyzer = SummaryAnalyzer([gd])
        stats = analyzer.get_all_player_stats()["P1"]
        assert stats.important_moves_count == 7
        assert stats.tagged_moves_count == 3
        assert stats.tag_occurrences_total == 5

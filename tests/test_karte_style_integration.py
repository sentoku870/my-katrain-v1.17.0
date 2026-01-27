# -*- coding: utf-8 -*-
"""Integration tests for Karte style output (Phase 57).

All tests are self-contained with no external file dependencies.
Uses MagicMock for game/snapshot to minimize CI fragility.
"""

import pytest
from unittest.mock import patch, MagicMock

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.analysis.style import STYLE_ARCHETYPES
from katrain.core.analysis.models import EvalSnapshot


# -----------------------------------------------------------------------------
# Unit tests for helper functions
# -----------------------------------------------------------------------------


class TestBuildTagCountsFromMoves:
    """Unit tests for _build_tag_counts_from_moves helper."""

    def test_empty_moves_returns_empty_dict(self):
        from katrain.core.reports.karte.builder import _build_tag_counts_from_moves

        result = _build_tag_counts_from_moves([], None)
        assert result == {}

    def test_counts_cached_meaning_tag_id(self):
        from katrain.core.reports.karte.builder import _build_tag_counts_from_moves

        moves = [
            MagicMock(player="B", meaning_tag_id="overplay"),
            MagicMock(player="B", meaning_tag_id="overplay"),
            MagicMock(player="B", meaning_tag_id="missed_tesuji"),
            MagicMock(player="W", meaning_tag_id="slow_move"),
        ]
        result = _build_tag_counts_from_moves(moves, None)

        assert result[MeaningTagId.OVERPLAY] == 2
        assert result[MeaningTagId.MISSED_TESUJI] == 1
        assert result[MeaningTagId.SLOW_MOVE] == 1

    def test_filters_by_player_B(self):
        from katrain.core.reports.karte.builder import _build_tag_counts_from_moves

        moves = [
            MagicMock(player="B", meaning_tag_id="overplay"),
            MagicMock(player="W", meaning_tag_id="slow_move"),
            MagicMock(player="B", meaning_tag_id="overplay"),
        ]
        result = _build_tag_counts_from_moves(moves, "B")

        assert result.get(MeaningTagId.OVERPLAY) == 2
        assert MeaningTagId.SLOW_MOVE not in result

    def test_skips_none_meaning_tag_id(self):
        from katrain.core.reports.karte.builder import _build_tag_counts_from_moves

        moves = [
            MagicMock(player="B", meaning_tag_id=None),
            MagicMock(player="B", meaning_tag_id="overplay"),
        ]
        result = _build_tag_counts_from_moves(moves, None)

        assert result.get(MeaningTagId.OVERPLAY) == 1
        assert len(result) == 1

    def test_skips_invalid_tag_id(self):
        from katrain.core.reports.karte.builder import _build_tag_counts_from_moves

        moves = [
            MagicMock(player="B", meaning_tag_id="invalid_tag_xyz"),
            MagicMock(player="B", meaning_tag_id="overplay"),
        ]
        result = _build_tag_counts_from_moves(moves, None)

        assert result.get(MeaningTagId.OVERPLAY) == 1
        assert len(result) == 1

    def test_valid_tag_ids_convert_successfully(self):
        """Verify all MeaningTagId values can be converted from string."""
        for tag in MeaningTagId:
            converted = MeaningTagId(tag.value)
            assert converted == tag


class TestComputeStyleSafe:
    """Unit tests for _compute_style_safe with graceful fallback."""

    def test_returns_none_on_exception(self):
        from katrain.core.reports.karte.builder import _compute_style_safe

        with patch(
            "katrain.core.reports.karte.builder.compute_radar_from_moves",
            side_effect=ValueError("Test error"),
        ):
            result = _compute_style_safe([], None)
            assert result is None

    def test_logs_exception_at_debug_level(self):
        from katrain.core.reports.karte.builder import _compute_style_safe

        with patch(
            "katrain.core.reports.karte.builder.compute_radar_from_moves",
            side_effect=ValueError("Test error"),
        ), patch("katrain.core.reports.karte.builder.logger") as mock_logger:
            _compute_style_safe([], None)
            mock_logger.debug.assert_called_once()
            call_kwargs = mock_logger.debug.call_args[1]
            assert call_kwargs.get("exc_info") is True


# -----------------------------------------------------------------------------
# Integration test: _build_karte_report_impl with minimal mocks
# -----------------------------------------------------------------------------


class TestKarteStyleIntegration:
    """Integration test verifying Karte Meta section includes style lines.

    Uses MagicMock for game/snapshot with only the fields actually accessed
    by _build_karte_report_impl.
    """

    @pytest.fixture
    def mock_game(self):
        """Create minimal mock game with required fields only."""
        game = MagicMock()
        game.game_id = "test-game-001"
        game.sgf_filename = "test.sgf"
        game.board_size = (19, 19)
        game.komi = 6.5
        game.rules = "japanese"
        game.katrain = None  # Skip katrain-dependent code paths
        game.root.get_property.return_value = ""
        game.root.handicap = 0
        # CRITICAL: Set children to empty list to prevent infinite loop in parse_time_data
        game.root.children = []
        game.get_important_move_evals.return_value = []
        return game

    @pytest.fixture
    def mock_snapshot(self):
        """Create minimal mock snapshot with moves list."""
        snapshot = MagicMock(spec=EvalSnapshot)
        snapshot.moves = []
        return snapshot

    def test_karte_meta_includes_style_lines(self, mock_game, mock_snapshot):
        """Verify Karte Meta section contains Style and Style Confidence lines."""
        from katrain.core.reports.karte.builder import _build_karte_report_impl

        mock_style = MagicMock()
        mock_style.archetype.name_key = "style:kiai_fighter:name"
        mock_style.confidence = 0.85

        with patch(
            "katrain.core.reports.karte.builder._compute_style_safe",
            return_value=mock_style,
        ), patch(
            "katrain.core.reports.karte.builder.i18n._", return_value="Kiai Fighter"
        ):
            karte_output = _build_karte_report_impl(
                game=mock_game,
                snapshot=mock_snapshot,
                level="normal",
                player_filter=None,
            )

        assert "- Style: Kiai Fighter" in karte_output, (
            f"Expected '- Style: Kiai Fighter' in output.\nGot:\n{karte_output[:500]}"
        )
        assert "- Style Confidence: 85%" in karte_output, (
            f"Expected '- Style Confidence: 85%' in output.\nGot:\n{karte_output[:500]}"
        )

    def test_karte_meta_shows_unknown_style_on_failure(self, mock_game, mock_snapshot):
        """Verify Karte Meta section shows 'Unknown' style when computation fails.

        Phase 66: When style computation fails (returns None), we show
        'Style: Unknown' but no confidence line.
        """
        from katrain.core.reports.karte.builder import _build_karte_report_impl

        with patch(
            "katrain.core.reports.karte.builder._compute_style_safe",
            return_value=None,
        ):
            karte_output = _build_karte_report_impl(
                game=mock_game,
                snapshot=mock_snapshot,
                level="normal",
                player_filter=None,
            )

        # Phase 66: Show "Unknown" when style computation fails
        assert "- Style:" in karte_output, "Style line should be present with 'Unknown'"
        # No confidence line when computation fails
        assert "- Style Confidence:" not in karte_output


class TestStyleI18nKeys:
    """Verify i18n keys match model definitions."""

    def test_all_archetypes_have_valid_name_key(self):
        for archetype in STYLE_ARCHETYPES.values():
            assert archetype.name_key.startswith("style:")
            assert archetype.name_key.endswith(":name")

    def test_all_archetypes_have_valid_summary_key(self):
        """Summary keys exist in model but not used in Phase 57."""
        for archetype in STYLE_ARCHETYPES.values():
            assert archetype.summary_key.startswith("style:")
            assert archetype.summary_key.endswith(":summary")

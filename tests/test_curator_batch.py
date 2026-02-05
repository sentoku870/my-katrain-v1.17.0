"""Tests for Curator batch output (Phase 64).

Tests cover:
- guide_extractor.py: HighlightMoment, ReplayGuide, extract_replay_guide()
- batch.py: CuratorBatchResult, generate_curator_outputs()
- Determinism tests for JSON output
- Edge cases (empty batch, percentile=None, etc.)
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.curator.batch import (
    CuratorBatchResult,
    _build_game_title,
    _extract_recommended_tags,
    _get_user_weak_axes_sorted,
    _normalize_percentile,
    _round_float,
    generate_curator_outputs,
)
from katrain.core.curator.guide_extractor import (
    HighlightMoment,
    ReplayGuide,
    extract_replay_guide,
)
from katrain.core.curator.models import (
    UNCERTAIN_TAG,
    SuitabilityScore,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tmp_curator_dir():
    """Create a temporary directory for curator outputs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture
def mock_game():
    """Create a mock Game object for testing."""
    game = MagicMock()
    game.root = MagicMock()
    game.root.children = []
    game.root.analysis = None
    return game


@pytest.fixture
def sample_stats():
    """Create sample game stats dict."""
    return {
        "game_name": "test_games/game_001.sgf",
        "player_b": "Player Black",
        "player_w": "Player White",
        "total_moves": 150,
        "meaning_tags_by_player": {
            "B": {"overplay": 3, "reading_failure": 2},
            "W": {"direction_error": 1},
        },
    }


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions in batch.py."""

    def test_round_float_precision(self):
        """Verify float rounding to 3 decimal places."""
        assert _round_float(0.8541234567) == 0.854
        assert _round_float(0.9219876543) == 0.922
        assert _round_float(0.8794561234) == 0.879
        # Python uses banker's rounding (round half to even)
        assert _round_float(0.5556) == 0.556
        assert _round_float(0.5554) == 0.555

    def test_normalize_percentile_with_value(self):
        """Percentile int is passed through."""
        score = SuitabilityScore(needs_match=0.5, stability=0.5, total=0.5, percentile=75)
        assert _normalize_percentile(score) == 75

    def test_normalize_percentile_with_none(self):
        """Percentile None is normalized to 0."""
        score = SuitabilityScore(needs_match=0.5, stability=0.5, total=0.5, percentile=None)
        assert _normalize_percentile(score) == 0

    def test_build_game_title_with_players(self):
        """Title uses player names when available."""
        stats = {"player_b": "Shin Jinseo", "player_w": "Ke Jie"}
        assert _build_game_title(stats) == "Shin Jinseo vs Ke Jie"

    def test_build_game_title_fallback(self):
        """Title falls back to game_name stem."""
        stats = {"game_name": "pro_games/2026/game_001.sgf"}
        assert _build_game_title(stats) == "game_001"

    def test_build_game_title_unknown(self):
        """Title falls back to 'Unknown' when no info."""
        stats = {}
        assert _build_game_title(stats) == "Unknown"

    def test_extract_recommended_tags_sorted_by_count(self):
        """Tags are sorted by count descending."""
        stats = {
            "meaning_tags_by_player": {
                "B": {"overplay": 5, "reading_failure": 3, "direction_error": 1},
                "W": {},
            }
        }
        tags = _extract_recommended_tags(stats, max_tags=3)
        assert tags == ["overplay", "reading_failure", "direction_error"]

    def test_extract_recommended_tags_tie_breaking(self):
        """Same count -> sorted alphabetically."""
        stats = {
            "meaning_tags_by_player": {
                "B": {"overplay": 2, "reading_failure": 2, "direction_error": 2},
                "W": {},
            }
        }
        tags = _extract_recommended_tags(stats, max_tags=3)
        assert tags == ["direction_error", "overplay", "reading_failure"]

    def test_extract_recommended_tags_excludes_uncertain(self):
        """UNCERTAIN_TAG is never included in recommended_tags."""
        stats = {
            "meaning_tags_by_player": {
                "B": {
                    UNCERTAIN_TAG: 10,  # High count, but should be excluded
                    "overplay": 2,
                    "reading_failure": 1,
                },
                "W": {UNCERTAIN_TAG: 5},
            }
        }
        tags = _extract_recommended_tags(stats, max_tags=5)
        assert UNCERTAIN_TAG not in tags
        assert tags == ["overplay", "reading_failure"]

    def test_extract_recommended_tags_max_limit(self):
        """Only returns up to max_tags."""
        stats = {
            "meaning_tags_by_player": {
                "B": {"a": 5, "b": 4, "c": 3, "d": 2, "e": 1},
                "W": {},
            }
        }
        tags = _extract_recommended_tags(stats, max_tags=2)
        assert tags == ["a", "b"]

    def test_get_user_weak_axes_sorted_empty(self):
        """Returns empty list when no user aggregate."""
        assert _get_user_weak_axes_sorted(None) == []

    def test_get_user_weak_axes_sorted_order(self):
        """Weak axes are sorted alphabetically."""
        mock_aggregate = MagicMock()
        # Mock is_weak_axis to return True for specific axes
        from katrain.core.analysis.skill_radar import RadarAxis

        weak_axes = {RadarAxis.FIGHTING, RadarAxis.ENDGAME}
        mock_aggregate.is_weak_axis = lambda axis: axis in weak_axes

        result = _get_user_weak_axes_sorted(mock_aggregate)
        assert result == ["endgame", "fighting"]  # Sorted alphabetically


# =============================================================================
# HighlightMoment Tests
# =============================================================================


class TestHighlightMoment:
    """Tests for HighlightMoment dataclass."""

    def test_to_dict_score_loss_rounded(self):
        """score_loss is rounded to 2 decimals in to_dict()."""
        moment = HighlightMoment(
            move_number=45,
            player="B",
            gtp_coord="D10",
            meaning_tag_id="overplay",
            meaning_tag_label="過剰な攻め",
            score_loss=5.2468,
            game_phase="middle",
        )
        d = moment.to_dict()
        assert d["score_loss"] == 5.25
        assert d["meaning_tag_id"] == "overplay"
        assert d["meaning_tag_label"] == "過剰な攻め"

    def test_to_dict_complete(self):
        """to_dict() includes all fields."""
        moment = HighlightMoment(
            move_number=10,
            player="W",
            gtp_coord="Q16",
            meaning_tag_id="direction_error",
            meaning_tag_label=None,
            score_loss=2.5,
            game_phase="opening",
        )
        d = moment.to_dict()
        assert d == {
            "move_number": 10,
            "player": "W",
            "gtp_coord": "Q16",
            "meaning_tag_id": "direction_error",
            "meaning_tag_label": None,
            "score_loss": 2.5,
            "game_phase": "opening",
        }


# =============================================================================
# ReplayGuide Tests
# =============================================================================


class TestReplayGuide:
    """Tests for ReplayGuide dataclass."""

    def test_to_dict_complete(self):
        """to_dict() includes all fields with nested moments."""
        moment = HighlightMoment(
            move_number=45,
            player="B",
            gtp_coord="D10",
            meaning_tag_id="overplay",
            meaning_tag_label="過剰な攻め",
            score_loss=5.24,
            game_phase="middle",
        )
        guide = ReplayGuide(
            game_id="test.sgf",
            game_title="Test Game",
            total_moves=100,
            highlight_moments=[moment],
        )
        d = guide.to_dict()
        assert d["game_id"] == "test.sgf"
        assert d["game_title"] == "Test Game"
        assert d["total_moves"] == 100
        assert len(d["highlight_moments"]) == 1
        assert d["highlight_moments"][0]["meaning_tag_id"] == "overplay"


# =============================================================================
# extract_replay_guide Tests
# =============================================================================


class TestExtractReplayGuide:
    """Tests for extract_replay_guide function."""

    def test_select_critical_moves_called_with_level(self, mock_game):
        """Verify select_critical_moves is called with explicit level parameter."""
        # Patch the function where it's imported from (inside the function body)
        with patch("katrain.core.analysis.select_critical_moves") as mock_select:
            mock_select.return_value = []

            extract_replay_guide(
                game=mock_game,
                game_id="test.sgf",
                game_title="Test Game",
                total_moves=100,
                lang="jp",
                level="normal",
            )

            mock_select.assert_called_once()
            call_kwargs = mock_select.call_args.kwargs
            assert call_kwargs["level"] == "normal"
            assert call_kwargs["lang"] == "ja"  # Converted from "jp" to ISO

    def test_lang_converted_to_iso(self, mock_game):
        """Verify lang is converted to ISO for select_critical_moves."""
        with patch("katrain.core.analysis.select_critical_moves") as mock_select:
            mock_select.return_value = []

            extract_replay_guide(
                game=mock_game,
                game_id="test.sgf",
                game_title="Test Game",
                total_moves=100,
                lang="jp",  # Internal code
            )

            call_kwargs = mock_select.call_args.kwargs
            assert call_kwargs["lang"] == "ja"  # ISO code

    def test_returns_replay_guide(self, mock_game):
        """Verify return type is ReplayGuide."""
        with patch("katrain.core.analysis.select_critical_moves") as mock_select:
            mock_select.return_value = []

            result = extract_replay_guide(
                game=mock_game,
                game_id="test.sgf",
                game_title="Test Game",
                total_moves=100,
            )

            assert isinstance(result, ReplayGuide)
            assert result.game_id == "test.sgf"
            assert result.game_title == "Test Game"
            assert result.total_moves == 100


# =============================================================================
# generate_curator_outputs Tests
# =============================================================================


class TestGenerateCuratorOutputs:
    """Tests for generate_curator_outputs function."""

    def test_empty_batch_generates_valid_json(self, tmp_curator_dir):
        """Empty games_and_stats produces valid empty JSON files."""
        result = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=tmp_curator_dir,
            batch_timestamp="20260126-153000",
        )

        assert result.ranking_path is not None
        assert result.guide_path is not None
        assert result.games_scored == 0
        assert result.guides_generated == 0

        # Verify ranking JSON is valid
        with open(result.ranking_path, encoding="utf-8") as f:
            ranking = json.load(f)
        assert ranking["total_games"] == 0
        assert ranking["rankings"] == []

        # Verify guide JSON is valid
        with open(result.guide_path, encoding="utf-8") as f:
            guide = json.load(f)
        assert guide["total_games"] == 0
        assert guide["games"] == []

    def test_result_paths_are_strings(self, tmp_curator_dir):
        """Verify result paths are str, not Path."""
        result = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=tmp_curator_dir,
            batch_timestamp="20260126-153000",
        )

        assert isinstance(result.ranking_path, str)
        assert isinstance(result.guide_path, str)

    def test_creates_curator_dir(self, tmp_curator_dir):
        """Verify curator_dir is created if it doesn't exist."""
        nested_dir = os.path.join(tmp_curator_dir, "nested", "curator")
        assert not os.path.exists(nested_dir)

        result = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=nested_dir,
            batch_timestamp="20260126-153000",
        )

        assert os.path.exists(nested_dir)
        assert result.ranking_path is not None

    def test_float_precision_in_ranking(self, tmp_curator_dir, mock_game, sample_stats):
        """Verify float fields are rounded to 3 decimal places."""
        with (
            patch("katrain.core.curator.batch.score_batch_suitability") as mock_score,
            patch("katrain.core.curator.batch.extract_replay_guide") as mock_guide,
        ):
            mock_score.return_value = [
                SuitabilityScore(
                    needs_match=0.8541234567,
                    stability=0.9219876543,
                    total=0.8794561234,
                    percentile=75,
                ),
            ]
            mock_guide.return_value = ReplayGuide(
                game_id="test.sgf",
                game_title="Test",
                total_moves=100,
                highlight_moments=[],
            )

            result = generate_curator_outputs(
                games_and_stats=[(mock_game, sample_stats)],
                curator_dir=tmp_curator_dir,
                batch_timestamp="20260126-153000",
            )

        with open(result.ranking_path, encoding="utf-8") as f:
            data = json.load(f)

        ranking = data["rankings"][0]
        assert ranking["needs_match"] == 0.854
        assert ranking["stability"] == 0.922
        assert ranking["total"] == 0.879

    def test_percentile_none_normalized_to_zero(self, tmp_curator_dir, mock_game, sample_stats):
        """Verify percentile=None becomes 0 in JSON."""
        with (
            patch("katrain.core.curator.batch.score_batch_suitability") as mock_score,
            patch("katrain.core.curator.batch.extract_replay_guide") as mock_guide,
        ):
            mock_score.return_value = [
                SuitabilityScore(
                    needs_match=0.5,
                    stability=0.5,
                    total=0.5,
                    percentile=None,  # None should become 0
                ),
            ]
            mock_guide.return_value = ReplayGuide(
                game_id="test.sgf",
                game_title="Test",
                total_moves=100,
                highlight_moments=[],
            )

            result = generate_curator_outputs(
                games_and_stats=[(mock_game, sample_stats)],
                curator_dir=tmp_curator_dir,
                batch_timestamp="20260126-153000",
            )

        with open(result.ranking_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["rankings"][0]["score_percentile"] == 0

    def test_percentile_is_int_0_to_100(self, tmp_curator_dir, mock_game, sample_stats):
        """Verify percentile scale and type in JSON."""
        with (
            patch("katrain.core.curator.batch.score_batch_suitability") as mock_score,
            patch("katrain.core.curator.batch.extract_replay_guide") as mock_guide,
        ):
            mock_score.return_value = [
                SuitabilityScore(0.5, 0.5, 0.5, percentile=75),
            ]
            mock_guide.return_value = ReplayGuide(
                game_id="test.sgf",
                game_title="Test",
                total_moves=100,
                highlight_moments=[],
            )

            result = generate_curator_outputs(
                games_and_stats=[(mock_game, sample_stats)],
                curator_dir=tmp_curator_dir,
                batch_timestamp="20260126-153000",
            )

        with open(result.ranking_path, encoding="utf-8") as f:
            data = json.load(f)

        for ranking in data["rankings"]:
            assert isinstance(ranking["score_percentile"], int)
            assert 0 <= ranking["score_percentile"] <= 100

    def test_timestamp_via_helper_patch(self, tmp_curator_dir):
        """Verify timestamp uses helper function (patchable)."""
        with patch(
            "katrain.core.curator.batch._get_iso_generated_timestamp",
            return_value="2026-01-26T15:30:00+09:00",
        ):
            result = generate_curator_outputs(
                games_and_stats=[],
                curator_dir=tmp_curator_dir,
                batch_timestamp="20260126-153000",
            )

        with open(result.ranking_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["generated"] == "2026-01-26T15:30:00+09:00"

    def test_user_weak_axes_sorted(self, tmp_curator_dir):
        """weak_axes in JSON are sorted alphabetically."""
        mock_aggregate = MagicMock()
        from katrain.core.analysis.skill_radar import RadarAxis

        weak_axes = {RadarAxis.FIGHTING, RadarAxis.ENDGAME}
        mock_aggregate.is_weak_axis = lambda axis: axis in weak_axes

        result = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=tmp_curator_dir,
            batch_timestamp="20260126-153000",
            user_aggregate=mock_aggregate,
        )

        with open(result.ranking_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["user_weak_axes"] == ["endgame", "fighting"]

    def test_partial_failure_counting(self, tmp_curator_dir, mock_game, sample_stats):
        """Verify error counting when guide extraction fails."""
        stats1 = {**sample_stats, "game_name": "game1.sgf"}
        stats2 = {**sample_stats, "game_name": "game2.sgf"}
        stats3 = {**sample_stats, "game_name": "game3.sgf"}

        guide1 = ReplayGuide("game1.sgf", "Game 1", 100, [])
        guide3 = ReplayGuide("game3.sgf", "Game 3", 100, [])

        with (
            patch("katrain.core.curator.batch.score_batch_suitability") as mock_score,
            patch("katrain.core.curator.batch.extract_replay_guide") as mock_guide,
        ):
            mock_score.return_value = [
                SuitabilityScore(0.5, 0.5, 0.5, percentile=50),
                SuitabilityScore(0.6, 0.6, 0.6, percentile=60),
                SuitabilityScore(0.7, 0.7, 0.7, percentile=70),
            ]
            mock_guide.side_effect = [
                guide1,
                Exception("fail"),
                guide3,
            ]

            result = generate_curator_outputs(
                games_and_stats=[
                    (mock_game, stats1),
                    (mock_game, stats2),
                    (mock_game, stats3),
                ],
                curator_dir=tmp_curator_dir,
                batch_timestamp="20260126-153000",
            )

        assert result.games_scored == 3
        assert result.guides_generated == 2
        assert len(result.errors) == 1

    def test_rankings_sorted_by_percentile_total_game_id(self, tmp_curator_dir, mock_game, sample_stats):
        """Verify rankings are sorted correctly."""
        stats1 = {**sample_stats, "game_name": "game_a.sgf"}
        stats2 = {**sample_stats, "game_name": "game_b.sgf"}
        stats3 = {**sample_stats, "game_name": "game_c.sgf"}

        with (
            patch("katrain.core.curator.batch.score_batch_suitability") as mock_score,
            patch("katrain.core.curator.batch.extract_replay_guide") as mock_guide,
        ):
            # Same percentile and total, should sort by game_id
            mock_score.return_value = [
                SuitabilityScore(0.5, 0.5, 0.5, percentile=50),
                SuitabilityScore(0.5, 0.5, 0.5, percentile=50),
                SuitabilityScore(0.7, 0.7, 0.7, percentile=70),  # Higher
            ]
            mock_guide.return_value = ReplayGuide("", "", 0, [])

            result = generate_curator_outputs(
                games_and_stats=[
                    (mock_game, stats1),
                    (mock_game, stats2),
                    (mock_game, stats3),
                ],
                curator_dir=tmp_curator_dir,
                batch_timestamp="20260126-153000",
            )

        with open(result.ranking_path, encoding="utf-8") as f:
            data = json.load(f)

        rankings = data["rankings"]
        # First should be game_c (highest percentile)
        assert rankings[0]["game_id"] == "game_c.sgf"
        assert rankings[0]["rank"] == 1
        # Then game_a and game_b (same percentile, sorted by game_id)
        assert rankings[1]["game_id"] == "game_a.sgf"
        assert rankings[1]["rank"] == 2
        assert rankings[2]["game_id"] == "game_b.sgf"
        assert rankings[2]["rank"] == 3

    def test_json_version_field(self, tmp_curator_dir):
        """Verify JSON version field is set."""
        result = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=tmp_curator_dir,
            batch_timestamp="20260126-153000",
        )

        with open(result.ranking_path, encoding="utf-8") as f:
            ranking = json.load(f)
        assert ranking["version"] == "1.0"

        with open(result.guide_path, encoding="utf-8") as f:
            guide = json.load(f)
        assert guide["version"] == "1.0"


# =============================================================================
# CuratorBatchResult Tests
# =============================================================================


class TestCuratorBatchResult:
    """Tests for CuratorBatchResult dataclass."""

    def test_default_values(self):
        """Verify default values."""
        result = CuratorBatchResult()
        assert result.ranking_path is None
        assert result.guide_path is None
        assert result.games_scored == 0
        assert result.guides_generated == 0
        assert result.errors == []

    def test_errors_is_list(self):
        """Verify errors field is mutable list."""
        result = CuratorBatchResult()
        result.errors.append("test error")
        assert len(result.errors) == 1

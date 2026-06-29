"""Tests for katrain.core.curator.batch (Phase 64).

Tests cover:
- _round_float (float rounding to FLOAT_PRECISION)
- _normalize_percentile (Optional[int] → int)
- _build_game_title (player B/W vs fallback)
- _extract_recommended_tags (top tags sorted, UNCERTAIN excluded)
- _get_user_weak_axes_sorted (deprecated)
- CuratorBatchResult (dataclass defaults)
- generate_curator_outputs (integration test with tmp_path,
  mocked dependencies for select_critical_moves and labels)

Note: _get_iso_generated_timestamp uses datetime.now().astimezone() and is
intentionally tested lightly (output structure check only).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.curator.batch import (
    FLOAT_PRECISION,
    CuratorBatchResult,
    _build_game_title,
    _extract_recommended_tags,
    _get_iso_generated_timestamp,
    _get_user_weak_axes_sorted,
    _normalize_percentile,
    _round_float,
    generate_curator_outputs,
)
from katrain.core.curator.models import UNCERTAIN_TAG, SuitabilityScore
from katrain.core.game_node import GameNode

# =============================================================================
# FLOAT_PRECISION constant
# =============================================================================


class TestFloatPrecisionConstant:
    """Tests for FLOAT_PRECISION constant."""

    def test_value_is_three(self):
        """Per Phase 64 docs, FLOAT_PRECISION should be 3."""
        assert FLOAT_PRECISION == 3


# =============================================================================
# _round_float
# =============================================================================


class TestRoundFloat:
    """Tests for _round_float helper."""

    def test_rounds_to_three_decimals(self):
        """Floats are rounded to FLOAT_PRECISION (3) decimals."""
        assert _round_float(1.23456789) == pytest.approx(1.235)

    def test_zero(self):
        """Zero stays zero."""
        assert _round_float(0.0) == 0.0

    def test_already_three_decimals(self):
        """Floats with 3 decimals are returned as-is."""
        assert _round_float(0.123) == 0.123

    def test_integer_input(self):
        """Integer input is converted to float."""
        assert _round_float(2) == 2.0


# =============================================================================
# _normalize_percentile
# =============================================================================


class TestNormalizePercentile:
    """Tests for Optional[int] → int normalization."""

    def test_none_becomes_zero(self):
        """None percentile (should not happen in batch context) becomes 0."""
        score = SuitabilityScore(needs_match=0.5, stability=0.5, total=0.5, percentile=None)
        assert _normalize_percentile(score) == 0

    def test_value_preserved(self):
        """Non-None percentile is preserved as int."""
        score = SuitabilityScore(needs_match=0.5, stability=0.5, total=0.5, percentile=75)
        assert _normalize_percentile(score) == 75

    def test_zero_preserved(self):
        """Percentile=0 stays 0."""
        score = SuitabilityScore(needs_match=0.0, stability=0.0, total=0.0, percentile=0)
        assert _normalize_percentile(score) == 0

    def test_hundred_preserved(self):
        """Percentile=100 stays 100."""
        score = SuitabilityScore(needs_match=1.0, stability=1.0, total=1.0, percentile=100)
        assert _normalize_percentile(score) == 100


# =============================================================================
# _get_iso_generated_timestamp
# =============================================================================


class TestGetIsoGeneratedTimestamp:
    """Tests for ISO timestamp generation."""

    def test_returns_string(self):
        """Output is a string."""
        ts = _get_iso_generated_timestamp()
        assert isinstance(ts, str)

    def test_iso_format_shape(self):
        """Format looks like ISO with timezone offset."""
        ts = _get_iso_generated_timestamp()
        # Pattern: 2026-01-26T15:30:00+09:00 or similar
        pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}"
        assert re.match(pattern, ts), f"Got: {ts}"


# =============================================================================
# _build_game_title
# =============================================================================


class TestBuildGameTitle:
    """Tests for game title builder."""

    def test_uses_player_names(self):
        """'Player B vs Player W' when both names present."""
        stats = {"player_b": "Shin Jinseo", "player_w": "Ke Jie"}
        assert _build_game_title(stats) == "Shin Jinseo vs Ke Jie"

    def test_falls_back_to_game_name(self):
        """When player names missing, uses game_name stem."""
        stats = {"player_b": "", "player_w": "", "game_name": "pro_games/game_001.sgf"}
        assert _build_game_title(stats) == "game_001"

    def test_missing_player_names_falls_back(self):
        """Partial player names still fallback to game_name."""
        stats = {"player_b": "", "player_w": "Ke Jie", "game_name": "my_game.sgf"}
        assert _build_game_title(stats) == "my_game"

    def test_empty_game_name_returns_empty_stem(self):
        """Empty game_name string falls through to Path('').stem = ''."""
        stats = {"player_b": "", "player_w": "", "game_name": ""}
        # stats.get uses default only when key MISSING. Existing empty key returns "".
        assert _build_game_title(stats) == ""

    def test_default_unknown_when_keys_missing(self):
        """Stats without player names uses default 'Unknown'."""
        stats: dict = {}
        assert _build_game_title(stats) == "Unknown"

    def test_strips_path_components(self):
        """Path-based game_name strips directory and extension."""
        stats = {"player_b": "", "player_w": "", "game_name": "/abs/path/foo.sgf"}
        assert _build_game_title(stats) == "foo"


# =============================================================================
# _extract_recommended_tags
# =============================================================================


class TestExtractRecommendedTags:
    """Tests for recommended tag extraction."""

    def test_empty_combined_returns_empty(self):
        """No tags → empty list."""
        assert _extract_recommended_tags({}) == []

    def test_single_player_tags(self):
        """Tags from one player."""
        stats = {
            "meaning_tags_by_player": {
                "B": {"overplay": 5, "missed_tesuji": 2},
            }
        }
        result = _extract_recommended_tags(stats)
        assert result == ["overplay", "missed_tesuji"]

    def test_combines_b_and_w(self):
        """Tag counts from B and W are combined."""
        stats = {
            "meaning_tags_by_player": {
                "B": {"overplay": 3},
                "W": {"overplay": 2},
            }
        }
        result = _extract_recommended_tags(stats)
        assert result == ["overplay"]

    def test_sorted_by_count_desc(self):
        """Higher counts come first."""
        stats = {
            "meaning_tags_by_player": {
                "B": {"overplay": 1, "missed_tesuji": 5, "slow_move": 3},
            }
        }
        result = _extract_recommended_tags(stats)
        assert result == ["missed_tesuji", "slow_move", "overplay"]

    def test_alphabetical_for_ties(self):
        """Ties broken alphabetically."""
        stats = {
            "meaning_tags_by_player": {
                "B": {"overplay": 3, "missed_tesuji": 3, "slow_move": 3},
            }
        }
        result = _extract_recommended_tags(stats)
        assert result == ["missed_tesuji", "overplay", "slow_move"]

    def test_excludes_uncertain(self):
        """UNCERTAIN tag is filtered out."""
        stats = {
            "meaning_tags_by_player": {
                "B": {"overplay": 3, UNCERTAIN_TAG: 10},
            }
        }
        result = _extract_recommended_tags(stats)
        assert UNCERTAIN_TAG not in result
        assert result == ["overplay"]

    def test_max_tags_limit(self):
        """max_tags limits output count."""
        stats = {
            "meaning_tags_by_player": {
                "B": {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5},
            }
        }
        result = _extract_recommended_tags(stats, max_tags=2)
        assert len(result) == 2
        assert result == ["e", "d"]  # top 2 by count

    def test_default_max_tags_three(self):
        """Default max_tags is 3."""
        stats = {
            "meaning_tags_by_player": {
                "B": {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5},
            }
        }
        result = _extract_recommended_tags(stats)
        assert len(result) == 3


# =============================================================================
# _get_user_weak_axes_sorted (deprecated)
# =============================================================================


class TestGetUserWeakAxesSorted:
    """Tests for deprecated weak axes getter."""

    def test_returns_empty_list(self):
        """Radar axes deprecated → empty list."""
        assert _get_user_weak_axes_sorted() == []


# =============================================================================
# CuratorBatchResult
# =============================================================================


class TestCuratorBatchResult:
    """Tests for CuratorBatchResult dataclass."""

    def test_default_initialization(self):
        """Defaults: paths None, counts 0, empty errors."""
        result = CuratorBatchResult()
        assert result.ranking_path is None
        assert result.guide_path is None
        assert result.games_scored == 0
        assert result.guides_generated == 0
        assert result.errors == []

    def test_can_set_all_fields(self):
        """All fields settable."""
        result = CuratorBatchResult(
            ranking_path="/tmp/rank.json",
            guide_path="/tmp/guide.json",
            games_scored=5,
            guides_generated=5,
            errors=["err1"],
        )
        assert result.ranking_path == "/tmp/rank.json"
        assert result.guide_path == "/tmp/guide.json"
        assert result.games_scored == 5
        assert result.guides_generated == 5
        assert result.errors == ["err1"]


# =============================================================================
# generate_curator_outputs (integration test with tmp_path + mocks)
# =============================================================================


def _build_mock_game_stats(game_name: str = "game_001.sgf", player_b: str = "P1", player_w: str = "P2") -> tuple:
    """Build a (game, stats) tuple for batch output generation.

    Uses a real GameNode so _collect_score_leads terminates (avoids infinite loop
    with MagicMock where MagicMock.__bool__ is True).
    """
    root = GameNode(properties={"SZ": ["19"], "KM": ["6.5"], "RU": ["Japanese"]})
    root.analysis = None
    game = MagicMock()
    game.root = root
    stats = {
        "game_name": game_name,
        "player_b": player_b,
        "player_w": player_w,
        "total_moves": 100,
        "meaning_tags_by_player": {
            "B": {"overplay": 3},
        },
    }
    return game, stats


class TestGenerateCuratorOutputs:
    """Integration tests for generate_curator_outputs with mocked deps."""

    def test_creates_output_directory(self, tmp_path: Path):
        """Non-existent curator_dir is created."""
        nonexistent = tmp_path / "new_curator_dir"
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            result = generate_curator_outputs(
                games_and_stats=[_build_mock_game_stats()],
                curator_dir=str(nonexistent),
                batch_timestamp="20260126-153000",
            )
        assert nonexistent.exists()
        assert result.errors == []

    def test_writes_ranking_file(self, tmp_path: Path):
        """ranking_path is set to created JSON file."""
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            result = generate_curator_outputs(
                games_and_stats=[_build_mock_game_stats()],
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
            )
        assert result.ranking_path is not None
        assert Path(result.ranking_path).exists()
        assert "curator_ranking_20260126-153000.json" in result.ranking_path

    def test_writes_guide_file(self, tmp_path: Path):
        """guide_path is set to created JSON file."""
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            result = generate_curator_outputs(
                games_and_stats=[_build_mock_game_stats()],
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
            )
        assert result.guide_path is not None
        assert Path(result.guide_path).exists()
        assert "replay_guide_20260126-153000.json" in result.guide_path

    def test_games_scored_count(self, tmp_path: Path):
        """games_scored reflects input length."""
        games = [_build_mock_game_stats(f"game_{i}.sgf") for i in range(3)]
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            result = generate_curator_outputs(
                games_and_stats=games,
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
            )
        assert result.games_scored == 3

    def test_guides_generated_count(self, tmp_path: Path):
        """guides_generated matches games count (success)."""
        games = [_build_mock_game_stats(f"game_{i}.sgf") for i in range(2)]
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            result = generate_curator_outputs(
                games_and_stats=games,
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
            )
        assert result.guides_generated == 2

    def test_empty_batch_writes_empty_files(self, tmp_path: Path):
        """Empty games_and_stats writes valid empty JSON files."""
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            result = generate_curator_outputs(
                games_and_stats=[],
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
            )
        assert result.games_scored == 0
        assert result.guides_generated == 0
        # Both files exist and contain valid JSON
        assert Path(result.ranking_path).exists()  # type: ignore[arg-type]
        assert Path(result.guide_path).exists()  # type: ignore[arg-type]
        ranking = json.loads(Path(result.ranking_path).read_text())  # type: ignore[arg-type]
        assert ranking["rankings"] == []
        assert ranking["total_games"] == 0

    def test_ranking_json_structure(self, tmp_path: Path):
        """Ranking JSON has expected structure."""
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            result = generate_curator_outputs(
                games_and_stats=[_build_mock_game_stats()],
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
            )
        data = json.loads(Path(result.ranking_path).read_text())  # type: ignore[arg-type]
        assert "version" in data
        assert data["version"] == "1.0"
        assert "generated" in data
        assert "total_games" in data
        assert data["total_games"] == 1
        assert "user_weak_axes" in data
        assert data["user_weak_axes"] == []  # deprecated
        assert "rankings" in data
        assert len(data["rankings"]) == 1

    def test_ranking_has_all_fields(self, tmp_path: Path):
        """Each ranking entry has all expected fields."""
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            result = generate_curator_outputs(
                games_and_stats=[_build_mock_game_stats("game_X.sgf", "Alice", "Bob")],
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
            )
        data = json.loads(Path(result.ranking_path).read_text())  # type: ignore[arg-type]
        ranking = data["rankings"][0]
        expected_keys = {
            "game_id", "title", "score_percentile", "needs_match",
            "stability", "total", "recommended_tags", "rank",
        }
        assert set(ranking.keys()) == expected_keys
        assert ranking["game_id"] == "game_X.sgf"
        assert ranking["title"] == "Alice vs Bob"
        assert ranking["recommended_tags"] == ["overplay"]

    def test_rankings_sorted_with_assigned_rank(self, tmp_path: Path):
        """Rankings are sorted and have rank field assigned."""
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            games = [_build_mock_game_stats(f"game_{i}.sgf") for i in range(3)]
            result = generate_curator_outputs(
                games_and_stats=games,
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
            )
        data = json.loads(Path(result.ranking_path).read_text())  # type: ignore[arg-type]
        ranks = [r["rank"] for r in data["rankings"]]
        # Ranks should be 1, 2, 3 in order
        assert ranks == [1, 2, 3]

    def test_user_aggregate_arg_accepted(self, tmp_path: Path):
        """user_aggregate parameter is accepted (even if unused since Phase 137)."""
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            result = generate_curator_outputs(
                games_and_stats=[_build_mock_game_stats()],
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
                user_aggregate={"fake": "aggregate"},
            )
        assert result.errors == []

    def test_log_cb_invoked(self, tmp_path: Path):
        """log_cb is called for status messages."""
        log_calls: list[str] = []
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            generate_curator_outputs(
                games_and_stats=[_build_mock_game_stats()],
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
                log_cb=log_calls.append,
            )
        assert len(log_calls) > 0

    def test_no_log_cb_no_error(self, tmp_path: Path):
        """log_cb=None works (no errors)."""
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            result = generate_curator_outputs(
                games_and_stats=[_build_mock_game_stats()],
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
                log_cb=None,
            )
        assert result.errors == []

    def test_custom_lang(self, tmp_path: Path):
        """Custom lang is passed to extract_replay_guide."""
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="en",
            ) as mock_iso,
        ):
            generate_curator_outputs(
                games_and_stats=[_build_mock_game_stats()],
                curator_dir=str(tmp_path),
                batch_timestamp="20260126-153000",
                lang="en",
            )
            # to_iso_lang_code called with "en"
            assert any(call.args and call.args[0] == "en" for call in mock_iso.call_args_list)

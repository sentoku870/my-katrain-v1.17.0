"""Tests for katrain.core.curator.guide_extractor (Phase 64).

Tests cover:
- HighlightMoment dataclass + to_dict() (with score_loss rounded to 2 decimals)
- ReplayGuide dataclass + to_dict()
- extract_replay_guide() (with select_critical_moves and
  get_meaning_tag_label_safe mocked)
- Language code normalization
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from katrain.core.curator.guide_extractor import (
    HighlightMoment,
    ReplayGuide,
    extract_replay_guide,
)

# =============================================================================
# Helpers
# =============================================================================


def _make_critical_move(**kwargs) -> MagicMock:
    """Build a MagicMock CriticalMove with sensible defaults."""
    defaults = {
        "move_number": 1,
        "player": "B",
        "gtp_coord": "D4",
        "meaning_tag_id": "overplay",
        "meaning_tag_label": "Overplay",
        "score_loss": 1.234,
        "game_phase": "middle",
    }
    defaults.update(kwargs)
    cm = MagicMock()
    for k, v in defaults.items():
        setattr(cm, k, v)
    return cm


# =============================================================================
# HighlightMoment
# =============================================================================


class TestHighlightMoment:
    """Tests for HighlightMoment dataclass."""

    def test_basic_creation(self):
        """All fields can be set with positional/keyword args."""
        hm = HighlightMoment(
            move_number=10,
            player="W",
            gtp_coord="Q5",
            meaning_tag_id="overplay",
            meaning_tag_label="Overplay",
            score_loss=2.5,
            game_phase="yose",
        )
        assert hm.move_number == 10
        assert hm.player == "W"
        assert hm.gtp_coord == "Q5"
        assert hm.meaning_tag_id == "overplay"
        assert hm.meaning_tag_label == "Overplay"
        assert hm.score_loss == 2.5
        assert hm.game_phase == "yose"

    def test_label_can_be_none(self):
        """meaning_tag_label is Optional[str] (None if tag not found)."""
        hm = HighlightMoment(
            move_number=1,
            player="B",
            gtp_coord="D4",
            meaning_tag_id="unknown_tag",
            meaning_tag_label=None,
            score_loss=1.0,
            game_phase="opening",
        )
        assert hm.meaning_tag_label is None

    def test_to_dict_basic(self):
        """to_dict returns all fields with score_loss rounded to 2 decimals."""
        hm = HighlightMoment(
            move_number=1,
            player="B",
            gtp_coord="D4",
            meaning_tag_id="overplay",
            meaning_tag_label="Overplay",
            score_loss=1.234567,
            game_phase="middle",
        )
        d = hm.to_dict()
        assert d["move_number"] == 1
        assert d["player"] == "B"
        assert d["gtp_coord"] == "D4"
        assert d["meaning_tag_id"] == "overplay"
        assert d["meaning_tag_label"] == "Overplay"
        assert d["game_phase"] == "middle"

    def test_to_dict_rounds_score_loss(self):
        """score_loss is rounded to 2 decimals in to_dict output."""
        hm = HighlightMoment(
            move_number=1,
            player="B",
            gtp_coord="D4",
            meaning_tag_id="overplay",
            meaning_tag_label="Overplay",
            score_loss=1.235,  # rounds to 1.24 (banker's rounding: round half to even)
            game_phase="middle",
        )
        # Python's round() uses banker's rounding by default
        d = hm.to_dict()
        assert d["score_loss"] == 1.24

    def test_to_dict_zero_score_loss(self):
        """score_loss=0.0 stays 0.0 in output."""
        hm = HighlightMoment(
            move_number=1,
            player="B",
            gtp_coord="D4",
            meaning_tag_id="overplay",
            meaning_tag_label="Overplay",
            score_loss=0.0,
            game_phase="opening",
        )
        assert hm.to_dict()["score_loss"] == 0.0

    def test_frozen_dataclass(self):
        """HighlightMoment is frozen (immutable)."""
        hm = HighlightMoment(
            move_number=1,
            player="B",
            gtp_coord="D4",
            meaning_tag_id="overplay",
            meaning_tag_label="Overplay",
            score_loss=1.0,
            game_phase="middle",
        )
        with pytest.raises((AttributeError, Exception)):
            hm.move_number = 99  # type: ignore[misc]

    def test_to_dict_with_none_label(self):
        """to_dict works when meaning_tag_label is None."""
        hm = HighlightMoment(
            move_number=1,
            player="B",
            gtp_coord="D4",
            meaning_tag_id="unknown",
            meaning_tag_label=None,
            score_loss=1.0,
            game_phase="middle",
        )
        d = hm.to_dict()
        assert d["meaning_tag_label"] is None


# =============================================================================
# ReplayGuide
# =============================================================================


class TestReplayGuide:
    """Tests for ReplayGuide dataclass."""

    def test_basic_creation_empty_highlights(self):
        """ReplayGuide with zero highlights is valid."""
        rg = ReplayGuide(
            game_id="game_001.sgf",
            game_title="Player B vs Player W",
            total_moves=200,
            highlight_moments=[],
        )
        assert rg.game_id == "game_001.sgf"
        assert rg.game_title == "Player B vs Player W"
        assert rg.total_moves == 200
        assert rg.highlight_moments == []

    def test_to_dict_empty(self):
        """to_dict with no highlights."""
        rg = ReplayGuide(
            game_id="game_001.sgf",
            game_title="Test",
            total_moves=100,
            highlight_moments=[],
        )
        d = rg.to_dict()
        assert d["game_id"] == "game_001.sgf"
        assert d["game_title"] == "Test"
        assert d["total_moves"] == 100
        assert d["highlight_moments"] == []

    def test_to_dict_with_highlights(self):
        """to_dict serializes highlights as dicts."""
        hm = HighlightMoment(
            move_number=10,
            player="B",
            gtp_coord="D4",
            meaning_tag_id="overplay",
            meaning_tag_label="Overplay",
            score_loss=1.5,
            game_phase="middle",
        )
        rg = ReplayGuide(
            game_id="game_001.sgf",
            game_title="Test Game",
            total_moves=200,
            highlight_moments=[hm],
        )
        d = rg.to_dict()
        assert len(d["highlight_moments"]) == 1
        h = d["highlight_moments"][0]
        assert h["move_number"] == 10
        assert h["gtp_coord"] == "D4"
        assert h["score_loss"] == 1.5

    def test_frozen_dataclass(self):
        """ReplayGuide is frozen."""
        rg = ReplayGuide(
            game_id="g", game_title="T", total_moves=0, highlight_moments=[]
        )
        with pytest.raises((AttributeError, Exception)):
            rg.game_id = "other"  # type: ignore[misc]


# =============================================================================
# extract_replay_guide
# =============================================================================


class TestExtractReplayGuide:
    """Tests for extract_replay_guide with mocked dependencies."""

    def test_returns_replay_guide(self):
        """extract_replay_guide returns ReplayGuide."""
        game = MagicMock()
        cm = _make_critical_move()
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[cm],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="Overplay",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            guide = extract_replay_guide(
                game=game,
                game_id="game_001.sgf",
                game_title="Test",
                total_moves=100,
            )
        assert isinstance(guide, ReplayGuide)

    def test_uses_provided_metadata(self):
        """game_id, game_title, total_moves passed through to ReplayGuide."""
        game = MagicMock()
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
            guide = extract_replay_guide(
                game=game,
                game_id="pro_games/2026/game_001.sgf",
                game_title="Shin Jinseo vs Ke Jie",
                total_moves=257,
            )
        assert guide.game_id == "pro_games/2026/game_001.sgf"
        assert guide.game_title == "Shin Jinseo vs Ke Jie"
        assert guide.total_moves == 257

    def test_max_highlights_respected(self):
        """max_highlights is passed to select_critical_moves."""
        game = MagicMock()
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ) as mock_sel,
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            extract_replay_guide(game=game, game_id="g", game_title="T", total_moves=10, max_highlights=3)
            mock_sel.assert_called_once()
            args, kwargs = mock_sel.call_args
            assert kwargs.get("max_moves") == 3 or (
                len(args) >= 2 and args[1] == 3
            )

    def test_level_passed_through(self):
        """level parameter is passed to select_critical_moves."""
        game = MagicMock()
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ) as mock_sel,
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            extract_replay_guide(
                game=game, game_id="g", game_title="T", total_moves=10, level="hard"
            )
            args, kwargs = mock_sel.call_args
            assert kwargs.get("level") == "hard" or (len(args) >= 3 and args[2] == "hard")

    def test_lang_conversion_to_iso(self):
        """Internal lang code is converted via to_iso_lang_code before select."""
        game = MagicMock()
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ) as mock_sel,
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="en",
            ) as mock_iso,
        ):
            extract_replay_guide(
                game=game, game_id="g", game_title="T", total_moves=10, lang="en"
            )
            # to_iso_lang_code called
            mock_iso.assert_called_once_with("en")
            # select_critical_moves received the ISO code
            args, kwargs = mock_sel.call_args
            iso_lang = kwargs.get("lang")
            if iso_lang is None and len(args) >= 4:
                iso_lang = args[3]
            assert iso_lang == "en"

    def test_highlight_moments_constructed(self):
        """Each CriticalMove → HighlightMoment with proper fields."""
        game = MagicMock()
        cm = _make_critical_move(
            move_number=42, player="W", gtp_coord="Q16",
            meaning_tag_id="reading_failure",
            meaning_tag_label="Reading Failure",
            score_loss=2.789,
            game_phase="middle",
        )
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[cm],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="Reading Failure",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            guide = extract_replay_guide(
                game=game, game_id="g", game_title="T", total_moves=200
            )
        assert len(guide.highlight_moments) == 1
        hm = guide.highlight_moments[0]
        assert hm.move_number == 42
        assert hm.player == "W"
        assert hm.gtp_coord == "Q16"
        assert hm.meaning_tag_id == "reading_failure"
        assert hm.meaning_tag_label == "Reading Failure"
        assert hm.score_loss == 2.789
        assert hm.game_phase == "middle"

    def test_label_resolved_per_highlight(self):
        """get_meaning_tag_label_safe called for each CriticalMove."""
        game = MagicMock()
        cm1 = _make_critical_move(meaning_tag_id="overplay", meaning_tag_label="Over")
        cm2 = _make_critical_move(meaning_tag_id="missed_tesuji", meaning_tag_label="MT")
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[cm1, cm2],
            ),
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                side_effect=lambda tag_id, lang: f"Label-{tag_id}",
            ) as mock_label,
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            extract_replay_guide(
                game=game, game_id="g", game_title="T", total_moves=200, lang="jp"
            )
        # Called twice (once per CriticalMove)
        assert mock_label.call_count == 2

    def test_empty_highlights(self):
        """Zero critical moves → empty highlight_moments list."""
        game = MagicMock()
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
            guide = extract_replay_guide(
                game=game, game_id="g", game_title="T", total_moves=10
            )
        assert guide.highlight_moments == []

    def test_default_max_highlights(self):
        """Default max_highlights=5 is passed to select_critical_moves."""
        game = MagicMock()
        with (
            patch(
                "katrain.core.analysis.select_critical_moves",
                return_value=[],
            ) as mock_sel,
            patch(
                "katrain.core.curator.guide_extractor.get_meaning_tag_label_safe",
                return_value="x",
            ),
            patch(
                "katrain.core.curator.guide_extractor.to_iso_lang_code",
                return_value="ja",
            ),
        ):
            extract_replay_guide(game=game, game_id="g", game_title="T", total_moves=10)
            args, kwargs = mock_sel.call_args
            assert kwargs.get("max_moves") == 5 or (
                len(args) >= 2 and args[1] == 5
            )

    def test_default_lang_jp(self):
        """Default lang='jp' is passed to to_iso_lang_code."""
        game = MagicMock()
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
            ) as mock_iso,
        ):
            extract_replay_guide(game=game, game_id="g", game_title="T", total_moves=10)
            mock_iso.assert_called_once_with("jp")

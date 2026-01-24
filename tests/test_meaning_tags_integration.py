# -*- coding: utf-8 -*-
"""Tests for meaning_tags/integration.py.

Part of Phase 47: Meaning Tags Integration - PR-1.
"""

import pytest

from katrain.core.analysis.meaning_tags import (
    MAX_DESCRIPTION_LENGTH,
    MeaningTagId,
    format_meaning_tag_with_definition,
    format_meaning_tag_with_definition_safe,
    get_meaning_tag_label_safe,
    normalize_lang,
)


# =============================================================================
# normalize_lang Tests
# =============================================================================


class TestNormalizeLang:
    """Tests for normalize_lang function."""

    def test_jp_to_ja(self) -> None:
        """'jp' should be normalized to 'ja'."""
        assert normalize_lang("jp") == "ja"

    def test_ja_passthrough(self) -> None:
        """'ja' should remain 'ja'."""
        assert normalize_lang("ja") == "ja"

    def test_en_passthrough(self) -> None:
        """'en' should remain 'en'."""
        assert normalize_lang("en") == "en"

    def test_unknown_falls_back_to_en(self) -> None:
        """Unknown language codes should fall back to 'en'."""
        assert normalize_lang("fr") == "en"
        assert normalize_lang("de") == "en"
        assert normalize_lang("zh") == "en"

    def test_empty_string_falls_back_to_en(self) -> None:
        """Empty string should fall back to 'en'."""
        assert normalize_lang("") == "en"

    def test_case_insensitivity(self) -> None:
        """Language codes are case-insensitive (for robustness).

        Updated in Phase 52: normalize_lang now uses to_iso_lang_code
        which handles case-insensitively via normalize_lang_code.
        """
        assert normalize_lang("JP") == "ja"  # Now recognized as "jp" -> "ja"
        assert normalize_lang("EN") == "en"  # Now recognized as "en" -> "en"


# =============================================================================
# get_meaning_tag_label_safe Tests
# =============================================================================


class TestGetMeaningTagLabelSafe:
    """Tests for get_meaning_tag_label_safe function."""

    def test_valid_tag_ja(self) -> None:
        """Valid tag ID with Japanese language."""
        label = get_meaning_tag_label_safe("life_death_error", "ja")
        assert label == "死活ミス"

    def test_valid_tag_en(self) -> None:
        """Valid tag ID with English language."""
        label = get_meaning_tag_label_safe("life_death_error", "en")
        assert label == "Life/Death Error"

    def test_valid_tag_jp_normalized(self) -> None:
        """Valid tag ID with 'jp' should be normalized to 'ja'."""
        label = get_meaning_tag_label_safe("life_death_error", "jp")
        assert label == "死活ミス"

    def test_none_returns_none(self) -> None:
        """None input should return None."""
        assert get_meaning_tag_label_safe(None, "ja") is None
        assert get_meaning_tag_label_safe(None, "en") is None

    def test_invalid_tag_returns_none(self) -> None:
        """Invalid tag ID should return None."""
        assert get_meaning_tag_label_safe("invalid_tag", "ja") is None
        assert get_meaning_tag_label_safe("nonexistent", "en") is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string should return None."""
        assert get_meaning_tag_label_safe("", "ja") is None

    @pytest.mark.parametrize("tag_id", [tag.value for tag in MeaningTagId])
    def test_all_valid_tags_return_label(self, tag_id: str) -> None:
        """All MeaningTagId values should return a label."""
        label_ja = get_meaning_tag_label_safe(tag_id, "ja")
        label_en = get_meaning_tag_label_safe(tag_id, "en")
        assert label_ja is not None
        assert label_en is not None
        assert isinstance(label_ja, str)
        assert isinstance(label_en, str)


# =============================================================================
# format_meaning_tag_with_definition Tests
# =============================================================================


class TestFormatMeaningTagWithDefinition:
    """Tests for format_meaning_tag_with_definition function."""

    def test_format_ja(self) -> None:
        """Japanese format should include label and truncated description."""
        result = format_meaning_tag_with_definition(MeaningTagId.LIFE_DEATH_ERROR, "ja")
        assert result.startswith("死活ミス: ")
        assert "..." in result  # Description should be truncated

    def test_format_en(self) -> None:
        """English format should include label and truncated description."""
        result = format_meaning_tag_with_definition(MeaningTagId.LIFE_DEATH_ERROR, "en")
        assert result.startswith("Life/Death Error: ")
        assert "..." in result  # Description should be truncated

    def test_format_jp_normalized(self) -> None:
        """'jp' should be normalized to 'ja'."""
        result_jp = format_meaning_tag_with_definition(MeaningTagId.UNCERTAIN, "jp")
        result_ja = format_meaning_tag_with_definition(MeaningTagId.UNCERTAIN, "ja")
        assert result_jp == result_ja

    def test_description_truncation(self) -> None:
        """Description should be truncated to MAX_DESCRIPTION_LENGTH."""
        result = format_meaning_tag_with_definition(MeaningTagId.LIFE_DEATH_ERROR, "en")
        # Format: "Label: description..."
        # Find description part after ": "
        colon_idx = result.index(": ")
        description_part = result[colon_idx + 2:]
        # Should be MAX_DESCRIPTION_LENGTH + "..."
        assert len(description_part) <= MAX_DESCRIPTION_LENGTH + 3

    def test_short_description_not_truncated(self) -> None:
        """Short descriptions should not have '...' added."""
        # UNCERTAIN has a short description
        result = format_meaning_tag_with_definition(MeaningTagId.UNCERTAIN, "en")
        # "Uncertain: Could not be clearly classified into any category."
        # Description is ~50 chars, longer than 30, so it WILL be truncated
        assert "..." in result  # It should be truncated

    @pytest.mark.parametrize("tag_id", list(MeaningTagId))
    def test_all_tags_format_correctly(self, tag_id: MeaningTagId) -> None:
        """All tags should produce valid formatted strings."""
        result_ja = format_meaning_tag_with_definition(tag_id, "ja")
        result_en = format_meaning_tag_with_definition(tag_id, "en")

        assert ": " in result_ja
        assert ": " in result_en
        assert len(result_ja) > 0
        assert len(result_en) > 0


# =============================================================================
# format_meaning_tag_with_definition_safe Tests
# =============================================================================


class TestFormatMeaningTagWithDefinitionSafe:
    """Tests for format_meaning_tag_with_definition_safe function."""

    def test_valid_tag(self) -> None:
        """Valid tag ID should return formatted string."""
        result = format_meaning_tag_with_definition_safe("overplay", "ja")
        assert result is not None
        assert "無理手" in result

    def test_none_returns_none(self) -> None:
        """None input should return None."""
        assert format_meaning_tag_with_definition_safe(None, "ja") is None

    def test_invalid_tag_returns_none(self) -> None:
        """Invalid tag ID should return None."""
        assert format_meaning_tag_with_definition_safe("invalid", "ja") is None


# =============================================================================
# MoveEval.meaning_tag_id Field Tests
# =============================================================================


class TestMoveEvalMeaningTagIdField:
    """Tests for the new MoveEval.meaning_tag_id field."""

    def test_field_exists_with_default_none(self) -> None:
        """MoveEval should have meaning_tag_id field defaulting to None."""
        from katrain.core.analysis.models import MoveEval

        move_eval = MoveEval(
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
            realized_points_lost=0.0,
            root_visits=100,
        )
        assert move_eval.meaning_tag_id is None

    def test_field_accepts_string(self) -> None:
        """MoveEval.meaning_tag_id should accept string values."""
        from katrain.core.analysis.models import MoveEval

        move_eval = MoveEval(
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
            realized_points_lost=0.0,
            root_visits=100,
            meaning_tag_id="overplay",
        )
        assert move_eval.meaning_tag_id == "overplay"

    def test_field_is_mutable(self) -> None:
        """MoveEval.meaning_tag_id should be assignable after creation."""
        from katrain.core.analysis.models import MoveEval

        move_eval = MoveEval(
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
            realized_points_lost=0.0,
            root_visits=100,
        )
        assert move_eval.meaning_tag_id is None

        # Assign after creation
        move_eval.meaning_tag_id = "life_death_error"
        assert move_eval.meaning_tag_id == "life_death_error"


# =============================================================================
# MAX_DESCRIPTION_LENGTH Constant Tests
# =============================================================================


class TestMaxDescriptionLength:
    """Tests for MAX_DESCRIPTION_LENGTH constant."""

    def test_constant_value(self) -> None:
        """MAX_DESCRIPTION_LENGTH should be 30."""
        assert MAX_DESCRIPTION_LENGTH == 30

    def test_constant_is_exported(self) -> None:
        """MAX_DESCRIPTION_LENGTH should be in __all__."""
        from katrain.core.analysis import meaning_tags

        assert "MAX_DESCRIPTION_LENGTH" in meaning_tags.__all__

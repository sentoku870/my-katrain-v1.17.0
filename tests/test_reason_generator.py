# -*- coding: utf-8 -*-
"""Tests for reason_generator.py (Phase 86)."""

import pytest

from katrain.core.analysis.board_context import BoardArea
from katrain.core.analysis.reason_generator import (
    AREA_VOCABULARY,
    COMBINATION_REASONS,
    PHASE_VOCABULARY,
    SINGLE_TAG_REASONS,
    SUPPORTED_TAGS,
    ReasonTemplate,
    generate_reason,
    generate_reason_safe,
)


# =============================================================================
# Template Coverage Tests
# =============================================================================


class TestSupportedTagsCoverage:
    """Verify SINGLE_TAG_REASONS covers SUPPORTED_TAGS."""

    def test_supported_tags_coverage(self):
        """All SUPPORTED_TAGS have a template in SINGLE_TAG_REASONS."""
        for tag in SUPPORTED_TAGS:
            assert tag in SINGLE_TAG_REASONS, f"Missing template for tag: {tag}"

    def test_single_tag_reasons_keys_match_supported(self):
        """SINGLE_TAG_REASONS keys exactly match SUPPORTED_TAGS."""
        assert set(SINGLE_TAG_REASONS.keys()) == SUPPORTED_TAGS


class TestCombinationReasonsBilingual:
    """Verify COMBINATION_REASONS have both languages."""

    def test_combination_reasons_have_both_languages(self):
        """All COMBINATION_REASONS entries have jp and en."""
        for key, template in COMBINATION_REASONS.items():
            assert isinstance(template, ReasonTemplate), f"Invalid template for {key}"
            assert template.jp, f"Empty jp for {key}"
            assert template.en, f"Empty en for {key}"


# =============================================================================
# Vocabulary Validation Tests
# =============================================================================


class TestVocabularyValidation:
    """Verify vocabulary matches actual enum/dataclass values."""

    def test_area_vocabulary_matches_board_area(self):
        """AREA_VOCABULARY matches BoardArea enum values."""
        board_area_values = {area.value for area in BoardArea}
        assert AREA_VOCABULARY == board_area_values

    def test_phase_vocabulary_matches_signature(self):
        """PHASE_VOCABULARY contains valid phase values."""
        expected = {"opening", "middle", "endgame"}
        assert PHASE_VOCABULARY == expected


# =============================================================================
# Matching Priority Tests
# =============================================================================


class TestMatchingPriority:
    """Test combination vs single-tag matching priority."""

    def test_combination_priority(self):
        """Combination match is preferred over single-tag."""
        # ("opening", "corner", "direction_error") exists in COMBINATION_REASONS
        result = generate_reason(
            "direction_error",
            phase="opening",
            area="corner",
            lang="jp",
        )
        # Should use combination template, not single-tag
        assert result is not None
        assert "布石" in result  # Combination has "布石の基本を復習"

    def test_unknown_tag_returns_none(self):
        """Unknown tag returns None."""
        result = generate_reason(
            "unknown_tag_xyz",
            phase="middle",
            area="corner",
            lang="jp",
        )
        assert result is None


# =============================================================================
# Language Normalization Tests
# =============================================================================


class TestLanguageNormalization:
    """Test language code normalization behavior."""

    def test_lang_none_defaults_to_jp(self):
        """lang=None returns Japanese output."""
        result = generate_reason("overplay", lang=None)
        assert result is not None
        assert "無理な手" in result  # Japanese text

    def test_lang_empty_defaults_to_en(self):
        """lang="" returns English output."""
        result = generate_reason("overplay", lang="")
        assert result is not None
        assert "overplay" in result.lower()  # English text

    def test_lang_whitespace_defaults_to_en(self):
        """lang="  " returns English output."""
        result = generate_reason("overplay", lang="   ")
        assert result is not None
        assert "overplay" in result.lower()

    def test_lang_jp_variants(self):
        """jp/ja/ja_JP/ja-JP all return Japanese."""
        for lang in ["jp", "ja", "ja_JP", "ja-JP"]:
            result = generate_reason("overplay", lang=lang)
            assert result is not None
            assert "無理な手" in result, f"Failed for lang={lang}"

    def test_lang_en_variants(self):
        """en/en_US return English."""
        for lang in ["en", "en_US"]:
            result = generate_reason("overplay", lang=lang)
            assert result is not None
            assert "overplay" in result.lower(), f"Failed for lang={lang}"

    def test_lang_unknown_defaults_to_en(self):
        """Unknown language code falls back to English."""
        result = generate_reason("overplay", lang="fr")
        assert result is not None
        assert "overplay" in result.lower()


# =============================================================================
# Safe Version Tests
# =============================================================================


class TestGenerateReasonSafe:
    """Test generate_reason_safe behavior."""

    def test_safe_never_raises(self):
        """generate_reason_safe never raises with any input."""
        # Should not raise
        result = generate_reason_safe(None, None, None, None)
        assert isinstance(result, str)

    def test_safe_returns_string(self):
        """generate_reason_safe always returns str."""
        result = generate_reason_safe("overplay")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_safe_unknown_tag_returns_empty(self):
        """Unknown tag returns empty string (no fallback_label)."""
        result = generate_reason_safe("unknown_tag_xyz")
        assert result == ""

    def test_safe_fallback_label(self):
        """Unknown tag returns fallback_label if provided."""
        result = generate_reason_safe(
            "unknown_tag_xyz",
            fallback_label="[分類不明]",
        )
        assert result == "[分類不明]"


# =============================================================================
# Wildcard Matching Tests
# =============================================================================


class TestWildcardMatching:
    """Test wildcard matching behavior."""

    def test_wildcard_area_match(self):
        """(phase, "*", tag) matches with any area value."""
        # ("middle", "*", "overplay") exists
        result = generate_reason(
            "overplay",
            phase="middle",
            area="center",  # Any area should match
            lang="jp",
        )
        assert result is not None
        assert "中盤" in result  # Combination template

    def test_area_none_uses_wildcard(self):
        """area=None still matches (phase, "*", tag)."""
        # ("middle", "*", "overplay") exists
        result = generate_reason(
            "overplay",
            phase="middle",
            area=None,  # None should also match wildcard
            lang="jp",
        )
        assert result is not None
        assert "中盤" in result

    def test_phase_none_skips_phase_wildcard(self):
        """phase=None cannot match (phase, "*", tag)."""
        # With phase=None, should fall back to single-tag
        result = generate_reason(
            "overplay",
            phase=None,
            area="corner",
            lang="jp",
        )
        assert result is not None
        # Should use single-tag template
        assert "無理な手" in result

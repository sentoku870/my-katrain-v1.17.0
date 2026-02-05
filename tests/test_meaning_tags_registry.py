"""Tests for meaning_tags/registry.py.

Part of Phase 46: Meaning Tags System Core - PR-1.
"""

import pytest

from katrain.core.analysis.meaning_tags import (
    MEANING_TAG_REGISTRY,
    MeaningTagDefinition,
    MeaningTagId,
    get_tag_definition,
    get_tag_description,
    get_tag_label,
)

# =============================================================================
# MEANING_TAG_REGISTRY Tests
# =============================================================================


class TestMeaningTagRegistry:
    """Tests for MEANING_TAG_REGISTRY completeness and correctness."""

    def test_registry_contains_all_twelve_tags(self) -> None:
        """Registry should contain all 12 MeaningTagId values."""
        expected_ids = set(MeaningTagId)
        actual_ids = set(MEANING_TAG_REGISTRY.keys())
        assert actual_ids == expected_ids

    def test_registry_values_are_definitions(self) -> None:
        """All registry values should be MeaningTagDefinition instances."""
        for tag_id, definition in MEANING_TAG_REGISTRY.items():
            assert isinstance(definition, MeaningTagDefinition)
            assert definition.id == tag_id

    def test_all_definitions_have_labels(self) -> None:
        """All definitions should have non-empty labels."""
        for definition in MEANING_TAG_REGISTRY.values():
            assert definition.ja_label, f"{definition.id} missing ja_label"
            assert definition.en_label, f"{definition.id} missing en_label"

    def test_all_definitions_have_descriptions(self) -> None:
        """All definitions should have non-empty descriptions."""
        for definition in MEANING_TAG_REGISTRY.values():
            assert definition.ja_description, f"{definition.id} missing ja_description"
            assert definition.en_description, f"{definition.id} missing en_description"


# =============================================================================
# Lexicon Anchor Tests
# =============================================================================


class TestLexiconAnchors:
    """Tests for Lexicon anchor configuration."""

    # Tags with valid Lexicon anchors (5 tags)
    # Note: direction_of_play is in concepts section of YAML, not entries,
    # so it's not available in LexiconStore
    TAGS_WITH_ANCHORS = {
        MeaningTagId.MISSED_TESUJI: "tesuji",
        MeaningTagId.ENDGAME_SLIP: "yose",
        MeaningTagId.CONNECTION_MISS: "connection",
        MeaningTagId.CAPTURE_RACE_LOSS: "semeai",
        MeaningTagId.TERRITORIAL_LOSS: "territory",
    }

    # Tags without Lexicon anchors (7 tags)
    TAGS_WITHOUT_ANCHORS = {
        MeaningTagId.OVERPLAY,
        MeaningTagId.SLOW_MOVE,
        MeaningTagId.DIRECTION_ERROR,  # direction_of_play not in entries
        MeaningTagId.SHAPE_MISTAKE,
        MeaningTagId.READING_FAILURE,
        MeaningTagId.LIFE_DEATH_ERROR,
        MeaningTagId.UNCERTAIN,
    }

    def test_five_tags_have_anchors(self) -> None:
        """Exactly 5 tags should have Lexicon anchors."""
        tags_with_anchors = {
            tag_id for tag_id, defn in MEANING_TAG_REGISTRY.items() if defn.default_lexicon_anchor is not None
        }
        assert tags_with_anchors == set(self.TAGS_WITH_ANCHORS.keys())

    def test_seven_tags_have_no_anchors(self) -> None:
        """Exactly 7 tags should have no Lexicon anchors."""
        tags_without_anchors = {
            tag_id for tag_id, defn in MEANING_TAG_REGISTRY.items() if defn.default_lexicon_anchor is None
        }
        assert tags_without_anchors == self.TAGS_WITHOUT_ANCHORS

    @pytest.mark.parametrize(
        "tag_id,expected_anchor",
        [
            (MeaningTagId.MISSED_TESUJI, "tesuji"),
            (MeaningTagId.ENDGAME_SLIP, "yose"),
            (MeaningTagId.CONNECTION_MISS, "connection"),
            (MeaningTagId.CAPTURE_RACE_LOSS, "semeai"),
            (MeaningTagId.TERRITORIAL_LOSS, "territory"),
        ],
    )
    def test_specific_anchor_values(self, tag_id: MeaningTagId, expected_anchor: str) -> None:
        """Verify specific anchor IDs match the plan."""
        definition = MEANING_TAG_REGISTRY[tag_id]
        assert definition.default_lexicon_anchor == expected_anchor

    @pytest.mark.parametrize(
        "tag_id",
        [
            MeaningTagId.OVERPLAY,
            MeaningTagId.SLOW_MOVE,
            MeaningTagId.DIRECTION_ERROR,  # direction_of_play not in entries
            MeaningTagId.SHAPE_MISTAKE,
            MeaningTagId.READING_FAILURE,
            MeaningTagId.LIFE_DEATH_ERROR,
            MeaningTagId.UNCERTAIN,
        ],
    )
    def test_tags_without_anchor_are_none(self, tag_id: MeaningTagId) -> None:
        """Tags without valid Lexicon entries should have None anchor."""
        definition = MEANING_TAG_REGISTRY[tag_id]
        assert definition.default_lexicon_anchor is None


# =============================================================================
# Related Reason Tags Tests
# =============================================================================


class TestRelatedReasonTags:
    """Tests for related_reason_tags configuration."""

    def test_reason_tags_are_tuples(self) -> None:
        """related_reason_tags should be tuples (immutable)."""
        for definition in MEANING_TAG_REGISTRY.values():
            assert isinstance(definition.related_reason_tags, tuple)

    def test_capture_race_loss_reason_tags(self) -> None:
        """CAPTURE_RACE_LOSS should have atari and low_liberties."""
        defn = MEANING_TAG_REGISTRY[MeaningTagId.CAPTURE_RACE_LOSS]
        assert "atari" in defn.related_reason_tags
        assert "low_liberties" in defn.related_reason_tags

    def test_connection_miss_reason_tags(self) -> None:
        """CONNECTION_MISS should have need_connect and cut_risk."""
        defn = MEANING_TAG_REGISTRY[MeaningTagId.CONNECTION_MISS]
        assert "need_connect" in defn.related_reason_tags
        assert "cut_risk" in defn.related_reason_tags

    def test_reading_failure_reason_tags(self) -> None:
        """READING_FAILURE should have reading_failure."""
        defn = MEANING_TAG_REGISTRY[MeaningTagId.READING_FAILURE]
        assert "reading_failure" in defn.related_reason_tags

    def test_endgame_slip_reason_tags(self) -> None:
        """ENDGAME_SLIP should have endgame_hint."""
        defn = MEANING_TAG_REGISTRY[MeaningTagId.ENDGAME_SLIP]
        assert "endgame_hint" in defn.related_reason_tags

    def test_overplay_reason_tags(self) -> None:
        """OVERPLAY should have heavy_loss."""
        defn = MEANING_TAG_REGISTRY[MeaningTagId.OVERPLAY]
        assert "heavy_loss" in defn.related_reason_tags

    def test_uncertain_has_no_reason_tags(self) -> None:
        """UNCERTAIN should have empty reason_tags."""
        defn = MEANING_TAG_REGISTRY[MeaningTagId.UNCERTAIN]
        assert defn.related_reason_tags == ()


# =============================================================================
# get_tag_definition Tests
# =============================================================================


class TestGetTagDefinition:
    """Tests for get_tag_definition function."""

    def test_returns_definition(self) -> None:
        """Should return MeaningTagDefinition for valid ID."""
        definition = get_tag_definition(MeaningTagId.LIFE_DEATH_ERROR)
        assert isinstance(definition, MeaningTagDefinition)
        assert definition.id == MeaningTagId.LIFE_DEATH_ERROR

    def test_all_tags_accessible(self) -> None:
        """All tags should be accessible via get_tag_definition."""
        for tag_id in MeaningTagId:
            definition = get_tag_definition(tag_id)
            assert definition.id == tag_id

    def test_invalid_key_raises_key_error(self) -> None:
        """Invalid key should raise KeyError."""
        with pytest.raises(KeyError):
            get_tag_definition("invalid")  # type: ignore


# =============================================================================
# get_tag_label Tests
# =============================================================================


class TestGetTagLabel:
    """Tests for get_tag_label function."""

    def test_default_is_japanese(self) -> None:
        """Default language should be Japanese."""
        label = get_tag_label(MeaningTagId.LIFE_DEATH_ERROR)
        assert label == "死活ミス"

    def test_japanese_explicit(self) -> None:
        """Explicit 'ja' should return Japanese."""
        label = get_tag_label(MeaningTagId.LIFE_DEATH_ERROR, "ja")
        assert label == "死活ミス"

    def test_english(self) -> None:
        """'en' should return English."""
        label = get_tag_label(MeaningTagId.LIFE_DEATH_ERROR, "en")
        assert label == "Life/Death Error"

    def test_unknown_language_falls_back_to_japanese(self) -> None:
        """Unknown language should fall back to Japanese."""
        label = get_tag_label(MeaningTagId.LIFE_DEATH_ERROR, "fr")
        assert label == "死活ミス"

    @pytest.mark.parametrize("tag_id", list(MeaningTagId))
    def test_all_tags_have_japanese_label(self, tag_id: MeaningTagId) -> None:
        """All tags should have non-empty Japanese labels."""
        label = get_tag_label(tag_id, "ja")
        assert label
        assert isinstance(label, str)

    @pytest.mark.parametrize("tag_id", list(MeaningTagId))
    def test_all_tags_have_english_label(self, tag_id: MeaningTagId) -> None:
        """All tags should have non-empty English labels."""
        label = get_tag_label(tag_id, "en")
        assert label
        assert isinstance(label, str)


# =============================================================================
# get_tag_description Tests
# =============================================================================


class TestGetTagDescription:
    """Tests for get_tag_description function."""

    def test_default_is_japanese(self) -> None:
        """Default language should be Japanese."""
        desc = get_tag_description(MeaningTagId.MISSED_TESUJI)
        assert "手筋" in desc

    def test_english(self) -> None:
        """'en' should return English."""
        desc = get_tag_description(MeaningTagId.MISSED_TESUJI, "en")
        assert "tesuji" in desc.lower()

    @pytest.mark.parametrize("tag_id", list(MeaningTagId))
    def test_all_tags_have_descriptions(self, tag_id: MeaningTagId) -> None:
        """All tags should have non-empty descriptions."""
        ja_desc = get_tag_description(tag_id, "ja")
        en_desc = get_tag_description(tag_id, "en")
        assert len(ja_desc) > 10, f"{tag_id} ja_description too short"
        assert len(en_desc) > 10, f"{tag_id} en_description too short"


# =============================================================================
# MeaningTagDefinition Tests
# =============================================================================


class TestMeaningTagDefinition:
    """Tests for MeaningTagDefinition dataclass."""

    def test_is_frozen(self) -> None:
        """MeaningTagDefinition should be immutable."""
        definition = MEANING_TAG_REGISTRY[MeaningTagId.UNCERTAIN]
        with pytest.raises(AttributeError):
            definition.ja_label = "changed"  # type: ignore

    def test_default_lexicon_anchor_is_none(self) -> None:
        """Default lexicon anchor should be None."""
        # Create a minimal definition
        defn = MeaningTagDefinition(
            id=MeaningTagId.UNCERTAIN,
            ja_label="test",
            en_label="test",
            ja_description="test",
            en_description="test",
        )
        assert defn.default_lexicon_anchor is None

    def test_default_reason_tags_is_empty_tuple(self) -> None:
        """Default related_reason_tags should be empty tuple."""
        defn = MeaningTagDefinition(
            id=MeaningTagId.UNCERTAIN,
            ja_label="test",
            en_label="test",
            ja_description="test",
            en_description="test",
        )
        assert defn.related_reason_tags == ()

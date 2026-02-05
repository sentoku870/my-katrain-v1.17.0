"""Tests for meaning_tags/models.py.

Part of Phase 46: Meaning Tags System Core - PR-1.
"""

import json
from dataclasses import FrozenInstanceError

import pytest

from katrain.core.analysis.meaning_tags import MeaningTag, MeaningTagId

# =============================================================================
# MeaningTagId Tests
# =============================================================================


class TestMeaningTagId:
    """Tests for MeaningTagId enum."""

    def test_all_twelve_tags_exist(self) -> None:
        """Verify all 12 tags are defined."""
        expected_tags = {
            "MISSED_TESUJI",
            "OVERPLAY",
            "SLOW_MOVE",
            "DIRECTION_ERROR",
            "SHAPE_MISTAKE",
            "READING_FAILURE",
            "ENDGAME_SLIP",
            "CONNECTION_MISS",
            "CAPTURE_RACE_LOSS",
            "LIFE_DEATH_ERROR",
            "TERRITORIAL_LOSS",
            "UNCERTAIN",
        }
        actual_tags = {tag.name for tag in MeaningTagId}
        assert actual_tags == expected_tags

    def test_inherits_from_str(self) -> None:
        """MeaningTagId should inherit from str for JSON serialization."""
        assert isinstance(MeaningTagId.LIFE_DEATH_ERROR, str)
        assert MeaningTagId.LIFE_DEATH_ERROR == "life_death_error"

    def test_json_serializable_directly(self) -> None:
        """Enum values should serialize to JSON without .value."""
        tag_id = MeaningTagId.MISSED_TESUJI
        # Direct serialization works because it's a str subclass
        serialized = json.dumps({"tag": tag_id})
        assert serialized == '{"tag": "missed_tesuji"}'

    def test_value_is_snake_case(self) -> None:
        """All tag values should be snake_case."""
        for tag in MeaningTagId:
            assert tag.value.islower() or "_" in tag.value
            assert " " not in tag.value
            assert "-" not in tag.value

    def test_enum_member_access_by_name(self) -> None:
        """Can access enum members by name."""
        assert MeaningTagId["LIFE_DEATH_ERROR"] == MeaningTagId.LIFE_DEATH_ERROR

    def test_enum_member_access_by_value(self) -> None:
        """Can access enum members by value."""
        assert MeaningTagId("life_death_error") == MeaningTagId.LIFE_DEATH_ERROR

    def test_invalid_value_raises_error(self) -> None:
        """Invalid values should raise ValueError."""
        with pytest.raises(ValueError):
            MeaningTagId("invalid_tag")


# =============================================================================
# MeaningTag Tests
# =============================================================================


class TestMeaningTag:
    """Tests for MeaningTag dataclass."""

    def test_create_minimal(self) -> None:
        """Create tag with only required field."""
        tag = MeaningTag(id=MeaningTagId.UNCERTAIN)
        assert tag.id == MeaningTagId.UNCERTAIN
        assert tag.lexicon_anchor_id is None
        assert tag.confidence == 1.0
        assert tag.debug_reason is None

    def test_create_with_all_fields(self) -> None:
        """Create tag with all fields."""
        tag = MeaningTag(
            id=MeaningTagId.MISSED_TESUJI,
            lexicon_anchor_id="tesuji",
            confidence=0.95,
            debug_reason="policy_gap",
        )
        assert tag.id == MeaningTagId.MISSED_TESUJI
        assert tag.lexicon_anchor_id == "tesuji"
        assert tag.confidence == 0.95
        assert tag.debug_reason == "policy_gap"

    def test_is_frozen(self) -> None:
        """MeaningTag should be immutable (frozen)."""
        tag = MeaningTag(id=MeaningTagId.UNCERTAIN)
        with pytest.raises(FrozenInstanceError):
            tag.id = MeaningTagId.OVERPLAY  # type: ignore

    def test_is_hashable(self) -> None:
        """Frozen dataclasses should be hashable."""
        tag1 = MeaningTag(id=MeaningTagId.LIFE_DEATH_ERROR)
        tag2 = MeaningTag(id=MeaningTagId.LIFE_DEATH_ERROR)
        # Same hash for equal objects
        assert hash(tag1) == hash(tag2)
        # Can be used in sets
        tag_set = {tag1, tag2}
        assert len(tag_set) == 1

    def test_equality(self) -> None:
        """Equal values should be equal."""
        tag1 = MeaningTag(id=MeaningTagId.OVERPLAY, debug_reason="stdev_high")
        tag2 = MeaningTag(id=MeaningTagId.OVERPLAY, debug_reason="stdev_high")
        assert tag1 == tag2

    def test_inequality_different_id(self) -> None:
        """Different IDs should not be equal."""
        tag1 = MeaningTag(id=MeaningTagId.OVERPLAY)
        tag2 = MeaningTag(id=MeaningTagId.UNCERTAIN)
        assert tag1 != tag2

    def test_inequality_different_anchor(self) -> None:
        """Different anchors should not be equal."""
        tag1 = MeaningTag(id=MeaningTagId.MISSED_TESUJI, lexicon_anchor_id="tesuji")
        tag2 = MeaningTag(id=MeaningTagId.MISSED_TESUJI, lexicon_anchor_id=None)
        assert tag1 != tag2

    def test_default_confidence_is_one(self) -> None:
        """Default confidence should be 1.0."""
        tag = MeaningTag(id=MeaningTagId.SLOW_MOVE)
        assert tag.confidence == 1.0

    def test_confidence_validation_too_low(self) -> None:
        """Confidence below 0.0 should raise ValueError."""
        with pytest.raises(ValueError, match="confidence must be in"):
            MeaningTag(id=MeaningTagId.UNCERTAIN, confidence=-0.1)

    def test_confidence_validation_too_high(self) -> None:
        """Confidence above 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="confidence must be in"):
            MeaningTag(id=MeaningTagId.UNCERTAIN, confidence=1.1)

    def test_confidence_boundary_zero(self) -> None:
        """Confidence of 0.0 should be valid."""
        tag = MeaningTag(id=MeaningTagId.UNCERTAIN, confidence=0.0)
        assert tag.confidence == 0.0

    def test_confidence_boundary_one(self) -> None:
        """Confidence of 1.0 should be valid."""
        tag = MeaningTag(id=MeaningTagId.UNCERTAIN, confidence=1.0)
        assert tag.confidence == 1.0

    def test_invalid_id_type_raises_error(self) -> None:
        """Non-MeaningTagId should raise TypeError."""
        with pytest.raises(TypeError, match="id must be MeaningTagId"):
            MeaningTag(id="life_death_error")  # type: ignore

    def test_debug_reason_can_be_any_string(self) -> None:
        """Any string is valid for debug_reason."""
        tag = MeaningTag(
            id=MeaningTagId.UNCERTAIN,
            debug_reason="pass_move",
        )
        assert tag.debug_reason == "pass_move"

    def test_repr_is_readable(self) -> None:
        """repr should be human-readable."""
        tag = MeaningTag(id=MeaningTagId.LIFE_DEATH_ERROR, debug_reason="ownership_flux")
        repr_str = repr(tag)
        assert "MeaningTag" in repr_str
        assert "LIFE_DEATH_ERROR" in repr_str
        assert "ownership_flux" in repr_str


# =============================================================================
# MeaningTag JSON Serialization Tests
# =============================================================================


class TestMeaningTagSerialization:
    """Tests for MeaningTag JSON serialization."""

    def test_serialize_to_dict(self) -> None:
        """Can convert to dict for JSON."""
        from dataclasses import asdict

        tag = MeaningTag(
            id=MeaningTagId.ENDGAME_SLIP,
            lexicon_anchor_id="yose",
            confidence=1.0,
            debug_reason=None,
        )
        d = asdict(tag)
        # id is automatically converted to str via str inheritance
        assert d["id"] == "endgame_slip"
        assert d["lexicon_anchor_id"] == "yose"
        assert d["confidence"] == 1.0
        assert d["debug_reason"] is None

    def test_full_json_round_trip(self) -> None:
        """Can serialize to JSON and back."""
        from dataclasses import asdict

        original = MeaningTag(
            id=MeaningTagId.CONNECTION_MISS,
            lexicon_anchor_id="connection",
            confidence=0.9,
            debug_reason="cut_risk",
        )
        json_str = json.dumps(asdict(original))
        loaded = json.loads(json_str)

        # Reconstruct (need to convert id back to enum)
        reconstructed = MeaningTag(
            id=MeaningTagId(loaded["id"]),
            lexicon_anchor_id=loaded["lexicon_anchor_id"],
            confidence=loaded["confidence"],
            debug_reason=loaded["debug_reason"],
        )
        assert reconstructed == original

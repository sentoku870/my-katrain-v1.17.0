"""Tests for katrain.core.curator.models (Phase 63).

Data models for suitability scoring:
- SuitabilityConfig (frozen dataclass with default weights)
- SuitabilityScore (frozen dataclass with optional debug_info)
- UNCERTAIN_TAG constant
- DEFAULT_CONFIG instance

These are pure data models with no I/O, so tests focus on:
- Default values and field types
- Immutability (frozen)
- MappingProxyType wrapping for debug_info
- Imports and re-exports
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from katrain.core.analysis.meaning_tags.models import MeaningTagId
from katrain.core.curator.models import (
    DEFAULT_CONFIG,
    UNCERTAIN_TAG,
    SuitabilityConfig,
    SuitabilityScore,
)

# =============================================================================
# UNCERTAIN_TAG constant
# =============================================================================


class TestUncertainTag:
    """Tests for UNCERTAIN_TAG constant."""

    def test_value_matches_meaning_tag_id(self):
        """UNCERTAIN_TAG should match MeaningTagId.UNCERTAIN.value."""
        assert MeaningTagId.UNCERTAIN.value == UNCERTAIN_TAG

    def test_value_is_string(self):
        """UNCERTAIN_TAG must be a string for JSON compatibility."""
        assert isinstance(UNCERTAIN_TAG, str)

    def test_value_not_empty(self):
        """UNCERTAIN_TAG must be a non-empty identifier."""
        assert len(UNCERTAIN_TAG) > 0


# =============================================================================
# SuitabilityConfig
# =============================================================================


class TestSuitabilityConfig:
    """Tests for SuitabilityConfig dataclass."""

    def test_default_values(self):
        """Default config has expected values per Phase 63 docs."""
        cfg = SuitabilityConfig()
        assert cfg.needs_match_weight == 0.0
        assert cfg.stability_weight == 1.0
        assert cfg.min_tag_occurrences == 3
        assert cfg.max_volatility == 15.0
        assert cfg.stability_insufficient_data == 0.0

    def test_frozen_dataclass(self):
        """SuitabilityConfig is frozen: attribute assignment should fail."""
        cfg = SuitabilityConfig()
        with pytest.raises((AttributeError, Exception)):
            cfg.needs_match_weight = 0.5  # type: ignore[misc]

    def test_custom_weights(self):
        """Custom weights should be accepted as floats."""
        cfg = SuitabilityConfig(needs_match_weight=0.6, stability_weight=0.4)
        assert cfg.needs_match_weight == 0.6
        assert cfg.stability_weight == 0.4
        # Other fields use defaults
        assert cfg.min_tag_occurrences == 3
        assert cfg.max_volatility == 15.0

    def test_min_tag_occurrences_can_be_configured(self):
        """min_tag_occurrences threshold is configurable for needs_match."""
        cfg = SuitabilityConfig(min_tag_occurrences=5)
        assert cfg.min_tag_occurrences == 5

    def test_max_volatility_can_be_configured(self):
        """max_volatility threshold is configurable for stability scaling."""
        cfg = SuitabilityConfig(max_volatility=10.0)
        assert cfg.max_volatility == 10.0

    def test_stability_insufficient_data_configurable(self):
        """stability_insufficient_data can override the 0.0 default."""
        cfg = SuitabilityConfig(stability_insufficient_data=0.5)
        assert cfg.stability_insufficient_data == 0.5

    def test_default_config_is_suitability_config_instance(self):
        """DEFAULT_CONFIG must be a SuitabilityConfig instance."""
        assert isinstance(DEFAULT_CONFIG, SuitabilityConfig)

    def test_default_config_uses_defaults(self):
        """DEFAULT_CONFIG should match SuitabilityConfig() values."""
        assert DEFAULT_CONFIG.needs_match_weight == SuitabilityConfig().needs_match_weight
        assert DEFAULT_CONFIG.stability_weight == SuitabilityConfig().stability_weight
        assert DEFAULT_CONFIG.min_tag_occurrences == SuitabilityConfig().min_tag_occurrences
        assert DEFAULT_CONFIG.max_volatility == SuitabilityConfig().max_volatility
        assert DEFAULT_CONFIG.stability_insufficient_data == SuitabilityConfig().stability_insufficient_data


# =============================================================================
# SuitabilityScore
# =============================================================================


class TestSuitabilityScore:
    """Tests for SuitabilityScore dataclass."""

    def test_required_fields_only(self):
        """Core fields without debug_info / percentile."""
        score = SuitabilityScore(
            needs_match=0.5,
            stability=0.7,
            total=0.6,
        )
        assert score.needs_match == 0.5
        assert score.stability == 0.7
        assert score.total == 0.6
        assert score.percentile is None  # Default
        assert score.debug_info is None  # Default

    def test_with_percentile(self):
        """Percentile can be set when batch percentile is computed."""
        score = SuitabilityScore(
            needs_match=0.5,
            stability=0.7,
            total=0.6,
            percentile=80,
        )
        assert score.percentile == 80

    def test_with_debug_info(self):
        """debug_info can be set to a Mapping."""
        debug = MappingProxyType({"key": "value"})
        score = SuitabilityScore(
            needs_match=0.5,
            stability=0.7,
            total=0.6,
            debug_info=debug,
        )
        assert score.debug_info is not None
        assert score.debug_info["key"] == "value"  # type: ignore[index]

    def test_frozen_dataclass(self):
        """SuitabilityScore is immutable."""
        score = SuitabilityScore(needs_match=0.5, stability=0.7, total=0.6)
        with pytest.raises((AttributeError, Exception)):
            score.total = 0.9  # type: ignore[misc]

    def test_zero_values(self):
        """Score fields accept 0.0 (lower bound of [0,1])."""
        score = SuitabilityScore(needs_match=0.0, stability=0.0, total=0.0)
        assert score.needs_match == 0.0
        assert score.stability == 0.0
        assert score.total == 0.0

    def test_one_values(self):
        """Score fields accept 1.0 (upper bound of [0,1])."""
        score = SuitabilityScore(needs_match=1.0, stability=1.0, total=1.0)
        assert score.needs_match == 1.0
        assert score.stability == 1.0
        assert score.total == 1.0

    def test_percentile_zero(self):
        """Percentile can be 0 (worst in batch)."""
        score = SuitabilityScore(needs_match=0.0, stability=0.0, total=0.0, percentile=0)
        assert score.percentile == 0

    def test_percentile_hundred(self):
        """Percentile can be 100 (best in batch)."""
        score = SuitabilityScore(needs_match=1.0, stability=1.0, total=1.0, percentile=100)
        assert score.percentile == 100

    def test_debug_info_must_be_mapping_or_none(self):
        """debug_info type is Mapping[str, Any] | None."""
        score = SuitabilityScore(needs_match=0.5, stability=0.5, total=0.5, debug_info=None)
        assert score.debug_info is None


# =============================================================================
# Equality and hashing
# =============================================================================


class TestEqualityAndHashing:
    """Tests for equality/hashing behavior of frozen dataclasses."""

    def test_suitability_config_equality(self):
        """Two configs with same fields compare equal."""
        c1 = SuitabilityConfig(needs_match_weight=0.3, stability_weight=0.7)
        c2 = SuitabilityConfig(needs_match_weight=0.3, stability_weight=0.7)
        assert c1 == c2

    def test_suitability_config_inequality(self):
        """Different configs compare unequal."""
        c1 = SuitabilityConfig(needs_match_weight=0.3)
        c2 = SuitabilityConfig(needs_match_weight=0.4)
        assert c1 != c2

    def test_suitability_score_equality(self):
        """Two scores with same fields compare equal."""
        s1 = SuitabilityScore(needs_match=0.5, stability=0.5, total=0.5, percentile=50)
        s2 = SuitabilityScore(needs_match=0.5, stability=0.5, total=0.5, percentile=50)
        assert s1 == s2

    def test_suitability_score_hashable(self):
        """Frozen dataclasses are hashable when debug_info is None."""
        s1 = SuitabilityScore(needs_match=0.5, stability=0.5, total=0.5)
        s2 = SuitabilityScore(needs_match=0.5, stability=0.5, total=0.5)
        assert hash(s1) == hash(s2)
        # Can be used in sets
        assert {s1, s2} == {s1}


# =============================================================================
# Module imports / re-exports
# =============================================================================


class TestExports:
    """Tests for module public API."""

    def test_module_imports_dataclass_models(self):
        """All named exports should be importable from .models."""
        from katrain.core.curator import (
            DEFAULT_CONFIG as D,
        )
        from katrain.core.curator import (
            UNCERTAIN_TAG as U,
        )
        from katrain.core.curator import (
            SuitabilityConfig as SC,
        )
        from katrain.core.curator import (
            SuitabilityScore as SS,
        )

        assert D is DEFAULT_CONFIG
        assert U is UNCERTAIN_TAG
        assert SC is SuitabilityConfig
        assert SS is SuitabilityScore

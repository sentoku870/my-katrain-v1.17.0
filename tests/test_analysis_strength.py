"""Tests for AnalysisStrength enum and resolve_visits() (Phase 30)."""

import pytest
from katrain.core.analysis.models import (
    AnalysisStrength,
    ENGINE_VISITS_DEFAULTS,
    LEELA_FAST_VISITS_MIN,
    resolve_visits,
)


class TestAnalysisStrength:
    """AnalysisStrength enum tests."""

    def test_quick_is_fast(self):
        """Contract: QUICK.is_fast returns True"""
        assert AnalysisStrength.QUICK.is_fast is True

    def test_deep_is_not_fast(self):
        """Contract: DEEP.is_fast returns False"""
        assert AnalysisStrength.DEEP.is_fast is False

    def test_value_strings(self):
        """Contract: enum values are stable strings"""
        assert AnalysisStrength.QUICK.value == "quick"
        assert AnalysisStrength.DEEP.value == "deep"

    def test_enum_has_at_least_two_members(self):
        """Contract: at least QUICK and DEEP exist"""
        strengths = list(AnalysisStrength)
        assert len(strengths) >= 2


class TestResolveVisits:
    """resolve_visits() function tests."""

    # --- Contract: Config values are respected ---
    def test_katago_quick_with_config(self):
        """Contract: uses fast_visits from config for QUICK"""
        config = {"fast_visits": 30, "max_visits": 600}
        assert resolve_visits(AnalysisStrength.QUICK, config, "katago") == 30

    def test_katago_deep_with_config(self):
        """Contract: uses max_visits from config for DEEP"""
        config = {"fast_visits": 30, "max_visits": 600}
        assert resolve_visits(AnalysisStrength.DEEP, config, "katago") == 600

    def test_leela_quick_with_config(self):
        """Contract: uses fast_visits from config for QUICK (leela)"""
        config = {"fast_visits": 150, "max_visits": 2000}
        assert resolve_visits(AnalysisStrength.QUICK, config, "leela") == 150

    def test_leela_deep_with_config(self):
        """Contract: uses max_visits from config for DEEP (leela)"""
        config = {"fast_visits": 150, "max_visits": 2000}
        assert resolve_visits(AnalysisStrength.DEEP, config, "leela") == 2000

    # --- Contract: Defaults when config is empty (backward compatibility) ---
    def test_katago_defaults_when_config_empty(self):
        """Contract: falls back to ENGINE_VISITS_DEFAULTS when config is empty"""
        assert (
            resolve_visits(AnalysisStrength.QUICK, {}, "katago")
            == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        )
        assert (
            resolve_visits(AnalysisStrength.DEEP, {}, "katago")
            == ENGINE_VISITS_DEFAULTS["katago"]["max_visits"]
        )

    def test_leela_defaults_when_config_empty(self):
        """Contract: falls back to ENGINE_VISITS_DEFAULTS when config is empty (leela)"""
        assert (
            resolve_visits(AnalysisStrength.QUICK, {}, "leela")
            == ENGINE_VISITS_DEFAULTS["leela"]["fast_visits"]
        )
        assert (
            resolve_visits(AnalysisStrength.DEEP, {}, "leela")
            == ENGINE_VISITS_DEFAULTS["leela"]["max_visits"]
        )

    def test_partial_config_missing_key_uses_default(self):
        """Contract: missing key falls back to default, present key is used"""
        config = {"max_visits": 1000}
        assert (
            resolve_visits(AnalysisStrength.QUICK, config, "katago")
            == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        )
        assert resolve_visits(AnalysisStrength.DEEP, config, "katago") == 1000

    # --- Contract: Unknown engine falls back to katago ---
    def test_unknown_engine_falls_back_to_katago(self):
        """Contract: unknown engine_type uses katago defaults"""
        assert (
            resolve_visits(AnalysisStrength.QUICK, {}, "unknown")
            == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        )
        assert (
            resolve_visits(AnalysisStrength.DEEP, {}, "future_engine")
            == ENGINE_VISITS_DEFAULTS["katago"]["max_visits"]
        )

    # --- Contract: Invalid values fall back to defaults (no crash) ---
    def test_none_value_falls_back_to_default(self):
        """Contract: None value falls back to default"""
        config = {"fast_visits": None}
        assert (
            resolve_visits(AnalysisStrength.QUICK, config, "katago")
            == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        )

    def test_invalid_string_falls_back_to_default(self):
        """Contract: non-numeric string falls back to default"""
        config = {"fast_visits": "invalid"}
        assert (
            resolve_visits(AnalysisStrength.QUICK, config, "katago")
            == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        )

    def test_empty_string_falls_back_to_default(self):
        """Contract: empty string falls back to default"""
        config = {"fast_visits": ""}
        assert (
            resolve_visits(AnalysisStrength.QUICK, config, "katago")
            == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        )

    # --- Contract: Return value is always >= 1 ---
    def test_negative_value_clamped_to_one(self):
        """Contract: negative values are clamped to 1"""
        config = {"fast_visits": -10}
        assert resolve_visits(AnalysisStrength.QUICK, config, "katago") >= 1

    def test_zero_value_clamped_to_one(self):
        """Contract: zero is clamped to 1"""
        config = {"max_visits": 0}
        assert resolve_visits(AnalysisStrength.DEEP, config, "leela") >= 1

    # --- Contract: Valid string is parsed ---
    def test_numeric_string_parsed(self):
        """Contract: valid numeric string is converted to int"""
        config = {"max_visits": "1000"}
        assert resolve_visits(AnalysisStrength.DEEP, config, "leela") == 1000

    def test_string_with_whitespace_parsed(self):
        """Contract: whitespace is stripped before parsing"""
        config = {"fast_visits": " 30 "}
        assert resolve_visits(AnalysisStrength.QUICK, config, "katago") == 30

    # --- Implementation detail tests (may change) ---
    def test_float_value_truncated(self):
        """Implementation detail: float is truncated to int"""
        config = {"fast_visits": 25.9}
        result = resolve_visits(AnalysisStrength.QUICK, config, "katago")
        assert isinstance(result, int)
        assert result > 0  # flexible: just ensure it's valid

    def test_extremely_large_value_preserved(self):
        """Implementation detail: no upper bound enforcement"""
        config = {"max_visits": 10_000_000}
        assert resolve_visits(AnalysisStrength.DEEP, config, "katago") == 10_000_000

    def test_whitespace_only_string_falls_back_to_default(self):
        """Implementation detail: whitespace-only string behavior"""
        config = {"fast_visits": "   "}
        result = resolve_visits(AnalysisStrength.QUICK, config, "katago")
        assert result > 0  # flexible: just ensure it's valid


class TestEngineVisitsDefaults:
    """ENGINE_VISITS_DEFAULTS constant tests."""

    def test_katago_defaults_exist(self):
        """Contract: katago defaults are defined"""
        assert "katago" in ENGINE_VISITS_DEFAULTS
        assert "max_visits" in ENGINE_VISITS_DEFAULTS["katago"]
        assert "fast_visits" in ENGINE_VISITS_DEFAULTS["katago"]

    def test_leela_defaults_exist(self):
        """Contract: leela defaults are defined"""
        assert "leela" in ENGINE_VISITS_DEFAULTS
        assert "max_visits" in ENGINE_VISITS_DEFAULTS["leela"]
        assert "fast_visits" in ENGINE_VISITS_DEFAULTS["leela"]

    def test_fast_visits_less_than_max_visits(self):
        """Contract: fast_visits < max_visits for all engines"""
        for engine, defaults in ENGINE_VISITS_DEFAULTS.items():
            assert defaults["fast_visits"] < defaults["max_visits"], (
                f"{engine}: fast >= max"
            )

    def test_all_values_are_positive(self):
        """Contract: all default values are positive"""
        for engine, defaults in ENGINE_VISITS_DEFAULTS.items():
            assert defaults["max_visits"] > 0
            assert defaults["fast_visits"] > 0


class TestLeelaFastVisitsMin:
    """LEELA_FAST_VISITS_MIN constant tests."""

    def test_leela_fast_visits_min_is_positive(self):
        """Contract: LEELA_FAST_VISITS_MIN is positive"""
        assert LEELA_FAST_VISITS_MIN > 0

    def test_leela_fast_visits_min_is_reasonable(self):
        """Contract: LEELA_FAST_VISITS_MIN is within reasonable range"""
        assert 10 <= LEELA_FAST_VISITS_MIN <= 200


# ---------------------------------------------------------------------------
# Phase 37 T3: Contract-based tests for resolve_visits()
# ---------------------------------------------------------------------------


class TestResolveVisitsContract:
    """Contract-based tests for resolve_visits() (Phase 37 T3).

    These tests verify the function's contract without hardcoding specific
    default values, making them resilient to future default value changes.

    Note: Key names are shared between KataGo/Leela (fast_visits/max_visits).
    Only default values differ per engine (see ENGINE_VISITS_DEFAULTS).
    """

    def test_returns_positive_integer(self):
        """Contract: return value is always a positive integer."""
        result = resolve_visits(AnalysisStrength.QUICK, {"fast_visits": 100}, "katago")
        assert isinstance(result, int)
        assert result >= 1

    def test_respects_config_value_when_valid(self):
        """Contract: valid config values are respected (both engines share key names)."""
        # KataGo
        assert resolve_visits(AnalysisStrength.QUICK, {"fast_visits": 500}, "katago") == 500
        # Leela - same key name
        assert resolve_visits(AnalysisStrength.QUICK, {"fast_visits": 500}, "leela") == 500

    def test_missing_key_uses_engine_specific_default(self):
        """Contract: missing key uses engine-specific default (no hardcoding)."""
        # Get expected values from the constant (avoid hardcoding 25/200)
        katago_default = ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        leela_default = ENGINE_VISITS_DEFAULTS["leela"]["fast_visits"]

        assert resolve_visits(AnalysisStrength.QUICK, {}, "katago") == katago_default
        assert resolve_visits(AnalysisStrength.QUICK, {}, "leela") == leela_default

    def test_negative_or_zero_becomes_positive(self):
        """Contract: non-positive values become positive (clamped to >= 1)."""
        assert resolve_visits(AnalysisStrength.QUICK, {"fast_visits": -10}, "katago") >= 1
        assert resolve_visits(AnalysisStrength.QUICK, {"fast_visits": 0}, "katago") >= 1

    def test_float_input_returns_int(self):
        """Contract: float input still returns int (truncated/rounded)."""
        result = resolve_visits(AnalysisStrength.QUICK, {"fast_visits": 99.9}, "katago")
        assert isinstance(result, int)

    def test_deep_uses_max_visits_key(self):
        """Contract: DEEP strength uses max_visits key (no hardcoding)."""
        katago_max = ENGINE_VISITS_DEFAULTS["katago"]["max_visits"]
        leela_max = ENGINE_VISITS_DEFAULTS["leela"]["max_visits"]

        assert resolve_visits(AnalysisStrength.DEEP, {}, "katago") == katago_max
        assert resolve_visits(AnalysisStrength.DEEP, {}, "leela") == leela_max

    def test_quick_and_deep_return_different_values_for_same_engine(self):
        """Contract: QUICK and DEEP return different values (fast vs max)."""
        quick_visits = resolve_visits(AnalysisStrength.QUICK, {}, "katago")
        deep_visits = resolve_visits(AnalysisStrength.DEEP, {}, "katago")
        # fast_visits should be less than max_visits by design
        assert quick_visits < deep_visits

    def test_unknown_engine_uses_katago_defaults(self):
        """Contract: unknown engine falls back to katago defaults."""
        katago_default = ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        result = resolve_visits(AnalysisStrength.QUICK, {}, "unknown_engine")
        assert result == katago_default

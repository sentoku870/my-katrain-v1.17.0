"""Phase 248-B3: tests for :mod:`katrain.core.analysis.internal_params`.

Locks in the public contract of the resolver and the baseline
defaults. The resolver is permissive: unknown keys, out-of-range
values, and type mismatches silently fall back to defaults so a
user typo can never crash the GUI.
"""

from __future__ import annotations

import pytest

from katrain.core.analysis import (
    DEFAULT_INTERNAL_PARAMS,
    InternalParams,
    get_default_internal_params,
    resolve_internal_params,
)

# ---------------------------------------------------------------------------
# Baseline defaults — guard against silent drift
# ---------------------------------------------------------------------------


class TestDefaultInternalParams:
    """The Phase 50-179 baseline must not drift silently."""

    def test_threshold_score_stdev_chaos_baseline(self):
        # Phase 83.
        assert DEFAULT_INTERNAL_PARAMS.threshold_score_stdev_chaos == pytest.approx(20.0)

    def test_complexity_discount_factor_baseline(self):
        # Phase 83.
        assert DEFAULT_INTERNAL_PARAMS.complexity_discount_factor == pytest.approx(0.3)

    def test_diversity_penalty_factor_baseline(self):
        # Phase 158-F.
        assert DEFAULT_INTERNAL_PARAMS.diversity_penalty_factor == pytest.approx(0.85)

    def test_min_loss_display_baseline(self):
        # Phase 148-B2.
        assert DEFAULT_INTERNAL_PARAMS.min_loss_display == pytest.approx(0.3)

    def test_beginner_hint_min_visits_baseline(self):
        # Phase 179.
        assert DEFAULT_INTERNAL_PARAMS.beginner_hint_min_visits == 100

    def test_katago_uncertain_min_visits_baseline(self):
        # Phase 179.2.
        assert DEFAULT_INTERNAL_PARAMS.katago_uncertain_min_visits == 300

    def test_get_default_internal_params_returns_fresh_copy(self):
        """``get_default_internal_params`` must not be a shared mutable."""
        a = get_default_internal_params()
        b = get_default_internal_params()
        assert a is not b
        # dataclass(frozen=True) prevents mutation either way, but the
        # point is the *identity* check above.
        assert a == b

    def test_dataclass_is_frozen(self):
        """The dataclass is frozen so callers cannot mutate the baseline."""
        with pytest.raises((AttributeError, Exception)):
            DEFAULT_INTERNAL_PARAMS.threshold_score_stdev_chaos = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Resolver — happy paths
# ---------------------------------------------------------------------------


class TestResolveInternalParamsHappy:
    """``resolve_internal_params`` honours well-formed user overrides."""

    def test_none_input_returns_defaults(self):
        result = resolve_internal_params(None)
        assert result == DEFAULT_INTERNAL_PARAMS

    def test_empty_dict_returns_defaults(self):
        result = resolve_internal_params({})
        assert result == DEFAULT_INTERNAL_PARAMS

    def test_no_advanced_params_key_returns_defaults(self):
        result = resolve_internal_params({"critical_3_max_moves": 3})
        assert result == DEFAULT_INTERNAL_PARAMS

    def test_empty_advanced_params_returns_defaults(self):
        result = resolve_internal_params({"advanced_params": {}})
        assert result == DEFAULT_INTERNAL_PARAMS

    def test_override_threshold_score_stdev_chaos(self):
        result = resolve_internal_params({"advanced_params": {"threshold_score_stdev_chaos": 25.0}})
        assert result.threshold_score_stdev_chaos == pytest.approx(25.0)
        # Other fields keep the baseline.
        assert result.complexity_discount_factor == DEFAULT_INTERNAL_PARAMS.complexity_discount_factor

    def test_override_all_six_fields(self):
        result = resolve_internal_params(
            {
                "advanced_params": {
                    "threshold_score_stdev_chaos": 30.0,
                    "complexity_discount_factor": 0.5,
                    "diversity_penalty_factor": 0.9,
                    "min_loss_display": 0.5,
                    "beginner_hint_min_visits": 200,
                    "katago_uncertain_min_visits": 500,
                }
            }
        )
        assert result.threshold_score_stdev_chaos == pytest.approx(30.0)
        assert result.complexity_discount_factor == pytest.approx(0.5)
        assert result.diversity_penalty_factor == pytest.approx(0.9)
        assert result.min_loss_display == pytest.approx(0.5)
        assert result.beginner_hint_min_visits == 200
        assert result.katago_uncertain_min_visits == 500

    def test_override_preserves_known_fields(self):
        """Unknown keys are dropped silently; known keys still apply."""
        result = resolve_internal_params(
            {
                "advanced_params": {
                    "threshold_score_stdev_chaos": 22.0,
                    "garbage_key": "should be dropped",
                }
            }
        )
        assert result.threshold_score_stdev_chaos == pytest.approx(22.0)


# ---------------------------------------------------------------------------
# Resolver — graceful failure modes
# ---------------------------------------------------------------------------


class TestResolveInternalParamsFailure:
    """The resolver never raises — it returns the baseline on any problem."""

    def test_non_dict_input_returns_defaults(self):
        assert resolve_internal_params("not a dict") == DEFAULT_INTERNAL_PARAMS  # type: ignore[arg-type]
        assert resolve_internal_params(42) == DEFAULT_INTERNAL_PARAMS  # type: ignore[arg-type]
        assert resolve_internal_params([1, 2, 3]) == DEFAULT_INTERNAL_PARAMS  # type: ignore[arg-type]

    def test_non_dict_advanced_params_returns_defaults(self):
        for bad in ("string", 42, [1, 2], True):
            result = resolve_internal_params({"advanced_params": bad})  # type: ignore[arg-type]
            assert result == DEFAULT_INTERNAL_PARAMS

    def test_unparseable_value_uses_default(self):
        """String values that can't be parsed as float/int fall back to defaults."""
        result = resolve_internal_params({"advanced_params": {"threshold_score_stdev_chaos": "not a number"}})
        assert result.threshold_score_stdev_chaos == DEFAULT_INTERNAL_PARAMS.threshold_score_stdev_chaos

    def test_none_value_uses_default(self):
        result = resolve_internal_params({"advanced_params": {"threshold_score_stdev_chaos": None}})
        assert result.threshold_score_stdev_chaos == DEFAULT_INTERNAL_PARAMS.threshold_score_stdev_chaos

    def test_out_of_range_high_uses_default(self):
        result = resolve_internal_params(
            {"advanced_params": {"threshold_score_stdev_chaos": 200.0}}  # > 100
        )
        assert result.threshold_score_stdev_chaos == DEFAULT_INTERNAL_PARAMS.threshold_score_stdev_chaos

    def test_out_of_range_low_uses_default(self):
        result = resolve_internal_params(
            {"advanced_params": {"complexity_discount_factor": 0.0}}  # < 0.05
        )
        assert result.complexity_discount_factor == DEFAULT_INTERNAL_PARAMS.complexity_discount_factor

    def test_visits_field_accepts_int_only(self):
        """``beginner_hint_min_visits`` rejects non-integer strings."""
        result = resolve_internal_params({"advanced_params": {"beginner_hint_min_visits": "abc"}})
        assert result.beginner_hint_min_visits == DEFAULT_INTERNAL_PARAMS.beginner_hint_min_visits

    def test_visits_field_accepts_numeric_string(self):
        """A numeric string coerces to int (Python's ``int()`` is permissive)."""
        result = resolve_internal_params({"advanced_params": {"beginner_hint_min_visits": "250"}})
        assert result.beginner_hint_min_visits == 250

    def test_partial_override_only_overrides_set_fields(self):
        """Other fields keep defaults when only some are set."""
        result = resolve_internal_params({"advanced_params": {"diversity_penalty_factor": 0.95}})
        assert result.diversity_penalty_factor == pytest.approx(0.95)
        assert result.threshold_score_stdev_chaos == DEFAULT_INTERNAL_PARAMS.threshold_score_stdev_chaos
        assert result.complexity_discount_factor == DEFAULT_INTERNAL_PARAMS.complexity_discount_factor


# ---------------------------------------------------------------------------
# Type integration
# ---------------------------------------------------------------------------


class TestInternalParamsTypeContract:
    """The dataclass + resolver together expose the documented types."""

    def test_dataclass_fields_are_typed(self):

        hints = InternalParams.__dataclass_fields__  # type: ignore[attr-defined]
        assert "threshold_score_stdev_chaos" in hints
        assert "beginner_hint_min_visits" in hints

    def test_resolver_returns_internal_params_instance(self):
        result = resolve_internal_params(None)
        assert isinstance(result, InternalParams)

    def test_resolver_with_overrides_returns_internal_params_instance(self):
        result = resolve_internal_params({"advanced_params": {"threshold_score_stdev_chaos": 25.0}})
        assert isinstance(result, InternalParams)

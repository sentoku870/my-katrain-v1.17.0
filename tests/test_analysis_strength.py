"""Tests for AnalysisStrength enum and resolve_visits() (Phase 30, Phase 171 KataGo-only).

Phase 171 で Leela 経路を削除したため、resolve_visits() は KataGo 専用。
"""

from katrain.core.analysis.logic import (
    compute_effective_threshold,
    compute_reliability_stats,
)
from katrain.core.analysis.models import (
    ENGINE_VISITS_DEFAULTS,
    RELIABILITY_RATIO,
    RELIABILITY_VISITS_THRESHOLD,
    AnalysisStrength,
    resolve_visits,
)
from tests.helpers_eval_metrics import make_move_eval


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
    """resolve_visits() function tests (Phase 171: KataGo-only)."""

    # --- Contract: Config values are respected ---
    def test_katago_quick_with_config(self):
        """Contract: uses fast_visits from config for QUICK"""
        config = {"fast_visits": 30, "max_visits": 600}
        assert resolve_visits(AnalysisStrength.QUICK, config, "katago") == 30

    def test_katago_deep_with_config(self):
        """Contract: uses max_visits from config for DEEP"""
        config = {"fast_visits": 30, "max_visits": 600}
        assert resolve_visits(AnalysisStrength.DEEP, config, "katago") == 600

    # --- Contract: Defaults when config is empty (backward compatibility) ---
    def test_katago_defaults_when_config_empty(self):
        """Contract: falls back to ENGINE_VISITS_DEFAULTS when config is empty"""
        assert resolve_visits(AnalysisStrength.QUICK, {}, "katago") == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        assert resolve_visits(AnalysisStrength.DEEP, {}, "katago") == ENGINE_VISITS_DEFAULTS["katago"]["max_visits"]

    def test_partial_config_missing_key_uses_default(self):
        """Contract: missing key falls back to default, present key is used"""
        config = {"max_visits": 1000}
        assert (
            resolve_visits(AnalysisStrength.QUICK, config, "katago") == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        )
        assert resolve_visits(AnalysisStrength.DEEP, config, "katago") == 1000

    # --- Contract: Unknown engine falls back to katago ---
    def test_unknown_engine_falls_back_to_katago(self):
        """Contract: unknown engine_type uses katago defaults"""
        assert resolve_visits(AnalysisStrength.QUICK, {}, "unknown") == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        assert (
            resolve_visits(AnalysisStrength.DEEP, {}, "future_engine") == ENGINE_VISITS_DEFAULTS["katago"]["max_visits"]
        )

    # --- Contract: Invalid values fall back to defaults (no crash) ---
    def test_none_value_falls_back_to_default(self):
        """Contract: None value falls back to default"""
        config = {"fast_visits": None}
        assert (
            resolve_visits(AnalysisStrength.QUICK, config, "katago") == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        )

    def test_invalid_string_falls_back_to_default(self):
        """Contract: non-numeric string falls back to default"""
        config = {"fast_visits": "invalid"}
        assert (
            resolve_visits(AnalysisStrength.QUICK, config, "katago") == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        )

    def test_empty_string_falls_back_to_default(self):
        """Contract: empty string falls back to default"""
        config = {"fast_visits": ""}
        assert (
            resolve_visits(AnalysisStrength.QUICK, config, "katago") == ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        )

    # --- Contract: Return value is always >= 1 ---
    def test_negative_value_clamped_to_one(self):
        """Contract: negative values are clamped to 1"""
        config = {"fast_visits": -10}
        assert resolve_visits(AnalysisStrength.QUICK, config, "katago") >= 1

    def test_zero_value_clamped_to_one(self):
        """Contract: zero is clamped to 1"""
        config = {"max_visits": 0}
        assert resolve_visits(AnalysisStrength.DEEP, config, "katago") >= 1

    # --- Contract: Valid string is parsed ---
    def test_numeric_string_parsed(self):
        """Contract: valid numeric string is converted to int"""
        config = {"max_visits": "1000"}
        assert resolve_visits(AnalysisStrength.DEEP, config, "katago") == 1000

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
        assert result > 0

    def test_extremely_large_value_preserved(self):
        """Implementation detail: no upper bound enforcement"""
        config = {"max_visits": 10_000_000}
        assert resolve_visits(AnalysisStrength.DEEP, config, "katago") == 10_000_000

    def test_whitespace_only_string_falls_back_to_default(self):
        """Implementation detail: whitespace-only string behavior"""
        config = {"fast_visits": "   "}
        result = resolve_visits(AnalysisStrength.QUICK, config, "katago")
        assert result > 0


class TestEngineVisitsDefaults:
    """ENGINE_VISITS_DEFAULTS constant tests (Phase 171: KataGo-only)."""

    def test_katago_defaults_exist(self):
        """Contract: katago defaults are defined"""
        assert "katago" in ENGINE_VISITS_DEFAULTS
        assert "max_visits" in ENGINE_VISITS_DEFAULTS["katago"]
        assert "fast_visits" in ENGINE_VISITS_DEFAULTS["katago"]

    def test_leela_no_longer_in_defaults(self):
        """Phase 171: ENGINE_VISITS_DEFAULTS から leela が削除されたこと。"""
        assert "leela" not in ENGINE_VISITS_DEFAULTS

    def test_fast_visits_less_than_max_visits(self):
        """Contract: fast_visits < max_visits for all engines"""
        for engine, defaults in ENGINE_VISITS_DEFAULTS.items():
            assert defaults["fast_visits"] < defaults["max_visits"], f"{engine}: fast >= max"

    def test_all_values_are_positive(self):
        """Contract: all default values are positive"""
        for _engine, defaults in ENGINE_VISITS_DEFAULTS.items():
            assert defaults["max_visits"] > 0
            assert defaults["fast_visits"] > 0


# =============================================================================
# Phase 44: Tests for compute_effective_threshold
# =============================================================================


class TestComputeEffectiveThreshold:
    """Tests for compute_effective_threshold function (Phase 44)."""

    def test_low_target_100(self):
        """target=100 -> threshold=90 (100 * 0.9)"""
        assert compute_effective_threshold(100) == 90

    def test_medium_target_200(self):
        """target=200 -> threshold=180 (200 * 0.9)"""
        assert compute_effective_threshold(200) == 180

    def test_high_target_capped_at_200(self):
        """target=300 -> threshold=200 (capped at max_threshold)"""
        assert compute_effective_threshold(300) == 200

    def test_very_high_target_capped(self):
        """target=1000 -> threshold=200 (capped at max_threshold)"""
        assert compute_effective_threshold(1000) == 200

    def test_no_target_default(self):
        """target=None -> default max_threshold (200)"""
        assert compute_effective_threshold(None) == RELIABILITY_VISITS_THRESHOLD

    def test_zero_target_default(self):
        """target=0 -> default max_threshold (200)"""
        assert compute_effective_threshold(0) == RELIABILITY_VISITS_THRESHOLD

    def test_negative_target_default(self):
        """target=-100 -> default max_threshold (200)"""
        assert compute_effective_threshold(-100) == RELIABILITY_VISITS_THRESHOLD

    def test_very_low_target_minimum_1(self):
        """target=1 -> threshold=1 (never goes below 1)"""
        assert compute_effective_threshold(1) == 1

    def test_target_2_gives_2(self):
        """target=2 -> threshold=2 (round(2*0.9)=2)"""
        assert compute_effective_threshold(2) == 2

    def test_target_50_gives_45(self):
        """target=50 -> threshold=45 (50 * 0.9)"""
        assert compute_effective_threshold(50) == 45

    def test_custom_max_threshold(self):
        """Custom max_threshold is respected"""
        assert compute_effective_threshold(500, max_threshold=100) == 100

    def test_custom_ratio(self):
        """Custom ratio is respected"""
        assert compute_effective_threshold(100, ratio=0.5) == 50

    def test_default_ratio_is_reliability_ratio(self):
        """Default ratio should be RELIABILITY_RATIO (0.9)"""
        expected = max(1, round(100 * RELIABILITY_RATIO))
        assert compute_effective_threshold(100) == expected


class TestReliabilityStatsWithTargetVisits:
    """Tests for compute_reliability_stats with target_visits (Phase 44)."""

    def test_stats_stores_effective_threshold(self):
        """Ensure stats object has correct effective_threshold."""
        moves = [make_move_eval(move_number=1, player="B", gtp="D4", root_visits=95)]
        stats = compute_reliability_stats(moves, target_visits=100)
        assert stats.effective_threshold == 90

    def test_reliable_with_target_100(self):
        """95 visits is reliable when target=100 (threshold=90)."""
        moves = [make_move_eval(move_number=1, player="B", gtp="D4", root_visits=95)]
        stats = compute_reliability_stats(moves, target_visits=100)
        assert stats.reliable_count == 1
        assert stats.low_confidence_count == 0

    def test_unreliable_with_default_threshold(self):
        """95 visits is NOT reliable with default threshold (200)."""
        moves = [make_move_eval(move_number=1, player="B", gtp="D4", root_visits=95)]
        stats = compute_reliability_stats(moves)
        assert stats.reliable_count == 0
        assert stats.low_confidence_count == 1

    def test_boundary_exactly_at_threshold(self):
        """Visits exactly at threshold counts as reliable."""
        moves = [make_move_eval(move_number=1, player="B", gtp="D4", root_visits=90)]
        stats = compute_reliability_stats(moves, target_visits=100)
        assert stats.reliable_count == 1
        assert stats.low_confidence_count == 0

    def test_boundary_just_below_threshold(self):
        """Visits just below threshold is low-confidence."""
        moves = [make_move_eval(move_number=1, player="B", gtp="D4", root_visits=89)]
        stats = compute_reliability_stats(moves, target_visits=100)
        assert stats.reliable_count == 0
        assert stats.low_confidence_count == 1

    def test_mixed_visits_with_target(self):
        """Mixed visits are classified correctly with target_visits."""
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", root_visits=95),
            make_move_eval(move_number=2, player="W", gtp="Q16", root_visits=85),
            make_move_eval(move_number=3, player="B", gtp="C3", root_visits=100),
        ]
        stats = compute_reliability_stats(moves, target_visits=100)
        assert stats.reliable_count == 2
        assert stats.low_confidence_count == 1
        assert stats.total_moves == 3

    def test_target_visits_with_capped_threshold(self):
        """High target_visits uses capped threshold (200)."""
        moves = [make_move_eval(move_number=1, player="B", gtp="D4", root_visits=199)]
        stats = compute_reliability_stats(moves, target_visits=500)
        assert stats.effective_threshold == 200
        assert stats.reliable_count == 0
        assert stats.low_confidence_count == 1


# ---------------------------------------------------------------------------
# Phase 37 T3: Contract-based tests for resolve_visits()
# ---------------------------------------------------------------------------


class TestResolveVisitsContract:
    """Contract-based tests for resolve_visits() (Phase 171 KataGo-only)."""

    def test_returns_positive_integer(self):
        """Contract: return value is always a positive integer."""
        result = resolve_visits(AnalysisStrength.QUICK, {"fast_visits": 100}, "katago")
        assert isinstance(result, int)
        assert result >= 1

    def test_respects_config_value_when_valid(self):
        """Contract: valid config values are respected (KataGo 専用)。"""
        assert resolve_visits(AnalysisStrength.QUICK, {"fast_visits": 500}, "katago") == 500

    def test_missing_key_uses_engine_specific_default(self):
        """Contract: missing key uses engine-specific default."""
        katago_default = ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]

        assert resolve_visits(AnalysisStrength.QUICK, {}, "katago") == katago_default

    def test_negative_or_zero_becomes_positive(self):
        """Contract: non-positive values become positive (clamped to >= 1)."""
        assert resolve_visits(AnalysisStrength.QUICK, {"fast_visits": -10}, "katago") >= 1
        assert resolve_visits(AnalysisStrength.QUICK, {"fast_visits": 0}, "katago") >= 1

    def test_float_input_returns_int(self):
        """Contract: float input still returns int (truncated/rounded)."""
        result = resolve_visits(AnalysisStrength.QUICK, {"fast_visits": 99.9}, "katago")
        assert isinstance(result, int)

    def test_deep_uses_max_visits_key(self):
        """Contract: DEEP strength uses max_visits key."""
        katago_max = ENGINE_VISITS_DEFAULTS["katago"]["max_visits"]

        assert resolve_visits(AnalysisStrength.DEEP, {}, "katago") == katago_max

    def test_quick_and_deep_return_different_values_for_same_engine(self):
        """Contract: QUICK and DEEP return different values (fast vs max)."""
        quick_visits = resolve_visits(AnalysisStrength.QUICK, {}, "katago")
        deep_visits = resolve_visits(AnalysisStrength.DEEP, {}, "katago")
        assert quick_visits < deep_visits

    def test_unknown_engine_uses_katago_defaults(self):
        """Contract: unknown engine falls back to katago defaults."""
        katago_default = ENGINE_VISITS_DEFAULTS["katago"]["fast_visits"]
        result = resolve_visits(AnalysisStrength.QUICK, {}, "unknown_engine")
        assert result == katago_default


# =============================================================================
# Phase 44: Integration tests for extract_game_stats with target_visits
# =============================================================================


class TestExtractGameStatsTargetVisits:
    """Tests for extract_game_stats() target_visits parameter (Phase 44)."""

    def test_extract_game_stats_accepts_target_visits_parameter(self):
        """Contract: extract_game_stats accepts target_visits parameter."""
        import inspect

        from katrain.core.batch.stats import extract_game_stats

        sig = inspect.signature(extract_game_stats)
        params = list(sig.parameters.keys())
        assert "target_visits" in params

    def test_extract_game_stats_target_visits_defaults_to_none(self):
        """Contract: target_visits defaults to None."""
        import inspect

        from katrain.core.batch.stats import extract_game_stats

        sig = inspect.signature(extract_game_stats)
        param = sig.parameters["target_visits"]
        assert param.default is None


class TestBuildKarteReportTargetVisits:
    """Tests for build_karte_report() target_visits parameter (Phase 44)."""

    def test_build_karte_report_accepts_target_visits_parameter(self):
        """Contract: build_karte_report accepts target_visits parameter."""
        import inspect

        from katrain.core.reports.karte.builder import build_karte_report

        sig = inspect.signature(build_karte_report)
        params = list(sig.parameters.keys())
        assert "target_visits" in params

    def test_build_karte_report_target_visits_defaults_to_none(self):
        """Contract: target_visits defaults to None."""
        import inspect

        from katrain.core.reports.karte.builder import build_karte_report

        sig = inspect.signature(build_karte_report)
        param = sig.parameters["target_visits"]
        assert param.default is None

    def test_game_build_karte_report_accepts_target_visits(self):
        """Contract: Game.build_karte_report accepts target_visits parameter."""
        import inspect

        from katrain.core.game import Game

        sig = inspect.signature(Game.build_karte_report)
        params = list(sig.parameters.keys())
        assert "target_visits" in params

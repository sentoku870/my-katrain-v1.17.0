"""Tests for analysis engine configuration (Phase 33, Phase 171 KataGo-only)."""

import logging

import pytest

from katrain.core.analysis import (
    DEFAULT_ANALYSIS_ENGINE,
    VALID_ANALYSIS_ENGINES,
    EngineType,
    get_analysis_engine,
)


class TestAnalysisEngineConstants:
    """Tests for analysis engine constants (Phase 171 KataGo-only)."""

    def test_only_katago_is_valid(self):
        """Phase 171: KataGo のみが valid engine。"""
        assert EngineType.KATAGO.value in VALID_ANALYSIS_ENGINES
        assert EngineType.UNKNOWN.value not in VALID_ANALYSIS_ENGINES

    def test_valid_engines_is_frozenset(self):
        """VALID_ANALYSIS_ENGINES should be immutable."""
        assert isinstance(VALID_ANALYSIS_ENGINES, frozenset)

    def test_default_is_katago(self):
        """Default engine should be KataGo."""
        assert EngineType.KATAGO.value == DEFAULT_ANALYSIS_ENGINE
        assert DEFAULT_ANALYSIS_ENGINE == "katago"

    def test_exactly_one_valid_engine(self):
        """Phase 171: KataGo 1 つだけ。"""
        assert len(VALID_ANALYSIS_ENGINES) == 1


class TestGetAnalysisEngine:
    """Tests for get_analysis_engine function (Phase 171 KataGo-only)."""

    @pytest.mark.parametrize(
        "config,expected",
        [
            ({}, "katago"),
            ({"other_key": "value"}, "katago"),
            ({"analysis_engine": "katago"}, "katago"),
            # Phase 171: leela は KataGo にフォールバック
            ({"analysis_engine": "leela"}, "katago"),
            ({"analysis_engine": "invalid"}, "katago"),
            ({"analysis_engine": "unknown"}, "katago"),
            ({"analysis_engine": ""}, "katago"),
            ({"analysis_engine": "   "}, "katago"),
            ({"analysis_engine": "KataGo"}, "katago"),
            ({"analysis_engine": "KATAGO"}, "katago"),
            ({"analysis_engine": "Leela"}, "katago"),
            ({"analysis_engine": "LEELA"}, "katago"),
            ({"analysis_engine": None}, "katago"),
            ({"analysis_engine": 123}, "katago"),
            ({"analysis_engine": []}, "katago"),
            ({"analysis_engine": {"a": 1}}, "katago"),
        ],
    )
    def test_get_analysis_engine(self, config, expected):
        assert get_analysis_engine(config) == expected

    def test_does_not_modify_input(self):
        """Ensure function doesn't mutate input dict."""
        config = {"analysis_engine": "leela", "other": "value"}
        original = config.copy()
        get_analysis_engine(config)
        assert config == original


class TestGetAnalysisEngineWarnings:
    """Tests for warning behavior (separate class to isolate caplog)."""

    LOGGER_NAME = "katrain.core.analysis.models"

    def _relevant_records(self, caplog):
        return [r for r in caplog.records if r.name == self.LOGGER_NAME or r.name.startswith(self.LOGGER_NAME + ".")]

    @pytest.mark.parametrize(
        "invalid_value",
        [
            "LEELA",
            "KataGo",
            "invalid",
            "",
            None,
            123,
            [],
            {"a": 1},
        ],
    )
    def test_logs_warning_for_invalid_values(self, invalid_value, caplog):
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=self.LOGGER_NAME):
            result = get_analysis_engine({"analysis_engine": invalid_value})
        assert result == "katago"
        relevant_records = self._relevant_records(caplog)
        assert any(
            "Invalid analysis_engine" in r.getMessage() and "falling back" in r.getMessage() for r in relevant_records
        ), f"Expected warning not found in {[r.getMessage() for r in relevant_records]}"

    def test_no_warning_for_katago(self, caplog):
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=self.LOGGER_NAME):
            get_analysis_engine({"analysis_engine": "katago"})
        relevant_records = self._relevant_records(caplog)
        assert not any("Invalid analysis_engine" in r.getMessage() for r in relevant_records)


class TestGetAnalysisEngineContract:
    """Contract-based tests for get_analysis_engine() (Phase 171 KataGo-only)."""

    def test_valid_katago_accepted(self):
        """Contract: KataGo が唯一の valid engine として受理される。"""
        for engine in VALID_ANALYSIS_ENGINES:
            result = get_analysis_engine({"analysis_engine": engine})
            assert result == engine

    def test_invalid_values_return_katago(self):
        """Contract: invalid values always return "katago" (never crash)."""
        invalid_inputs = [
            None,
            "",
            123,
            [],
            {},
            " katago ",
            "LEELA",
            "Leela",
            "KataGo",
            object(),
            3.14,
            True,
            False,
        ]
        for invalid in invalid_inputs:
            result = get_analysis_engine({"analysis_engine": invalid})
            assert result in VALID_ANALYSIS_ENGINES

    def test_missing_key_returns_valid_engine(self):
        """Contract: missing key returns a valid engine (default)."""
        result = get_analysis_engine({})
        assert result in VALID_ANALYSIS_ENGINES

    def test_return_type_is_always_string(self):
        """Contract: return type is always a string."""
        test_cases = [
            {"analysis_engine": "katago"},
            {"analysis_engine": "leela"},
            {"analysis_engine": None},
            {},
        ]
        for config in test_cases:
            result = get_analysis_engine(config)
            assert isinstance(result, str)

    def test_valid_engines_non_empty(self):
        """Contract: at least KataGo がある。"""
        assert len(VALID_ANALYSIS_ENGINES) >= 1

    def test_default_is_in_valid_engines(self):
        """Contract: DEFAULT_ANALYSIS_ENGINE is in VALID_ANALYSIS_ENGINES."""
        assert DEFAULT_ANALYSIS_ENGINE in VALID_ANALYSIS_ENGINES

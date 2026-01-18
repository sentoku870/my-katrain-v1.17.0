"""Tests for analysis engine configuration (Phase 33)."""
import logging

import pytest

from katrain.core.analysis import (
    EngineType,
    VALID_ANALYSIS_ENGINES,
    DEFAULT_ANALYSIS_ENGINE,
    get_analysis_engine,
)


class TestAnalysisEngineConstants:
    """Tests for analysis engine constants."""

    def test_valid_engines_derived_from_engine_type(self):
        """Constants should be derived from EngineType enum values."""
        assert EngineType.KATAGO.value in VALID_ANALYSIS_ENGINES
        assert EngineType.LEELA.value in VALID_ANALYSIS_ENGINES
        # UNKNOWN is not a valid analysis engine
        assert EngineType.UNKNOWN.value not in VALID_ANALYSIS_ENGINES

    def test_valid_engines_is_frozenset(self):
        """VALID_ANALYSIS_ENGINES should be immutable."""
        assert isinstance(VALID_ANALYSIS_ENGINES, frozenset)

    def test_default_is_katago(self):
        """Default engine should be KataGo."""
        assert DEFAULT_ANALYSIS_ENGINE == EngineType.KATAGO.value
        assert DEFAULT_ANALYSIS_ENGINE == "katago"

    def test_exactly_two_valid_engines(self):
        """Only katago and leela are valid (no unknown)."""
        assert len(VALID_ANALYSIS_ENGINES) == 2


class TestGetAnalysisEngine:
    """Tests for get_analysis_engine function."""

    @pytest.mark.parametrize("config,expected", [
        # Default behavior (key missing)
        ({}, "katago"),
        ({"other_key": "value"}, "katago"),
        # Explicit valid values
        ({"analysis_engine": "katago"}, "katago"),
        ({"analysis_engine": "leela"}, "leela"),
        # Invalid string values -> fallback to katago
        ({"analysis_engine": "invalid"}, "katago"),
        ({"analysis_engine": "unknown"}, "katago"),  # EngineType.UNKNOWN is not valid
        ({"analysis_engine": ""}, "katago"),
        ({"analysis_engine": "   "}, "katago"),  # whitespace
        # Case sensitivity (strict: lowercase only)
        ({"analysis_engine": "KataGo"}, "katago"),
        ({"analysis_engine": "KATAGO"}, "katago"),
        ({"analysis_engine": "Leela"}, "katago"),
        ({"analysis_engine": "LEELA"}, "katago"),
        # Non-string types -> fallback (must not crash)
        ({"analysis_engine": None}, "katago"),
        ({"analysis_engine": 123}, "katago"),
        ({"analysis_engine": []}, "katago"),       # unhashable
        ({"analysis_engine": {"a": 1}}, "katago"), # unhashable
    ])
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

    # Logger name for filtering (matches models.py's _log)
    LOGGER_NAME = "katrain.core.analysis.models"

    @pytest.mark.parametrize("invalid_value", [
        "LEELA",
        "KataGo",
        "invalid",
        "",
        None,
        123,
        [],      # unhashable type - must not crash
        {"a": 1},  # unhashable type - must not crash
    ])
    def test_logs_warning_for_invalid_values(self, invalid_value, caplog):
        """Invalid values should log a warning with expected message prefix."""
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=self.LOGGER_NAME):
            result = get_analysis_engine({"analysis_engine": invalid_value})
        assert result == "katago"
        # Filter by logger name to avoid false positives from other warnings
        relevant_records = [r for r in caplog.records if r.name == self.LOGGER_NAME]
        # Use getMessage() for standard logging compatibility (handles lazy formatting)
        assert any(
            "Invalid analysis_engine" in r.getMessage() and "falling back" in r.getMessage()
            for r in relevant_records
        ), f"Expected warning not found in {[r.getMessage() for r in relevant_records]}"

    def test_no_warning_for_valid_values(self, caplog):
        """Valid values should not log a warning."""
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=self.LOGGER_NAME):
            get_analysis_engine({"analysis_engine": "katago"})
            get_analysis_engine({"analysis_engine": "leela"})
        relevant_records = [r for r in caplog.records if r.name == self.LOGGER_NAME]
        # Use getMessage() for standard logging compatibility
        assert not any(
            "Invalid analysis_engine" in r.getMessage()
            for r in relevant_records
        )

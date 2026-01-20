# tests/test_analysis_mode.py
"""Tests for AnalysisMode Enum and parse_analysis_mode function (Phase 41-A)."""

import json

import pytest

from katrain.core.constants import AnalysisMode, parse_analysis_mode


class TestAnalysisModeEnumInterop:
    """str Enum interoperability tests (verify assumptions from the plan)."""

    def test_string_equality(self):
        """String comparison works in both directions."""
        assert AnalysisMode.STOP == "stop"
        assert "stop" == AnalysisMode.STOP
        assert AnalysisMode.PONDER == "ponder"
        assert AnalysisMode.EXTRA == "extra"
        assert AnalysisMode.GAME == "game"
        assert AnalysisMode.SWEEP == "sweep"
        assert AnalysisMode.EQUALIZE == "equalize"
        assert AnalysisMode.ALTERNATIVE == "alternative"
        assert AnalysisMode.LOCAL == "local"

    def test_dict_key_compatibility(self):
        """Dict keys work interchangeably with strings."""
        d = {"stop": 1, "ponder": 2, "extra": 3}
        assert d[AnalysisMode.STOP] == 1
        assert d[AnalysisMode.PONDER] == 2
        assert d[AnalysisMode.EXTRA] == 3

    def test_json_serialization(self):
        """JSON output is a plain string."""
        result = json.dumps({"mode": AnalysisMode.STOP})
        assert result == '{"mode": "stop"}'

        result2 = json.dumps({"mode": AnalysisMode.PONDER})
        assert result2 == '{"mode": "ponder"}'

    def test_str_returns_value(self):
        """str() returns .value (f-string compatibility)."""
        assert str(AnalysisMode.STOP) == "stop"
        assert str(AnalysisMode.PONDER) == "ponder"
        assert f"Mode: {AnalysisMode.STOP}" == "Mode: stop"
        assert f"Analysis mode is {AnalysisMode.GAME}" == "Analysis mode is game"

    def test_in_operator(self):
        """in operator works with tuples/lists of Enum members."""
        modes = (AnalysisMode.EQUALIZE, AnalysisMode.ALTERNATIVE, AnalysisMode.LOCAL)
        assert AnalysisMode.EQUALIZE in modes
        assert AnalysisMode.ALTERNATIVE in modes
        assert AnalysisMode.LOCAL in modes
        assert AnalysisMode.STOP not in modes


class TestParseAnalysisMode:
    """Tests for parse_analysis_mode function."""

    def test_parse_valid_modes(self):
        """Valid mode strings are parsed correctly."""
        assert parse_analysis_mode("stop") == AnalysisMode.STOP
        assert parse_analysis_mode("ponder") == AnalysisMode.PONDER
        assert parse_analysis_mode("extra") == AnalysisMode.EXTRA
        assert parse_analysis_mode("game") == AnalysisMode.GAME
        assert parse_analysis_mode("sweep") == AnalysisMode.SWEEP
        assert parse_analysis_mode("equalize") == AnalysisMode.EQUALIZE
        assert parse_analysis_mode("alternative") == AnalysisMode.ALTERNATIVE
        assert parse_analysis_mode("local") == AnalysisMode.LOCAL

    def test_parse_with_whitespace(self):
        """Whitespace is stripped before parsing."""
        assert parse_analysis_mode(" stop ") == AnalysisMode.STOP
        assert parse_analysis_mode("  PONDER  ") == AnalysisMode.PONDER
        assert parse_analysis_mode("\textra\n") == AnalysisMode.EXTRA

    def test_parse_case_insensitive(self):
        """Parsing is case-insensitive."""
        assert parse_analysis_mode("STOP") == AnalysisMode.STOP
        assert parse_analysis_mode("Ponder") == AnalysisMode.PONDER
        assert parse_analysis_mode("EXTRA") == AnalysisMode.EXTRA
        assert parse_analysis_mode("Game") == AnalysisMode.GAME

    def test_parse_enum_passthrough(self):
        """AnalysisMode values pass through unchanged."""
        assert parse_analysis_mode(AnalysisMode.STOP) == AnalysisMode.STOP
        assert parse_analysis_mode(AnalysisMode.PONDER) == AnalysisMode.PONDER
        assert parse_analysis_mode(AnalysisMode.EXTRA) == AnalysisMode.EXTRA

    def test_parse_invalid_fallback(self):
        """Invalid values fall back to STOP (default)."""
        assert parse_analysis_mode("invalid") == AnalysisMode.STOP
        assert parse_analysis_mode("unknown") == AnalysisMode.STOP
        assert parse_analysis_mode("") == AnalysisMode.STOP
        assert parse_analysis_mode("  ") == AnalysisMode.STOP

    def test_parse_toggle_not_a_mode(self):
        """'toggle' is NOT a valid AnalysisMode (it's an action token for set_insert_mode)."""
        # toggle should fall back to STOP since it's not a valid analysis mode
        assert parse_analysis_mode("toggle") == AnalysisMode.STOP

    def test_parse_custom_fallback(self):
        """Custom fallback value is used for invalid inputs."""
        assert parse_analysis_mode("invalid", fallback=AnalysisMode.PONDER) == AnalysisMode.PONDER
        assert parse_analysis_mode("", fallback=AnalysisMode.GAME) == AnalysisMode.GAME

    def test_parse_none_fallback(self):
        """None input falls back (AttributeError caught)."""
        # This tests the AttributeError branch
        assert parse_analysis_mode(None) == AnalysisMode.STOP  # type: ignore

    def test_all_modes_have_unique_values(self):
        """All AnalysisMode members have unique values."""
        values = [m.value for m in AnalysisMode]
        assert len(values) == len(set(values))
        assert len(values) == 8  # stop, ponder, extra, game, sweep, equalize, alternative, local

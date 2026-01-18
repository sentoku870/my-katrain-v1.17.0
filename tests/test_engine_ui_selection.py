"""Tests for analysis engine UI selection (Phase 34).

CI-friendly: no Kivy event loop required.
Tests production code directly where possible.
"""
import pytest

from katrain.core.analysis import (
    EngineType,
    VALID_ANALYSIS_ENGINES,
    DEFAULT_ANALYSIS_ENGINE,
    get_analysis_engine,
    needs_leela_warning,
)
from katrain.common.settings_export import TAB_RESET_KEYS, get_default_value


class TestNeedsLeelaWarning:
    """Production helper: needs_leela_warning()"""

    @pytest.mark.parametrize(
        "selected,leela_enabled,expected",
        [
            (EngineType.LEELA.value, False, True),  # Leela selected, disabled -> warn
            (EngineType.LEELA.value, True, False),  # Leela selected, enabled -> no warn
            (EngineType.KATAGO.value, False, False),  # KataGo selected -> no warn
            (EngineType.KATAGO.value, True, False),  # KataGo selected -> no warn
        ],
    )
    def test_warning_conditions(self, selected, leela_enabled, expected):
        """Production function with EngineType values"""
        assert needs_leela_warning(selected, leela_enabled) == expected

    def test_case_sensitive(self):
        """Uppercase does not match (EngineType.LEELA.value is lowercase)"""
        assert needs_leela_warning("LEELA", False) is False
        assert needs_leela_warning("Leela", False) is False


class TestTABResetKeysEngineEntry:
    """TAB_RESET_KEYS should include analysis_engine"""

    def test_analysis_tab_includes_engine_key(self):
        analysis_keys = TAB_RESET_KEYS.get("analysis", [])
        assert ("engine", "analysis_engine") in analysis_keys

    def test_analysis_tab_has_expected_keys(self):
        """All required keys are present (order doesn't matter)"""
        analysis_keys = TAB_RESET_KEYS.get("analysis", [])
        expected = {
            ("engine", "analysis_engine"),
            ("general", "skill_preset"),
            ("general", "pv_filter_level"),
        }
        assert expected.issubset(set(analysis_keys))


class TestResetDefaultValue:
    """Reset default value should be correct"""

    def test_default_analysis_engine_matches_constant(self):
        """get_default_value and DEFAULT_ANALYSIS_ENGINE should match"""
        default_val = get_default_value("engine", "analysis_engine")
        assert default_val == DEFAULT_ANALYSIS_ENGINE

    def test_constant_is_katago(self):
        """DEFAULT_ANALYSIS_ENGINE should be "katago" (Phase 33 contract)"""
        # This documents the expected default; if it changes, update both here and config.json
        assert DEFAULT_ANALYSIS_ENGINE == "katago"


class TestEngineMergePattern:
    """engine section save MERGE pattern verification

    Note: This tests the Python dict merge pattern used in implementation.
    It documents expected behavior rather than testing production code directly.
    """

    def test_merge_preserves_other_keys(self):
        """analysis_engine update should preserve other keys (katago, model, etc.)"""
        existing = {
            "katago": "/path/to/katago",
            "model": "model.bin.gz",
            "analysis_engine": EngineType.KATAGO.value,
        }
        new_value = EngineType.LEELA.value

        # Implementation pattern: {**existing, "analysis_engine": new_value}
        updated = {**existing, "analysis_engine": new_value}

        assert updated["katago"] == existing["katago"]
        assert updated["model"] == existing["model"]
        assert updated["analysis_engine"] == new_value

    def test_merge_with_empty_existing(self):
        """Should work with empty existing config"""
        existing = {}
        updated = {**existing, "analysis_engine": EngineType.LEELA.value}
        assert updated == {"analysis_engine": EngineType.LEELA.value}


class TestEngineValueConsistency:
    """Engine value name consistency tests"""

    def test_engine_type_values_in_valid_engines(self):
        """EngineType values should be in VALID_ANALYSIS_ENGINES"""
        assert EngineType.KATAGO.value in VALID_ANALYSIS_ENGINES
        assert EngineType.LEELA.value in VALID_ANALYSIS_ENGINES

    def test_unknown_not_in_valid_engines(self):
        """UNKNOWN should not be in valid engines"""
        assert EngineType.UNKNOWN.value not in VALID_ANALYSIS_ENGINES

    def test_default_is_valid_engine(self):
        """Default engine should be in valid engines"""
        assert DEFAULT_ANALYSIS_ENGINE in VALID_ANALYSIS_ENGINES

    def test_get_analysis_engine_returns_valid(self):
        """get_analysis_engine should always return a valid engine"""
        # Empty config -> default
        assert get_analysis_engine({}) in VALID_ANALYSIS_ENGINES
        # Valid config
        assert get_analysis_engine({"analysis_engine": "leela"}) in VALID_ANALYSIS_ENGINES
        # Invalid config -> fallback to default
        assert get_analysis_engine({"analysis_engine": "invalid"}) in VALID_ANALYSIS_ENGINES


class TestAnalysisModuleExports:
    """analysis module public interface check"""

    def test_needs_leela_warning_is_exported(self):
        """needs_leela_warning should be importable from analysis package"""
        from katrain.core.analysis import needs_leela_warning

        assert callable(needs_leela_warning)

    def test_engine_type_is_exported(self):
        """EngineType should be importable from analysis package"""
        from katrain.core.analysis import EngineType

        assert hasattr(EngineType, "KATAGO")
        assert hasattr(EngineType, "LEELA")


class TestNeedsLeelaWarningEdgeCases:
    """Edge cases for needs_leela_warning() - CI-stable"""

    def test_empty_string_engine(self):
        """Empty string should not trigger warning (doesn't match LEELA)"""
        assert needs_leela_warning("", False) is False

    def test_none_leela_enabled_behavior(self):
        """leela_enabled=None behavior check (TypeError or False)

        Python `not None` is True, so Leela + None -> True.
        This documents the expected behavior.
        """
        result = needs_leela_warning(EngineType.LEELA.value, None)
        assert result is True  # `not None` == True

    def test_whitespace_engine(self):
        """Whitespace should not match LEELA"""
        assert needs_leela_warning(" leela ", False) is False
        assert needs_leela_warning("leela ", False) is False

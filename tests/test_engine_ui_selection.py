"""Tests for analysis engine UI selection (Phase 34, Phase 171 KataGo-only).

CI-friendly: no Kivy event loop required.
Tests production code directly where possible.

Phase 171: Leela 削除に伴い ``needs_leela_warning`` /
``EngineType.LEELA`` 関連のテストを KataGo-only に整理。
"""

from katrain.common.settings_export import TAB_RESET_KEYS, get_default_value
from katrain.core.analysis import (
    DEFAULT_ANALYSIS_ENGINE,
    VALID_ANALYSIS_ENGINES,
    EngineType,
    get_analysis_engine,
)


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

    def test_no_leela_tab_after_phase_171(self):
        """Phase 171: leela タブは廃止。"""
        assert "leela" not in TAB_RESET_KEYS


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
        # Phase 171: KataGo 固定。以前は LEELA.value を入れていた。
        new_value = EngineType.KATAGO.value

        # Implementation pattern: {**existing, "analysis_engine": new_value}
        updated = {**existing, "analysis_engine": new_value}

        assert updated["katago"] == existing["katago"]
        assert updated["model"] == existing["model"]
        assert updated["analysis_engine"] == new_value

    def test_merge_with_empty_existing(self):
        """Should work with empty existing config"""
        existing = {}
        updated = {**existing, "analysis_engine": EngineType.KATAGO.value}
        assert updated == {"analysis_engine": EngineType.KATAGO.value}


class TestEngineValueConsistency:
    """Engine value name consistency tests (Phase 171 KataGo-only)"""

    def test_katago_in_valid_engines(self):
        """EngineType.KATAGO.value should be in VALID_ANALYSIS_ENGINES"""
        assert EngineType.KATAGO.value in VALID_ANALYSIS_ENGINES

    def test_leela_no_longer_in_engine_type(self):
        """Phase 171: EngineType.LEELA は削除された。"""
        assert not hasattr(EngineType, "LEELA")

    def test_unknown_not_in_valid_engines(self):
        """UNKNOWN should not be in valid engines"""
        assert EngineType.UNKNOWN.value not in VALID_ANALYSIS_ENGINES

    def test_default_is_valid_engine(self):
        """Default engine should be in valid engines"""
        assert DEFAULT_ANALYSIS_ENGINE in VALID_ANALYSIS_ENGINES

    def test_get_analysis_engine_always_returns_valid(self):
        """get_analysis_engine should always return a valid engine (KataGo)"""
        # Empty config -> default
        assert get_analysis_engine({}) == EngineType.KATAGO.value
        # Phase 171: leela 設定は KataGo にフォールバック
        assert get_analysis_engine({"analysis_engine": "leela"}) == EngineType.KATAGO.value
        # Invalid config -> fallback to default
        assert get_analysis_engine({"analysis_engine": "invalid"}) == EngineType.KATAGO.value


class TestAnalysisModuleExports:
    """analysis module public interface check (Phase 171 KataGo-only)"""

    def test_needs_leela_warning_no_longer_exported(self):
        """Phase 171: needs_leela_warning は削除された。"""
        from katrain.core import analysis as analysis_module

        assert not hasattr(analysis_module, "needs_leela_warning")

    def test_engine_type_is_exported(self):
        """EngineType should be importable from analysis package"""
        from katrain.core.analysis import EngineType

        assert hasattr(EngineType, "KATAGO")
        assert hasattr(EngineType, "UNKNOWN")
        assert not hasattr(EngineType, "LEELA")

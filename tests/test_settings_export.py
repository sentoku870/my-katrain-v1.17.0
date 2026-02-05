# tests/test_settings_export.py
"""Tests for katrain.common.settings_export module (22 tests)."""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from katrain.common.settings_export import (
    SCHEMA_VERSION,
    TAB_RESET_KEYS,
    _ensure_json_safe,
    atomic_save_config,
    create_backup_path,
    export_settings,
    get_default_value,
    parse_exported_settings,
)


# --- Fixtures ---
@pytest.fixture
def mock_package_defaults():
    """Mock for package defaults."""
    defaults = {
        "general": {
            "version": "1.17.0",
            "lang": "en",
            "skill_preset": "standard",
            "pv_filter_level": "auto",
            "debug_level": 0,
        },
        "mykatrain_settings": {
            "default_user_name": "",
            "karte_format": "both",
        },
        "leela": {
            "enabled": False,
            "loss_scale_k": 0.5,
        },
    }
    with patch("katrain.common.settings_export.get_package_defaults", return_value=defaults):
        yield defaults


# --- JSON Safety Tests (2 tests) ---
class TestEnsureJsonSafe:
    """Tests for _ensure_json_safe function."""

    def test_primitive_types(self):
        """Primitive types should pass through unchanged."""
        assert _ensure_json_safe(None) is None
        assert _ensure_json_safe(True) is True
        assert _ensure_json_safe(False) is False
        assert _ensure_json_safe(42) == 42
        assert _ensure_json_safe(3.14) == 3.14
        assert _ensure_json_safe("hello") == "hello"

    def test_non_serializable_returns_none(self):
        """Non-serializable types should return None."""

        class Custom:
            pass

        assert _ensure_json_safe(Custom()) is None
        # In nested dict, non-serializable values become None
        result = _ensure_json_safe({"key": Custom()})
        assert result == {"key": None}


# --- Export Tests (7 tests) ---
class TestExportSettings:
    """Tests for export_settings function."""

    def test_excludes_engine_section(self):
        """Engine section should be excluded from export."""
        config = {
            "engine": {"katago": "/path/to/katago"},
            "general": {"skill_preset": "standard"},
        }
        result = json.loads(export_settings(config, "1.17.0"))
        assert "engine" not in result["sections"]
        assert "general" in result["sections"]

    def test_excludes_ui_state_section(self):
        """UI state section should be excluded from export."""
        config = {
            "ui_state": {"size": [800, 600]},
            "general": {"skill_preset": "standard"},
        }
        result = json.loads(export_settings(config, "1.17.0"))
        assert "ui_state" not in result["sections"]

    def test_excludes_version_and_lang(self):
        """Version and lang keys should be excluded from general section."""
        config = {
            "general": {
                "version": "1.17.0",
                "lang": "en",
                "skill_preset": "standard",
            }
        }
        result = json.loads(export_settings(config, "1.17.0"))
        assert "version" not in result["sections"]["general"]
        assert "lang" not in result["sections"]["general"]
        assert "skill_preset" in result["sections"]["general"]

    def test_includes_user_settings(self):
        """User settings sections should be included."""
        config = {
            "mykatrain_settings": {"default_user_name": "test"},
            "leela": {"enabled": False},
        }
        result = json.loads(export_settings(config, "1.17.0"))
        assert "mykatrain_settings" in result["sections"]
        assert "leela" in result["sections"]

    def test_schema_version_included(self):
        """Schema version should be included in export."""
        result = json.loads(export_settings({}, "1.17.0"))
        assert result["schema_version"] == SCHEMA_VERSION

    def test_skips_non_dict_sections(self):
        """Non-dict sections should be skipped."""
        config = {
            "general": {"skill_preset": "standard"},
            "invalid": "not a dict",
        }
        result = json.loads(export_settings(config, "1.17.0"))
        assert "invalid" not in result["sections"]

    def test_deep_copy_prevents_mutation(self):
        """Export should not mutate the original config."""
        config = {"general": {"skill_preset": "standard", "version": "1.17.0"}}
        original_general = dict(config["general"])
        export_settings(config, "1.17.0")
        assert config["general"] == original_general


# --- Parse Tests (7 tests) ---
class TestParseExportedSettings:
    """Tests for parse_exported_settings function."""

    def test_parse_valid_json(self):
        """Valid JSON should parse successfully."""
        json_str = json.dumps(
            {
                "schema_version": "1.0",
                "app_version": "1.17.0",
                "sections": {"general": {"skill_preset": "standard"}},
            }
        )
        result = parse_exported_settings(json_str)
        assert result.schema_version == "1.0"
        assert result.sections["general"]["skill_preset"] == "standard"

    def test_parse_invalid_schema_version_raises(self):
        """Invalid schema version should raise ValueError."""
        json_str = json.dumps({"schema_version": "2.0", "sections": {}})
        with pytest.raises(ValueError, match="Unsupported schema version"):
            parse_exported_settings(json_str)

    def test_parse_malformed_json_raises(self):
        """Malformed JSON should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_exported_settings("not json")

    def test_parse_missing_sections_raises(self):
        """Missing sections should raise ValueError."""
        json_str = json.dumps({"schema_version": "1.0"})
        with pytest.raises(ValueError, match="'sections' must be"):
            parse_exported_settings(json_str)

    def test_parse_skips_non_dict_sections(self):
        """Non-dict sections should be skipped during parse."""
        json_str = json.dumps(
            {
                "schema_version": "1.0",
                "sections": {"valid": {"key": "value"}, "invalid": "string"},
            }
        )
        result = parse_exported_settings(json_str)
        assert "valid" in result.sections
        assert "invalid" not in result.sections

    def test_parse_empty_sections(self):
        """Empty sections dict should work."""
        json_str = json.dumps({"schema_version": "1.0", "sections": {}})
        result = parse_exported_settings(json_str)
        assert result.sections == {}

    def test_parse_null_values_in_section(self):
        """Null values in sections should be preserved."""
        json_str = json.dumps({"schema_version": "1.0", "sections": {"general": {"key": None}}})
        result = parse_exported_settings(json_str)
        assert result.sections["general"]["key"] is None


# --- Defaults Tests (3 tests) ---
class TestGetDefaults:
    """Tests for get_default_value function."""

    def test_get_default_value_existing_key(self, mock_package_defaults):
        """Should return default value for existing key."""
        value = get_default_value("general", "debug_level")
        assert value == 0

    def test_get_default_value_missing_key_returns_none(self, mock_package_defaults):
        """Should return None for missing key."""
        value = get_default_value("general", "nonexistent_key")
        assert value is None

    def test_get_default_value_missing_section_returns_none(self, mock_package_defaults):
        """Should return None for missing section."""
        value = get_default_value("nonexistent_section", "key")
        assert value is None


# --- Roundtrip Test (1 test) ---
class TestRoundtrip:
    """Tests for export/parse roundtrip."""

    def test_export_parse_roundtrip(self):
        """Exported settings should parse back correctly."""
        config = {
            "general": {"skill_preset": "standard", "pv_filter_level": "auto"},
            "mykatrain_settings": {"default_user_name": "Player"},
        }
        json_str = export_settings(config, "1.17.0")
        parsed = parse_exported_settings(json_str)
        assert parsed.sections["general"]["skill_preset"] == "standard"
        assert parsed.sections["mykatrain_settings"]["default_user_name"] == "Player"


# --- Backup Path Test (1 test) ---
class TestBackupPath:
    """Tests for create_backup_path function."""

    def test_create_backup_path_format(self):
        """Backup path should have correct format."""
        path = create_backup_path("/home/user/.katrain/config.json")
        assert path.startswith("/home/user/.katrain/config.json.backup.")
        # Timestamp format: YYYYMMDD_HHMMSS (15 chars)
        timestamp_part = path.split(".")[-1]
        assert len(timestamp_part) == 15


# --- Atomic Save Tests (5 tests) ---
class TestAtomicSave:
    """Tests for atomic_save_config function."""

    def test_atomic_save_creates_file(self):
        """Should create new config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            config = {"general": {"skill_preset": "standard"}}
            atomic_save_config(config, config_path)
            assert os.path.exists(config_path)
            with open(config_path, encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["general"]["skill_preset"] == "standard"

    def test_atomic_save_replaces_existing(self):
        """Should replace existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            # Create existing file
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"old": "data"}, f)
            # Replace with new data
            config = {"new": "data"}
            atomic_save_config(config, config_path)
            with open(config_path, encoding="utf-8") as f:
                loaded = json.load(f)
            assert "new" in loaded
            assert "old" not in loaded

    def test_cleanup_on_serialization_failure(self):
        """Temp file should be cleaned up on serialization failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")

            class NotSerializable:
                pass

            config = {"bad": NotSerializable()}
            with pytest.raises(TypeError):
                atomic_save_config(config, config_path)
            # Temp file should not remain
            temp_files = [f for f in os.listdir(tmpdir) if f.startswith("config_")]
            assert len(temp_files) == 0

    def test_no_corruption_on_failure(self):
        """Original file should not be corrupted on failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            # Create existing file
            original = {"original": "data"}
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(original, f)

            # Attempt failed write
            class NotSerializable:
                pass

            with pytest.raises(TypeError):
                atomic_save_config({"bad": NotSerializable()}, config_path)
            # Original file should be intact
            with open(config_path, encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded == original

    def test_creates_parent_directory(self):
        """Should create parent directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "subdir", "config.json")
            config = {"key": "value"}
            atomic_save_config(config, config_path)
            assert os.path.exists(config_path)


# --- TAB_RESET_KEYS Integrity Tests (2 tests) ---
class TestTabResetKeys:
    """Tests for TAB_RESET_KEYS mapping integrity."""

    def test_all_tabs_defined(self):
        """All expected tabs should be defined."""
        assert "analysis" in TAB_RESET_KEYS
        assert "export" in TAB_RESET_KEYS
        assert "leela" in TAB_RESET_KEYS

    def test_keys_are_tuples(self):
        """All keys should be (section, key) tuples."""
        for tab, keys in TAB_RESET_KEYS.items():
            for item in keys:
                assert isinstance(item, tuple), f"Item in {tab} is not a tuple"
                assert len(item) == 2, f"Item in {tab} doesn't have 2 elements"
                section, key = item
                assert isinstance(section, str), f"Section in {tab} is not a string"
                assert isinstance(key, str), f"Key in {tab} is not a string"

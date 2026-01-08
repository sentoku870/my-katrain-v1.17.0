"""
Tests for KaTrain Qt Settings module.

Tests cover:
- Settings persistence (JSON file)
- Environment variable overrides
- Default values
- Settings reset
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from katrain_qt.settings import (
    Settings,
    AppSettings,
    DEFAULT_MAX_VISITS,
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_KOMI,
    DEFAULT_RULES,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_settings_dir(tmp_path):
    """Create a temporary directory for settings."""
    return tmp_path


@pytest.fixture
def settings(temp_settings_dir):
    """Create a Settings instance with temporary directory."""
    return Settings(settings_dir=temp_settings_dir)


@pytest.fixture
def clean_env():
    """Remove any KataGo environment variables for testing."""
    env_vars = ["KATAGO_EXE", "KATAGO_CONFIG", "KATAGO_MODEL"]
    original = {k: os.environ.get(k) for k in env_vars}

    for k in env_vars:
        if k in os.environ:
            del os.environ[k]

    yield

    # Restore original values
    for k, v in original.items():
        if v is not None:
            os.environ[k] = v
        elif k in os.environ:
            del os.environ[k]


# =============================================================================
# AppSettings Tests
# =============================================================================

class TestAppSettings:
    """Tests for AppSettings dataclass."""

    def test_default_values(self):
        """AppSettings should have sensible defaults."""
        settings = AppSettings()
        assert settings.katago_exe == ""
        assert settings.config_path == ""
        assert settings.model_path == ""
        assert settings.max_visits == DEFAULT_MAX_VISITS
        assert settings.max_candidates == DEFAULT_MAX_CANDIDATES
        assert settings.komi == DEFAULT_KOMI
        assert settings.rules == DEFAULT_RULES

    def test_to_dict(self):
        """to_dict should return all fields."""
        settings = AppSettings(katago_exe="/path/to/katago", max_visits=500)
        d = settings.to_dict()
        assert d["katago_exe"] == "/path/to/katago"
        assert d["max_visits"] == 500

    def test_from_dict(self):
        """from_dict should create settings from dictionary."""
        data = {
            "katago_exe": "/path/to/katago",
            "max_visits": 2000,
            "rules": "chinese",
        }
        settings = AppSettings.from_dict(data)
        assert settings.katago_exe == "/path/to/katago"
        assert settings.max_visits == 2000
        assert settings.rules == "chinese"

    def test_from_dict_ignores_unknown_keys(self):
        """from_dict should ignore unknown keys."""
        data = {
            "katago_exe": "/path/to/katago",
            "unknown_key": "ignored",
        }
        settings = AppSettings.from_dict(data)
        assert settings.katago_exe == "/path/to/katago"
        assert not hasattr(settings, "unknown_key")


# =============================================================================
# Settings Manager Tests
# =============================================================================

class TestSettings:
    """Tests for Settings manager."""

    def test_default_values(self, settings, clean_env):
        """Fresh settings should have defaults."""
        assert settings.katago_exe == ""
        assert settings.max_visits == DEFAULT_MAX_VISITS
        assert settings.komi == DEFAULT_KOMI

    def test_set_and_get_values(self, settings, clean_env):
        """Settings should be settable and gettable."""
        settings.katago_exe = "/path/to/katago"
        settings.max_visits = 2000
        settings.komi = 7.5

        assert settings.katago_exe == "/path/to/katago"
        assert settings.max_visits == 2000
        assert settings.komi == 7.5

    def test_max_visits_clamped(self, settings, clean_env):
        """max_visits should be clamped to valid range."""
        settings.max_visits = 0  # Below minimum
        assert settings.max_visits == 1  # Clamped to 1

        settings.max_visits = 200000  # Above maximum
        assert settings.max_visits == 100000  # Clamped to 100000

    def test_max_candidates_clamped(self, settings, clean_env):
        """max_candidates should be clamped to valid range."""
        settings.max_candidates = 0
        assert settings.max_candidates == 1

        settings.max_candidates = 50
        assert settings.max_candidates == 20

    def test_save_and_load(self, temp_settings_dir, clean_env):
        """Settings should persist across instances."""
        # Create and save settings
        s1 = Settings(settings_dir=temp_settings_dir)
        s1.katago_exe = "/path/to/katago"
        s1.max_visits = 1500
        s1.save()

        # Create new instance and verify persistence
        s2 = Settings(settings_dir=temp_settings_dir)
        assert s2._settings.katago_exe == "/path/to/katago"
        assert s2.max_visits == 1500

    def test_settings_file_created(self, settings, temp_settings_dir, clean_env):
        """save() should create settings file."""
        settings.katago_exe = "/path/to/katago"
        settings.save()

        assert settings.settings_path.exists()

        # Verify JSON content
        with open(settings.settings_path) as f:
            data = json.load(f)
        assert data["katago_exe"] == "/path/to/katago"

    def test_reset_to_defaults(self, settings, clean_env):
        """reset_to_defaults should restore all settings."""
        settings.katago_exe = "/path/to/katago"
        settings.max_visits = 2000
        settings.save()

        settings.reset_to_defaults()

        assert settings.katago_exe == ""
        assert settings.max_visits == DEFAULT_MAX_VISITS


# =============================================================================
# Environment Variable Override Tests
# =============================================================================

class TestEnvironmentOverrides:
    """Tests for environment variable overrides."""

    def test_katago_exe_env_override(self, settings, clean_env):
        """KATAGO_EXE should override saved value."""
        settings.katago_exe = "/saved/path"
        settings.save()

        os.environ["KATAGO_EXE"] = "/env/path"

        assert settings.katago_exe == "/env/path"
        assert settings.is_katago_exe_from_env()

    def test_config_path_env_override(self, settings, clean_env):
        """KATAGO_CONFIG should override saved value."""
        settings.config_path = "/saved/config"
        settings.save()

        os.environ["KATAGO_CONFIG"] = "/env/config"

        assert settings.config_path == "/env/config"
        assert settings.is_config_path_from_env()

    def test_model_path_env_override(self, settings, clean_env):
        """KATAGO_MODEL should override saved value."""
        settings.model_path = "/saved/model"
        settings.save()

        os.environ["KATAGO_MODEL"] = "/env/model"

        assert settings.model_path == "/env/model"
        assert settings.is_model_path_from_env()

    def test_env_check_without_env(self, settings, clean_env):
        """is_*_from_env should return False when no env var set."""
        assert not settings.is_katago_exe_from_env()
        assert not settings.is_config_path_from_env()
        assert not settings.is_model_path_from_env()

    def test_saved_value_preserved_with_env(self, temp_settings_dir, clean_env):
        """Saved value should be preserved even when env var overrides."""
        # Save a value
        s1 = Settings(settings_dir=temp_settings_dir)
        s1.katago_exe = "/saved/path"
        s1.save()

        # Set env var
        os.environ["KATAGO_EXE"] = "/env/path"

        # New instance should have env var value but saved value preserved
        s2 = Settings(settings_dir=temp_settings_dir)
        assert s2.katago_exe == "/env/path"  # Effective value
        assert s2._settings.katago_exe == "/saved/path"  # Saved value


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_corrupt_json_file(self, temp_settings_dir, clean_env):
        """Should handle corrupt JSON file gracefully."""
        # Create corrupt file
        settings_path = temp_settings_dir / "katrain_qt_settings.json"
        with open(settings_path, "w") as f:
            f.write("{ invalid json")

        # Should load defaults without error
        settings = Settings(settings_dir=temp_settings_dir)
        assert settings.max_visits == DEFAULT_MAX_VISITS

    def test_missing_settings_file(self, temp_settings_dir, clean_env):
        """Should work with missing settings file."""
        settings = Settings(settings_dir=temp_settings_dir)
        assert settings.max_visits == DEFAULT_MAX_VISITS

    def test_settings_path_property(self, settings, temp_settings_dir):
        """settings_path should return correct path."""
        assert settings.settings_path == temp_settings_dir / "katrain_qt_settings.json"

    def test_settings_dir_property(self, settings, temp_settings_dir):
        """settings_dir should return correct directory."""
        assert settings.settings_dir == temp_settings_dir

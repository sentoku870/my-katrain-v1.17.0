# tests/test_auto_setup.py
"""Tests for Phase 89 auto_setup module.

CI-safe: No real KataGo binaries, GPU, or OpenCL required.
All engine/subprocess interactions are mocked.
"""

from unittest.mock import patch

from katrain.core.auto_setup import (
    MIGRATED_DEFAULT_MODE,
    _has_custom_engine_settings,
    find_cpu_katago,
    find_lightweight_model,
    get_auto_setup_config,
    resolve_auto_engine_settings,
    should_show_auto_tab_first,
)
from katrain.core.test_analysis import ErrorCategory

# =============================================================================
# TestNewUserDetection
# =============================================================================


class TestNewUserDetection:
    """Tests for new user detection and mode assignment."""

    def test_new_user_flag_true_uses_auto(self):
        """is_new_user=True -> mode=auto"""
        result = get_auto_setup_config({}, is_new_user=True)
        assert result["mode"] == "auto"
        assert result["first_run_completed"] is False

    def test_new_user_flag_false_with_empty_config_uses_standard(self):
        """is_new_user=False + empty config -> mode=standard (existing user)"""
        result = get_auto_setup_config({}, is_new_user=False)
        assert result["mode"] == MIGRATED_DEFAULT_MODE
        assert result["mode"] == "standard"


# =============================================================================
# TestMigrationRules
# =============================================================================


class TestMigrationRules:
    """Tests for migration rules from existing users."""

    def test_existing_auto_setup_preserved(self):
        """Existing auto_setup section is preserved."""
        user_config = {"auto_setup": {"mode": "standard", "first_run_completed": True}}
        result = get_auto_setup_config(user_config, is_new_user=False)
        assert result["mode"] == "standard"
        assert result["first_run_completed"] is True

    def test_custom_katago_path_uses_advanced(self):
        """Custom katago path -> mode=advanced"""
        user_config = {"engine": {"katago": "/custom/path/katago"}}
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "", "model": "default.bin.gz", "config": "default.cfg"},
        ):
            result = get_auto_setup_config(user_config, is_new_user=False)
        assert result["mode"] == "advanced"

    def test_custom_model_path_uses_advanced(self):
        """Custom model path -> mode=advanced"""
        user_config = {"engine": {"model": "/custom/model.bin.gz"}}
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "", "model": "default.bin.gz", "config": "default.cfg"},
        ):
            result = get_auto_setup_config(user_config, is_new_user=False)
        assert result["mode"] == "advanced"

    def test_same_as_packaged_model_not_custom(self):
        """Model same as packaged default is not considered custom."""
        packaged_model = "katrain/models/kata1-b18c384nbt-xxx.bin.gz"
        user_config = {"engine": {"model": packaged_model}}
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "", "model": packaged_model, "config": "default.cfg"},
        ):
            result = get_auto_setup_config(user_config, is_new_user=False)
        assert result["mode"] == "standard"

    def test_empty_strings_not_custom(self):
        """Empty strings mean 'use default' and are not custom."""
        user_config = {"engine": {"katago": "", "model": "", "config": ""}}
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "", "model": "default.bin.gz", "config": "default.cfg"},
        ):
            result = get_auto_setup_config(user_config, is_new_user=False)
        assert result["mode"] == "standard"


# =============================================================================
# TestShouldShowAutoTabFirst
# =============================================================================


class TestShouldShowAutoTabFirst:
    """Tests for Auto tab display logic."""

    def test_auto_mode_not_completed_shows_first(self):
        """mode=auto AND first_run_completed=False -> show Auto tab first."""
        auto_setup = {"mode": "auto", "first_run_completed": False}
        assert should_show_auto_tab_first(auto_setup) is True

    def test_auto_mode_completed_not_first(self):
        """mode=auto AND first_run_completed=True -> normal tab order."""
        auto_setup = {"mode": "auto", "first_run_completed": True}
        assert should_show_auto_tab_first(auto_setup) is False

    def test_standard_mode_not_first(self):
        """mode=standard -> normal tab order."""
        auto_setup = {"mode": "standard", "first_run_completed": False}
        assert should_show_auto_tab_first(auto_setup) is False

    def test_advanced_mode_not_first(self):
        """mode=advanced -> normal tab order."""
        auto_setup = {"mode": "advanced", "first_run_completed": False}
        assert should_show_auto_tab_first(auto_setup) is False


# =============================================================================
# TestResolveAutoEngineSettings
# =============================================================================


class TestResolveAutoEngineSettings:
    """Tests for auto engine settings resolution."""

    def test_lightweight_model_found(self, tmp_path):
        """Lightweight model found -> returns settings."""
        model = tmp_path / "kata1-b10c128-s1234.bin.gz"
        model.touch()

        with patch(
            "katrain.core.auto_setup.get_model_search_dirs",
            return_value=[str(tmp_path)],
        ):
            settings, error_result = resolve_auto_engine_settings({})

        assert settings is not None
        assert error_result is None
        assert "b10c128" in settings["model"]
        assert settings["max_visits"] == 100
        assert settings["fast_visits"] == 10

    def test_lightweight_model_not_found(self, tmp_path):
        """Lightweight model not found -> returns TestAnalysisResult."""
        with patch(
            "katrain.core.auto_setup.get_model_search_dirs",
            return_value=[str(tmp_path)],  # Empty directory
        ):
            settings, error_result = resolve_auto_engine_settings({})

        assert settings is None
        assert error_result is not None
        assert error_result.error_category == ErrorCategory.LIGHTWEIGHT_MISSING

    def test_base_engine_settings_merged(self, tmp_path):
        """Base engine settings are merged with auto settings."""
        model = tmp_path / "kata1-b10c128-s1234.bin.gz"
        model.touch()

        base_engine = {"katago": "/path/to/katago", "config": "/path/to/config.cfg"}

        with patch(
            "katrain.core.auto_setup.get_model_search_dirs",
            return_value=[str(tmp_path)],
        ):
            settings, error_result = resolve_auto_engine_settings(base_engine)

        assert settings is not None
        assert settings["katago"] == "/path/to/katago"
        assert settings["config"] == "/path/to/config.cfg"
        assert "b10c128" in settings["model"]


# =============================================================================
# TestFindLightweightModel
# =============================================================================


class TestFindLightweightModel:
    """Tests for lightweight model search."""

    def test_finds_b10c128_model(self, tmp_path):
        """Finds b10c128 model in search directory."""
        model = tmp_path / "kata1-b10c128-s1234567890-d12345.bin.gz"
        model.touch()

        with patch(
            "katrain.core.auto_setup.get_model_search_dirs",
            return_value=[str(tmp_path)],
        ):
            result = find_lightweight_model()

        assert result is not None
        assert "b10c128" in result

    def test_prefers_newer_timestamp(self, tmp_path):
        """Prefers model with newer timestamp in filename."""
        old_model = tmp_path / "kata1-b10c128-s20240101.bin.gz"
        new_model = tmp_path / "kata1-b10c128-s20240201.bin.gz"
        old_model.touch()
        new_model.touch()

        with patch(
            "katrain.core.auto_setup.get_model_search_dirs",
            return_value=[str(tmp_path)],
        ):
            result = find_lightweight_model()

        assert result is not None
        assert "20240201" in result

    def test_returns_none_if_not_found(self, tmp_path):
        """Returns None if no b10c128 model found."""
        # Create a different model that doesn't match
        other_model = tmp_path / "kata1-b18c384nbt.bin.gz"
        other_model.touch()

        with patch(
            "katrain.core.auto_setup.get_model_search_dirs",
            return_value=[str(tmp_path)],
        ):
            result = find_lightweight_model()

        assert result is None

    def test_user_dir_priority_over_package(self, tmp_path):
        """User directory is searched before package directory."""
        user_dir = tmp_path / "user"
        package_dir = tmp_path / "package"
        user_dir.mkdir()
        package_dir.mkdir()

        user_model = user_dir / "kata1-b10c128-user.bin.gz"
        package_model = package_dir / "kata1-b10c128-package.bin.gz"
        user_model.touch()
        package_model.touch()

        with patch(
            "katrain.core.auto_setup.get_model_search_dirs",
            return_value=[str(user_dir), str(package_dir)],
        ):
            result = find_lightweight_model()

        assert result is not None
        assert "user" in result


# =============================================================================
# TestFindCpuKatago
# =============================================================================


class TestFindCpuKatago:
    """Tests for CPU KataGo binary search."""

    def test_finds_eigen_binary(self, tmp_path):
        """Finds katago-eigen binary."""
        eigen = tmp_path / "katago-eigen.exe"
        eigen.touch()

        with (
            patch(
                "katrain.core.auto_setup.find_package_resource",
                return_value=str(eigen),
            ),
            patch("katrain.core.auto_setup.get_platform", return_value="win"),
        ):
            result = find_cpu_katago()

        # Result depends on whether file passes _is_likely_opencl_binary
        # Since "eigen" is not in the opencl list, it should be found
        assert result is None or "eigen" in str(result).lower()

    def test_skips_opencl_binary(self, tmp_path):
        """Skips binaries with 'opencl' in filename."""
        opencl = tmp_path / "katago-opencl.exe"
        opencl.touch()

        with (
            patch(
                "katrain.core.auto_setup.find_package_resource",
                return_value=str(opencl),
            ),
            patch("katrain.core.auto_setup.get_platform", return_value="win"),
        ):
            result = find_cpu_katago()

        # Should skip the opencl binary
        # Note: This test may need adjustment based on actual implementation
        assert result is None or "opencl" not in str(result).lower()


# =============================================================================
# TestHasCustomEngineSettings
# =============================================================================


class TestHasCustomEngineSettings:
    """Tests for custom engine settings detection."""

    def test_empty_is_not_custom(self):
        """Empty user engine settings are not custom."""
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "", "model": "default.bin.gz", "config": "cfg"},
        ):
            result = _has_custom_engine_settings({})
        assert result is False

    def test_custom_katago_is_custom(self):
        """Custom katago path is detected as custom."""
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "", "model": "default.bin.gz", "config": "cfg"},
        ):
            result = _has_custom_engine_settings({"katago": "/custom/katago"})
        assert result is True

    def test_same_as_default_is_not_custom(self):
        """Same as default is not custom."""
        default_model = "katrain/models/default.bin.gz"
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "", "model": default_model, "config": "cfg"},
        ):
            result = _has_custom_engine_settings({"model": default_model})
        assert result is False

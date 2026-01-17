"""Tests for katrain.core.diagnostics module.

Phase 29: Diagnostics + Bug Report Bundle.
"""

import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from katrain.common.sanitize import SanitizationContext
from katrain.core.diagnostics import (
    AppInfo,
    DiagnosticsBundle,
    DiagnosticsResult,
    KataGoInfo,
    SystemInfo,
    collect_app_info,
    collect_katago_info,
    collect_settings_snapshot,
    collect_system_info,
    create_diagnostics_zip,
    generate_diagnostics_filename,
)


# --- Test Fixtures (deterministic, CI-stable) ---

TEST_USERNAME = "TestUser"
TEST_HOSTNAME = "TEST-PC"
TEST_HOME_WIN = "C:\\Users\\TestUser"
TEST_APP_DIR = "D:\\apps\\katrain"

# Forbidden tokens for privacy verification
FORBIDDEN_TOKENS = [
    TEST_USERNAME,
    TEST_USERNAME.lower(),
    TEST_HOSTNAME,
    TEST_HOSTNAME.lower(),
    TEST_HOME_WIN,
    TEST_HOME_WIN.lower(),
    TEST_HOME_WIN.replace("\\", "/"),
    TEST_APP_DIR,
    TEST_APP_DIR.lower(),
]


@pytest.fixture
def ctx() -> SanitizationContext:
    """Windows-style sanitization context for testing."""
    return SanitizationContext(
        username=TEST_USERNAME,
        hostname=TEST_HOSTNAME,
        home_dir=TEST_HOME_WIN,
        app_dir=TEST_APP_DIR,
    )


@pytest.fixture
def sample_bundle() -> DiagnosticsBundle:
    """Sample diagnostics bundle with test data containing sensitive info."""
    return DiagnosticsBundle(
        system_info=SystemInfo(
            os_name="Windows",
            os_version="10.0.19045",
            os_release="10",
            python_version="3.10.11",
            python_bits="64-bit",
            machine="AMD64",
            processor="Intel64 Family 6 Model 158",
        ),
        katago_info=KataGoInfo(
            exe_path=f"{TEST_APP_DIR}\\katago.exe",
            model_path=f"{TEST_APP_DIR}\\models\\kata1.gz",
            config_path=f"{TEST_APP_DIR}\\katago.cfg",
            is_running=True,
            version="1.14.0",
        ),
        app_info=AppInfo(
            version="1.17.1",
            config_path=f"{TEST_HOME_WIN}\\.katrain\\config.json",
            data_folder=f"{TEST_HOME_WIN}\\.katrain",
        ),
        settings={
            "general": {"skill_preset": "standard"},
            "mykatrain_settings": {
                "default_user_name": TEST_USERNAME,
                "karte_output_directory": f"{TEST_HOME_WIN}\\Documents\\karte",
            },
        },
        logs=[
            f"[2026-01-17T12:00:00] [INFO] User {TEST_USERNAME} logged in",
            f"[2026-01-17T12:00:01] [INFO] Loading {TEST_HOME_WIN}\\game.sgf",
            f"[2026-01-17T12:00:02] [ERROR] Failed on {TEST_HOSTNAME}",
        ],
    )


def assert_no_forbidden_tokens(content: str, filename: str) -> None:
    """Verify no forbidden tokens appear in content (case-insensitive)."""
    content_lower = content.lower()
    for token in FORBIDDEN_TOKENS:
        token_lower = token.lower()
        if token_lower in content_lower:
            raise AssertionError(
                f"Found forbidden token '{token}' (case-insensitive) in {filename}"
            )


class TestCollectSystemInfo:
    """Tests for collect_system_info function."""

    def test_returns_system_info(self) -> None:
        """Returns valid SystemInfo dataclass."""
        info = collect_system_info()
        assert isinstance(info, SystemInfo)
        assert info.os_name  # Should have a value
        assert info.python_version  # Should have a value

    def test_python_bits_valid(self) -> None:
        """Python bits is either 32-bit or 64-bit."""
        info = collect_system_info()
        assert info.python_bits in ("32-bit", "64-bit")

    def test_os_name_not_empty(self) -> None:
        """OS name is populated."""
        info = collect_system_info()
        assert len(info.os_name) > 0


class TestCollectKataGoInfo:
    """Tests for collect_katago_info function."""

    def test_returns_katago_info(self) -> None:
        """Returns valid KataGoInfo dataclass."""
        info = collect_katago_info(
            exe_path="/path/to/katago",
            model_path="/path/to/model.gz",
            config_path="/path/to/config.cfg",
            is_running=True,
            version="1.14.0",
        )
        assert isinstance(info, KataGoInfo)
        assert info.is_running is True

    def test_version_optional(self) -> None:
        """Version can be None."""
        info = collect_katago_info(
            exe_path="",
            model_path="",
            config_path="",
            is_running=False,
            version=None,
        )
        assert info.version is None

    def test_not_running_state(self) -> None:
        """Can represent engine not running."""
        info = collect_katago_info(
            exe_path="",
            model_path="",
            config_path="",
            is_running=False,
        )
        assert info.is_running is False


class TestCollectAppInfo:
    """Tests for collect_app_info function."""

    def test_returns_app_info(self) -> None:
        """Returns valid AppInfo dataclass."""
        info = collect_app_info(
            version="1.17.1",
            config_path="/path/to/config.json",
            data_folder="/path/to/data",
        )
        assert isinstance(info, AppInfo)
        assert info.version == "1.17.1"


class TestCollectSettingsSnapshot:
    """Tests for collect_settings_snapshot function."""

    def test_excludes_engine_section(self) -> None:
        """Engine section is excluded from snapshot."""
        config = {
            "general": {"debug_level": 0},
            "engine": {"katago": "/path/to/katago", "model": "/path/to/model"},
            "mykatrain_settings": {"skill_preset": "standard"},
        }
        snapshot = collect_settings_snapshot(config)

        assert "general" in snapshot
        assert "mykatrain_settings" in snapshot
        assert "engine" not in snapshot

    def test_excludes_export_settings(self) -> None:
        """Export settings section is excluded."""
        config = {
            "general": {"debug_level": 0},
            "export_settings": {"format": "pdf"},
        }
        snapshot = collect_settings_snapshot(config)
        assert "export_settings" not in snapshot

    def test_preserves_safe_sections(self) -> None:
        """Non-excluded sections are preserved."""
        config = {
            "general": {"skill_preset": "standard", "debug_level": 1},
            "board": {"size": 19},
        }
        snapshot = collect_settings_snapshot(config)
        assert snapshot["general"] == config["general"]
        assert snapshot["board"] == config["board"]


class TestGenerateDiagnosticsFilename:
    """Tests for generate_diagnostics_filename function."""

    def test_filename_format(self) -> None:
        """Filename matches expected format."""
        filename = generate_diagnostics_filename()
        assert filename.startswith("diagnostics_")
        assert filename.endswith(".zip")

    def test_contains_timestamp(self) -> None:
        """Filename contains date-time components."""
        filename = generate_diagnostics_filename()
        # Format: diagnostics_YYYYMMDD-HHMMSS_XXXX.zip
        parts = filename.replace(".zip", "").split("_")
        assert len(parts) == 3
        assert len(parts[1]) == 15  # YYYYMMDD-HHMMSS
        assert len(parts[2]) == 4  # random suffix


class TestZipStructure:
    """Tests for ZIP structure and contents."""

    def test_contains_required_files(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """ZIP contains all required files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            result = create_diagnostics_zip(sample_bundle, output_path, ctx)

            assert result.success
            with zipfile.ZipFile(output_path, "r") as zf:
                names = zf.namelist()
                assert "manifest.json" in names
                assert "system_info.json" in names
                assert "katago_info.json" in names
                assert "app_info.json" in names
                assert "settings.json" in names
                assert "logs.txt" in names

    def test_manifest_schema_version(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """Manifest has correct schema version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                manifest = json.loads(zf.read("manifest.json"))
                assert manifest["schema_version"] == "1.0"

    def test_manifest_files_list(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """Manifest contains file list with types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                manifest = json.loads(zf.read("manifest.json"))
                files = {f["name"]: f["type"] for f in manifest["files"]}

                assert files["system_info.json"] == "system"
                assert files["katago_info.json"] == "katago"
                assert files["app_info.json"] == "app"
                assert files["settings.json"] == "settings"
                assert files["logs.txt"] == "logs"

    def test_manifest_privacy_flags(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """Manifest includes privacy information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                manifest = json.loads(zf.read("manifest.json"))
                assert manifest["privacy"]["sanitized"] is True
                assert "paths" in manifest["privacy"]["rules_applied"]

    def test_manifest_timestamp_deterministic(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """Manifest timestamp is deterministic with now_fn injection."""
        fixed_time = datetime(2026, 1, 17, 14, 30, 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(
                sample_bundle, output_path, ctx, now_fn=lambda: fixed_time
            )

            with zipfile.ZipFile(output_path, "r") as zf:
                manifest = json.loads(zf.read("manifest.json"))
                assert manifest["generated_at"] == "2026-01-17T14:30:00"

    def test_all_files_utf8(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """All files can be decoded as UTF-8."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                for name in zf.namelist():
                    content = zf.read(name)
                    # Should not raise
                    content.decode("utf-8")


class TestNoForbiddenTokens:
    """Verify no sensitive information leaks in ZIP contents."""

    def test_system_info_no_forbidden(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """system_info.json contains no forbidden tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("system_info.json").decode("utf-8")
                assert_no_forbidden_tokens(content, "system_info.json")

    def test_katago_info_no_forbidden(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """katago_info.json contains no forbidden tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("katago_info.json").decode("utf-8")
                assert_no_forbidden_tokens(content, "katago_info.json")

    def test_app_info_no_forbidden(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """app_info.json contains no forbidden tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("app_info.json").decode("utf-8")
                assert_no_forbidden_tokens(content, "app_info.json")

    def test_settings_no_forbidden(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """settings.json contains no forbidden tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("settings.json").decode("utf-8")
                assert_no_forbidden_tokens(content, "settings.json")

    def test_logs_no_forbidden(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """logs.txt contains no forbidden tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("logs.txt").decode("utf-8")
                assert_no_forbidden_tokens(content, "logs.txt")


class TestDiagnosticsResult:
    """Tests for DiagnosticsResult handling."""

    def test_success_result(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """Successful generation returns success result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            result = create_diagnostics_zip(sample_bundle, output_path, ctx)

            assert result.success is True
            assert result.output_path == output_path
            assert result.error_message is None

    def test_error_result_invalid_path(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """Invalid path returns error result."""
        # Try to write to a non-existent directory
        output_path = Path("/nonexistent/directory/test.zip")
        result = create_diagnostics_zip(sample_bundle, output_path, ctx)

        assert result.success is False
        assert result.error_message is not None


class TestSanitizedContent:
    """Verify content is properly sanitized with placeholders."""

    def test_katago_paths_use_placeholders(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """KataGo paths are replaced with <APP_DIR> placeholder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("katago_info.json").decode("utf-8")
                data = json.loads(content)
                assert "<APP_DIR>" in data["exe_path"]
                assert "<APP_DIR>" in data["model_path"]

    def test_app_paths_use_placeholders(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """App paths are replaced with placeholder tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("app_info.json").decode("utf-8")
                data = json.loads(content)
                # Username is replaced with <USER> in paths
                assert "<USER>" in data["config_path"]
                assert "<USER>" in data["data_folder"]
                # Original username should not appear
                assert TEST_USERNAME not in data["config_path"]

    def test_logs_use_placeholders(
        self, sample_bundle: DiagnosticsBundle, ctx: SanitizationContext
    ) -> None:
        """Log messages use placeholder tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            create_diagnostics_zip(sample_bundle, output_path, ctx)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("logs.txt").decode("utf-8")
                # Username and hostname are replaced
                assert "<USER>" in content
                assert "<HOST>" in content
                # Original values should not appear
                assert TEST_USERNAME not in content
                assert TEST_HOSTNAME not in content

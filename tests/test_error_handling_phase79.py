"""Phase 79 error handling tests - Core Batch + Package Export.

Focused on 3 high-value paths:
1. analyze_single_file with invalid SGF (A1)
2. _is_writable_directory edge case (B9)
3. create_llm_package with ZIP error (B11)
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


class TestAnalyzeSingleFileSGFError:
    """A1: Invalid SGF should fail gracefully with log output."""

    def test_invalid_sgf_returns_false_and_logs_error(self, tmp_path):
        """Invalid SGF content should return False and log an error."""
        from katrain.core.batch.analysis import analyze_single_file

        # Create invalid SGF file
        bad_sgf = tmp_path / "invalid.sgf"
        bad_sgf.write_text("not valid sgf content", encoding="utf-8")

        # Capture logs
        logs: list = []

        # Create minimal mocks
        mock_katrain = MagicMock()
        mock_engine = MagicMock()
        mock_engine.is_idle.return_value = True

        result = analyze_single_file(
            katrain=mock_katrain,
            engine=mock_engine,
            sgf_path=str(bad_sgf),
            output_path=None,
            visits=10,
            timeout=5.0,
            cancel_flag=None,
            log_cb=logs.append,
            save_sgf=False,
            return_game=False,
        )

        # Assertions: graceful failure + logged
        assert result is False, "Invalid SGF should return False"
        assert any("error" in log.lower() for log in logs), (
            f"Should log error message, got: {logs}"
        )


class TestIsWritableDirectory:
    """B9: Path validation edge cases should return False, not raise."""

    def test_none_path_returns_false(self):
        """None path should return False immediately."""
        from katrain.core.reports.package_export import _is_writable_directory

        result = _is_writable_directory(None)
        assert result is False

    def test_invalid_path_type_returns_false(self):
        """Invalid path (causes exception in Path()) should return False."""
        from katrain.core.reports.package_export import _is_writable_directory

        # Path with wrong type - both should be caught
        result = _is_writable_directory(12345)  # int, not path-like
        assert result is False, "Invalid path type should return False"

    def test_nonexistent_directory_returns_false(self, tmp_path):
        """Non-existent directory should return False (is_dir() returns False)."""
        from katrain.core.reports.package_export import _is_writable_directory

        nonexistent = tmp_path / "does_not_exist"
        result = _is_writable_directory(nonexistent)
        assert result is False


class TestCreateLlmPackageZipError:
    """B11: ZIP creation failure should return structured error result."""

    def test_zip_write_error_returns_failure_result(self, tmp_path, monkeypatch):
        """OSError during ZIP write should return PackageResult(success=False)."""
        from katrain.core.reports.package_export import (
            create_llm_package,
            PackageContent,
        )
        import zipfile

        # Create test content
        content = PackageContent(
            karte_md="# Test Karte",
            sgf_content="(;GM[1])",
            coach_md="# Coach",
            game_info={"black": "Test", "white": "Test"},
            skill_preset="standard",
            anonymized=False,
        )

        # Patch ZipFile in the target module to raise OSError
        class MockZipFile:
            def __init__(self, *args, **kwargs):
                raise OSError("Cannot write to path")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        # Patch at the usage site
        import katrain.core.reports.package_export as pkg_mod
        monkeypatch.setattr(pkg_mod.zipfile, "ZipFile", MockZipFile)

        # Use a valid path for the test
        output_path = tmp_path / "test_package.zip"

        result = create_llm_package(content=content, output_path=output_path)

        # Assertions
        assert result.success is False, "ZIP error should return success=False"
        assert result.error_message is not None, "Should have error message"
        assert "I/O" in result.error_message or "error" in result.error_message.lower(), (
            f"Error message should mention I/O error, got: {result.error_message}"
        )

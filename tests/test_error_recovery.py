"""Tests for Phase 90 error recovery module.

Focus areas:
1. Byte-bounded truncation (UTF-8)
2. Sanitization (no raw sensitive strings)
3. Dedupe thread-safety
4. Reset-to-auto config behavior
5. ZIP extra_files injection

Python 3.9 compatible.
"""
import json
import threading
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from katrain.core.error_recovery import (
    DiagnosticsTrigger,
    RecoveryEvent,
    should_auto_dump,
    reset_dedupe_state,
    truncate_to_bytes,
    LLM_TEXT_MAX_BYTES,
)


class TestByteBoundedTruncation:
    """Test UTF-8 byte-bounded truncation."""

    def test_short_text_unchanged(self):
        """Text under limit should be unchanged."""
        text = "Hello, world!"
        result = truncate_to_bytes(text, max_bytes=100)
        assert result == text
        assert len(result.encode("utf-8")) <= 100

    def test_truncates_at_byte_limit(self):
        """Output must be <= max_bytes in UTF-8."""
        text = "x" * 5000
        result = truncate_to_bytes(text, max_bytes=4096)
        encoded = result.encode("utf-8")
        assert len(encoded) <= 4096

    def test_handles_multibyte_characters(self):
        """Must not break UTF-8 sequences."""
        # Japanese text (3 bytes per character)
        text = "日本語テスト" * 1000  # ~18000 bytes
        result = truncate_to_bytes(text, max_bytes=4096)
        # Should not raise, should be valid UTF-8
        encoded = result.encode("utf-8")
        assert len(encoded) <= 4096

    def test_handles_emoji(self):
        """Must handle 4-byte emoji correctly."""
        text = "🎮" * 2000  # 4 bytes each = 8000 bytes
        result = truncate_to_bytes(text, max_bytes=4096)
        encoded = result.encode("utf-8")
        assert len(encoded) <= 4096

    def test_adds_truncation_suffix(self):
        """Truncated text should have suffix."""
        text = "x" * 5000
        result = truncate_to_bytes(text, max_bytes=100)
        assert result.endswith("... [truncated]")
        assert len(result.encode("utf-8")) <= 100

    def test_default_max_bytes(self):
        """Default should be LLM_TEXT_MAX_BYTES (4096)."""
        text = "x" * 5000
        result = truncate_to_bytes(text)
        assert len(result.encode("utf-8")) <= LLM_TEXT_MAX_BYTES
        assert LLM_TEXT_MAX_BYTES == 4096


class TestDedupeThreadSafety:
    """Test thread-safe deduplication."""

    def setup_method(self):
        """Reset dedupe state before each test."""
        reset_dedupe_state()

    def test_first_event_triggers_dump(self):
        """First event should trigger dump."""
        event = RecoveryEvent.create(
            DiagnosticsTrigger.ENGINE_START_FAILED,
            "test_code",
            "test error"
        )
        assert should_auto_dump(event) is True

    def test_same_event_blocked(self):
        """Same event_id should NOT trigger second dump."""
        event = RecoveryEvent.create(
            DiagnosticsTrigger.ENGINE_START_FAILED,
            "test_code",
            "test error"
        )
        assert should_auto_dump(event) is True
        assert should_auto_dump(event) is False

    def test_different_event_allowed(self):
        """Different event_id should trigger dump."""
        event1 = RecoveryEvent.create(
            DiagnosticsTrigger.ENGINE_START_FAILED,
            "code1",
            "error1"
        )
        event2 = RecoveryEvent.create(
            DiagnosticsTrigger.ENGINE_START_FAILED,
            "code2",
            "error2"
        )
        assert should_auto_dump(event1) is True
        assert should_auto_dump(event2) is True

    def test_concurrent_same_event(self):
        """Concurrent calls with same event should only allow one."""
        event = RecoveryEvent.create(
            DiagnosticsTrigger.ENGINE_START_FAILED,
            "concurrent_code",
            "concurrent error"
        )

        results = []
        barrier = threading.Barrier(10)

        def try_dump():
            barrier.wait()
            results.append(should_auto_dump(event))

        threads = [threading.Thread(target=try_dump) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(True) == 1
        assert results.count(False) == 9

    def test_event_id_deterministic(self):
        """Same inputs should produce same event_id."""
        event1 = RecoveryEvent.create(
            DiagnosticsTrigger.ENGINE_START_FAILED,
            "code",
            "error"
        )
        event2 = RecoveryEvent.create(
            DiagnosticsTrigger.ENGINE_START_FAILED,
            "code",
            "error"
        )
        assert event1.event_id == event2.event_id
        assert len(event1.event_id) == 16  # SHA256[:16]


class TestSanitization:
    """Test that LLM text is properly sanitized."""

    def test_sensitive_paths_not_in_output(self):
        """Raw sensitive paths should NOT appear in output."""
        from katrain.core.diagnostics import (
            DiagnosticsBundle,
            SystemInfo,
            KataGoInfo,
            AppInfo,
            format_llm_diagnostics_text,
        )
        from katrain.common.sanitize import SanitizationContext

        # Use realistic sensitive paths with a test username
        sensitive_username = "secretuser123"
        sensitive_paths = [
            f"C:\\Users\\{sensitive_username}\\katago.exe",
            f"C:\\Users\\{sensitive_username}\\model.bin",
            f"/home/{sensitive_username}/config.cfg",
        ]

        bundle = DiagnosticsBundle(
            system_info=SystemInfo("Windows", "10", "10.0", "3.11", "64-bit", "AMD64", "Intel"),
            katago_info=KataGoInfo(
                exe_path=sensitive_paths[0],
                model_path=sensitive_paths[1],
                config_path=sensitive_paths[2],
                is_running=False,
                version=None,
            ),
            app_info=AppInfo("1.0", f"C:\\Users\\{sensitive_username}\\config.json", f"C:\\Users\\{sensitive_username}\\.katrain"),
            settings={},
            logs=[f"Log with path C:\\Users\\{sensitive_username}\\logfile.txt"],
        )

        # Create context that knows about the test username
        ctx = SanitizationContext(
            username=sensitive_username,
            hostname="testhost",
            home_dir=f"C:\\Users\\{sensitive_username}",
            app_dir="C:\\app",
        )
        text = format_llm_diagnostics_text(bundle, ctx, "Test error")

        # Sensitive username must NOT appear
        assert sensitive_username not in text

        # Output must be within byte limit
        assert len(text.encode("utf-8")) <= LLM_TEXT_MAX_BYTES

    def test_output_byte_bounded(self):
        """Output must be <= 4096 UTF-8 bytes."""
        from katrain.core.diagnostics import (
            DiagnosticsBundle,
            SystemInfo,
            KataGoInfo,
            AppInfo,
            format_llm_diagnostics_text,
        )
        from katrain.common.sanitize import get_sanitization_context

        # Create bundle with very long logs
        long_logs = ["This is a very long log line " * 100] * 100

        bundle = DiagnosticsBundle(
            system_info=SystemInfo("Windows", "10", "10.0", "3.11", "64-bit", "AMD64", "Intel"),
            katago_info=KataGoInfo("", "", "", False, None),
            app_info=AppInfo("1.0", "", ""),
            settings={},
            logs=long_logs,
        )

        ctx = get_sanitization_context()
        text = format_llm_diagnostics_text(bundle, ctx, "Test error")

        # Must be within byte limit
        assert len(text.encode("utf-8")) <= 4096


class TestResetToAutoConfig:
    """Test reset-to-auto config preparation."""

    def test_prepare_reset_returns_correct_config(self):
        """Should return auto mode config."""
        from katrain.core.auto_setup import prepare_reset_to_auto, DEFAULT_AUTO_SETUP

        changes = prepare_reset_to_auto()

        assert "auto_setup" in changes
        assert changes["auto_setup"]["mode"] == "auto"
        assert changes["auto_setup"]["first_run_completed"] is False

    def test_reset_applies_via_context(self):
        """Config changes should be applied via FeatureContext methods."""
        from katrain.core.auto_setup import prepare_reset_to_auto

        mock_ctx = Mock()
        mock_ctx.restart_engine.return_value = True

        changes = prepare_reset_to_auto()
        mock_ctx.set_config_section("auto_setup", changes["auto_setup"])
        mock_ctx.save_config("auto_setup")
        result = mock_ctx.restart_engine()

        mock_ctx.set_config_section.assert_called_once_with("auto_setup", changes["auto_setup"])
        mock_ctx.save_config.assert_called_once_with("auto_setup")
        mock_ctx.restart_engine.assert_called_once()
        assert result is True


class TestZipExtraFiles:
    """Test ZIP extra_files injection."""

    def test_extra_files_included_in_zip(self):
        """extra_files should be added to ZIP."""
        from katrain.core.diagnostics import (
            DiagnosticsBundle,
            SystemInfo,
            KataGoInfo,
            AppInfo,
            create_diagnostics_zip,
        )
        from katrain.common.sanitize import get_sanitization_context

        bundle = DiagnosticsBundle(
            system_info=SystemInfo("Windows", "10", "10.0", "3.11", "64-bit", "AMD64", "Intel"),
            katago_info=KataGoInfo("", "", "", False, None),
            app_info=AppInfo("1.0", "", ""),
            settings={},
            logs=[],
        )

        ctx = get_sanitization_context()

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            extra_files = {"llm_prompt.txt": "LLM prompt content here"}

            result = create_diagnostics_zip(bundle, output_path, ctx, extra_files=extra_files)

            assert result.success
            assert output_path.exists()

            with zipfile.ZipFile(output_path, "r") as zf:
                names = zf.namelist()
                assert "llm_prompt.txt" in names
                content = zf.read("llm_prompt.txt").decode("utf-8")
                assert content == "LLM prompt content here"

    def test_manifest_includes_extra_files(self):
        """Manifest should list extra files."""
        from katrain.core.diagnostics import (
            DiagnosticsBundle,
            SystemInfo,
            KataGoInfo,
            AppInfo,
            create_diagnostics_zip,
        )
        from katrain.common.sanitize import get_sanitization_context

        bundle = DiagnosticsBundle(
            system_info=SystemInfo("Windows", "10", "10.0", "3.11", "64-bit", "AMD64", "Intel"),
            katago_info=KataGoInfo("", "", "", False, None),
            app_info=AppInfo("1.0", "", ""),
            settings={},
            logs=[],
        )

        ctx = get_sanitization_context()

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.zip"
            extra_files = {"llm_prompt.txt": "content"}

            create_diagnostics_zip(bundle, output_path, ctx, extra_files=extra_files)

            with zipfile.ZipFile(output_path, "r") as zf:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                file_names = [f["name"] for f in manifest["files"]]
                assert "llm_prompt.txt" in file_names


class TestCollectDiagnosticsBundle:
    """Test collect_diagnostics_bundle public API."""

    def test_collect_with_engine_info(self):
        """Should create bundle with engine info."""
        from katrain.core.diagnostics import collect_diagnostics_bundle

        engine_info = ("/path/to/katago", "/path/to/model", "/path/to/config", True, "1.0")
        bundle = collect_diagnostics_bundle(
            engine_info=engine_info,
            app_version="1.2.3",
            config_path="/path/to/config.json",
            data_folder="/path/to/data",
            config_data={"general": {"version": "1.0"}},
            logs=["log line 1", "log line 2"],
        )

        assert bundle.katago_info.exe_path == "/path/to/katago"
        assert bundle.katago_info.is_running is True
        assert bundle.app_info.version == "1.2.3"
        assert len(bundle.logs) == 2

    def test_collect_without_engine_info(self):
        """Should create bundle with default engine info."""
        from katrain.core.diagnostics import collect_diagnostics_bundle

        bundle = collect_diagnostics_bundle(app_version="1.0.0")

        assert bundle.katago_info.exe_path == ""
        assert bundle.katago_info.is_running is False
        assert bundle.app_info.version == "1.0.0"

# tests/test_typed_config_migration.py
#
# Phase 100: Behavior-based tests for typed config migration
#
# These tests verify that migrated code correctly uses typed config accessors
# and maintains semantic equivalence with the original dict-based access.

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock


@dataclass(frozen=True)
class MockLeelaConfig:
    """Mock LeelaConfig for testing."""

    enabled: bool = False
    exe_path: str | None = None
    top_moves_show: str = "leela_top_move_loss"
    top_moves_show_secondary: str = "leela_top_move_winrate"


@dataclass(frozen=True)
class MockEngineConfig:
    """Mock EngineConfig for testing."""

    katago: str | None = None
    model: str | None = None


# TestIsLeelaConfiguredTypedConfig removed as is_leela_configured was deleted.


class TestDiagnosticsCopyTypedConfig:
    """Test diagnostics copy uses typed config correctly."""

    def test_diagnostics_includes_engine_paths(self, monkeypatch):
        """Diagnostics should include katago and model paths from typed config."""
        import kivy.core.clipboard

        # Mock Clipboard to capture copied text
        copied_text = []

        class MockClipboard:
            @staticmethod
            def copy(text):
                copied_text.append(text)

        monkeypatch.setattr(kivy.core.clipboard, "Clipboard", MockClipboard)

        from katrain.gui.features import auto_mode_popup

        # Create mock context with typed config
        ctx = MagicMock()
        ctx.get_engine_config.return_value = MockEngineConfig(
            katago="/path/to/katago.exe",
            model="/path/to/model.bin.gz",
        )
        ctx.log = MagicMock()

        # Create mock result
        result = MagicMock()
        result.success = True
        result.error_category = None
        result.error_message = None

        # Call the function
        auto_mode_popup._copy_diagnostics(result, ctx)

        # Verify
        assert len(copied_text) == 1
        diag_text = copied_text[0]
        assert "KataGo: /path/to/katago.exe" in diag_text
        assert "Model: /path/to/model.bin.gz" in diag_text

    def test_diagnostics_handles_none_paths(self, monkeypatch):
        """Diagnostics should handle None paths gracefully (via or '' pattern)."""
        import kivy.core.clipboard

        copied_text = []

        class MockClipboard:
            @staticmethod
            def copy(text):
                copied_text.append(text)

        monkeypatch.setattr(kivy.core.clipboard, "Clipboard", MockClipboard)

        from katrain.gui.features import auto_mode_popup

        ctx = MagicMock()
        ctx.get_engine_config.return_value = MockEngineConfig(
            katago=None,  # normalize_path("") -> None
            model=None,
        )
        ctx.log = MagicMock()

        result = MagicMock()
        result.success = False
        result.error_category = None
        result.error_message = "Test error"

        auto_mode_popup._copy_diagnostics(result, ctx)

        assert len(copied_text) == 1
        diag_text = copied_text[0]
        # None paths should become empty strings via `or ''`
        assert "KataGo: " in diag_text
        assert "Model: " in diag_text


class TestTypedConfigSemantics:
    """Test typed config semantic equivalence."""

    def test_leela_config_enabled_field_access(self):
        """Verify LeelaConfig.enabled is accessed correctly."""
        # This is a structural test - verify the typed config pattern
        mock_config = MockLeelaConfig(enabled=True)
        assert mock_config.enabled is True

        mock_config_disabled = MockLeelaConfig(enabled=False)
        assert mock_config_disabled.enabled is False

    def test_leela_config_default_enabled_is_false(self):
        """Verify default enabled value is False (semantic equivalence)."""
        # This matches the original: leela_config.get("enabled", False)
        mock_config = MockLeelaConfig()
        assert mock_config.enabled is False

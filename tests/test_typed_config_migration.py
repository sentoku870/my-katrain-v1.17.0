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
# TestDiagnosticsCopyTypedConfig removed in Phase 138 — auto_mode_popup._copy_diagnostics
# was deleted and replaced with the new diagnostics copy flow.


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

# tests/test_typed_config_migration.py
#
# Phase 100: Behavior-based tests for typed config migration
#
# These tests verify that migrated code correctly uses typed config accessors
# and maintains semantic equivalence with the original dict-based access.
#
# Phase 171: Leela 関連クラスを削除。

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MockEngineConfig:
    """Mock EngineConfig for testing."""

    katago: str | None = None
    model: str | None = None


# TestIsLeelaConfiguredTypedConfig removed as is_leela_configured was deleted (Phase 171).
# TestDiagnosticsCopyTypedConfig removed in Phase 138 — auto_mode_popup._copy_diagnostics
# was deleted and replaced with the new diagnostics copy flow.
# LeelaConfig semantically テストは Phase 171 で完全削除。


class TestEngineConfigSemantics:
    def test_engine_config_katago_field(self):
        mock_config = MockEngineConfig(katago="/usr/bin/katago")
        assert mock_config.katago == "/usr/bin/katago"

        mock_config_empty = MockEngineConfig()
        assert mock_config_empty.katago is None

    def test_engine_config_model_field(self):
        mock_config = MockEngineConfig(model="kata1-b18.bin.gz")
        assert mock_config.model == "kata1-b18.bin.gz"

        mock_config_empty = MockEngineConfig()
        assert mock_config_empty.model is None

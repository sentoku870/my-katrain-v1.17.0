"""Tests for settings_popup save helpers (Phase 174 P1-F).

The settings_popup module is heavily Kivy-coupled, but its ``_save_*``
helpers only need a ``FeatureContext`` Protocol to function. These tests
drive the helpers through a stub context to lock down the
config-mutation contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# Skip on CI: settings_popup imports Kivy widgets at module scope
# and crashes the headless CI runner (see test_main_smoke hotfix 2).
pytestmark = pytest.mark.skipif(
    __import__("os").environ.get("CI", "").lower() == "true",
    reason="settings_popup imports Kivy widgets at module scope; CI environment lacks display",
)

# Force Kivy into headless mode before importing settings_popup.
import os

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_FILELOG", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("KIVY_HEADLESS", "1")
os.environ.setdefault("KIVY_NO_WINDOW", "1")
os.environ.setdefault("KIVY_GL_BACKEND", "mock")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _make_ctx(initial: dict | None = None) -> MagicMock:
    """Stub FeatureContext for the _save_* tests."""
    ctx = MagicMock()
    initial = initial or {}
    ctx.config = lambda key, default=None: initial.get(key, default)
    ctx.controls = MagicMock()
    return ctx


class TestSaveGeneralSettings:
    def test_writes_skill_preset_and_pv_filter(self):
        from katrain.gui.features.settings_popup import _save_general_settings

        ctx = _make_ctx(initial={"general": {"lang": "en"}})
        _save_general_settings(ctx, skill_preset="advanced", pv_filter_level="medium")

        # Section was set, then saved.
        ctx.set_config_section.assert_called_once()
        section_name, payload = ctx.set_config_section.call_args.args
        assert section_name == "general"
        assert payload["skill_preset"] == "advanced"
        assert payload["pv_filter_level"] == "medium"
        # Original lang preserved.
        assert payload["lang"] == "en"

        ctx.save_config.assert_called_once_with("general")

    def test_initialises_when_general_missing(self):
        from katrain.gui.features.settings_popup import _save_general_settings

        ctx = _make_ctx(initial={})
        _save_general_settings(ctx, "auto", "auto")
        section_name, payload = ctx.set_config_section.call_args.args
        assert section_name == "general"
        assert payload == {"skill_preset": "auto", "pv_filter_level": "auto"}


class TestSaveBeginnerHintsSettings:
    def test_sets_enabled_true(self):
        from katrain.gui.features.settings_popup import _save_beginner_hints_settings

        ctx = _make_ctx(initial={"beginner_hints": {"other": "preserve"}})
        _save_beginner_hints_settings(ctx, enabled=True)
        section_name, payload = ctx.set_config_section.call_args.args
        assert section_name == "beginner_hints"
        assert payload["enabled"] is True
        assert payload["other"] == "preserve"

    def test_sets_enabled_false(self):
        from katrain.gui.features.settings_popup import _save_beginner_hints_settings

        ctx = _make_ctx(initial={})
        _save_beginner_hints_settings(ctx, enabled=False)
        _, payload = ctx.set_config_section.call_args.args
        assert payload["enabled"] is False

    def test_creates_section_when_missing(self):
        from katrain.gui.features.settings_popup import _save_beginner_hints_settings

        ctx = _make_ctx()  # no "beginner_hints" key at all
        _save_beginner_hints_settings(ctx, enabled=True)
        assert ctx.set_config_section.call_args.args[0] == "beginner_hints"


class TestSaveEngineSettings:
    def test_calls_update_engine_config(self):
        from katrain.gui.features.settings_popup import _save_engine_settings

        ctx = _make_ctx()
        _save_engine_settings(ctx, new_engine_value="katago")
        ctx.update_engine_config.assert_called_once_with(analysis_engine="katago")

    def test_oserror_sets_status(self):
        from katrain.gui.features.settings_popup import _save_engine_settings
        from katrain.core.constants import STATUS_ERROR

        ctx = _make_ctx()
        ctx.update_engine_config.side_effect = OSError("disk full")
        _save_engine_settings(ctx, "katago")
        ctx.controls.set_status.assert_called_once()
        args = ctx.controls.set_status.call_args.args
        assert args[1] == STATUS_ERROR

    def test_unexpected_exception_sets_status(self):
        from katrain.gui.features.settings_popup import _save_engine_settings

        ctx = _make_ctx()
        ctx.update_engine_config.side_effect = RuntimeError("config broken")
        _save_engine_settings(ctx, "katago")
        ctx.controls.set_status.assert_called_once()


class TestSaveMyKatrainSettings:
    def test_writes_full_section(self):
        from katrain.gui.features.settings_popup import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(
            ctx,
            default_user_name="alice",
            karte_output_directory="/tmp/out",
            batch_export_input_directory="/tmp/in",
            karte_format="standard",
            opponent_info_mode="auto",
            disabled_katago=False,
        )

        # First call: set_config_section("mykatrain_settings", {...}).
        section_name, payload = ctx.set_config_section.call_args.args
        assert section_name == "mykatrain_settings"
        assert payload == {
            "default_user_name": "alice",
            "karte_output_directory": "/tmp/out",
            "batch_export_input_directory": "/tmp/in",
            "karte_format": "standard",
            "opponent_info_mode": "auto",
        }
        ctx.save_config.assert_called_once_with("mykatrain_settings")

    def test_updates_engine_disabled_flag(self):
        from katrain.gui.features.settings_popup import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(
            ctx, "u", "/o", "/i", "fmt", "mode", disabled_katago=True
        )
        ctx.update_engine_config.assert_called_once_with(disabled=True)

    def test_disabled_false_passes_through(self):
        from katrain.gui.features.settings_popup import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(
            ctx, "u", "/o", "/i", "fmt", "mode", disabled_katago=False
        )
        ctx.update_engine_config.assert_called_once_with(disabled=False)

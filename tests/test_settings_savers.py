"""Tests for settings_popup_savers helpers (Phase 174 P1-F / Phase 175).

Phase 175: The ``_save_*`` helpers were extracted into
``settings_popup_savers.py``, which has NO dependency on Kivy widgets.
These tests therefore run on CI without any display/headless workarounds.
"""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_ctx(initial: dict | None = None) -> MagicMock:
    """Stub FeatureContext for the _save_* tests."""
    ctx = MagicMock()
    initial = initial or {}
    ctx.config = lambda key, default=None: initial.get(key, default)
    ctx.controls = MagicMock()
    return ctx


class TestSaveGeneralSettings:
    def test_writes_skill_preset_and_pv_filter(self):
        from katrain.gui.features.settings_popup_savers import _save_general_settings

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
        # Phase 229: player_rank defaults to "" when omitted.
        assert payload["player_rank"] == ""

        ctx.save_config.assert_called_once_with("general")

    def test_initialises_when_general_missing(self):
        from katrain.gui.features.settings_popup_savers import _save_general_settings

        ctx = _make_ctx(initial={})
        _save_general_settings(ctx, "auto", "auto")
        section_name, payload = ctx.set_config_section.call_args.args
        assert section_name == "general"
        assert payload == {"skill_preset": "auto", "pv_filter_level": "auto", "player_rank": ""}

    def test_persists_player_rank_when_provided(self):
        """Phase 229: player_rank is the primary input from the analysis tab."""
        from katrain.gui.features.settings_popup_savers import _save_general_settings

        ctx = _make_ctx(initial={})
        _save_general_settings(ctx, skill_preset="advanced", pv_filter_level="auto", player_rank="5d")
        _, payload = ctx.set_config_section.call_args.args
        assert payload["player_rank"] == "5d"
        assert payload["skill_preset"] == "advanced"  # resolved preset still saved

    def test_player_rank_whitespace_stripped(self):
        """Phase 229: leading/trailing whitespace in the rank input is ignored."""
        from katrain.gui.features.settings_popup_savers import _save_general_settings

        ctx = _make_ctx(initial={})
        _save_general_settings(ctx, "standard", "auto", player_rank="  4段  ")
        _, payload = ctx.set_config_section.call_args.args
        assert payload["player_rank"] == "4段"


class TestSaveBeginnerHintsSettings:
    def test_sets_enabled_true(self):
        from katrain.gui.features.settings_popup_savers import _save_beginner_hints_settings

        ctx = _make_ctx(initial={"beginner_hints": {"other": "preserve"}})
        _save_beginner_hints_settings(ctx, enabled=True)
        section_name, payload = ctx.set_config_section.call_args.args
        assert section_name == "beginner_hints"
        assert payload["enabled"] is True
        assert payload["other"] == "preserve"

    def test_sets_enabled_false(self):
        from katrain.gui.features.settings_popup_savers import _save_beginner_hints_settings

        ctx = _make_ctx(initial={})
        _save_beginner_hints_settings(ctx, enabled=False)
        _, payload = ctx.set_config_section.call_args.args
        assert payload["enabled"] is False

    def test_creates_section_when_missing(self):
        from katrain.gui.features.settings_popup_savers import _save_beginner_hints_settings

        ctx = _make_ctx()  # no "beginner_hints" key at all
        _save_beginner_hints_settings(ctx, enabled=True)
        assert ctx.set_config_section.call_args.args[0] == "beginner_hints"


class TestSaveEngineSettings:
    def test_calls_update_engine_config(self):
        from katrain.gui.features.settings_popup_savers import _save_engine_settings

        ctx = _make_ctx()
        _save_engine_settings(ctx, new_engine_value="katago")
        ctx.update_engine_config.assert_called_once_with(analysis_engine="katago")

    def test_oserror_sets_status(self):
        from katrain.core.constants import STATUS_ERROR
        from katrain.gui.features.settings_popup_savers import _save_engine_settings

        ctx = _make_ctx()
        ctx.update_engine_config.side_effect = OSError("disk full")
        _save_engine_settings(ctx, "katago")
        ctx.controls.set_status.assert_called_once()
        args = ctx.controls.set_status.call_args.args
        assert args[1] == STATUS_ERROR

    def test_unexpected_exception_sets_status(self):
        from katrain.gui.features.settings_popup_savers import _save_engine_settings

        ctx = _make_ctx()
        ctx.update_engine_config.side_effect = RuntimeError("config broken")
        _save_engine_settings(ctx, "katago")
        ctx.controls.set_status.assert_called_once()


class TestSaveMyKatrainSettings:
    def test_writes_full_section(self):
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

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
            "default_user_rank": "",
            "karte_output_directory": "/tmp/out",
            "batch_export_input_directory": "/tmp/in",
            "karte_format": "standard",
            "opponent_info_mode": "auto",
        }

    def test_writes_rank_when_provided(self):
        """Phase 225.8: default_user_rank is persisted when set."""
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(
            ctx,
            default_user_name="alice",
            karte_output_directory="/tmp/out",
            batch_export_input_directory="/tmp/in",
            karte_format="standard",
            opponent_info_mode="auto",
            disabled_katago=False,
            default_user_rank="4段",
        )
        _, payload = ctx.set_config_section.call_args.args
        assert payload["default_user_rank"] == "4段"
        ctx.save_config.assert_called_once_with("mykatrain_settings")

    def test_updates_engine_disabled_flag(self):
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(ctx, "u", "/o", "/i", "fmt", "mode", disabled_katago=True)
        ctx.update_engine_config.assert_called_once_with(disabled=True)

    def test_disabled_false_passes_through(self):
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(ctx, "u", "/o", "/i", "fmt", "mode", disabled_katago=False)
        ctx.update_engine_config.assert_called_once_with(disabled=False)

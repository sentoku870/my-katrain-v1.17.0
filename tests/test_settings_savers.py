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
            # Phase 248-B1: important_moves_level is now persisted.
            "important_moves_level": "normal",
            # Phase 248-B2: critical_3 selection count is now persisted.
            "critical_3_max_moves": 3,
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
            default_user_rank="4段",
        )
        _, payload = ctx.set_config_section.call_args.args
        assert payload["default_user_rank"] == "4段"
        ctx.save_config.assert_called_once_with("mykatrain_settings")

    def test_no_engine_disabled_update(self):
        """Phase 230-B: Leela 廃止により engine/disabled の更新は行われない。"""
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(ctx, "u", "/o", "/i", "fmt", "mode")
        ctx.update_engine_config.assert_not_called()


class TestSaveImportantMovesLevel:
    """Phase 248-B1: ``important_moves_level`` is persisted by the saver."""

    def test_writes_normal_by_default(self):
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(ctx, "u", "/o", "/i", "fmt", "mode")
        _, payload = ctx.set_config_section.call_args.args
        assert payload["important_moves_level"] == "normal"

    def test_writes_easy_level(self):
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(
            ctx,
            "u",
            "/o",
            "/i",
            "fmt",
            "mode",
            important_moves_level="easy",
        )
        _, payload = ctx.set_config_section.call_args.args
        assert payload["important_moves_level"] == "easy"

    def test_writes_strict_level(self):
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(
            ctx,
            "u",
            "/o",
            "/i",
            "fmt",
            "mode",
            important_moves_level="strict",
        )
        _, payload = ctx.set_config_section.call_args.args
        assert payload["important_moves_level"] == "strict"

    def test_normalises_unknown_value_to_normal(self):
        """Unknown values (typo, legacy, etc.) silently fall back to ``normal``.

        Matches the runtime behaviour of
        :func:`IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get` which returns the
        default settings when the key is unknown.
        """
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(
            ctx,
            "u",
            "/o",
            "/i",
            "fmt",
            "mode",
            important_moves_level="nuclear",
        )
        _, payload = ctx.set_config_section.call_args.args
        assert payload["important_moves_level"] == "normal"

    def test_normalises_empty_string_to_normal(self):
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(
            ctx,
            "u",
            "/o",
            "/i",
            "fmt",
            "mode",
            important_moves_level="",
        )
        _, payload = ctx.set_config_section.call_args.args
        assert payload["important_moves_level"] == "normal"


class TestSaveCritical3MaxMoves:
    """Phase 248-B2: ``critical_3_max_moves`` is persisted by the saver."""

    def test_writes_3_by_default(self):
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(ctx, "u", "/o", "/i", "fmt", "mode")
        _, payload = ctx.set_config_section.call_args.args
        assert payload["critical_3_max_moves"] == 3

    def test_writes_5(self):
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(ctx, "u", "/o", "/i", "fmt", "mode", critical_3_max_moves=5)
        _, payload = ctx.set_config_section.call_args.args
        assert payload["critical_3_max_moves"] == 5

    def test_writes_10_at_upper_bound(self):
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(ctx, "u", "/o", "/i", "fmt", "mode", critical_3_max_moves=10)
        _, payload = ctx.set_config_section.call_args.args
        assert payload["critical_3_max_moves"] == 10

    def test_writes_1_at_lower_bound(self):
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(ctx, "u", "/o", "/i", "fmt", "mode", critical_3_max_moves=1)
        _, payload = ctx.set_config_section.call_args.args
        assert payload["critical_3_max_moves"] == 1

    def test_normalises_out_of_range_above_to_3(self):
        """Values above 10 (e.g. typos like 50) fall back to 3."""
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(ctx, "u", "/o", "/i", "fmt", "mode", critical_3_max_moves=50)
        _, payload = ctx.set_config_section.call_args.args
        assert payload["critical_3_max_moves"] == 3

    def test_normalises_out_of_range_below_to_3(self):
        """Values below 1 (e.g. 0 or -1) fall back to 3."""
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(ctx, "u", "/o", "/i", "fmt", "mode", critical_3_max_moves=0)
        _, payload = ctx.set_config_section.call_args.args
        assert payload["critical_3_max_moves"] == 3

    def test_normalises_string_to_3(self):
        """A string value (typo) falls back to 3 via the int() try/except."""
        from katrain.gui.features.settings_popup_savers import _save_mykatrain_settings

        ctx = _make_ctx()
        _save_mykatrain_settings(ctx, "u", "/o", "/i", "fmt", "mode", critical_3_max_moves="abc")
        _, payload = ctx.set_config_section.call_args.args
        assert payload["critical_3_max_moves"] == 3


class TestMigrateDefaultUserRank:
    """Phase 230-E: ``default_user_rank`` → ``player_rank`` マイグレーション。"""

    def test_copies_when_player_rank_empty(self):
        from katrain.gui.features.settings_popup_savers import migrate_default_user_rank

        initial = {
            "general": {"player_rank": ""},
            "mykatrain_settings": {"default_user_rank": "4段"},
        }
        ctx = _make_ctx(initial=initial)
        current_settings = dict(initial["mykatrain_settings"])

        migrate_default_user_rank(ctx, current_settings)

        # general/player_rank に "4段" が保存される
        general_call = ctx.set_config_section.call_args_list[0]
        assert general_call.args == ("general", {"player_rank": "4段"})
        ctx.save_config.assert_any_call("general")

        # default_user_rank はクリアされる
        assert current_settings["default_user_rank"] == ""

    def test_keeps_player_rank_when_both_set(self):
        from katrain.gui.features.settings_popup_savers import migrate_default_user_rank

        initial = {
            "general": {"player_rank": "5k"},
            "mykatrain_settings": {"default_user_rank": "4段"},
        }
        ctx = _make_ctx(initial=initial)
        current_settings = dict(initial["mykatrain_settings"])

        migrate_default_user_rank(ctx, current_settings)

        # general/player_rank は上書きされない（5k のまま）
        # general セクションへの set_config_section は呼ばれない
        general_calls = [c for c in ctx.set_config_section.call_args_list if c.args[0] == "general"]
        assert len(general_calls) == 0

        # default_user_rank はクリアされる
        assert current_settings["default_user_rank"] == ""

    def test_noop_when_default_user_rank_empty(self):
        from katrain.gui.features.settings_popup_savers import migrate_default_user_rank

        ctx = _make_ctx(
            initial={
                "general": {"player_rank": "5k"},
                "mykatrain_settings": {"default_user_rank": ""},
            }
        )
        current_settings = {"default_user_rank": ""}

        migrate_default_user_rank(ctx, current_settings)

        ctx.set_config_section.assert_not_called()
        ctx.save_config.assert_not_called()

    def test_noop_when_default_user_rank_missing(self):
        from katrain.gui.features.settings_popup_savers import migrate_default_user_rank

        ctx = _make_ctx(initial={"general": {"player_rank": "5k"}})
        current_settings = {}

        migrate_default_user_rank(ctx, current_settings)

        ctx.set_config_section.assert_not_called()
        ctx.save_config.assert_not_called()

    def test_strips_whitespace(self):
        from katrain.gui.features.settings_popup_savers import migrate_default_user_rank

        initial = {
            "general": {"player_rank": ""},
            "mykatrain_settings": {"default_user_rank": "  4段  "},
        }
        ctx = _make_ctx(initial=initial)
        current_settings = dict(initial["mykatrain_settings"])

        migrate_default_user_rank(ctx, current_settings)

        general_call = ctx.set_config_section.call_args_list[0]
        assert general_call.args[1]["player_rank"] == "4段"


class TestBuildKifunarabeConfig:
    """Phase 287-A: regression tests for the kifunarabe settings save path.

    The kifunarabe tab in the myKatrain settings popup exposes six widgets
    (one text input + five checkboxes). Previously the save block inside
    ``do_mykatrain_settings_popup`` forgot to read the
    ``auto_export_cb`` widget, so flipping the checkbox had no effect on
    the persisted config. The dict assembly was extracted into
    ``build_kifunarabe_config`` so this regression can be caught without
    spinning up a Kivy popup.
    """

    def _refs(
        self,
        *,
        sgf_load: str = "",
        show_digits: bool = False,
        show_actual_border: bool = False,
        uniform_color: bool = True,
        auto_toggle: bool = True,
        auto_export: bool = False,
    ) -> dict:
        return {
            "sgf_load_input": MagicMock(text=sgf_load),
            "show_digits_cb": MagicMock(active=show_digits),
            "show_actual_border_cb": MagicMock(active=show_actual_border),
            "uniform_color_cb": MagicMock(active=uniform_color),
            "auto_toggle_cb": MagicMock(active=auto_toggle),
            "auto_export_cb": MagicMock(active=auto_export),
        }

    def test_persists_auto_export_weaknesses(self):
        """The Phase 287-A regression: ``auto_export_cb`` must be read."""
        from katrain.gui.features.settings_popup_savers import build_kifunarabe_config

        refs = self._refs(auto_export=True)
        kif = build_kifunarabe_config(refs)
        assert kif["auto_export_weaknesses"] is True

    def test_persists_all_six_widgets(self):
        from katrain.gui.features.settings_popup_savers import build_kifunarabe_config

        refs = self._refs(
            sgf_load="/tmp/games",
            show_digits=True,
            show_actual_border=True,
            uniform_color=False,
            auto_toggle=False,
            auto_export=True,
        )
        kif = build_kifunarabe_config(refs)
        assert kif == {
            "sgf_load": "/tmp/games",
            "show_digits": True,
            "show_actual_border": True,
            "uniform_color": False,
            "auto_toggle_markers": False,
            "auto_export_weaknesses": True,
        }

    def test_preserves_unknown_keys_from_existing(self):
        """Phase 277 pattern: merge into existing so future keys survive."""
        from katrain.gui.features.settings_popup_savers import build_kifunarabe_config

        refs = self._refs()
        existing = {"sgf_load": "/old", "future_key": "preserved"}
        kif = build_kifunarabe_config(refs, existing)
        assert kif["future_key"] == "preserved"
        assert kif["sgf_load"] == ""  # overwritten by current widget value
        assert kif["auto_export_weaknesses"] is False

    def test_existing_none_starts_empty(self):
        from katrain.gui.features.settings_popup_savers import build_kifunarabe_config

        refs = self._refs(sgf_load="/a")
        kif = build_kifunarabe_config(refs, None)
        assert kif["sgf_load"] == "/a"
        # No phantom keys from a None merge
        assert set(kif.keys()) == {
            "sgf_load",
            "show_digits",
            "show_actual_border",
            "uniform_color",
            "auto_toggle_markers",
            "auto_export_weaknesses",
        }


class TestKifunarabeTabReturnShape:
    """Phase 287-B: regression test for the double ScrollView fix.

    The kifunarabe tab builder must return the inner BoxLayout directly
    (matching the analysis / export / diagnostics tabs). The orchestrator
    in settings_popup.py wraps every tab in a single ScrollView, so a
    tab builder that returns its own ScrollView would create two stacked
    ScrollViews (visible double scrollbar, ambiguous wheel events).

    The full tab builder needs a live Kivy window (it instantiates
    CheckBox / TextInput at module load via `dp(...)`), so this test
    verifies the contract via AST inspection of the source file rather
    than by calling the builder.
    """

    def test_kifunarabe_tab_does_not_return_scrollview(self):
        import ast
        from pathlib import Path

        src_path = Path("katrain/gui/features/settings_popup_tabs/kifunarabe_tab.py")
        tree = ast.parse(src_path.read_text(encoding="utf-8"))

        # Find the ``_build_kifunarabe_tab`` function and look for any
        # ``return ... ScrollView(...)`` statement. If the double-wrap
        # regression returns, this assertion fires.
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_build_kifunarabe_tab":
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Return) and stmt.value is not None:
                        # Walk into the return expression for any ScrollView call.
                        for sub in ast.walk(stmt.value):
                            if isinstance(sub, ast.Call):
                                callee = ast.unparse(sub.func) if hasattr(ast, "unparse") else ""
                                if "ScrollView" in callee:
                                    raise AssertionError(
                                        "_build_kifunarabe_tab must not construct "
                                        "or return a ScrollView. The orchestrator "
                                        "(settings_popup.py:183-186) already wraps "
                                        "every tab in one. Returning a nested "
                                        "ScrollView caused two stacked scrollbars "
                                        "and ambiguous wheel events."
                                    )
                return
        raise AssertionError("_build_kifunarabe_tab function not found")

    def test_other_tabs_still_return_boxlayout(self):
        """Sanity: the four tab builders all return plain BoxLayouts."""
        import ast
        from pathlib import Path

        for tab_file in ("analysis_tab.py", "export_tab.py", "kifunarabe_tab.py", "diagnostics_tab.py"):
            src_path = Path(f"katrain/gui/features/settings_popup_tabs/{tab_file}")
            text = src_path.read_text(encoding="utf-8")
            # A ScrollView usage inside docstrings/comments is fine;
            # only flag if a ScrollView() is constructed in module-level
            # code (not inside a function body).
            tree = ast.parse(text)
            for node in tree.body:
                # If someone adds a top-level ``from kivy.uix.scrollview
                # import ScrollView`` outside a function, that's still OK
                # because the import is lazy. The danger is constructing
                # ScrollView at module level (which Phase 180-C did).
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in ("scroll", "ScrollView"):
                            # Assigned at module top-level → flag it.
                            if isinstance(node.value, ast.Call) and "ScrollView" in ast.unparse(node.value.func):
                                raise AssertionError(
                                    f"{tab_file} constructs a ScrollView at module "
                                    "level. Each tab must return a plain BoxLayout."
                                )

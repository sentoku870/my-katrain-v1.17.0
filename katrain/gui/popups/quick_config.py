"""Quick config popups (timer, new game, teacher, AI, engine recovery).

Phase 140 P2-1: Extracted from katrain/gui/popups.py.

QuickConfigGui is a base class for simple configuration popups that read
input widgets and save changes back to the katrain config.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout

from katrain.core.ai import ai_rank_estimation
from katrain.core.constants import (
    AI_CONFIG_DEFAULT,
    AI_DEFAULT,
    AI_KEY_PROPERTIES,
    AI_OPTION_VALUES,
    AI_STRATEGIES_RECOMMENDED_ORDER,
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    OUTPUT_INFO,
    SGF_INTERNAL_COMMENTS_MARKER,
)
from katrain.core.lang import i18n, rank_label
from katrain.gui.kivyutils import BackgroundMixin
from katrain.gui.popups._base import (
    DescriptionLabel,
    InputParseError,
    LabelledCheckBox,
    LabelledFloatInput,
    LabelledSelectionSlider,
    LabelledSpinner,
    LabelledTextInput,
    wrap_anchor,
)
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Label


class QuickConfigGui(MDBoxLayout):
    def __init__(self, katrain: Any) -> None:
        super().__init__()
        self.katrain = katrain
        self.popup = None
        Clock.schedule_once(self.build_and_set_properties, 0)

    def collect_properties(self, widget: Any) -> dict[str, Any]:
        if isinstance(
            widget, (LabelledTextInput, LabelledSpinner, LabelledCheckBox, LabelledSelectionSlider)
        ) and getattr(widget, "input_property", None):
            try:
                ret = {widget.input_property: widget.input_value}
            except Exception as e:
                # Re-raise as InputParseError with full context and traceback
                raise InputParseError(
                    f"Could not parse value '{widget.raw_input_value}' for {widget.input_property} ({widget.__class__.__name__}): {e}"
                ) from e
        else:
            ret = {}
        for c in widget.children:
            for k, v in self.collect_properties(c).items():
                ret[k] = v
        return ret

    def get_setting(self, key: str) -> tuple[Any, dict[str, Any], str] | tuple[Any, list[Any], int]:
        keys = key.split("/")
        config = self.katrain._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        if "::" in keys[-1]:
            array_key, ix = keys[-1].split("::")
            ix_int = int(ix)
            array = config[array_key]
            return array[ix_int], array, ix_int
        else:
            if keys[-1] not in config:
                config[keys[-1]] = ""
                self.katrain.log(
                    f"Configuration setting {repr(key)} was missing, created it, but this likely indicates a broken config file.",
                    OUTPUT_ERROR,
                )
            return config[keys[-1]], config, keys[-1]

    def build_and_set_properties(self, *_args: Any) -> None:
        return self._set_properties_subtree(self)

    def _set_properties_subtree(self, widget: Any) -> None:
        if isinstance(
            widget, (LabelledTextInput, LabelledSpinner, LabelledCheckBox, LabelledSelectionSlider)
        ) and getattr(widget, "input_property", None):
            value = self.get_setting(widget.input_property)[0]
            if isinstance(widget, LabelledCheckBox):
                widget.active = value is True
            elif isinstance(widget, LabelledSelectionSlider):
                widget.set_value(value)
            elif isinstance(widget, LabelledSpinner):
                selected = 0  # Safe default before try block
                try:
                    selected = widget.value_refs.index(value)
                except ValueError:
                    # Control-flow: config value not in spinner options.
                    # Fall back to first option (index 0) - this can happen when
                    # options changed between versions or config was manually edited.
                    logging.debug(
                        f"Spinner value '{value}' not found in {widget.input_property}, using default index 0"
                    )
                    # selected remains 0 (set above)
                widget.text = widget.values[selected]
            else:
                widget.text = str(value)
        for c in widget.children:
            self._set_properties_subtree(c)

    def update_config(self, save_to_file: bool = True, close_popup: bool = True) -> set[str]:
        updated: set[str] = set()
        for multikey, value in self.collect_properties(self).items():
            old_value, conf, key = self.get_setting(multikey)
            if value != old_value:
                self.katrain.log(f"Updating setting {multikey} = {value}", OUTPUT_DEBUG)
                conf[key] = value  # type: ignore[index]  # reference straight back to katrain._config - may be array or dict
                updated.add(multikey)
        if save_to_file:
            self.katrain.save_config()
        if self.popup and close_popup:
            self.popup.dismiss()
        return updated


class ConfigTimerPopup(QuickConfigGui):
    def update_config(self, save_to_file: bool = True, close_popup: bool = True) -> set[str]:
        super().update_config(save_to_file=save_to_file, close_popup=close_popup)
        for p in self.katrain.players_info.values():
            p.periods_used = 0
        self.katrain.controls.timer.paused = True
        self.katrain.game.current_node.time_used = 0
        self.katrain.game.main_time_used = 0
        self.katrain.update_state()
        return set()


class NewGamePopup(QuickConfigGui):
    mode = StringProperty("newgame")

    def __init__(self, katrain: Any) -> None:
        super().__init__(katrain)
        for bw, info in katrain.players_info.items():
            self.player_setup.update_player_info(bw, info)

        self.rules_spinner.value_refs = [name for abbr, name in katrain.engine.RULESETS_ABBR]
        self.bind(mode=self.update_playername)
        Clock.schedule_once(self.update_from_current_game, 0.1)

    def normalized_rules(self) -> str | None:
        rules = self.katrain.game.root.get_property("RU", "japanese").strip().lower()
        for abbr, name in self.katrain.engine.RULESETS_ABBR:
            if abbr == rules or name == rules:
                return str(name)
        return None

    def update_playerinfo(self, *args: Any) -> None:
        for bw, player_setup in self.player_setup.players.items():
            name = self.player_name[bw].text
            if name:
                self.katrain.game.root.set_property("P" + bw, name)
            else:
                self.katrain.game.root.clear_property("P" + bw)
            self.katrain.update_player(bw, **player_setup.player_type_dump)

    def update_playername(self, *args: Any) -> None:
        for bw in "BW":
            name = self.katrain.game.root.get_property("P" + bw, None)
            if name and SGF_INTERNAL_COMMENTS_MARKER not in name:
                self.player_name[bw].text = name if self.mode == "editgame" else ""

    def update_from_current_game(self, *args: Any) -> None:  # set rules and komi
        rules = self.normalized_rules()
        self.km.text = str(self.katrain.game.root.komi)
        if rules is not None:
            self.rules_spinner.select_key(rules.strip())

    def update_config(self, save_to_file: bool = True, close_popup: bool = True) -> set[str]:
        super().update_config(save_to_file=save_to_file, close_popup=close_popup)
        props = self.collect_properties(self)
        self.katrain.log(f"Mode: {self.mode}, settings: {self.katrain.config('game')}", OUTPUT_DEBUG)
        self.update_playerinfo()  # type
        if self.mode == "newgame":
            if self.restart.active:
                self.katrain.log("Restarting Engine", OUTPUT_DEBUG)
                self.katrain.engine.restart()
            self.katrain._do_new_game()
        elif self.mode == "editgame":
            root = self.katrain.game.root
            changed = False
            for k, currentval, newval in [
                ("RU", self.normalized_rules(), props["game/rules"]),
                ("KM", root.komi, props["game/komi"]),
            ]:
                if currentval != newval:
                    changed = True
                    self.katrain.log(
                        f"Property {k} changed from {currentval} to {newval}, triggering re-analysis of entire game.",
                        OUTPUT_INFO,
                    )
                    self.katrain.game.root.set_property(k, newval)
            if changed:
                self.katrain.engine.on_new_game()
                self.katrain.game.analyze_all_nodes(analyze_fast=True)
        else:  # setup position
            self.katrain._do_new_game()
            self.katrain("selfplay-setup", props["game/setup_move"], props["game/setup_advantage"])
        self.update_playerinfo()  # name
        return set()


class ConfigTeacherPopup(QuickConfigGui):
    def __init__(self, katrain: Any) -> None:
        super().__init__(katrain)
        MDApp.get_running_app().bind(language=self.build_and_set_properties)

    def add_option_widgets(self, widgets: list[Any]) -> None:
        for widget in widgets:
            self.options_grid.add_widget(wrap_anchor(widget))

    def build_and_set_properties(self, *_args: Any) -> None:
        theme = self.katrain.config("trainer/theme")
        undos = self.katrain.config("trainer/num_undo_prompts")
        thresholds = self.katrain.config("trainer/eval_thresholds")
        savesgfs = self.katrain.config("trainer/save_feedback")
        show_dots = self.katrain.config("trainer/show_dots")

        self.themes_spinner.value_refs = list(Theme.EVAL_COLORS.keys())
        self.options_grid.clear_widgets()

        for k in ["dot color", "point loss threshold", "num undos", "show dots", "save dots"]:
            self.options_grid.add_widget(DescriptionLabel(text=i18n._(k), font_name=i18n.font_name, font_size=dp(17)))

        for i, color, threshold, undo, show_dot, savesgf in list(
            zip(range(len(thresholds)), Theme.EVAL_COLORS[theme], thresholds, undos, show_dots, savesgfs, strict=False)
        )[::-1]:
            self.add_option_widgets(
                [
                    BackgroundMixin(background_color=color, size_hint=[0.9, 0.9]),
                    LabelledFloatInput(text=str(threshold), input_property=f"trainer/eval_thresholds::{i}"),
                    LabelledFloatInput(text=str(undo), input_property=f"trainer/num_undo_prompts::{i}"),
                    LabelledCheckBox(text=str(show_dot), input_property=f"trainer/show_dots::{i}"),
                    LabelledCheckBox(text=str(savesgf), input_property=f"trainer/save_feedback::{i}"),
                ]
            )
        super().build_and_set_properties()

    def update_config(self, save_to_file: bool = True, close_popup: bool = True) -> set[str]:
        super().update_config(save_to_file=save_to_file, close_popup=close_popup)
        self.build_and_set_properties()
        return set()


class ConfigAIPopup(QuickConfigGui):
    max_options = NumericProperty(6)

    def __init__(self, katrain: Any) -> None:
        super().__init__(katrain)
        self.ai_select.value_refs = AI_STRATEGIES_RECOMMENDED_ORDER
        selected_strategies = {p.strategy for p in katrain.players_info.values()}
        config_strategy = list((selected_strategies - {AI_DEFAULT}) or {AI_CONFIG_DEFAULT})[0]
        self.ai_select.select_key(config_strategy)
        self.build_ai_options()
        self.ai_select.bind(text=self.build_ai_options)

    def estimate_rank_from_options(self, *_args: Any) -> None:
        strategy = self.ai_select.selected[1]
        try:
            options = self.collect_properties(self)  # [strategy]
        except InputParseError:
            self.estimated_rank_label.text = "??"
            return
        prefix = f"ai/{strategy}/"
        options = {k[len(prefix) :]: v for k, v in options.items() if k.startswith(prefix)}
        dan_rank = ai_rank_estimation(strategy, options)
        self.estimated_rank_label.text = rank_label(dan_rank)

    def build_ai_options(self, *_args: Any) -> None:
        strategy = self.ai_select.selected[1]
        mode_settings = self.katrain.config(f"ai/{strategy}")
        self.options_grid.clear_widgets()
        self.help_label.text = i18n._(strategy.replace("ai:", "aihelp:"))
        for k, v in sorted(mode_settings.items(), key=lambda kv: (kv[0] not in AI_KEY_PROPERTIES, kv[0])):
            self.options_grid.add_widget(DescriptionLabel(text=k, size_hint_x=0.275))
            if k in AI_OPTION_VALUES:
                values = AI_OPTION_VALUES[k]
                if values == "bool":
                    widget = LabelledCheckBox(input_property=f"ai/{strategy}/{k}")
                    widget.active = v
                    widget.bind(active=self.estimate_rank_from_options)
                else:
                    if isinstance(values[0], tuple):  # type: ignore[index]  # with descriptions, possibly language-specific
                        fixed_values = [(v, re.sub(r"\[(.*?)]", lambda m: i18n._(str(m[1])), label)) for v, label in values]  # type: ignore[attr-defined]
                    else:  # just numbers
                        fixed_values = [(v, str(v)) for v in values]  # type: ignore[attr-defined]
                    widget = LabelledSelectionSlider(
                        values=fixed_values, input_property=f"ai/{strategy}/{k}", key_option=(k in AI_KEY_PROPERTIES)
                    )
                    widget.set_value(v)
                    widget.textbox.bind(text=self.estimate_rank_from_options)
                self.options_grid.add_widget(wrap_anchor(widget))
            else:
                self.options_grid.add_widget(
                    wrap_anchor(LabelledFloatInput(text=str(v), input_property=f"ai/{strategy}/{k}"))
                )
        for _ in range((self.max_options - len(mode_settings)) * 2):
            self.options_grid.add_widget(Label(size_hint_x=None))
        Clock.schedule_once(self.estimate_rank_from_options)

    def update_config(self, save_to_file: bool = True, close_popup: bool = True) -> set[str]:
        super().update_config(save_to_file=save_to_file, close_popup=close_popup)
        self.katrain.update_calculated_ranks()
        Clock.schedule_once(self.katrain.controls.update_players, 0)
        return set()


class EngineRecoveryPopup(QuickConfigGui):
    error_message = StringProperty("")
    code = ObjectProperty(None)

    def __init__(self, katrain: Any, error_message: str, code: Any) -> None:
        super().__init__(katrain)
        self.error_message = str(error_message)
        self.code = code
        # Trigger auto-dump via single gate (should_auto_dump)
        self._trigger_auto_dump()

    def _trigger_auto_dump(self) -> None:
        """Trigger auto-dump using recovery_actions (single gate)."""
        from katrain.core.error_recovery import DiagnosticsTrigger
        from katrain.gui.features.recovery_actions import trigger_auto_dump

        trigger_auto_dump(
            self.katrain,
            DiagnosticsTrigger.ENGINE_START_FAILED,
            str(self.code) if self.code else "unknown",
            self.error_message,
        )

    def on_reset_to_auto(self) -> None:
        from katrain.core.constants import OUTPUT_INFO
        from katrain.core.lang import i18n
        from katrain.gui.features.recovery_actions import reset_to_auto_mode

        if reset_to_auto_mode(self.katrain):
            self.katrain.log(i18n._("mykatrain:recovery:reset_success"), OUTPUT_INFO)
        if self.popup:
            self.popup.dismiss()

    def on_copy_for_llm(self) -> None:
        from katrain.core.constants import OUTPUT_INFO
        from katrain.core.lang import i18n
        from katrain.gui.features.recovery_actions import copy_for_llm

        if copy_for_llm(self.katrain, self.error_message):
            self.katrain.log(i18n._("mykatrain:recovery:copied"), OUTPUT_INFO)

    def on_save_diagnostics(self) -> None:
        from katrain.common.file_opener import open_file_in_folder
        from katrain.core.constants import OUTPUT_INFO
        from katrain.core.lang import i18n
        from katrain.gui.features.recovery_actions import save_diagnostics_zip

        result = save_diagnostics_zip(self.katrain, self.error_message)
        if result:
            self.katrain.log(i18n._("mykatrain:recovery:saved").format(path=result), OUTPUT_INFO)
            open_file_in_folder(result)

    def on_copy_log(self) -> None:
        from katrain.core.constants import OUTPUT_INFO
        from katrain.core.lang import i18n
        from katrain.gui.features.recovery_actions import copy_log_tail

        if copy_log_tail(self.katrain):
            self.katrain.log(i18n._("mykatrain:recovery:log_copied"), OUTPUT_INFO)

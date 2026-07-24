"""Kivy controls for the BadukPan widget.

Phase D (P3) extracted these classes from ``badukpan.py`` so the
``BadukPanWidget`` itself stays focused on board display. Each
class is bound from the ``badukpan.kv`` rules via its Kivy class
name, so the imports here must remain discoverable from
``katrain.gui.badukpan``.

Backward compatibility:

Every class previously defined in ``katrain.gui.badukpan`` is re-
exported from this module via ``katrain.gui.badukpan``. KV rules
and tests that import ``from katrain.gui.badukpan import
AnalysisDropDown`` etc. continue to work.
"""

from __future__ import annotations

from typing import Any

from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty
from kivy.uix.dropdown import DropDown
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.floatlayout import MDFloatLayout

from katrain.core.constants.output import OUTPUT_DEBUG
from katrain.gui.popups import GameReportPopup, I18NPopup, ReAnalyzeGamePopup, TsumegoFramePopup
from katrain.gui.theme import Theme


class AnalysisDropDown(DropDown):
    def open_game_analysis_popup(self, *_args: Any) -> None:
        analysis_popup = I18NPopup(
            title_key="analysis:game", size=[dp(500), dp(350)], content=ReAnalyzeGamePopup(MDApp.get_running_app().gui)
        )
        analysis_popup.content.popup = analysis_popup
        analysis_popup.open()

    def open_report_popup(self, *_args: Any) -> None:
        report_content = GameReportPopup(katrain=MDApp.get_running_app().gui)
        report_popup = I18NPopup(
            title_key="analysis:report",
            size=[dp(750), dp(750)],
            content=report_content,
        )
        report_popup.content.popup = report_popup
        report_popup.bind(on_dismiss=lambda _instance: report_content.cancel_refresh())
        report_popup.open()

    def open_tsumego_frame_popup(self, *_args: Any) -> None:
        analysis_popup = I18NPopup(
            title_key="analysis:tsumegoframe", size=[dp(500), dp(350)], content=TsumegoFramePopup()
        )
        analysis_popup.content.popup = analysis_popup
        analysis_popup.content.katrain = MDApp.get_running_app().gui
        analysis_popup.open()


# ``dp`` is imported lazily inside the methods above; the import lives
# at module level to keep the file self-contained for ``from kivy.metrics import dp``
# style. Importing here at top avoids repeated lookups inside the popup
# factory closures.
from kivy.metrics import dp  # noqa: E402


class AnalysisControls(MDBoxLayout):
    dropdown = ObjectProperty(None)
    is_open = BooleanProperty(False)
    mykatrain_is_open = BooleanProperty(False)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.build_dropdown()

    def on_is_open(self, instance: Any, value: Any) -> None:
        if value:
            max_content_width = max(option.content_width for option in self.dropdown.container.children)
            self.dropdown.width = max_content_width
            self.dropdown.open(self.analysis_button)
        elif self.dropdown.attach_to:
            self.dropdown.dismiss()

    def on_mykatrain_is_open(self, instance: Any, value: Any) -> None:
        if value:
            if not hasattr(self, "mykatrain_dropdown") or not hasattr(self, "mykatrain_button"):
                self.mykatrain_is_open = False
                return
            if self.mykatrain_dropdown.container.children:
                max_content_width = max(option.content_width for option in self.mykatrain_dropdown.container.children)
                self.mykatrain_dropdown.width = max(max_content_width, 250)
            else:
                self.mykatrain_dropdown.width = 250
            self.mykatrain_dropdown.open(self.mykatrain_button)
        elif hasattr(self, "mykatrain_dropdown") and self.mykatrain_dropdown.attach_to:
            self.mykatrain_dropdown.dismiss()

    def close_dropdown(self, *largs: Any) -> None:
        self.is_open = False

    def close_mykatrain_dropdown(self, *largs: Any) -> None:
        self.mykatrain_is_open = False

    def toggle_dropdown(self, *largs: Any) -> None:
        self.is_open = not self.is_open

    def toggle_mykatrain_dropdown(self, *largs: Any) -> None:
        self.mykatrain_is_open = not self.mykatrain_is_open

    def build_dropdown(self) -> None:
        self.dropdown = AnalysisDropDown(auto_width=False)
        self.dropdown.bind(on_dismiss=self.close_dropdown)
        self.mykatrain_dropdown = MyKatrainDropDown(auto_width=False)
        self.mykatrain_dropdown.bind(on_dismiss=self.close_mykatrain_dropdown)


class MyKatrainDropDown(DropDown):
    """myKatrain dropdown menu.

    Kept as an explicit (empty) subclass of DropDown so that the
    ``<MyKatrainDropDown>`` rule in katrain/gui/kv/menu.kv is applied
    via Kivy's class-name-based rule matching. Using a direct alias
    (``MyKatrainDropDown = DropDown``) breaks rule application because
    the instance's ``__name__`` would be ``"DropDown"``.
    """


class BadukPanControls(MDFloatLayout):
    engine_status_col = ListProperty(Theme.ENGINE_DOWN_COLOR)
    engine_status_pondering = NumericProperty(-1)
    queries_remaining = NumericProperty(0)

    def update_controls(self, gui: Any) -> None:
        """Update controls (prisoners, engine status) from GUI state."""
        game = gui.game
        if not game:
            return

        # Update prisoners
        prisoners = game.prisoner_count
        # Handle circle display if available
        circles = getattr(self, "circles", None)
        if circles and len(circles) == 2:
            try:
                top, bot = [w.__self__ for w in circles]
                if gui.next_player_info.player == "W":
                    top, bot = bot, top
                    gui.controls.players["W"].active = True
                    gui.controls.players["B"].active = False
                else:
                    gui.controls.players["W"].active = False
                    gui.controls.players["B"].active = True
                mid_container = getattr(self, "mid_circles_container", None)
                if mid_container:
                    mid_container.clear_widgets()
                    mid_container.add_widget(bot)
                    mid_container.add_widget(top)
            except (ValueError, AttributeError, TypeError) as e:
                gui.log(f"circles parsing failed: {e}", OUTPUT_DEBUG)
        else:
            if gui.next_player_info.player == "W":
                gui.controls.players["W"].active = True
                gui.controls.players["B"].active = False
            else:
                gui.controls.players["W"].active = False
                gui.controls.players["B"].active = True

        gui.controls.players["W"].captures = prisoners["W"]
        gui.controls.players["B"].captures = prisoners["B"]

        # Update engine status dot
        engine = gui.engine
        if not engine or not engine.is_alive():
            self.engine_status_col = Theme.ENGINE_DOWN_COLOR
        elif engine.is_idle():
            self.engine_status_col = Theme.ENGINE_READY_COLOR
        else:
            self.engine_status_col = Theme.ENGINE_BUSY_COLOR
        if engine:
            self.queries_remaining = engine.queries_remaining()


__all__ = [
    "AnalysisDropDown",
    "AnalysisControls",
    "BadukPanControls",
    "MyKatrainDropDown",
]

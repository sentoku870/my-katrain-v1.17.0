"""SGF-related popups (load, save, re-analyze).

Phase 140 P2-1: Extracted from katrain/gui/popups.py.
"""
from __future__ import annotations

import os
from typing import Any

from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivymd.app import MDApp

from katrain.gui.popups.config_popup import BaseConfigPopup


class LoadSGFPopup(BaseConfigPopup):
    __events__ = ("on_success",)
    filesel = ObjectProperty(None)

    def on_success(self) -> None:
        """Default handler for on_success event (Kivy requirement)."""
        pass

    def __init__(self, katrain: Any) -> None:
        super().__init__(katrain)
        app = MDApp.get_running_app()
        self.filesel.favorites = [
            (os.path.abspath(app.gui.config("general/sgf_load")), "Last Load Dir"),
            (os.path.abspath(app.gui.config("general/sgf_save")), "Last Save Dir"),
        ]
        self.filesel.path = os.path.abspath(os.path.expanduser(app.gui.config("general/sgf_load")))
        self.filesel.select_string = "Load File"

    def on_submit(self) -> None:
        self.filesel.button_clicked()


class SaveSGFPopup(BoxLayout):
    __events__ = ("on_success",)
    filesel = ObjectProperty(None)

    def on_success(self) -> None:
        """Default handler for on_success event (Kivy requirement)."""
        pass

    def __init__(self, suggested_filename: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.suggested_filename = suggested_filename
        app = MDApp.get_running_app()
        self.filesel.favorites = [
            (os.path.abspath(app.gui.config("general/sgf_load")), "Last Load Dir"),
            (os.path.abspath(app.gui.config("general/sgf_save")), "Last Save Dir"),
        ]
        save_path = os.path.expanduser(MDApp.get_running_app().gui.config("general/sgf_save") or ".")

        def set_suggested(_widget: Any, path: str) -> None:
            self.filesel.ids.file_text.text = os.path.join(path, self.suggested_filename)

        self.filesel.ids.list_view.bind(path=set_suggested)
        self.filesel.path = os.path.abspath(save_path)
        self.filesel.select_string = "Save File"

    def on_submit(self) -> None:
        self.filesel.button_clicked()


class ReAnalyzeGamePopup(BoxLayout):
    popup = ObjectProperty(None)

    def on_checkbox_active(self, checkbox: Any, value: bool) -> None:
        self.start_move.opacity = 1.0 if value else 0.3
        self.end_move.opacity = 1.0 if value else 0.3
        self.start_move.disabled = not value
        self.end_move.disabled = not value

    def __init__(self, katrain: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.katrain = katrain
        self.move_range.bind(active=self.on_checkbox_active)

        self.start_move.disabled = True
        self.end_move.disabled = True
        self.start_move.opacity = 0.3
        self.end_move.opacity = 0.3

        self.start_move.text = str(katrain.game.current_node.depth)

    def on_submit(self) -> None:
        self.button.trigger_action(duration=0)

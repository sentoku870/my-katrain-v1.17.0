"""Kivy spinner widgets (Phase 144-A split).

Extracted from katrain/gui/kivyutils/widgets.py:
- KeyValueSpinner: Spinner with both display values and referenced key values.
- I18NSpinner: KeyValueSpinner whose values are auto-localized via i18n.
"""
from __future__ import annotations

from typing import Any

from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.spinner import Spinner
from kivymd.app import MDApp

from katrain.core.lang import i18n
from katrain.gui.theme import Theme


class KeyValueSpinner(Spinner):
    __events__ = ["on_select"]
    sync_height_frac = NumericProperty(1.0)
    value_refs = ListProperty()
    selected_index = NumericProperty(0)
    font_name = StringProperty(Theme.DEFAULT_FONT)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.build_values()
        self.bind(size=self.update_dropdown_props, pos=self.update_dropdown_props, value_refs=self.build_values)

    @property
    def input_value(self) -> Any:
        try:
            return self.value_refs[self.selected_index]
        except KeyError:
            return ""

    @property
    def selected(self) -> tuple[int, Any, Any]:
        try:
            selected = self.selected_index
            return selected, self.value_refs[selected], self.values[selected]
        except (ValueError, IndexError):
            return 0, "", ""

    def on_text(self, _widget: Any, text: str) -> None:
        try:
            new_index = self.values.index(text)
            if new_index != self.selected_index:
                self.selected_index = new_index
                self.dispatch("on_select")
        except (ValueError, IndexError):
            pass

    def on_select(self, *args: Any) -> None:
        pass

    def select_key(self, key: Any) -> None:
        try:
            ix = self.value_refs.index(key)
            self.text = self.values[ix]
        except (ValueError, IndexError):
            pass

    def build_values(self, *_args: Any) -> None:
        if self.value_refs and self.values:
            self.text = self.values[self.selected_index]
            self.font_name = i18n.font_name
            self.update_dropdown_props()

    def update_dropdown_props(self, *largs: Any) -> None:
        if not self.sync_height_frac:
            return
        dp = self._dropdown
        if not dp:
            return
        container = dp.container
        if not container:
            return
        h = self.height
        fsz = self.font_size
        for item in container.children[:]:
            item.height = h * self.sync_height_frac
            item.font_size = fsz
            item.font_name = self.font_name


class I18NSpinner(KeyValueSpinner):
    __events__ = ["on_select"]
    sync_height_frac = NumericProperty(1.0)
    value_refs = ListProperty()
    selected_index = NumericProperty(0)
    font_name = StringProperty(Theme.DEFAULT_FONT)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        MDApp.get_running_app().bind(language=self.build_values)

    def build_values(self, *_args: Any) -> None:
        self.values = [i18n._(ref) for ref in self.value_refs]
        super().build_values()

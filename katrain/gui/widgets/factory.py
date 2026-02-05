from __future__ import annotations

from typing import Any

from kivy.uix.button import Button as _Button
from kivy.uix.label import Label as _Label
from kivy.uix.popup import Popup as _Popup

from katrain.gui.theme import Theme


class Label(_Label):
    """
    A Label that defaults to Theme.DEFAULT_FONT to prevent Tofu (garbled text).
    """

    def __init__(self, **kwargs: Any) -> None:
        if "font_name" not in kwargs:
            kwargs["font_name"] = Theme.DEFAULT_FONT
        super().__init__(**kwargs)


class Button(_Button):
    """
    A Button that defaults to Theme.DEFAULT_FONT to prevent Tofu (garbled text).
    """

    def __init__(self, **kwargs: Any) -> None:
        if "font_name" not in kwargs:
            kwargs["font_name"] = Theme.DEFAULT_FONT
        super().__init__(**kwargs)


class Popup(_Popup):
    """
    A Popup that defaults title_font to Theme.DEFAULT_FONT to prevent Tofu in titles.
    """

    def __init__(self, **kwargs: Any) -> None:
        if "title_font" not in kwargs:
            kwargs["title_font"] = Theme.DEFAULT_FONT
        super().__init__(**kwargs)

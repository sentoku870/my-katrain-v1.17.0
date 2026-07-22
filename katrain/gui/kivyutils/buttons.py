"""Kivy button classes (resizable, sized, toggle, icon).

Phase 140 P2-2: Extracted from katrain/gui/kivyutils.py.
Phase 277: Reworked for KivyMD 1.2.0 (BaseFlatButton / BasePressedButton were
removed in 1.0.0; the entire button hierarchy is now rooted on
``kivymd.uix.button.BaseButton`` which already provides ripple + a
self-managed background). We keep the same external API and KV rules but
drop the now-defunct KivyMD base classes from the MRO.

Hierarchy:
- SizedButton (base for resizable buttons; KivyMD 1.2.0 ``BaseButton``
  + BackgroundMixin for the rounded-rectangle outline + LeftButtonBehavior
  for click dispatch)
  - AutoSizedButton
  - SizedRectangleButton
    - AutoSizedRectangleButton
- SizedToggleButton (ToggleButtonMixin + SizedButton)
- SizedRectangleToggleButton (ToggleButtonMixin + SizedRectangleButton)
- AutoSizedRectangleToggleButton (ToggleButtonMixin + AutoSizedRectangleButton)
- TransparentIconButton
- MaterialIconButton (Phase 287-G: KivyMD MDI フォント描画)
- PauseButton
"""

from __future__ import annotations

from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    OptionProperty,
    StringProperty,
)
from kivy.uix.widget import Widget
from kivymd.uix.behaviors import CircularRippleBehavior
from kivymd.uix.button import BaseButton

from katrain.gui.kivyutils.mixins import BackgroundMixin, LeftButtonBehavior, ToggleButtonMixin
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button


# -- resizeable buttons / avoid baserectangular for sizing
# Phase 277: KivyMD 1.2.0 removed BaseFlatButton / BasePressedButton and
# collapsed the hierarchy into a single BaseButton. BaseButton already
# extends RectangularRippleBehavior, ThemableBehavior, ButtonBehavior,
# and AnchorLayout, so we no longer need to mix RectangularRippleBehavior
# in explicitly -- only LeftButtonBehavior (for our left-click dispatch
# contract) and BackgroundMixin (for the project's custom rounded-rect
# outline drawn in widgets.kv).
class SizedButton(LeftButtonBehavior, BaseButton, BackgroundMixin):
    text = StringProperty("")
    text_color = ListProperty(Theme.BUTTON_TEXT_COLOR)
    text_size = ListProperty([100, 100])
    halign = OptionProperty("center", options=["left", "center", "right", "justify", "auto"])
    label = ObjectProperty(None)
    padding_x = NumericProperty(6)
    padding_y = NumericProperty(0)
    _font_size = NumericProperty(None)
    font_name = StringProperty(Theme.DEFAULT_FONT)
    # Phase 277: KivyMD 1.2.0 BaseButton defaults theme_text_color to None
    # which is then resolved by each subclass. We rely on text_color being
    # applied explicitly so the button is always rendered in our chosen
    # colour regardless of the subclass defaults.
    theme_text_color = OptionProperty(
        "Custom", options=["Primary", "Secondary", "Hint", "Error", "Custom", "ContrastParentBackground"]
    )


class AutoSizedButton(SizedButton):
    pass


class SizedRectangleButton(SizedButton):
    pass


class AutoSizedRectangleButton(AutoSizedButton):
    pass


class SizedToggleButton(ToggleButtonMixin, SizedButton):
    pass


class SizedRectangleToggleButton(ToggleButtonMixin, SizedRectangleButton):
    pass


class AutoSizedRectangleToggleButton(ToggleButtonMixin, AutoSizedRectangleButton):
    pass


class TransparentIconButton(CircularRippleBehavior, Button):
    color = ListProperty([1, 1, 1, 1])
    icon_size = ListProperty([25, 25])
    icon = StringProperty("")
    disabled = BooleanProperty(False)


class MaterialIconButton(CircularRippleBehavior, Button):
    """Phase 287-G: Material Design Icons 版の操作ボタン。

    アイコン名 (``menu`` 等の MDI 名、または既存の PNG パス) を受け取り、
    内部で PNG ファイルパスに解決して ``Image`` 描画する。``Image`` ベース
    の描画は Kivy で実績のあるパスで、確実に見える。

    MDI 名 (``menu`` 等) は ``theme_loader.MDI_TO_PNG_FALLBACK`` 経由で
    既存の Flaticon PNG ファイルに解決される。既存の ``TransparentIconButton``
    と全く同じ描画パスを使うため、互換性も維持される。

    ライセンス上、``katrain/img/`` 配下のアイコン PNG は Flaticon 由来
    (LICENSE に帰属記載済み) であり、本マップは当該ライセンスを尊重する。
    """

    color = ListProperty(Theme.TEXT_COLOR if hasattr(Theme, "TEXT_COLOR") else [1, 1, 1, 1])
    icon_size = ListProperty([25, 25])
    icon = StringProperty("")
    disabled = BooleanProperty(False)
    image = ObjectProperty(None)

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)

    def _resolved_source(self) -> str:
        """Resolve ``self.icon`` (MDI name or PNG path) to a PNG file path."""
        from katrain.gui.theme_loader import (  # noqa: WPS433
            LEGACY_ICON_TO_MDI,
            MDI_TO_PNG_FALLBACK,
        )

        name = self.icon or ""
        if not name:
            return ""
        # Already a PNG / image asset path? Pass through.
        if name.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
            # If it's a legacy PNG name, still return as-is.
            if name in LEGACY_ICON_TO_MDI or "/" in name:
                return name
            return name
        # Resolve legacy PNG name -> MDI name (in case someone still passes
        # the legacy PNG name).
        mdi_name = LEGACY_ICON_TO_MDI.get(name, name)
        # MDI name -> PNG fallback file.
        return MDI_TO_PNG_FALLBACK.get(mdi_name, "")

    def on_icon(self, *_args: object) -> None:
        if self.image is not None:
            self.image.source = self._resolved_source()

    def on_color(self, *_args: object) -> None:
        if self.image is not None:
            self.image.color = [c * 0.4 for c in self.color[:3]] + [1] if self.disabled else list(self.color)

    def on_disabled(self, *_args: object) -> None:
        if self.image is not None:
            self.image.color = [c * 0.4 for c in self.color[:3]] + [1] if self.disabled else list(self.color)


class PauseButton(CircularRippleBehavior, LeftButtonBehavior, Widget):
    active = BooleanProperty(True)
    active_line_color = ListProperty([0.5, 0.5, 0.8, 1])
    inactive_line_color = ListProperty([1, 1, 1, 1])
    active_fill_color = ListProperty([0.5, 0.5, 0.5, 1])
    inactive_fill_color = ListProperty([1, 1, 1, 0])
    line_width = NumericProperty(5)
    fill_color = ListProperty([0.5, 0.5, 0.5, 1])
    line_color = ListProperty([0.5, 0.5, 0.5, 1])
    min_size = NumericProperty(100)

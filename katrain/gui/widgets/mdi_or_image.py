"""MDI + 画像フォールバックの最小描画部品 (Phase 287-G).

既存の ``MenuItem`` のような ``icon`` プロパティが文字列で渡される部品に対し、
MDI 名なら KivyMD が登録する ``"Icons"`` フォントでレンダリングしたグリフ
テクスチャを ``canvas`` に直接描画し、PNG ファイルパスなら ``Image`` として
描画する。フラグのように MDI 辞書に存在しない画像アセットはそのまま PNG 表示
する。

設計意図:
- ``MenuItem.icon`` の API を変更しない。
- ``kivymd.font_definitions`` を import することで ``LabelBase`` に
  ``"Icons"`` フォントが登録される (論理名)。ファイル名ではなく論理名で
  ``CoreLabel`` に渡す必要がある。
- ヘルパー (``resolve_mdi_glyph`` / ``is_png_path``) はモジュールレベル関数
  として公開し、Widget インスタンス化なしでテストできる。
"""

from __future__ import annotations

from kivy.clock import Clock
from kivy.properties import ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image


def resolve_mdi_glyph(icon_name: str) -> str:
    """Return the Unicode glyph for an icon name, or empty string.

    Resolves legacy PNG names via ``LEGACY_ICON_TO_MDI`` before consulting
    ``kivymd.icon_definitions.md_icons``. Safe to call before any widget
    is constructed.
    """
    from katrain.gui.theme_loader import LEGACY_ICON_TO_MDI  # noqa: WPS433

    resolved = LEGACY_ICON_TO_MDI.get(icon_name, icon_name)
    if not resolved:
        return ""
    try:
        from kivymd.icon_definitions import md_icons  # noqa: WPS433
    except Exception:
        return ""
    result = md_icons.get(resolved, "")
    return result if isinstance(result, str) else ""


def is_png_path(icon_name: str) -> bool:
    """Return True iff the icon name looks like an image file path."""
    return icon_name.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))


def resolve_mdi_name(icon_name: str) -> str:
    """Return the canonical MDI name (legacy PNG name -> MDI name)."""
    from katrain.gui.theme_loader import LEGACY_ICON_TO_MDI  # noqa: WPS433

    return LEGACY_ICON_TO_MDI.get(icon_name, icon_name)


class MdiIconOrImage(BoxLayout):
    """Renders an MDI glyph (canvas Rectangle) or a PNG fallback (Image).

    ``icon`` property accepts either an MDI name (``menu``) or a legacy
    PNG path (``flags/flag-jp.png``). The widget chooses the rendering
    mode automatically.

    The MDI glyph is pre-rendered to a texture via ``CoreLabel`` and
    drawn with a ``Rectangle`` canvas instruction. This avoids the
    nested-Label rendering issues that arise when a ``Label`` is added
    as a child of a ``Button`` (which itself extends ``Label``).
    """

    icon = StringProperty("")
    color = ListProperty([1, 1, 1, 1])
    font_size = NumericProperty(0)
    _resolved_name = StringProperty("")
    _glyph_texture = ObjectProperty(None, allownone=True)
    _glyph_size = ListProperty([0, 0])

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._image: Image | None = None
        self.bind(
            icon=self._on_icon_changed,
            color=self._refresh_glyph,
            font_size=self._refresh_glyph,
            size=self._refresh_glyph,
        )
        Clock.schedule_once(lambda _dt: self._refresh_glyph(), 0)

    def _on_icon_changed(self, *_args: object) -> None:
        from katrain.gui.theme_loader import LEGACY_ICON_TO_MDI  # noqa: WPS433

        self._resolved_name = LEGACY_ICON_TO_MDI.get(self.icon, self.icon)
        self._refresh_glyph()

    @staticmethod
    def resolve_mdi_glyph(icon_name: str) -> str:
        """Static accessor exposing the helper to tests."""
        return resolve_mdi_glyph(icon_name)

    @staticmethod
    def is_png_path(icon_name: str) -> bool:
        """Static accessor exposing the helper to tests."""
        return is_png_path(icon_name)

    def _resolved_mdi_glyph(self) -> str:
        return resolve_mdi_glyph(self.icon)

    def _is_png_path(self) -> bool:
        return is_png_path(self.icon)

    def glyph_rect_pos(self) -> list[float]:
        """Return the Rectangle ``pos`` that centres the glyph inside the widget.

        KV パーサーは ``pos: (multi, line, expression)`` の深いインデントを
        許可しないため、計算は Python 側で 1 行のリストにまとめて返す。
        """
        gw = self._glyph_size[0] if self._glyph_size else 0
        gh = self._glyph_size[1] if self._glyph_size else 0
        return [self.x + (self.width - gw) / 2, self.y + (self.height - gh) / 2]

    def glyph_rect_size(self) -> list[float]:
        """Return the Rectangle ``size`` matching the glyph texture."""
        return list(self._glyph_size) if self._glyph_size else [0, 0]

    def _refresh_glyph(self, *_args: object) -> None:
        """(Re)generate glyph texture and rebuild the children tree."""
        glyph = self._resolved_mdi_glyph()
        if glyph:
            self._regenerate_glyph_texture(glyph)
        self._rebuild()

    def _regenerate_glyph_texture(self, glyph: str) -> None:
        from kivy.uix.label import Label as KivyLabel  # noqa: WPS433

        from katrain.gui.theme import Theme  # noqa: WPS433

        size_px = int(self.font_size) if self.font_size > 0 else 24
        try:
            lbl = KivyLabel(
                text=glyph,
                font_name=Theme.DEFAULT_ICON_FONT,
                font_size=size_px,
                color=self.color,
            )
            lbl.texture_update()
            self._glyph_texture = lbl.texture
            self._glyph_size = list(lbl.texture_size)
        except Exception:
            self._glyph_texture = None
            self._glyph_size = [0, 0]

    def _rebuild(self, *_args: object) -> None:
        glyph = self._resolved_mdi_glyph()
        self.clear_widgets()
        # PNG fallback path (e.g. national flags): use a real Image widget.
        if not glyph and self._is_png_path():
            if self._image is None:
                self._image = Image(mipmap=True)
            self._image.source = self.icon
            self._image.color = self.color
            self._image.size_hint = (1, 1)
            self.add_widget(self._image)
        # MDI glyph is drawn via canvas (see KV rule below) — no child widget.
        # else: empty icon -> render nothing

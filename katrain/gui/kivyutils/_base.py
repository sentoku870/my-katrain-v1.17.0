"""Kivy utilities: base imports, module-level state, and free functions.

Phase 140 P2-2: Extracted from katrain/gui/kivyutils.py to enable focused
maintenance of 32 widget/button/mixin classes.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from kivy.core.image import Image
from kivy.core.text import Label as CoreLabel
from kivy.core.text.markup import MarkupLabel as CoreMarkupLabel
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.graphics.texture import Texture
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    OptionProperty,
    StringProperty,
)
from kivy.resources import resource_find
from kivy.uix.behaviors import ButtonBehavior, ToggleButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.behaviors import CircularRippleBehavior, RectangularRippleBehavior
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import BaseFlatButton, BasePressedButton
from kivymd.uix.navigationdrawer import MDNavigationDrawer
from kivymd.uix.textfield import MDTextField

from katrain.core.constants import (
    AI_STRATEGIES_RECOMMENDED_ORDER,
    GAME_TYPES,
    MODE_PLAY,
    PLAYER_AI,
    PLAYER_HUMAN,
    PLAYING_NORMAL,
    PLAYING_TEACHING,
)
from katrain.core.lang import i18n
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button, Label

_logger = logging.getLogger(__name__)

# v5: フォールバックテクスチャをシングルトン化（毎回作成を避ける）
_fallback_texture: Any = None

# v5: ログは関数外で管理（lru_cache内でログを呼ばない）
_missing_resources: set[str] = set()


def _make_hashable(value: Any) -> Any:
    """kwargs値をhashableに変換（list/dict/set/tuple対応）

    v4: エッジケース対策
    - tuple: そのまま返す（既にhashable）
    - set: sorted tupleに変換
    - numpy配列/カスタムオブジェクト: repr()でフォールバック（サイズ制限付き）
    """
    if isinstance(value, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in value.items()))
    elif isinstance(value, list):
        return tuple(_make_hashable(v) for v in value)
    elif isinstance(value, set):
        # v4: setをsorted tupleに変換（要素がcomparableな場合のみ）
        try:
            return tuple(sorted(_make_hashable(v) for v in value))
        except TypeError:
            return tuple(_make_hashable(v) for v in value)
    elif isinstance(value, tuple):
        # v4: tupleはそのまま（既にhashable、ネストは再帰処理）
        return tuple(_make_hashable(v) for v in value)
    # v4: その他のオブジェクト（numpy配列等）はrepr()でフォールバック
    try:
        hash(value)
        return value
    except TypeError:
        # unhashableな場合はrepr()で文字列化（サイズ制限）
        repr_str = repr(value)
        if len(repr_str) > 200:
            repr_str = repr_str[:200] + "..."
        return f"__unhashable__:{type(value).__name__}:{repr_str}"


@lru_cache(maxsize=500)
def _create_text_texture(text: str, resolved_font_name: str, markup: bool, kwargs_tuple: tuple[Any, ...]) -> Any:
    """LRU制限付きテクスチャ生成（内部用）

    Args:
        resolved_font_name: 解決済みのフォント名（Noneは許可しない）
    """
    kwargs = dict(kwargs_tuple)
    label_cls = CoreMarkupLabel if markup else CoreLabel
    label = label_cls(text=text, bold=True, font_name=resolved_font_name, **kwargs)
    label.refresh()
    return label.texture


def cached_text_texture(text: str, font_name: str | None, markup: bool, **kwargs: Any) -> Any:
    """互換性維持のラッパー（API変更なし）

    Note: Kivyの描画はメインスレッドのみなのでスレッドセーフは不要
    """
    # v3: font_nameをキャッシュ前に解決（言語変更時のキャッシュ問題を回避）
    # v5: i18n.font_nameがNoneの場合のフォールバック追加
    resolved_font_name = font_name if font_name else (i18n.font_name or "Roboto")
    # kwargsをhashableなtupleに変換（list/dict値も対応）
    kwargs_tuple = tuple(sorted((k, _make_hashable(v)) for k, v in kwargs.items()))
    return _create_text_texture(text, resolved_font_name, markup, kwargs_tuple)


def draw_text(
    pos: Sequence[float], text: str, font_name: str | None = None, markup: bool = False, **kwargs: Any
) -> None:
    texture = cached_text_texture(text, font_name, markup, **kwargs)
    Rectangle(texture=texture, pos=(pos[0] - texture.size[0] / 2, pos[1] - texture.size[1] / 2), size=texture.size)


def draw_circle(pos: Sequence[float], r: float, col: Sequence[float]) -> None:
    Color(*col)
    Ellipse(pos=(pos[0] - r, pos[1] - r), size=(2 * r, 2 * r))


def _get_fallback_texture() -> Any:
    """1x1透明フォールバックテクスチャを取得（シングルトン）"""
    global _fallback_texture
    if _fallback_texture is None:
        _fallback_texture = Texture.create(size=(1, 1))
        _fallback_texture.blit_buffer(b"\x00\x00\x00\x00", colorfmt="rgba")
    return _fallback_texture


@lru_cache(maxsize=100)
def cached_texture(path: str) -> Any:
    """画像テクスチャのLRUキャッシュ

    Args:
        path: リソースパス

    Returns:
        テクスチャ（成功時）またはフォールバックテクスチャ（失敗時）

    Note: v4変更 - FileNotFoundErrorを内部で処理しフォールバック返却
          呼び出し元（badukpan.py 8箇所）はすべてTexture前提のため、
          例外を投げずに1x1透明テクスチャをフォールバックとして返す
    Note: v5変更 - フォールバックをシングルトン化、ログスパム防止
    """
    resolved = resource_find(path)
    if resolved is None:
        # v5: 同じパスは一度だけログ出力（スパム防止）
        if path not in _missing_resources:
            _missing_resources.add(path)
            _logger.error(f"Resource not found: {path!r} - returning fallback texture")
        return _get_fallback_texture()
    return Image(resolved).texture


def clear_texture_caches() -> None:
    """テクスチャキャッシュをクリア（言語変更時に呼び出す）

    Note: i18n.set_language()等から呼び出すことで、
          古いフォントのテクスチャがメモリに残り続けることを防ぐ
    """
    _create_text_texture.cache_clear()
    _logger.debug("Text texture cache cleared")

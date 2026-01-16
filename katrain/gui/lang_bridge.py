# katrain/gui/lang_bridge.py
"""Kivy binding bridge for Lang (v5: fbind/funbind戦略に一本化).

v5設計:
- EventDispatcher（公開API）を使用
- fbind/funbindでKVバインディングを維持
- 既存KVファイルの変更不要
"""
import weakref
from typing import Any, Callable, List, Tuple, Union

from kivy.event import EventDispatcher
from kivy.properties import StringProperty
from kivy.weakproxy import WeakProxy

from katrain.core.lang import i18n as core_i18n, DEFAULT_LANGUAGE


def _deref_widget(widget_ref: Union[weakref.ref, WeakProxy]):
    """Dereference a widget from either weakref.ref or WeakProxy.

    Returns None if the widget has been garbage collected.
    """
    if isinstance(widget_ref, WeakProxy):
        try:
            # Access any attribute to check if still alive
            _ = widget_ref.__class__
            return widget_ref
        except ReferenceError:
            return None
    else:
        # weakref.ref - call to get the object
        return widget_ref()


class KivyLangBridge(EventDispatcher):
    """Kivy-compatible wrapper for Lang instance.

    v5: fbind/funbindレガシーAPIを維持。
    KVファイルの変更は不要。
    """
    font_name = StringProperty("")
    current_lang = StringProperty(DEFAULT_LANGUAGE)

    def __init__(self, lang_instance, **kwargs):
        super().__init__(**kwargs)
        self._lang = lang_instance
        # WeakProxy or weakref.ref - both support () call to get the widget
        self._observers: List[Tuple[Union[weakref.ref, WeakProxy], Callable, Tuple[Any, ...]]] = []

        self.font_name = lang_instance.font_name
        self.current_lang = lang_instance.lang or DEFAULT_LANGUAGE

        lang_instance.add_change_callback(self._on_lang_change)

        # テクスチャキャッシュクリアをGUI層で登録
        try:
            from katrain.gui.kivyutils import clear_texture_caches
            lang_instance.add_change_callback(lambda _: clear_texture_caches())
        except ImportError:
            pass

    def _on_lang_change(self, lang_instance) -> None:
        """言語変更時の処理"""
        self.font_name = lang_instance.font_name
        self.current_lang = lang_instance.lang or DEFAULT_LANGUAGE
        self._notify_observers()

    def _(self, text: str) -> str:
        """翻訳関数（KVから呼び出される）"""
        return self._lang._(text)

    def switch_lang(self, lang: str) -> None:
        """言語切替（ラッパー）"""
        self._lang.switch_lang(lang)

    def set_widget_font(self, widget) -> None:
        """ウィジェットにフォントを設定"""
        widget.font_name = self.font_name
        for sub_widget in [getattr(widget, "_hint_lbl", None), getattr(widget, "_msg_lbl", None)]:
            if sub_widget:
                sub_widget.font_name = self.font_name

    def fbind(self, name, func, *args):
        """KVバインディング用（レガシー互換）"""
        if name == "_":
            widget, property_name, *_ = args[0]
            # WeakProxy is already a weak reference, don't wrap it again
            if isinstance(widget, WeakProxy):
                widget_ref = widget
            else:
                widget_ref = weakref.ref(widget)
            self._observers.append((widget_ref, func, args))
            try:
                self.set_widget_font(widget)
            except Exception:
                pass
        else:
            return super().fbind(name, func, *args)

    def funbind(self, name, func, *args):
        """KVアンバインド用（レガシー互換）"""
        if name == "_":
            widget, *_ = args[0]
            self._observers = [
                (ref, f, a) for ref, f, a in self._observers
                if _deref_widget(ref) is not None and _deref_widget(ref) is not widget
            ]
        else:
            return super().funbind(name, func, *args)

    def _notify_observers(self) -> None:
        """レガシーobserversに通知"""
        alive_observers = []
        for widget_ref, func, args in self._observers:
            widget = _deref_widget(widget_ref)
            if widget is None:
                continue

            alive_observers.append((widget_ref, func, args))
            try:
                func(args[0], None, None)
                self.set_widget_font(widget)
            except Exception as e:
                print(f"Error in observer: {e}")

        self._observers = alive_observers


# KVファイルからインポートされるインスタンス
i18n = KivyLangBridge(core_i18n)

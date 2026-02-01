# katrain/core/lang.py
"""Language support module (v5: core層はKivy依存なし).

変更通知はコールバックリストで提供。
GUI層でKivyブリッジが登録する。
"""
import gettext
import os
import sys
from typing import Callable, List, Optional

from katrain.common import DEFAULT_FONT
from katrain.core.utils import find_package_resource


DEFAULT_LANGUAGE = "en"


class Lang:
    """Language manager (v5: Observable継承なし、コールバックベース)."""
    FONTS = {"jp": "NotoSansJP-Regular.otf"}

    def __init__(self, lang: str):
        self._change_callbacks: List[Callable[["Lang"], None]] = []
        self.lang: Optional[str] = None
        self.font_name: str = DEFAULT_FONT
        self.ugettext: Callable[[str], str] = lambda x: x
        self.switch_lang(lang)

    def _(self, text: str) -> str:
        return self.ugettext(text)

    def add_change_callback(self, callback: Callable[["Lang"], None]) -> None:
        """言語変更時のコールバックを追加"""
        if callback not in self._change_callbacks:
            self._change_callbacks.append(callback)

    def remove_change_callback(self, callback: Callable[["Lang"], None]) -> None:
        """コールバックを削除"""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)

    def switch_lang(self, lang: str) -> None:
        if lang == self.lang:
            return

        self.lang = lang
        self.font_name = self.FONTS.get(lang) or DEFAULT_FONT

        i18n_dir, _ = os.path.split(find_package_resource("katrain/i18n/__init__.py"))
        locale_dir = os.path.join(i18n_dir, "locales")
        locales = gettext.translation("katrain", locale_dir, languages=[lang, DEFAULT_LANGUAGE])
        self.ugettext = locales.gettext

        self._notify_change()

    def _notify_change(self) -> None:
        """全コールバックに変更を通知"""
        for callback in self._change_callbacks[:]:
            try:
                callback(self)
            except Exception as e:
                print(f"Error in language change callback: {e}", file=sys.stderr)


i18n = Lang(DEFAULT_LANGUAGE)


def rank_label(rank: float | None) -> str:
    if rank is None:
        return "??k"
    if rank >= 0.5:
        return f"{rank:.0f}{i18n._('strength:dan')}"
    else:
        return f"{1-rank:.0f}{i18n._('strength:kyu')}"

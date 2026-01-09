"""
Language/i18n support for KaTrain.

Provides translation functionality using gettext.
Kivy Observable has been removed - the Qt frontend uses its own i18n system.
"""
import gettext
import os
import sys

from katrain.core.utils import find_package_resource


# Default font (previously from Theme)
DEFAULT_FONT = "Roboto"


class Lang:
    """
    Language translation class.

    Simplified from Kivy Observable-based implementation.
    Core translation functionality preserved.
    """
    observers = []
    callbacks = []
    FONTS = {"jp": "NotoSansJP-Regular.otf"}

    def __init__(self, lang):
        self.lang = None
        self.font_name = DEFAULT_FONT
        self.ugettext = lambda x: x  # Default: return text unchanged
        self.switch_lang(lang)

    def _(self, text):
        """Translate text."""
        return self.ugettext(text)

    def switch_lang(self, lang):
        """Switch to a different language."""
        if lang == self.lang:
            return
        self.lang = lang
        self.font_name = self.FONTS.get(lang) or DEFAULT_FONT

        try:
            i18n_dir, _ = os.path.split(find_package_resource("katrain/i18n/__init__.py"))
            locale_dir = os.path.join(i18n_dir, "locales")
            locales = gettext.translation("katrain", locale_dir, languages=[lang, DEFAULT_LANGUAGE])
            self.ugettext = locales.gettext
        except Exception as e:
            print(f"Warning: Failed to load translations for {lang}: {e}", file=sys.stderr)
            self.ugettext = lambda x: x  # Fall back to untranslated text

        # Notify callbacks (if any)
        for cb in self.callbacks:
            try:
                cb(self)
            except Exception as e:
                print(f"Failed callback on language change: {e}", file=sys.stderr)


DEFAULT_LANGUAGE = "en"
i18n = Lang(DEFAULT_LANGUAGE)


def rank_label(rank):
    """Format rank as dan/kyu string."""
    if rank is None:
        return "??k"

    if rank >= 0.5:
        return f"{rank:.0f}{i18n._('strength:dan')}"
    else:
        return f"{1-rank:.0f}{i18n._('strength:kyu')}"

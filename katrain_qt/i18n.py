"""
Simple i18n translation wrapper for KaTrain Qt.

Reads .po files from katrain/i18n/locales/{lang}/LC_MESSAGES/katrain.po
and provides a simple tr() function for translation.

Usage:
    from katrain_qt.i18n import tr, set_language

    set_language("jp")  # Switch to Japanese
    print(tr("menu:save"))  # -> "棋譜保存"
"""

from pathlib import Path
from typing import Dict, Optional

# Translation cache: {msgid: msgstr}
_translations: Dict[str, str] = {}
_current_language: str = "en"


def _parse_po_file(po_path: Path) -> Dict[str, str]:
    """
    Parse a .po file and return a dict of msgid -> msgstr.

    Simple parser that handles basic .po format:
    - msgid "text"
    - msgstr "translation"
    - Multi-line strings with ""
    """
    translations = {}
    if not po_path.exists():
        return translations

    try:
        with open(po_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except IOError:
        return translations

    current_msgid = None
    current_msgstr = None
    in_msgid = False
    in_msgstr = False

    for line in lines:
        line = line.strip()

        if line.startswith("msgid "):
            # Start of msgid
            in_msgid = True
            in_msgstr = False
            # Extract the string (remove 'msgid ' and quotes)
            content = line[6:].strip()
            if content.startswith('"') and content.endswith('"'):
                current_msgid = content[1:-1]
            else:
                current_msgid = ""

        elif line.startswith("msgstr "):
            # Start of msgstr
            in_msgid = False
            in_msgstr = True
            content = line[7:].strip()
            if content.startswith('"') and content.endswith('"'):
                current_msgstr = content[1:-1]
            else:
                current_msgstr = ""

        elif line.startswith('"') and line.endswith('"'):
            # Continuation line
            content = line[1:-1]
            if in_msgid and current_msgid is not None:
                current_msgid += content
            elif in_msgstr and current_msgstr is not None:
                current_msgstr += content

        elif line == "" or line.startswith("#"):
            # Empty line or comment - end of entry
            if current_msgid and current_msgstr:
                # Decode escape sequences
                current_msgstr = current_msgstr.replace("\\n", "\n")
                translations[current_msgid] = current_msgstr
            current_msgid = None
            current_msgstr = None
            in_msgid = False
            in_msgstr = False

    # Don't forget the last entry
    if current_msgid and current_msgstr:
        current_msgstr = current_msgstr.replace("\\n", "\n")
        translations[current_msgid] = current_msgstr

    return translations


def set_language(lang: str) -> None:
    """
    Set the current language and load translations.

    Args:
        lang: Language code ("en", "jp")
    """
    global _translations, _current_language

    _current_language = lang
    _translations = {}

    if lang == "en":
        # English is the default, no translation needed
        return

    # Find the .po file
    # Try katrain/i18n/locales/{lang}/LC_MESSAGES/katrain.po
    base_path = Path(__file__).parent.parent / "katrain" / "i18n" / "locales"
    po_path = base_path / lang / "LC_MESSAGES" / "katrain.po"

    if po_path.exists():
        _translations = _parse_po_file(po_path)


def tr(msgid: str, default: Optional[str] = None) -> str:
    """
    Translate a message ID to the current language.

    Args:
        msgid: The message ID to translate
        default: Default text if translation not found (defaults to msgid)

    Returns:
        Translated string, or default/msgid if not found
    """
    if _current_language == "en":
        return default if default is not None else msgid

    translated = _translations.get(msgid)
    if translated:
        return translated

    return default if default is not None else msgid


def get_current_language() -> str:
    """Get the current language code."""
    return _current_language


# Initialize with default language
set_language("en")

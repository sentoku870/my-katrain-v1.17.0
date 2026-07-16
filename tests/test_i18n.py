"""
Tests for i18n translations.

These tests verify that translation keys are properly translated
and don't appear as raw keys in the UI.
"""

import gettext
from pathlib import Path

import pytest


class TestBatchAnalyzeI18n:
    """Tests for batch analyze i18n translations."""

    @pytest.fixture
    def locale_dir(self):
        """Get the path to the locales directory."""
        # Find katrain package
        import katrain

        katrain_dir = Path(katrain.__file__).parent
        return katrain_dir / "i18n" / "locales"

    def test_english_translations_exist(self, locale_dir):
        """English translations should have human-readable strings."""
        en_mo = locale_dir / "en" / "LC_MESSAGES" / "katrain.mo"
        assert en_mo.exists(), f"English .mo file not found at {en_mo}"

        # Load English translations
        locales = gettext.translation("katrain", str(locale_dir), languages=["en"])

        # Test batch analyze keys
        test_keys = [
            ("mykatrain:batch:save_analyzed_sgf", "Save analyzed SGFs"),
            ("mykatrain:batch:generate_karte", "Generate Karte"),
            ("mykatrain:batch:generate_summary", "Generate Summary"),
            ("mykatrain:batch:complete_extended", "Complete!"),  # Partial match
        ]

        for key, expected_substring in test_keys:
            translated = locales.gettext(key)
            # Should NOT be the raw key
            assert translated != key, f"Key '{key}' was not translated"
            # Should contain expected text
            assert expected_substring in translated, (
                f"Translation for '{key}' should contain '{expected_substring}', but got: '{translated}'"
            )

    def test_japanese_translations_exist(self, locale_dir):
        """Japanese translations should have translated strings."""
        jp_mo = locale_dir / "jp" / "LC_MESSAGES" / "katrain.mo"
        assert jp_mo.exists(), f"Japanese .mo file not found at {jp_mo}"

        # Load Japanese translations
        locales = gettext.translation("katrain", str(locale_dir), languages=["jp"])

        # Test batch analyze keys - should be Japanese, not English
        test_keys = [
            "mykatrain:batch:save_analyzed_sgf",
            "mykatrain:batch:generate_karte",
            "mykatrain:batch:generate_summary",
        ]

        for key in test_keys:
            translated = locales.gettext(key)
            # Should NOT be the raw key
            assert translated != key, f"Key '{key}' was not translated in Japanese"
            # Should NOT be the English text (indicating fallback)
            assert "Save" not in translated and "Generate" not in translated, (
                f"Translation for '{key}' appears to be English fallback: '{translated}'"
            )

    def test_mo_files_are_up_to_date(self, locale_dir):
        """Compiled .mo files should be newer than or same age as .po files."""
        for lang in ["en", "jp"]:
            po_file = locale_dir / lang / "LC_MESSAGES" / "katrain.po"
            mo_file = locale_dir / lang / "LC_MESSAGES" / "katrain.mo"

            assert po_file.exists(), f"PO file not found: {po_file}"
            assert mo_file.exists(), f"MO file not found: {mo_file}"

            # MO file should not be older than PO file
            po_mtime = po_file.stat().st_mtime
            mo_mtime = mo_file.stat().st_mtime

            # Allow 1 second tolerance for filesystem timing
            assert mo_mtime >= po_mtime - 1, (
                f"MO file for {lang} is older than PO file. Recompile with "
                f"`python -c \"import polib; polib.pofile('{po_file}').save_as_mofile('{mo_file}')\"` "
                f"or `uv run pytest tests/test_i18n.py` after editing the .po."
            )

    def test_all_batch_keys_translated(self, locale_dir):
        """All batch analyze keys should be translated in both languages."""
        batch_keys = [
            "mykatrain:batch:title",
            "mykatrain:batch:input_dir",
            "mykatrain:batch:output_dir",
            "mykatrain:batch:save_analyzed_sgf",
            "mykatrain:batch:generate_karte",
            "mykatrain:batch:generate_summary",
            "mykatrain:batch:complete_extended",
            "mykatrain:batch:error_input_dir",
            "mykatrain:batch:error_no_engine",
            # Phase A new keys
            "mykatrain:batch:player_filter",
            "mykatrain:batch:filter_both",
            "mykatrain:batch:filter_black",
            "mykatrain:batch:filter_white",
            "mykatrain:batch:min_games",
            "mykatrain:batch:summary_player",
        ]

        for lang in ["en", "jp"]:
            locales = gettext.translation("katrain", str(locale_dir), languages=[lang])

            for key in batch_keys:
                translated = locales.gettext(key)
                assert translated != key, f"Key '{key}' is not translated in '{lang}' locale"

    def test_skill_auto_key_translated(self, locale_dir):
        """The skill_auto key should be translated in supported locales."""
        # Supported locales (JP + EN only)
        locales_list = ["en", "jp"]
        key = "mykatrain:settings:skill_auto"

        for lang in locales_list:
            locale = gettext.translation("katrain", str(locale_dir), languages=[lang])
            assert locale.gettext(key)


# ---------------------------------------------------------------------------
# Phase B-1: semantic dialog keys (button:ok, button:close, ...)
# ---------------------------------------------------------------------------


class TestSemanticDialogKeys:
    """Phase B-1: raw English msgids like ``i18n._("OK")`` are forbidden by
    the i18n workflow (docs/i18n-workflow.md: "Never use raw English phrases
    as msgid"). The codebase has been migrated to semantic keys; this test
    locks the keys in and scans source for any regression.
    """

    SEMANTIC_KEYS = ["button:ok", "button:close", "button:cancel", "dialog:title:error"]

    EXPECTED_TRANSLATIONS = {
        "en": {
            "button:ok": "OK",
            "button:close": "Close",
            "button:cancel": "Cancel",
            "dialog:title:error": "Error",
        },
        "jp": {
            "button:ok": "OK",
            "button:close": "閉じる",
            "button:cancel": "キャンセル",
            "dialog:title:error": "エラー",
        },
    }

    @pytest.fixture
    def locale_dir(self):
        from pathlib import Path

        import katrain

        return Path(katrain.__file__).parent / "i18n" / "locales"

    def test_semantic_keys_translated(self, locale_dir):
        """All semantic keys must be translated in both en and jp."""
        for lang, expected_map in self.EXPECTED_TRANSLATIONS.items():
            locale = gettext.translation("katrain", str(locale_dir), languages=[lang])
            for key, expected in expected_map.items():
                translated = locale.gettext(key)
                assert translated != key, f"Key '{key}' missing in '{lang}'"
                assert translated == expected, f"Key '{key}' in '{lang}': expected '{expected}', got '{translated}'"

    def test_no_raw_english_msgid_regression(self):
        """Scan Python and KV source for raw English msgids."""
        from pathlib import Path

        import katrain

        root = Path(katrain.__file__).parent
        forbidden = ('i18n._("OK")', 'i18n._("Close")', 'i18n._("Cancel")', 'i18n._("Error")')
        offenders: list[tuple[str, str]] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in (".py", ".kv"):
                continue
            if "i18n/locales" in str(path):  # exclude the .po definitions
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for needle in forbidden:
                if needle in text:
                    offenders.append((str(path.relative_to(root)), needle))
        assert not offenders, f"Raw English msgids reappeared: {offenders}"


# ---------------------------------------------------------------------------
# P2-B: previously-hardcoded Japanese strings now routed through i18n
# ---------------------------------------------------------------------------


class TestHardcodedJapaneseI18n:
    """P2-B (H5): focus toggle and important-line buttons used to be hardcoded
    Japanese strings in board.kv, panels.kv and analysis_controller.py.
    They are now ``i18n._(...)`` calls. This test locks down the new keys
    so a future regression (e.g. someone reverts one of these to a
    hardcoded literal) is caught at the i18n layer.
    """

    @pytest.fixture
    def locale_dir(self):
        """Get the path to the locales directory."""
        from pathlib import Path

        import katrain

        katrain_dir = Path(katrain.__file__).parent
        return katrain_dir / "i18n" / "locales"

    NEW_KEYS = [
        "focus:black",
        "focus:white",
        "focus:black-active",
        "focus:white-active",
        "prev-important-move",
        "next-important-move",
        "important-line",
    ]

    def test_all_keys_translated_in_en(self, locale_dir):
        locales = gettext.translation("katrain", str(locale_dir), languages=["en"])
        for key in self.NEW_KEYS:
            translated = locales.gettext(key)
            assert translated != key, f"Key '{key}' is not translated in 'en'"
            assert translated, f"Key '{key}' translates to empty string in 'en'"

    def test_all_keys_translated_in_jp(self, locale_dir):
        locales = gettext.translation("katrain", str(locale_dir), languages=["jp"])
        for key in self.NEW_KEYS:
            translated = locales.gettext(key)
            assert translated != key, f"Key '{key}' is not translated in 'jp'"

    def test_active_focus_keys_have_star_in_en(self, locale_dir):
        """The 'active' variants mark the currently selected focus with a
        star prefix so users see the active toggle at a glance."""
        locales = gettext.translation("katrain", str(locale_dir), languages=["en"])
        assert locales.gettext("focus:black-active").startswith("★")
        assert locales.gettext("focus:white-active").startswith("★")

    def test_active_focus_keys_have_star_in_jp(self, locale_dir):
        locales = gettext.translation("katrain", str(locale_dir), languages=["jp"])
        assert locales.gettext("focus:black-active").startswith("★")
        assert locales.gettext("focus:white-active").startswith("★")

    def test_kv_files_no_longer_hold_hardcoded_japanese(self):
        """board.kv and panels.kv used to ship literal Japanese strings.
        Those literal copies must not come back."""
        from pathlib import Path

        from katrain import __file__ as katrain_init

        kv_dir = Path(katrain_init).parent / "gui" / "kv"
        offenders = []
        for kv_file in ("board.kv", "panels.kv"):
            text = (kv_dir / kv_file).read_text(encoding="utf-8")
            for literal in ("黒優先", "白優先", "前の重要局面", "次の重要局面", "重要局面"):
                # The 'active' variants still contain the prefix (e.g. ★黒優先)
                # but those are now generated dynamically in Python, so a
                # plain "黒優先" or "白優先" literal in the .kv file is a bug.
                if literal in text:
                    offenders.append((kv_file, literal))
        assert not offenders, (
            f"Hardcoded Japanese literals reappeared in .kv files: {offenders}. Use i18n._(...) instead."
        )

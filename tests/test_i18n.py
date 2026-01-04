"""
Tests for i18n translations.

These tests verify that translation keys are properly translated
and don't appear as raw keys in the UI.
"""

import gettext
import os
import pytest
from pathlib import Path


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
                f"Translation for '{key}' should contain '{expected_substring}', "
                f"but got: '{translated}'"
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
                f"MO file for {lang} is older than PO file. "
                f"Run: python Tools/i18n/msgfmt.py -o {mo_file} {po_file}"
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
                assert translated != key, (
                    f"Key '{key}' is not translated in '{lang}' locale"
                )

    def test_skill_auto_key_translated(self, locale_dir):
        """The skill_auto key should be translated in all locales."""
        # All 10 locales
        locales_list = ["en", "jp", "cn", "tw", "ko", "de", "fr", "ru", "tr", "ua"]
        key = "mykatrain:settings:skill_auto"

        for lang in locales_list:
            try:
                locale = gettext.translation("katrain", str(locale_dir), languages=[lang])
                translated = locale.gettext(key)
                assert translated != key, (
                    f"Key '{key}' is not translated in '{lang}' locale"
                )
            except FileNotFoundError:
                pytest.skip(f"Locale '{lang}' not found")

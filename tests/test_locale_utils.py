# -*- coding: utf-8 -*-
"""Tests for katrain/common/locale_utils.py.

Part of Phase 52: Stabilization (tofu fix + jp/ja consistency).
"""
import pytest

from katrain.common.locale_utils import normalize_lang_code, to_iso_lang_code


class TestNormalizeLangCode:
    """Tests for normalize_lang_code function.

    normalize_lang_code returns the internal canonical language code:
    - "en" or "jp" (matching locale directories)
    """

    def test_ja_to_jp(self) -> None:
        """ISO 'ja' should normalize to internal 'jp'."""
        assert normalize_lang_code("ja") == "jp"

    def test_ja_JP_to_jp(self) -> None:
        """Region variant 'ja_JP' should normalize to internal 'jp'."""
        assert normalize_lang_code("ja_JP") == "jp"

    def test_ja_dash_JP_to_jp(self) -> None:
        """Region variant 'ja-JP' should normalize to internal 'jp'."""
        assert normalize_lang_code("ja-JP") == "jp"

    def test_jp_passthrough(self) -> None:
        """Internal 'jp' should pass through unchanged."""
        assert normalize_lang_code("jp") == "jp"

    def test_JP_uppercase(self) -> None:
        """Uppercase 'JP' should normalize to 'jp'."""
        assert normalize_lang_code("JP") == "jp"

    def test_jp_with_whitespace(self) -> None:
        """'jp' with whitespace should normalize to 'jp'."""
        assert normalize_lang_code(" jp ") == "jp"

    def test_en_passthrough(self) -> None:
        """Internal 'en' should pass through unchanged."""
        assert normalize_lang_code("en") == "en"

    def test_en_US_to_en(self) -> None:
        """Region variant 'en_US' should normalize to 'en'."""
        assert normalize_lang_code("en_US") == "en"

    def test_en_dash_GB_to_en(self) -> None:
        """Region variant 'en-GB' should normalize to 'en'."""
        assert normalize_lang_code("en-GB") == "en"

    def test_none_fallback(self) -> None:
        """None should fall back to 'en'."""
        assert normalize_lang_code(None) == "en"

    def test_empty_string_fallback(self) -> None:
        """Empty string should fall back to 'en'."""
        assert normalize_lang_code("") == "en"

    def test_whitespace_only_fallback(self) -> None:
        """Whitespace-only string should fall back to 'en'."""
        assert normalize_lang_code("   ") == "en"

    def test_unknown_lang_fallback(self) -> None:
        """Unknown language codes should fall back to 'en'."""
        assert normalize_lang_code("fr") == "en"
        assert normalize_lang_code("de") == "en"
        assert normalize_lang_code("zh") == "en"
        assert normalize_lang_code("ko") == "en"


class TestToIsoLangCode:
    """Tests for to_iso_lang_code function.

    to_iso_lang_code returns ISO 639-1 language codes:
    - "en" or "ja" (for external APIs like meaning tags registry)
    """

    def test_jp_to_ja(self) -> None:
        """Internal 'jp' should convert to ISO 'ja'."""
        assert to_iso_lang_code("jp") == "ja"

    def test_ja_passthrough(self) -> None:
        """ISO 'ja' should pass through unchanged."""
        assert to_iso_lang_code("ja") == "ja"

    def test_ja_JP_to_ja(self) -> None:
        """Region variant 'ja_JP' should convert to ISO 'ja'."""
        assert to_iso_lang_code("ja_JP") == "ja"

    def test_en_passthrough(self) -> None:
        """'en' should pass through unchanged."""
        assert to_iso_lang_code("en") == "en"

    def test_en_US_to_en(self) -> None:
        """Region variant 'en_US' should normalize to 'en'."""
        assert to_iso_lang_code("en_US") == "en"

    def test_none_fallback(self) -> None:
        """None should fall back to ISO 'en'."""
        assert to_iso_lang_code(None) == "en"

    def test_unknown_lang_fallback(self) -> None:
        """Unknown language codes should fall back to ISO 'en'."""
        assert to_iso_lang_code("fr") == "en"


class TestMeaningTagsBackwardCompatibility:
    """Tests for backward compatibility with meaning_tags normalize_lang.

    The meaning_tags module historically had:
    - normalize_lang("jp") -> "ja"
    - normalize_lang("ja") -> "ja"
    - normalize_lang("en") -> "en"

    This behavior must be preserved via the alias.
    """

    def test_normalize_lang_jp_to_ja(self) -> None:
        """meaning_tags normalize_lang("jp") should still return "ja"."""
        from katrain.core.analysis.meaning_tags.integration import normalize_lang

        assert normalize_lang("jp") == "ja"

    def test_normalize_lang_ja_to_ja(self) -> None:
        """meaning_tags normalize_lang("ja") should still return "ja"."""
        from katrain.core.analysis.meaning_tags.integration import normalize_lang

        assert normalize_lang("ja") == "ja"

    def test_normalize_lang_en_to_en(self) -> None:
        """meaning_tags normalize_lang("en") should still return "en"."""
        from katrain.core.analysis.meaning_tags.integration import normalize_lang

        assert normalize_lang("en") == "en"

    def test_normalize_lang_region_variant(self) -> None:
        """meaning_tags normalize_lang with region variant should work."""
        from katrain.core.analysis.meaning_tags.integration import normalize_lang

        assert normalize_lang("ja_JP") == "ja"
        assert normalize_lang("en_US") == "en"

    def test_normalize_lang_unknown_fallback(self) -> None:
        """meaning_tags normalize_lang with unknown lang should fall back to 'en'."""
        from katrain.core.analysis.meaning_tags.integration import normalize_lang

        assert normalize_lang("fr") == "en"

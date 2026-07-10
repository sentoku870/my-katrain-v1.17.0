"""Regression tests for the Karte error template i18n (Phase G-2).

Phase G-2 introduced :func:`katrain.core.reports.karte.builder._build_error_karte`
that routes the user-facing strings (title, meta header, checklist)
through ``i18n._()`` so the Japanese locale gets a translated error
karte. This test pins the new keys to their expected translations in
both supported locales.
"""

from __future__ import annotations

import gettext
from pathlib import Path

import pytest

from katrain.core.reports.karte.builder import _build_error_karte

# Keys introduced in Phase G-2. The English strings are the historical
# literals that used to be hard-coded in the karte error template.
EXPECTED_TRANSLATIONS = {
    "en": {
        "karte:error:title": "Karte (ERROR)",
        "karte:error:meta_header": "## Meta",
        "karte:error:game_label": "Game",
        "karte:error:player_filter_label": "Player Filter",
        "karte:error:player_filter_both": "both",
        "karte:error:section_title": "## ERROR",
        "karte:error:intro": "Karte generation failed with the following error:",
        "karte:error:checklist_header": "Please check:",
        "karte:error:check_analyzed": "The game has been analyzed (KT property present)",
        "karte:error:check_sgf": "The SGF file is not corrupted",
        "karte:error:check_katago": "KataGo engine is running correctly",
    },
    "jp": {
        "karte:error:title": "カルテ (エラー)",
        "karte:error:meta_header": "## メタ情報",
        "karte:error:game_label": "対局",
        "karte:error:player_filter_label": "プレイヤーフィルター",
        "karte:error:player_filter_both": "両方",
        "karte:error:section_title": "## エラー",
        "karte:error:intro": "カルテ生成中に以下のエラーが発生しました:",
        "karte:error:checklist_header": "以下を確認してください:",
        "karte:error:check_analyzed": "対局が解析済みであるか (KT プロパティが存在するか)",
        "karte:error:check_sgf": "SGF ファイルが破損していないか",
        "karte:error:check_katago": "KataGo エンジンが正常に動作しているか",
    },
}


@pytest.fixture
def locale_dir() -> Path:
    import katrain

    katrain_dir = Path(katrain.__file__).parent
    return katrain_dir / "i18n" / "locales"


class TestKarteErrorKeys:
    @pytest.mark.parametrize("lang,expected_map", list(EXPECTED_TRANSLATIONS.items()))
    def test_keys_translated(self, lang: str, expected_map: dict[str, str], locale_dir: Path) -> None:
        """All Phase G-2 karte-error keys must be translated in both en and jp."""
        catalog = gettext.translation("katrain", str(locale_dir), languages=[lang])
        for key, expected in expected_map.items():
            translated = catalog.gettext(key)
            assert translated != key, f"Key '{key}' missing in '{lang}'"
            assert translated == expected, f"Key '{key}' in '{lang}': expected '{expected}', got '{translated}'"

    def test_jp_keys_are_japanese(self) -> None:
        """Sanity check: the JP translations must actually contain
        Japanese characters (guards against accidentally pasting the
        English literal into the JP catalog)."""
        jp = EXPECTED_TRANSLATIONS["jp"]
        non_ascii_count = sum(1 for v in jp.values() if any(ord(c) > 127 for c in v))
        assert non_ascii_count >= len(jp) - 1, (
            "JP karte-error translations should contain Japanese characters; "
            f"only {non_ascii_count}/{len(jp)} keys are non-ASCII"
        )


class TestBuildErrorKarteUsesI18n:
    """The user-facing strings in :func:`_build_error_karte` must come
    from the i18n catalog, not from hard-coded English literals."""

    def test_contains_i18n_keys_after_compile(self) -> None:
        """Sanity check: the new keys must be in the .po source (this
        catches accidental deletion of one of the keys)."""
        repo_root = Path(__file__).resolve().parent.parent
        en_po = (repo_root / "katrain/i18n/locales/en/LC_MESSAGES/katrain.po").read_text(encoding="utf-8")
        for key in EXPECTED_TRANSLATIONS["en"]:
            assert key in en_po, f"key '{key}' missing from en .po source"

    def test_uses_i18n_call(self) -> None:
        """Source-level: ``_build_error_karte`` must use ``i18n._()``.

        The implementation imports the lang module and routes every
        literal through ``i18n._(<key>)``. This guards against
        regressions where someone pastes a raw English string back in.
        """
        import inspect

        from katrain.core.reports.karte import builder

        source = inspect.getsource(builder._build_error_karte)
        # The function must import i18n and call it for every label.
        assert "from katrain.core.lang import i18n" in source
        # The source uses both single- and double-quoted f-strings;
        # accept either style to stay robust to the formatter.
        assert "karte:error:title" in source and "i18n._(" in source
        assert "karte:error:intro" in source
        # The old hard-coded English strings must NOT appear in source.
        for literal in [
            "Karte generation failed with the following error:",
            "The game has been analyzed (KT property present)",
            "The SGF file is not corrupted",
            "KataGo engine is running correctly",
        ]:
            assert literal not in source, (
                f"_build_error_karte still has the hard-coded literal {literal!r}; use i18n._() instead."
            )

    def test_player_filter_both_uses_i18n(self) -> None:
        """``player_filter=None`` must fall back to the localised 'both'."""
        karte = _build_error_karte("game_001", None, "boom")
        # The default catalog entry is the English literal.
        assert "Player Filter: both" in karte

"""
Tests for i18n translations.

These tests verify that translation keys are properly translated
and don't appear as raw keys in the UI.
"""

import gettext
import os
import tempfile
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
        """Compiled ``.mo`` files must match what ``polib`` would rebuild.

        The legacy mtime comparison was unreliable on fresh checkouts
        (git does not preserve mtimes, so a stale ``.mo`` would pass).
        Compare the on-disk ``.mo`` bytes against the bytes produced
        by ``polib.pofile(...).save_as_mofile(...)`` so any drift is
        caught regardless of timestamps.
        """
        import polib

        for lang in ["en", "jp"]:
            po_file = locale_dir / lang / "LC_MESSAGES" / "katrain.po"
            mo_file = locale_dir / lang / "LC_MESSAGES" / "katrain.mo"

            assert po_file.exists(), f"PO file not found: {po_file}"
            assert mo_file.exists(), f"MO file not found: {mo_file}"

            with tempfile.NamedTemporaryFile(suffix=".mo", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                polib.pofile(str(po_file)).save_as_mofile(tmp_path)
                rebuilt = Path(tmp_path).read_bytes()
            finally:
                os.unlink(tmp_path)

            current = mo_file.read_bytes()
            assert rebuilt == current, (
                f"MO file for {lang} is out of sync with its PO source. "
                f"Recompile with:\n"
                f'    python -c "import polib; '
                f"polib.pofile('{po_file}').save_as_mofile('{mo_file}')\"\n"
                f"or run the workflow's Verify i18n step in "
                f"docs/i18n-workflow.md."
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


# ---------------------------------------------------------------------------
# Phase 248-B1: important-moves level (3 keys)
# ---------------------------------------------------------------------------


class TestImportantMovesLevelI18n:
    """Phase 248-B1: analysis tab now exposes the important-moves level
    via a 3-radio group. Lock down the i18n keys so any future
    regression (e.g. someone hardcodes a label in the radio group)
    is caught at the i18n layer.
    """

    @pytest.fixture
    def locale_dir(self):
        from pathlib import Path

        import katrain

        katrain_dir = Path(katrain.__file__).parent
        return katrain_dir / "i18n" / "locales"

    NEW_KEYS = [
        "mykatrain:settings:important_moves_level",
        "mykatrain:settings:important_moves_level_desc",
        "mykatrain:settings:important_moves_level_easy",
        "mykatrain:settings:important_moves_level_normal",
        "mykatrain:settings:important_moves_level_strict",
        # Phase 248-B2: critical_3 selection count
        "mykatrain:settings:critical_3_max_moves",
        "mykatrain:settings:critical_3_max_moves_desc",
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

    def test_mo_files_are_up_to_date(self, locale_dir):
        """Same byte-level comparison as :class:`TestBatchAnalyzeI18n.test_mo_files_are_up_to_date`,
        scoped to the new keys.

        Relies on the canonical ``polib`` rebuild rather than mtime
        so the check survives fresh clones and parallel CI clones.
        """
        import polib

        for lang in ("en", "jp"):
            po = locale_dir / lang / "LC_MESSAGES" / "katrain.po"
            mo = locale_dir / lang / "LC_MESSAGES" / "katrain.mo"
            if not po.exists() or not mo.exists():
                pytest.skip(f"Missing po/mo for {lang}")
            with tempfile.NamedTemporaryFile(suffix=".mo", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                polib.pofile(str(po)).save_as_mofile(tmp_path)
                rebuilt = Path(tmp_path).read_bytes()
            finally:
                os.unlink(tmp_path)
            current = mo.read_bytes()
            if rebuilt != current:
                pytest.fail(
                    f"{lang}/katrain.mo is out of sync with katrain.po. "
                    f"Run `polib.pofile('{po}').save_as_mofile('{mo}')` to refresh."
                )

    def test_active_focus_keys_have_star_in_en(self, locale_dir):
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


# ---------------------------------------------------------------------------
# Phase 250: i18n cleanup — no duplicate msgids, no orphan radar:* keys
# ---------------------------------------------------------------------------


def _parse_po_msgids(po_path: Path) -> list[str]:
    """Return the ordered list of msgids in a .po file (header excluded).

    Used by Phase 250 duplicate-detection tests. Pure-Python parser so
    no external dependencies (polib / babel) are required to run the test.
    """
    import re

    text = po_path.read_text(encoding="utf-8")
    quoted_re = re.compile(r'"((?:[^"\\]|\\.)*)"')
    msgids: list[str] = []
    cur: list[str] = []
    in_msgid = False
    for line in text.splitlines():
        if not in_msgid:
            if line.startswith("msgid "):
                in_msgid = True
                m = quoted_re.search(line)
                cur = [m.group(1) if m else ""]
        else:
            if line.startswith("msgstr"):
                full = "".join(cur)
                if full:  # skip header (empty msgid)
                    msgids.append(full)
                in_msgid = False
                cur = []
            elif line.startswith('"'):
                m = quoted_re.search(line)
                if m:
                    cur.append(m.group(1))
            elif line.strip() == "":
                in_msgid = False
                cur = []
    return msgids


class TestPhase250I18nCleanup:
    """Phase 250: regression tests for the i18n cleanup.

    Two structural issues were fixed in Phase 250:

    1. **Duplicate msgids** in both jp.po and en.po for
       ``mistake:good``, ``mistake:inaccuracy``, ``mistake:mistake``,
       ``mistake:blunder``, ``summary:table:avg_loss``. gettext
       returns the first occurrence only, so the second copy was
       silently shadowing the first. These tests pin the set to
       exactly one entry per key.

    2. **Orphan ``radar:*`` keys** in en.po (21 entries, 0 hits in
       source). The radar feature was removed in Phase 86; only the
       en translations were cleaned up at the time, leaving a
       21-key JP/EN asymmetry. These tests pin the set parity.

    Both classes of bug are silent (no runtime error, just wrong
    translations) so explicit regression tests are warranted.
    """

    @pytest.fixture
    def locale_dir(self):
        from pathlib import Path

        import katrain

        katrain_dir = Path(katrain.__file__).parent
        return katrain_dir / "i18n" / "locales"

    # Keys that USED to be duplicated; if a future change reintroduces
    # a duplicate, this test catches it at the .po level.
    DUPLICATE_KEYS = [
        "mistake:good",
        "mistake:inaccuracy",
        "mistake:mistake",
        "mistake:blunder",
        "summary:table:avg_loss",
    ]

    # Orphan keys (removed in Phase 250). Locked-down so a future
    # re-introduction (e.g. via an outdated .po merge) is caught.
    ORPHAN_RADAR_KEYS = [
        "radar:axis-awareness",
        "radar:axis-endgame",
        "radar:axis-fighting",
        "radar:axis-opening",
        "radar:axis-stability",
        "radar:build-error",
        "radar:calc-error",
        "radar:insufficient-moves",
        "radar:menu-title",
        "radar:no-data",
        "radar:no-game",
        "radar:not-19x19",
        "radar:overall",
        "radar:tier-1",
        "radar:tier-2",
        "radar:tier-3",
        "radar:tier-4",
        "radar:tier-5",
        "radar:tier-unknown",
        "radar:title",
        "radar:weak-areas",
    ]

    def _duplicates(self, msgids: list[str]) -> dict[str, int]:
        from collections import Counter

        return {k: c for k, c in Counter(msgids).items() if c > 1}

    def test_jp_po_has_no_duplicate_msgids(self, locale_dir):
        """jp.po must not contain duplicate msgids.

        Previously had 5 duplicates (mistake:*, summary:table:avg_loss).
        See ``docs/ideas/phase250-hint-feature-audit.md`` I-1.
        """
        po = locale_dir / "jp" / "LC_MESSAGES" / "katrain.po"
        assert po.exists()
        msgids = _parse_po_msgids(po)
        dupes = self._duplicates(msgids)
        assert not dupes, (
            f"jp.po contains duplicate msgids (gettext returns the first only): {dupes}. "
            f"Known offenders: {self.DUPLICATE_KEYS}. See Phase 250 I-1."
        )

    def test_en_po_has_no_duplicate_msgids(self, locale_dir):
        """en.po must not contain duplicate msgids.

        Same 5 keys were duplicated in en.po. See Phase 250 I-1.
        """
        po = locale_dir / "en" / "LC_MESSAGES" / "katrain.po"
        assert po.exists()
        msgids = _parse_po_msgids(po)
        dupes = self._duplicates(msgids)
        assert not dupes, f"en.po contains duplicate msgids: {dupes}. Known offenders: {self.DUPLICATE_KEYS}."

    def test_en_po_has_no_orphan_radar_keys(self, locale_dir):
        """en.po must not contain radar:* keys (feature removed in Phase 86).

        See Phase 250 I-2. JP never had these keys; only en.po retained
        them as dead translations.
        """
        po = locale_dir / "en" / "LC_MESSAGES" / "katrain.po"
        msgids = _parse_po_msgids(po)
        radar = [m for m in msgids if m.startswith("radar:")]
        assert not radar, f"en.po contains orphan radar:* keys (feature removed Phase 86): {radar}. See Phase 250 I-2."

    def test_jp_en_msgid_set_parity(self, locale_dir):
        """jp.po and en.po must contain the exact same set of msgids.

        Phase 250 I-2: en.po had 21 extra radar:* keys. This test prevents
        future drift between the two locale files.
        """
        jp_ids = set(_parse_po_msgids(locale_dir / "jp" / "LC_MESSAGES" / "katrain.po"))
        en_ids = set(_parse_po_msgids(locale_dir / "en" / "LC_MESSAGES" / "katrain.po"))
        only_jp = jp_ids - en_ids
        only_en = en_ids - jp_ids
        assert not only_jp and not only_en, (
            f"msgid set parity broken: only_jp={sorted(only_jp)[:5]}, only_en={sorted(only_en)[:5]}."
        )

    def test_duplicate_keys_still_translated_once(self, locale_dir):
        """The 5 formerly-duplicated keys must still resolve to a non-empty
        string in both languages (we kept the first occurrence)."""
        for lang in ("en", "jp"):
            locales = gettext.translation("katrain", str(locale_dir), languages=[lang])
            for key in self.DUPLICATE_KEYS:
                translated = locales.gettext(key)
                assert translated and translated != key, (
                    f"Key '{key}' is not translated in '{lang}' after Phase 250 cleanup"
                )

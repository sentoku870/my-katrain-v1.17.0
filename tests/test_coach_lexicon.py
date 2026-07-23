"""Phase 208: Tests for katrain.core.coach.lexicon.

Covers:
- YAML parsing (entries + concepts)
- LexiconEntry / LexiconConcept dataclass construction
- Lookup by id
- Filter helpers (by_level, by_category)
- Reference integrity (validate_references)
- inject_lexicon_for_prompt rendering
- Caching behaviour

No Kivy — pure core-layer tests. The tests assume the canonical YAML at
``docs/resources/go_lexicon_master_last.yaml`` is present.
"""

from __future__ import annotations

from katrain.core.coach.lexicon import (
    DEFAULT_LEXICON_PATH,
    LexiconBundle,
    LexiconConcept,
    LexiconEntry,
    all_ids,
    entries_by_category,
    entries_by_level,
    get_concept,
    get_entry,
    inject_lexicon_for_prompt,
    load_lexicon,
    validate_references,
)

# --- YAML file presence ---


class TestLexiconPath:
    def test_default_path_exists(self):
        assert DEFAULT_LEXICON_PATH.exists(), f"Canonical YAML not found at {DEFAULT_LEXICON_PATH}"

    def test_default_path_is_yaml(self):
        assert DEFAULT_LEXICON_PATH.suffix == ".yaml"


# --- Bundle construction ---


class TestLoadLexicon:
    def test_returns_bundle(self):
        bundle = load_lexicon()
        assert isinstance(bundle, LexiconBundle)

    def test_schema_version(self):
        bundle = load_lexicon()
        assert bundle.schema_version == "go_lexicon_master_v1"

    def test_entry_count_matches_validation_report(self):
        # Phase 242-C: +5 L2 entries (116 -> 121). Phase 244: +3 L1/L2
        # entries (overplay / endgame_sente / star_point) bring the
        # total to 124.
        # go_lexicon_validation_report_updated.md reports the
        # original 116 entries; the 5 added by Phase 242-C are
        # time_management / ai_overload / post_game_review /
        # tilt_recovery / mental_state.
        bundle = load_lexicon()
        assert len(bundle.entries) == 124
        assert len(bundle.concepts) == 23

    def test_all_entries_are_dataclass(self):
        bundle = load_lexicon()
        for e in bundle.entries:
            assert isinstance(e, LexiconEntry)

    def test_all_concepts_are_dataclass(self):
        bundle = load_lexicon()
        for c in bundle.concepts:
            assert isinstance(c, LexiconConcept)

    def test_entry_levels_are_1_or_2(self):
        bundle = load_lexicon()
        for e in bundle.entries:
            assert e.level in (1, 2)

    def test_concept_levels_are_3(self):
        bundle = load_lexicon()
        for c in bundle.concepts:
            assert c.level == 3


# --- Field population ---


class TestEntryFields:
    def test_required_fields_populated(self):
        bundle = load_lexicon()
        for e in bundle.entries:
            assert e.id
            assert e.ja_term
            assert e.ja_one_liner
            assert e.en_one_liner
            assert e.ja_short
            assert e.en_short
            assert len(e.pitfalls) >= 1
            assert len(e.recognize_by) >= 1
            assert len(e.related_ids) >= 1
            assert len(e.sources) >= 2, f"validation report requires 2-4 sources, got {len(e.sources)} for {e.id}"

    def test_no_duplicate_ids(self):
        bundle = load_lexicon()
        ids = [e.id for e in bundle.entries]
        assert len(ids) == len(set(ids)), f"Duplicate ids: {[i for i in ids if ids.count(i) > 1]}"

    def test_known_entry_samples(self):
        # Spot-check representative entries (per validation report).
        assert get_entry("liberty") is not None
        assert get_entry("liberty").ja_term == "呼吸点"
        assert get_entry("atari") is not None
        assert get_entry("capture") is not None


class TestConceptFields:
    def test_required_concept_fields(self):
        bundle = load_lexicon()
        for c in bundle.concepts:
            assert c.id
            assert c.ja_title
            assert c.en_title
            assert c.ja_expanded
            assert c.en_expanded

    def test_known_concept_sample(self):
        c = get_concept("urgent_vs_big")
        assert c is not None
        assert c.ja_title == "急場と大場の判断"
        assert len(c.decision_checklist) >= 1


# --- Lookup / filter helpers ---


class TestLookup:
    def test_get_entry_existing(self):
        e = get_entry("liberty")
        assert e is not None
        assert e.id == "liberty"

    def test_get_entry_missing_returns_none(self):
        assert get_entry("definitely_not_an_entry_xxx") is None

    def test_get_concept_existing(self):
        c = get_concept("urgent_vs_big")
        assert c is not None
        assert c.id == "urgent_vs_big"

    def test_entries_by_level(self):
        lv1 = entries_by_level(1)
        lv2 = entries_by_level(2)
        assert len(lv1) >= 50  # validation report says 60
        assert len(lv2) >= 40  # validation report says 56
        for e in lv1:
            assert e.level == 1
        for e in lv2:
            assert e.level == 2

    def test_entries_by_category(self):
        rules = entries_by_category("rules")
        assert len(rules) >= 1
        for e in rules:
            assert e.category == "rules"

    def test_entries_by_category_unknown(self):
        assert entries_by_category("nonexistent_category_xyz") == []


# --- validate_references ---


class TestValidateReferences:
    def test_no_broken_refs(self):
        # validation report (2025-12-24) confirms broken_refs == 0
        report = validate_references()
        assert report["broken_refs"] == 0, f"Broken refs: {report['broken_ref_samples']}"

    def test_no_duplicate_ids(self):
        report = validate_references()
        assert report["duplicate_ids"] == []

    def test_counts_match(self):
        # Phase 242-C: 5 new L2 entries (time_management / ai_overload /
        # post_game_review / tilt_recovery / mental_state) bring the
        # total to 121. Phase 244: +3 L1/L2 entries (overplay /
        # endgame_sente / star_point) bring the total to 124.
        report = validate_references()
        assert report["total_entries"] == 124
        assert report["total_concepts"] == 23

    def test_level_distribution(self):
        # Phase 242-C: 5 new level-2 entries shift the L2 count.
        # Phase 244: +1 L1 (star_point) and +2 L2 (overplay,
        # endgame_sente) shift the distribution further.
        report = validate_references()
        assert report["level_distribution"]["1"] == 61
        assert report["level_distribution"]["2"] == 63
        assert report["level_distribution"]["3"] == 23


# --- inject_lexicon_for_prompt ---


class TestInjectLexicon:
    def test_renders_known_entry(self):
        snippet = inject_lexicon_for_prompt(["liberty"])
        assert "呼吸点" in snippet
        assert "石に隣接する空点" in snippet
        assert "【呼吸点 (liberty)】" in snippet

    def test_renders_multiple_entries(self):
        snippet = inject_lexicon_for_prompt(["liberty", "capture", "atari"])
        assert "呼吸点" in snippet
        assert "石を取る" in snippet or "相手の石" in snippet
        assert "アタリ" in snippet

    def test_skip_missing_ids_silently(self):
        snippet = inject_lexicon_for_prompt(["liberty", "does_not_exist_xyz"])
        assert "呼吸点" in snippet
        assert "does_not_exist_xyz" not in snippet

    def test_include_expanded_toggle(self):
        short = inject_lexicon_for_prompt(["overplay"], include_expanded=False)
        long = inject_lexicon_for_prompt(["overplay"], include_expanded=True)
        assert len(long) >= len(short)

    def test_empty_input(self):
        snippet = inject_lexicon_for_prompt([])
        assert snippet == ""


class TestPhase244LexiconExtension:
    """Phase 244: concepts-only IDs and 3 new entries.

    - ``inject_lexicon_for_prompt`` should accept concept IDs
      (Phase 244 fix: previously entries-only)
    - New entries: overplay, endgame_sente, star_point
    """

    def test_renders_concept_only_id(self):
        # urgent_vs_big lives in concepts (Lv3), not entries
        snippet = inject_lexicon_for_prompt(["urgent_vs_big"])
        assert "急場" in snippet or "urgent" in snippet.lower()
        assert "【" in snippet  # has the 【...】 block marker

    def test_renders_mixed_entry_and_concept(self):
        snippet = inject_lexicon_for_prompt(["liberty", "urgent_vs_big", "direction_of_play"])
        assert "呼吸点" in snippet
        assert "急場" in snippet or "方向" in snippet

    def test_new_overplay_entry(self):
        bundle = load_lexicon(DEFAULT_LEXICON_PATH)
        entry = bundle.entry_by_id.get("overplay")
        assert entry is not None
        assert entry.ja_term == "オーバープレイ"
        assert "overplay" in [t.lower() for t in entry.en_terms]
        assert "thickness" in entry.related_ids

    def test_new_endgame_sente_entry(self):
        bundle = load_lexicon(DEFAULT_LEXICON_PATH)
        entry = bundle.entry_by_id.get("endgame_sente")
        assert entry is not None
        assert entry.ja_term == "ヨセのセンテ"
        # endgame_sente references the related concept endgame_sente_value
        # (the broader Lv3 concept) and the L1 entries yose / counting.
        assert "endgame_sente_value" in entry.related_ids
        assert "yose" in entry.related_ids

    def test_new_star_point_entry(self):
        bundle = load_lexicon(DEFAULT_LEXICON_PATH)
        entry = bundle.entry_by_id.get("star_point")
        assert entry is not None
        assert entry.ja_term == "星"
        assert "komoku" in entry.related_ids

    def test_inject_overplay_renders(self):
        snippet = inject_lexicon_for_prompt(["overplay"])
        assert "オーバープレイ" in snippet
        assert "【オーバープレイ (overplay)】" in snippet

    def test_concept_id_missing_fields_uses_concept_format(self):
        # Concepts have no ja_term/ja_short/ja_pitfalls — they use
        # ja_title / ja_one_liner / ja_expanded. The injector should
        # handle this gracefully.
        snippet = inject_lexicon_for_prompt(["whole_board_balance"])
        assert "【" in snippet
        assert "定義" in snippet  # at minimum, the 定義: line should be present


# --- all_ids ---


class TestAllIds:
    def test_all_ids_returns_tuple(self):
        ids = all_ids()
        assert isinstance(ids, tuple)
        # Phase 242-C: +5 L2 entries. Phase 244: +3 L1/L2 entries.
        assert len(ids) == 124 + 23


# --- Public API ---

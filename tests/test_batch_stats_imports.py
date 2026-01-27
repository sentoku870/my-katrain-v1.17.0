"""Backward compatibility tests for stats package split (Phase 71).

These tests verify that all public and semi-public symbols remain
importable from katrain.core.batch.stats after the package split.

IMPORTANT: These tests must PASS on the current stats.py before refactoring.
They do NOT depend on __all__ (which stats.py does not define).
"""

import pytest
from collections.abc import Mapping
from dataclasses import fields, is_dataclass


class TestStatsModuleImports:
    """Verify all expected symbols are importable from the current module."""

    def test_module_import(self):
        """Module can be imported as stats_mod."""
        import katrain.core.batch.stats as stats_mod
        assert stats_mod is not None

    def test_public_functions_importable(self):
        """All 4 public functions are importable and callable."""
        from katrain.core.batch.stats import (
            extract_game_stats,
            build_batch_summary,
            extract_players_from_stats,
            build_player_summary,
        )
        assert callable(extract_game_stats)
        assert callable(build_batch_summary)
        assert callable(extract_players_from_stats)
        assert callable(build_player_summary)

    def test_evidence_dataclass_importable(self):
        """EvidenceMove dataclass is importable and is a dataclass."""
        from katrain.core.batch.stats import EvidenceMove
        assert is_dataclass(EvidenceMove)

    def test_private_functions_importable(self):
        """Private functions used by tests are importable and callable."""
        from katrain.core.batch.stats import (
            _select_evidence_moves,
            _format_evidence_with_links,
            _build_skill_profile_section,
            _build_radar_json_section,
        )
        assert callable(_select_evidence_moves)
        assert callable(_format_evidence_with_links)
        assert callable(_build_skill_profile_section)
        assert callable(_build_radar_json_section)

    def test_constants_importable(self):
        """Constants used by tests are importable and are Mappings."""
        from katrain.core.batch.stats import (
            TIER_LABELS,
            AXIS_LABELS,
            AXIS_PRACTICE_HINTS,
        )
        assert isinstance(TIER_LABELS, Mapping)
        assert isinstance(AXIS_LABELS, Mapping)
        assert isinstance(AXIS_PRACTICE_HINTS, Mapping)

    def test_backward_compat_aliases_exist(self):
        """Backward compatibility aliases exist and point to same functions."""
        from katrain.core.batch.stats import (
            _extract_game_stats,
            _build_batch_summary,
            _extract_players_from_stats,
            _build_player_summary,
            extract_game_stats,
            build_batch_summary,
            extract_players_from_stats,
            build_player_summary,
        )
        assert _extract_game_stats is extract_game_stats
        assert _build_batch_summary is build_batch_summary
        assert _extract_players_from_stats is extract_players_from_stats
        assert _build_player_summary is build_player_summary


class TestEvidenceMoveDataclassShape:
    """Verify EvidenceMove dataclass shape using dataclasses.fields().

    Note: We intentionally avoid type assertions because:
    - __future__.annotations can make field.type a string
    - Forward references like "MistakeCategory" may not resolve

    High-value checks: field names, field order, is_dataclass, frozen.
    """

    def test_evidence_move_field_names_and_order(self):
        """EvidenceMove has exactly the expected field names in order."""
        from katrain.core.batch.stats import EvidenceMove

        field_names = [f.name for f in fields(EvidenceMove)]
        expected = [
            "game_name",
            "move_number",
            "player",
            "gtp",
            "points_lost",
            "mistake_category",
        ]
        assert field_names == expected, f"Fields mismatch: {field_names}"

    def test_evidence_move_is_frozen(self):
        """EvidenceMove is immutable (frozen=True)."""
        from katrain.core.batch.stats import EvidenceMove
        assert EvidenceMove.__dataclass_params__.frozen is True

    def test_evidence_move_field_count(self):
        """EvidenceMove has exactly 6 fields."""
        from katrain.core.batch.stats import EvidenceMove
        assert len(fields(EvidenceMove)) == 6


class TestSymbolsAvailableViaHasattr:
    """Verify symbols are accessible via hasattr (no __all__ dependency)."""

    def test_all_required_symbols_accessible(self):
        """All required symbols are accessible via getattr."""
        import katrain.core.batch.stats as stats_mod

        required_symbols = [
            # Public API
            "extract_game_stats",
            "build_batch_summary",
            "extract_players_from_stats",
            "build_player_summary",
            "EvidenceMove",
            # Constants used by tests
            "TIER_LABELS",
            "AXIS_LABELS",
            "AXIS_PRACTICE_HINTS",
            # Private functions used by tests
            "_select_evidence_moves",
            "_format_evidence_with_links",
            "_build_skill_profile_section",
            "_build_radar_json_section",
            # Backward compat aliases
            "_extract_game_stats",
            "_build_batch_summary",
            "_extract_players_from_stats",
            "_build_player_summary",
            # i18n getter functions
            "get_phase_priority_text",
            "get_phase_label_localized",
            "get_section_header",
            "get_practice_intro_text",
            "get_notes_header",
            "get_axis_practice_hint",
            "get_mtag_practice_hint",
            "get_rtag_practice_hint",
            "format_hint_line",
            "get_percentage_note",
            "get_color_bias_note",
            # Helper functions
            "detect_color_bias",
            "get_dominant_tags",
            "build_tag_based_hints",
        ]

        missing = [s for s in required_symbols if not hasattr(stats_mod, s)]
        assert not missing, f"Missing symbols: {missing}"


class TestI18nGettersSemanticBehavior:
    """Verify i18n getter functions with semantic assertions.

    Avoid hard-coded exact strings - test behavior patterns instead.
    """

    def test_phase_label_returns_str_for_known_phases(self):
        """get_phase_label_localized returns str for known phase keys."""
        from katrain.core.batch.stats import get_phase_label_localized

        for phase in ["opening", "middle", "yose"]:
            for lang in ["jp", "en"]:
                result = get_phase_label_localized(phase, lang)
                assert isinstance(result, str), f"Expected str for {phase}/{lang}"
                assert len(result) > 0, f"Expected non-empty for {phase}/{lang}"

    def test_phase_label_jp_differs_from_en(self):
        """Japanese and English labels differ for at least one phase."""
        from katrain.core.batch.stats import get_phase_label_localized

        # At least one phase should have different jp vs en labels
        differences = []
        for phase in ["opening", "middle", "yose"]:
            jp = get_phase_label_localized(phase, "jp")
            en = get_phase_label_localized(phase, "en")
            if jp != en:
                differences.append(phase)

        assert len(differences) > 0, "Expected jp != en for at least one phase"

    def test_unknown_phase_returns_fallback(self):
        """Unknown phase key returns the key itself (fallback, no crash)."""
        from katrain.core.batch.stats import get_phase_label_localized

        unknown_key = "nonexistent_phase_xyz"
        result = get_phase_label_localized(unknown_key, "jp")
        # Should return the key itself as fallback, not crash
        assert isinstance(result, str)
        assert result == unknown_key or len(result) > 0

    def test_section_header_returns_str(self):
        """get_section_header returns str for known section keys."""
        from katrain.core.batch.stats import get_section_header

        # Test a few known section keys
        for key in ["skill_profile", "practice_priorities"]:
            for lang in ["jp", "en"]:
                result = get_section_header(key, lang)
                assert isinstance(result, str), f"Expected str for {key}/{lang}"

    def test_section_header_jp_differs_from_en(self):
        """Japanese and English section headers differ."""
        from katrain.core.batch.stats import get_section_header

        jp = get_section_header("skill_profile", "jp")
        en = get_section_header("skill_profile", "en")
        # They should be different
        assert jp != en, "Expected different headers for jp vs en"

    def test_language_not_frozen_at_import(self):
        """Verify translations are not frozen at import time.

        Call with jp first, then en - results should differ.
        This ensures translations are looked up at call time.
        """
        from katrain.core.batch.stats import get_phase_label_localized

        # Call with jp first
        jp_first = get_phase_label_localized("opening", "jp")
        # Then call with en
        en_second = get_phase_label_localized("opening", "en")
        # Call jp again to verify it's not cached as en
        jp_third = get_phase_label_localized("opening", "jp")

        # jp_first and jp_third should be equal
        assert jp_first == jp_third, "jp result should be consistent"
        # jp and en should differ
        assert jp_first != en_second, "jp and en should differ"

    def test_i18n_getters_are_callable(self):
        """All i18n getter functions are callable."""
        from katrain.core.batch.stats import (
            get_phase_priority_text,
            get_phase_label_localized,
            get_section_header,
            get_practice_intro_text,
            get_notes_header,
            get_axis_practice_hint,
            get_mtag_practice_hint,
            get_rtag_practice_hint,
            format_hint_line,
            get_percentage_note,
            get_color_bias_note,
        )

        assert callable(get_phase_priority_text)
        assert callable(get_phase_label_localized)
        assert callable(get_section_header)
        assert callable(get_practice_intro_text)
        assert callable(get_notes_header)
        assert callable(get_axis_practice_hint)
        assert callable(get_mtag_practice_hint)
        assert callable(get_rtag_practice_hint)
        assert callable(format_hint_line)
        assert callable(get_percentage_note)
        assert callable(get_color_bias_note)

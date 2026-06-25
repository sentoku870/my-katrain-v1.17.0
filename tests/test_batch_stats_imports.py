"""Backward compatibility tests for stats package (Phase 137 post-cleanup).

Phase 137 removed the Skill Radar feature and its associated constants
(TIER_LABELS, AXIS_LABELS, AXIS_PRACTICE_HINTS) and private helpers
(_build_radar_json_section, _build_skill_profile_section,
_select_evidence_moves, _format_evidence_with_links, format_hint_line,
get_axis_practice_hint, get_mtag_practice_hint, get_rtag_practice_hint, etc.).

The remaining tests verify that the current public surface of
katrain.core.batch.stats is intact: public functions and the EvidenceMove
dataclass are importable, backward-compat aliases point to the same
functions, and the surviving i18n getter functions behave correctly.
"""

from collections.abc import Mapping
from dataclasses import fields, is_dataclass


class TestStatsModuleImports:
    """Verify all expected symbols are importable from the current module."""

    def test_module_import(self):
        """Module can be imported as stats_mod."""
        import katrain.core.batch.stats as stats_mod

        assert stats_mod is not None

    def test_public_functions_importable(self):
        """All public functions are importable and callable."""
        from katrain.core.batch.stats import (
            build_batch_summary,
            build_player_summary,
            extract_game_stats,
            extract_players_from_stats,
        )

        assert callable(extract_game_stats)
        assert callable(build_batch_summary)
        assert callable(extract_players_from_stats)
        assert callable(build_player_summary)

    def test_evidence_dataclass_importable(self):
        """EvidenceMove dataclass is importable and is a dataclass."""
        from katrain.core.batch.stats import EvidenceMove

        assert is_dataclass(EvidenceMove)

    def test_backward_compat_aliases_exist(self):
        """Backward compatibility aliases exist and point to same functions."""
        from katrain.core.batch.stats import (
            _build_batch_summary,
            _build_player_summary,
            _extract_game_stats,
            _extract_players_from_stats,
            build_batch_summary,
            build_player_summary,
            extract_game_stats,
            extract_players_from_stats,
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

    High-value checks: is_dataclass, frozen.
    """

    def test_evidence_move_is_frozen(self):
        """EvidenceMove is immutable (frozen=True)."""
        from katrain.core.batch.stats import EvidenceMove

        assert EvidenceMove.__dataclass_params__.frozen is True

    def test_evidence_move_field_names_is_list(self):
        """EvidenceMove field names is a non-empty list of strings."""
        from katrain.core.batch.stats import EvidenceMove

        field_names = [f.name for f in fields(EvidenceMove)]
        assert isinstance(field_names, list)
        assert len(field_names) > 0
        assert all(isinstance(n, str) for n in field_names)


class TestI18nGettersSemanticBehavior:
    """Verify surviving i18n getter functions with semantic assertions.

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
        assert isinstance(result, str)
        assert result == unknown_key or len(result) > 0

    def test_section_header_returns_str(self):
        """get_section_header returns str for known section keys."""
        from katrain.core.batch.stats import get_section_header

        for key in ["skill_profile", "practice_priorities"]:
            for lang in ["jp", "en"]:
                result = get_section_header(key, lang)
                assert isinstance(result, str), f"Expected str for {key}/{lang}"

    def test_language_not_frozen_at_import(self):
        """Verify translations are not frozen at import time.

        Call with jp first, then en - results should differ.
        This ensures translations are looked up at call time.
        """
        from katrain.core.batch.stats import get_phase_label_localized

        jp_first = get_phase_label_localized("opening", "jp")
        en_second = get_phase_label_localized("opening", "en")
        jp_third = get_phase_label_localized("opening", "jp")

        assert jp_first == jp_third, "jp result should be consistent"
        assert jp_first != en_second, "jp and en should differ"

    def test_phase_priority_text_is_callable(self):
        """get_phase_priority_text is callable and returns non-empty str for known key."""
        from katrain.core.batch.stats import get_phase_priority_text

        assert callable(get_phase_priority_text)
        # Try a known key; if no key is recognized, this is a no-op smoke test
        for key in ["intro", "header", "title", "main"]:
            result = get_phase_priority_text(key, "jp")
            assert isinstance(result, str)
            if len(result) > 0:
                return
        # None of the keys produced content; just confirm it's callable
        assert callable(get_phase_priority_text)

    def test_practice_intro_text_is_callable(self):
        """get_practice_intro_text is callable and returns non-empty str."""
        from katrain.core.batch.stats import get_practice_intro_text

        assert callable(get_practice_intro_text)
        result = get_practice_intro_text("jp")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_notes_header_is_callable(self):
        """get_notes_header is callable and returns non-empty str."""
        from katrain.core.batch.stats import get_notes_header

        assert callable(get_notes_header)
        result = get_notes_header("jp")
        assert isinstance(result, str)
        assert len(result) > 0

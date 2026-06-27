"""Backward compatibility tests for stats package.

Phase 149 C-4: Removed i18n getter tests (dead code removed).
Remaining tests verify the current public surface of
katrain.core.batch.stats is intact.
"""

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
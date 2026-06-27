"""Tests for Phase 149 Sub-phase A bug fixes.

Covers:
- A-1: _generate_karte_for_file passes skill_preset to build_karte_report
- A-2: karte_export.py dynamic i18n key construction is fixed
- A-3: karte_export.py "Failed to save karte" uses i18n
- A-4: RELIABILITY_VISITS_THRESHOLD is no longer duplicated in reports.constants
- A-5: SummaryAnalyzer.worst_moves is truncated to top 10
- A-6: extractors.py Komi fallback uses except ValueError
- A-8: builder.py _build_karte_report_impl has no unused local vars
"""

from __future__ import annotations

import inspect
import json
from unittest.mock import MagicMock

import pytest


class TestA1SkillPresetInBatchKarte:
    """A-1: _generate_karte_for_file should accept and forward skill_preset."""

    def test_signature_accepts_skill_preset(self):
        from katrain.core.batch.orchestration import _generate_karte_for_file

        sig = inspect.signature(_generate_karte_for_file)
        assert "skill_preset" in sig.parameters

    def test_signature_skill_preset_optional(self):
        from katrain.core.batch.orchestration import _generate_karte_for_file

        sig = inspect.signature(_generate_karte_for_file)
        param = sig.parameters["skill_preset"]
        assert param.default is None

    def test_call_site_passes_skill_preset(self):
        """The call site in _process_single_file should forward skill_preset."""
        from katrain.core.batch import orchestration

        src = inspect.getsource(orchestration._process_single_file)
        assert "skill_preset=ctx.skill_preset" in src

    def test_build_karte_report_called_with_skill_preset(self):
        """_generate_karte_for_file should pass skill_preset to build_karte_report."""
        from katrain.core.batch import orchestration

        src = inspect.getsource(orchestration._generate_karte_for_file)
        assert "skill_preset=skill_preset" in src


class TestA2KarteExportColorWarningI18n:
    """A-2: dynamic i18n key construction is replaced with .format() pattern."""

    def test_no_dynamic_i18n_key_in_color_warning(self):
        from katrain.gui.features import karte_export

        src = inspect.getsource(karte_export)
        # Old buggy pattern: i18n._(f"...'{default_user}'...")
        assert "i18n._(f\"Could not determine color" not in src
        # New correct pattern uses .format() with default_user=
        assert "default_user=default_user" in src


class TestA3KarteExportSaveErrorI18n:
    """A-3: 'Failed to save karte' should use i18n key."""

    def test_uses_i18n_key_for_save_error(self):
        from katrain.gui.features import karte_export

        src = inspect.getsource(karte_export)
        # Should use i18n._("Failed to save karte:\\n{error}")
        assert 'i18n._("Failed to save karte:\\n{error}")' in src
        # Should format with error=exc
        assert "error=exc" in src

    def test_no_hardcoded_failed_to_save_string(self):
        """The Popup content should not have a hardcoded English error string."""
        from katrain.gui.features import karte_export

        src = inspect.getsource(karte_export)
        assert 'text=f"Failed to save karte:\\n{exc}"' not in src


class TestA4ReliabilityVisitsThresholdDedupe:
    """A-4: RELIABILITY_VISITS_THRESHOLD removed from reports.constants."""

    def test_not_in_reports_constants(self):
        from katrain.core.reports import constants

        assert not hasattr(constants, "RELIABILITY_VISITS_THRESHOLD"), (
            "RELIABILITY_VISITS_THRESHOLD should be removed from reports.constants "
            "and imported from katrain.core.analysis.models.reliability"
        )

    def test_still_available_from_analysis(self):
        from katrain.core.analysis.models.reliability import RELIABILITY_VISITS_THRESHOLD

        assert RELIABILITY_VISITS_THRESHOLD == 200


class TestA5SummaryAnalyzerWorstMovesTruncation:
    """A-5: SummaryAnalyzer.worst_moves should be truncated to top 10 after sort."""

    def test_worst_moves_truncated_to_10(self):
        """Insert >10 worst_moves and verify only top 10 retained."""
        from dataclasses import dataclass, field
        from typing import Any

        from katrain.core.analysis.models import MistakeCategory
        from katrain.core.eval_metrics import GameSummaryData, PositionDifficulty, SummaryStats
        from katrain.core.reports.summary_logic import SummaryAnalyzer

        @dataclass
        class _MockMove:
            move_number: int
            player: str
            gtp: str
            points_lost: float
            score_loss: float | None = None
            leela_loss_est: float | None = None
            mistake_category: MistakeCategory = MistakeCategory.MISTAKE
            reason_tags: list[str] = field(default_factory=list)
            tag: str = "middle"
            position_difficulty: PositionDifficulty = PositionDifficulty.NORMAL
            meaning_tag_id: str | None = None
            root_visits: int = 100

        # 15 moves with monotonically decreasing loss
        moves = [
            _MockMove(
                move_number=i,
                player="B",
                gtp="D4",
                points_lost=float(20 - i),
            )
            for i in range(1, 16)
        ]

        @dataclass
        class _MockSnapshot:
            ms: list[Any] = field(default_factory=list)

            @property
            def moves(self) -> list[Any]:
                return self.ms

        snapshot = _MockSnapshot(ms=moves)
        gd = GameSummaryData(
            game_name="t.sgf",
            player_black="P1",
            player_white="P2",
            snapshot=snapshot,
            board_size=(19, 19),
            skill_preset="standard",
        )

        analyzer = SummaryAnalyzer([gd])
        stats = analyzer.get_player_stats("P1")
        assert stats is not None
        # Should be truncated to 10
        assert len(stats.worst_moves) == 10, (
            f"Expected worst_moves to be truncated to 10, got {len(stats.worst_moves)}"
        )
        # Top loss should be 19.0 (loss 20-1)
        top_move = stats.worst_moves[0][1]
        assert top_move.points_lost == 19.0


class TestA6ExtractorsKomiBareExcept:
    """A-6: extractors.py should not use bare except."""

    def test_no_bare_except_in_extractors(self):
        from katrain.core.reports import extractors

        src = inspect.getsource(extractors)
        # Find "except:" (bare except)
        import re

        bare_excepts = re.findall(r"except\s*:", src)
        assert len(bare_excepts) == 0, (
            f"Found bare except in extractors.py: {bare_excepts}. "
            "Use 'except ValueError:' instead."
        )

    def test_komi_fallback_uses_value_error(self):
        from katrain.core.reports import extractors

        src = inspect.getsource(extractors)
        assert "except ValueError" in src


class TestA8BuilderImplNoUnusedLocals:
    """A-8: _build_karte_report_impl should not have unused local vars."""

    def test_no_thresholds_local_var(self):
        from katrain.core.reports.karte import builder

        src = inspect.getsource(builder._build_karte_report_impl)
        # Old code had: thresholds = game.katrain.config(...)
        # This is now removed.
        assert "thresholds = game.katrain.config" not in src

    def test_no_confidence_level_local_var(self):
        from katrain.core.reports.karte import builder

        src = inspect.getsource(builder._build_karte_report_impl)
        assert "confidence_level = eval_metrics.compute_confidence_level" not in src

    def test_no_settings_local_var(self):
        from katrain.core.reports.karte import builder

        src = inspect.getsource(builder._build_karte_report_impl)
        assert "settings = eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL" not in src

    def test_still_calls_build_karte_json(self):
        from katrain.core.reports.karte import builder

        src = inspect.getsource(builder._build_karte_report_impl)
        assert "build_karte_json" in src
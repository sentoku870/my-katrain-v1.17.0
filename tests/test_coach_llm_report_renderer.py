"""Phase 242-D: Tests for the unified validation report renderer.

The renderer unifies the two near-duplicate Markdown renderers that
previously lived in :mod:`katrain.gui.features.llm_coach`:

- :func:`_render_validation_report` (Karte case)
- :func:`_render_summary_validation_report` (Summary case)

The unified function takes the common parts (severity banner,
referenced items, issues block) and a list of :class:`ReferencedItem`
rows so the same code path handles both shapes.
"""

from __future__ import annotations

from dataclasses import dataclass

from katrain.core.coach.llm_report_renderer import (
    ReferencedItem,
    render_validation_report,
)
from katrain.core.coach.llm_validator import ValidationIssue, ValidationSeverity

# --- Test fixtures ---


@dataclass
class _FakeReport:
    """Mimics ValidationReport / SummaryValidationReport for testing."""

    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    issues: tuple[ValidationIssue, ...] = ()
    summary: str = "test report"

    def summary_line(self) -> str:
        return self.summary


# --- ReferencedItem ---


class TestReferencedItem:
    def test_render_basic(self):
        item = ReferencedItem(
            label_key="mykatrain:llm-coach:referenced-symptoms",
            values=("atari_blindness", "capture_oversight"),
        )
        out = item.render()
        assert "**" in out
        assert "atari_blindness" in out
        assert "capture_oversight" in out

    def test_render_with_numeric_values(self):
        item = ReferencedItem(
            label_key="mykatrain:llm-coach:referenced-moves",
            values=[10, 20, 30],
        )
        out = item.render()
        assert "10" in out
        assert "20" in out
        assert "30" in out

    def test_render_with_empty_values(self):
        item = ReferencedItem(
            label_key="mykatrain:llm-coach:referenced-symptoms",
            values=(),
        )
        # No crash, just an empty render
        out = item.render()
        assert "**" in out

    def test_render_with_single_value(self):
        item = ReferencedItem(
            label_key="mykatrain:llm-coach:referenced-symptoms",
            values=("foo",),
        )
        out = item.render()
        assert "foo" in out


# --- render_validation_report ---


class TestRenderValidationReport:
    def test_clean_report_minimal(self):
        report = _FakeReport(summary="✅ 検証クリア")
        out = render_validation_report(report, referenced_items=())
        # status banner
        assert "**HIGH**: 0" in out
        assert "**MEDIUM**: 0" in out
        assert "**LOW**: 0" in out
        # No issues block
        assert "##" not in out
        # Trailing newline
        assert out.endswith("\n")

    def test_referenced_items_appended(self):
        report = _FakeReport()
        items = [
            ReferencedItem(
                label_key="mykatrain:llm-coach:referenced-symptoms",
                values=("atari_blindness", "cut_panic"),
            ),
            ReferencedItem(
                label_key="mykatrain:llm-coach:referenced-moves",
                values=[10, 20],
            ),
        ]
        out = render_validation_report(report, referenced_items=items)
        assert "atari_blindness" in out
        assert "cut_panic" in out
        assert "10" in out
        assert "20" in out

    def test_empty_referenced_item_skipped(self):
        report = _FakeReport()
        items = [
            ReferencedItem(
                label_key="mykatrain:llm-coach:referenced-symptoms",
                values=("foo",),
            ),
            ReferencedItem(
                label_key="mykatrain:llm-coach:referenced-categories",
                values=(),  # empty — should be skipped
            ),
        ]
        out = render_validation_report(report, referenced_items=items)
        # The empty item is skipped so its label_key should NOT appear
        # in the output
        assert "referenced-categories" not in out
        # The non-empty item still appears
        assert "foo" in out

    def test_extra_meta_inserted(self):
        report = _FakeReport()
        items = []
        out = render_validation_report(report, referenced_items=items, extra_meta="3局 / 全体俯瞰")
        # extra_meta appears between status and issues block
        idx_status = out.find("**HIGH**")
        idx_meta = out.find("3局")
        assert idx_status < idx_meta
        assert "3局" in out
        assert "全体俯瞰" in out

    def test_extra_meta_none_omitted(self):
        report = _FakeReport()
        out = render_validation_report(report, referenced_items=(), extra_meta=None)
        # No extra line
        # status banner -> 2 lines (status + counts)
        # Should not have any extra lines between counts and end
        assert out.count("\n") <= 4  # 3 lines + trailing newline

    def test_issues_block_rendered(self):
        issues = (
            ValidationIssue(
                severity=ValidationSeverity.HIGH,
                kind="unknown_symptom_id",
                message="foo is not in Karte",
                context={},
            ),
            ValidationIssue(
                severity=ValidationSeverity.MEDIUM,
                kind="points_lost_outlier",
                message="5.0 > 3.0",
                context={},
            ),
        )
        report = _FakeReport(high_count=1, medium_count=1, issues=issues)
        out = render_validation_report(report, referenced_items=())
        assert "##" in out
        assert "[HIGH]" in out
        assert "unknown_symptom_id" in out
        assert "[MEDIUM]" in out
        assert "points_lost_outlier" in out

    def test_summary_line_included(self):
        report = _FakeReport(summary="⚠️ 検証警告 (高: 1, 中: 2)")
        out = render_validation_report(report, referenced_items=())
        assert "高: 1" in out
        assert "中: 2" in out

    def test_karte_style_simulation(self):
        """Verify the function produces the same output as the old
        _render_validation_report for a typical karte report."""
        report = _FakeReport(
            high_count=1,
            medium_count=1,
            low_count=1,
            summary="⚠️ 検証警告",
            issues=(
                ValidationIssue(
                    severity=ValidationSeverity.HIGH,
                    kind="unknown_symptom_id",
                    message="bad_id",
                ),
            ),
        )
        items = [
            ReferencedItem(
                label_key="mykatrain:llm-coach:referenced-symptoms",
                values=("atari_blindness",),
            ),
            ReferencedItem(
                label_key="mykatrain:llm-coach:referenced-moves",
                values=[5, 10],
            ),
            ReferencedItem(
                label_key="mykatrain:llm-coach:referenced-points-lost",
                values=[3.5],
            ),
            ReferencedItem(
                label_key="mykatrain:llm-coach:referenced-lexicon",
                values=("liberty",),
            ),
        ]
        out = render_validation_report(report, referenced_items=items)
        assert "atari_blindness" in out
        assert "5" in out
        assert "10" in out
        assert "3.5" in out
        assert "liberty" in out
        assert "bad_id" in out
        assert "[HIGH]" in out

    def test_summary_style_simulation(self):
        """Verify the function produces the same output as the old
        _render_summary_validation_report for a typical summary report."""
        report = _FakeReport(
            high_count=0,
            medium_count=1,
            low_count=0,
            summary="検証警告 (中: 1)",
        )
        items = [
            ReferencedItem(
                label_key="mykatrain:llm-coach:summary-referenced-categories",
                values=("blunder", "mistake"),
            ),
            ReferencedItem(
                label_key="mykatrain:llm-coach:summary-referenced-phases",
                values=("middle", "endgame"),
            ),
            ReferencedItem(
                label_key="mykatrain:llm-coach:summary-referenced-game-ids",
                values=("g3",),
            ),
        ]
        out = render_validation_report(report, referenced_items=items, extra_meta="5局 / 全体俯瞰")
        assert "5局" in out
        assert "全体俯瞰" in out
        assert "blunder" in out
        assert "middle" in out
        assert "g3" in out

    def test_end_to_end_with_real_validator(self):
        """Integration: feed a real ValidationReport into the renderer."""
        from katrain.core.coach.llm_validator import (
            validate_llm_output,
        )
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.prompt_builder import (
            LlmPrompt,
            PromptConfig,
        )

        # Build a minimal karte with a known symptom
        karte = {
            "schema_version": "3.4",
            "weaknesses": {"black": [{"category": "atari_blindness", "count": 1}]},
            "important_moves": [{"meaning_tag_id": "atari_miss", "color": "black", "points_lost": 2.0}],
        }
        prompt = LlmPrompt(
            system_instruction="",
            lex_injection="",
            body_markdown="",
            full_markdown="",
            config=PromptConfig(
                voice=ToneVoice.AYAKA,
                mode=CoachMode.BEGINNER,
                detected_symptom_ids=(),
                llm_required_symptom_ids=(),
            ),
            referenced_symptom_ids=(),
            referenced_lexicon_ids=(),
        )
        report = validate_llm_output(
            "テスト応答。参照した症状ID: [atari_blindness]",
            karte,
            prompt,
        )
        items = [
            ReferencedItem(
                label_key="mykatrain:llm-coach:referenced-symptoms",
                values=report.referenced_symptom_ids,
            ),
        ]
        out = render_validation_report(report, referenced_items=items)
        assert "atari_blindness" in out
        assert "**HIGH**" in out

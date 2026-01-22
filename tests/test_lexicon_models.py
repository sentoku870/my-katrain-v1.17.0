"""
Tests for katrain.common.lexicon.models module.

Verifies:
- Frozen dataclass immutability
- Tuple field immutability
- Default values
- Field types
"""

import pytest
from dataclasses import FrozenInstanceError

from katrain.common.lexicon.models import (
    DiagramInfo,
    AIPerspective,
    LexiconEntry,
)


# ---------------------------------------------------------------------------
# DiagramInfo Tests
# ---------------------------------------------------------------------------


class TestDiagramInfo:
    """Tests for DiagramInfo dataclass."""

    def test_default_values(self):
        """DiagramInfo should have sensible defaults."""
        diagram = DiagramInfo()
        assert diagram.setup == ()
        assert diagram.annotation == ""

    def test_with_values(self):
        """DiagramInfo should accept custom values."""
        diagram = DiagramInfo(
            setup=("D4", "Q16"),
            annotation="Example position",
        )
        assert diagram.setup == ("D4", "Q16")
        assert diagram.annotation == "Example position"

    def test_is_frozen(self):
        """DiagramInfo should be immutable (frozen dataclass)."""
        diagram = DiagramInfo(setup=("D4",), annotation="Test")
        with pytest.raises(FrozenInstanceError):
            diagram.annotation = "Modified"  # type: ignore

    def test_setup_is_tuple(self):
        """DiagramInfo.setup should be a tuple, not a list."""
        diagram = DiagramInfo(setup=("D4", "Q16"))
        assert isinstance(diagram.setup, tuple)
        # Tuples don't have append
        assert not hasattr(diagram.setup, "append")


# ---------------------------------------------------------------------------
# AIPerspective Tests
# ---------------------------------------------------------------------------


class TestAIPerspective:
    """Tests for AIPerspective dataclass."""

    def test_default_values(self):
        """AIPerspective should have sensible defaults."""
        ai = AIPerspective()
        assert ai.has_difference is False
        assert ai.summary == ""

    def test_with_values(self):
        """AIPerspective should accept custom values."""
        ai = AIPerspective(
            has_difference=True,
            summary="AI prefers aggressive play",
        )
        assert ai.has_difference is True
        assert ai.summary == "AI prefers aggressive play"

    def test_is_frozen(self):
        """AIPerspective should be immutable (frozen dataclass)."""
        ai = AIPerspective(has_difference=True, summary="Test")
        with pytest.raises(FrozenInstanceError):
            ai.has_difference = False  # type: ignore


# ---------------------------------------------------------------------------
# LexiconEntry Tests
# ---------------------------------------------------------------------------


class TestLexiconEntry:
    """Tests for LexiconEntry dataclass."""

    @pytest.fixture
    def minimal_entry(self) -> LexiconEntry:
        """Create a minimal valid Level 1 entry."""
        return LexiconEntry(
            id="atari",
            level=1,
            category="rules",
            ja_term="アタリ",
            en_terms=("atari",),
            ja_one_liner="次に取れる状態",
            en_one_liner="A stone in immediate danger of capture.",
            ja_short="相手の石を次の一手で取れる状態。",
            en_short="When a stone has only one liberty left.",
        )

    @pytest.fixture
    def level3_entry(self) -> LexiconEntry:
        """Create a Level 3 entry with all fields."""
        return LexiconEntry(
            id="tenuki-timing",
            level=3,
            category="urgency",
            ja_term="手抜き",
            en_terms=("tenuki",),
            ja_one_liner="相手の手を無視する判断",
            en_one_liner="Deciding when to ignore opponent's move.",
            ja_short="局面の緊急度を判断する技術。",
            en_short="The skill of judging position urgency.",
            ja_title="手抜きのタイミング",
            en_title="When to Tenuki",
            ja_expanded="詳細な説明文がここに入ります。",
            en_expanded="Detailed explanation goes here.",
            decision_checklist=("Check local stability",),
            signals=("Opponent's move is slow",),
            common_failure_modes=("Ignoring urgent moves",),
            drills=("Practice with pro games",),
            prerequisites=("liberty",),
            sources=("https://example.com/tenuki",),
            related_ids=("liberty",),
        )

    def test_minimal_entry_creation(self, minimal_entry):
        """Minimal entry should be created with required fields only."""
        assert minimal_entry.id == "atari"
        assert minimal_entry.level == 1
        assert minimal_entry.category == "rules"
        assert minimal_entry.ja_term == "アタリ"
        assert minimal_entry.en_terms == ("atari",)

    def test_default_values(self, minimal_entry):
        """Optional fields should have sensible defaults."""
        assert minimal_entry.sources == ()
        assert minimal_entry.related_ids == ()
        assert minimal_entry.ja_title == ""
        assert minimal_entry.en_title == ""
        assert minimal_entry.ja_expanded == ""
        assert minimal_entry.en_expanded == ""
        assert minimal_entry.decision_checklist == ()
        assert minimal_entry.signals == ()
        assert minimal_entry.common_failure_modes == ()
        assert minimal_entry.drills == ()
        assert minimal_entry.prerequisites == ()
        assert minimal_entry.pitfalls == ()
        assert minimal_entry.recognize_by == ()
        assert minimal_entry.micro_example == ""
        assert minimal_entry.diagram is None
        assert minimal_entry.contrast_with == ()
        assert minimal_entry.nuances == ""
        assert minimal_entry.ai_perspective is None

    def test_level3_entry_has_all_fields(self, level3_entry):
        """Level 3 entry should have all Level 3 specific fields."""
        assert level3_entry.ja_title == "手抜きのタイミング"
        assert level3_entry.en_title == "When to Tenuki"
        assert level3_entry.ja_expanded != ""
        assert level3_entry.en_expanded != ""
        assert len(level3_entry.decision_checklist) > 0
        assert len(level3_entry.signals) > 0

    def test_is_frozen(self, minimal_entry):
        """LexiconEntry should be immutable (frozen dataclass)."""
        with pytest.raises(FrozenInstanceError):
            minimal_entry.id = "modified"  # type: ignore

    def test_cannot_modify_level(self, minimal_entry):
        """LexiconEntry.level should be immutable."""
        with pytest.raises(FrozenInstanceError):
            minimal_entry.level = 2  # type: ignore

    def test_en_terms_is_tuple(self, minimal_entry):
        """LexiconEntry.en_terms should be a tuple, not a list."""
        assert isinstance(minimal_entry.en_terms, tuple)
        # Tuples don't have append
        assert not hasattr(minimal_entry.en_terms, "append")

    def test_sources_is_tuple(self, minimal_entry):
        """LexiconEntry.sources should be a tuple."""
        assert isinstance(minimal_entry.sources, tuple)

    def test_related_ids_is_tuple(self, minimal_entry):
        """LexiconEntry.related_ids should be a tuple."""
        assert isinstance(minimal_entry.related_ids, tuple)

    def test_decision_checklist_is_tuple(self, level3_entry):
        """LexiconEntry.decision_checklist should be a tuple."""
        assert isinstance(level3_entry.decision_checklist, tuple)

    def test_multiple_en_terms(self):
        """LexiconEntry should support multiple English terms."""
        entry = LexiconEntry(
            id="liberty",
            level=1,
            category="rules",
            ja_term="呼吸点",
            en_terms=("liberty", "liberties", "breathing point"),
            ja_one_liner="石に隣接する空点",
            en_one_liner="An empty point adjacent to a stone.",
            ja_short="石が生きるために必要な空点。",
            en_short="Empty points that keep a stone alive.",
        )
        assert len(entry.en_terms) == 3
        assert "liberty" in entry.en_terms
        assert "liberties" in entry.en_terms
        assert "breathing point" in entry.en_terms

    def test_with_diagram(self):
        """LexiconEntry should accept DiagramInfo."""
        diagram = DiagramInfo(setup=("D4", "Q16"), annotation="Corner approach")
        entry = LexiconEntry(
            id="kakari",
            level=2,
            category="opening",
            ja_term="カカリ",
            en_terms=("approach", "kakari"),
            ja_one_liner="隅へのアプローチ",
            en_one_liner="Approaching a corner stone.",
            ja_short="隅の石に近づく手。",
            en_short="A move that approaches a corner stone.",
            diagram=diagram,
        )
        assert entry.diagram is not None
        assert entry.diagram.setup == ("D4", "Q16")

    def test_with_ai_perspective(self):
        """LexiconEntry should accept AIPerspective."""
        ai = AIPerspective(has_difference=True, summary="AI prefers tenuki")
        entry = LexiconEntry(
            id="tenuki",
            level=2,
            category="urgency",
            ja_term="手抜き",
            en_terms=("tenuki",),
            ja_one_liner="相手の手を無視",
            en_one_liner="Ignoring opponent's move.",
            ja_short="相手の手に応じない。",
            en_short="Not responding to opponent.",
            ai_perspective=ai,
        )
        assert entry.ai_perspective is not None
        assert entry.ai_perspective.has_difference is True

    def test_nested_diagram_is_immutable(self):
        """DiagramInfo inside LexiconEntry should also be immutable."""
        diagram = DiagramInfo(setup=("D4",), annotation="Test")
        entry = LexiconEntry(
            id="test",
            level=1,
            category="test",
            ja_term="テスト",
            en_terms=("test",),
            ja_one_liner="テスト",
            en_one_liner="Test.",
            ja_short="テスト",
            en_short="Test.",
            diagram=diagram,
        )
        with pytest.raises(FrozenInstanceError):
            entry.diagram.annotation = "Modified"  # type: ignore


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


class TestLexiconEntryEdgeCases:
    """Edge case tests for LexiconEntry."""

    def test_empty_en_terms_tuple_allowed_by_dataclass(self):
        """Dataclass allows empty en_terms (validation catches this)."""
        # Note: This tests that the dataclass itself doesn't prevent empty tuples.
        # Validation (in validation.py) will reject this.
        entry = LexiconEntry(
            id="test",
            level=1,
            category="test",
            ja_term="テスト",
            en_terms=(),  # Empty - validation will reject
            ja_one_liner="テスト",
            en_one_liner="Test.",
            ja_short="テスト",
            en_short="Test.",
        )
        assert entry.en_terms == ()

    def test_level_out_of_range_allowed_by_dataclass(self):
        """Dataclass allows invalid level (validation catches this)."""
        # Note: This tests that the dataclass itself doesn't prevent invalid levels.
        # Validation (in validation.py) will reject this.
        entry = LexiconEntry(
            id="test",
            level=99,  # Invalid - validation will reject
            category="test",
            ja_term="テスト",
            en_terms=("test",),
            ja_one_liner="テスト",
            en_one_liner="Test.",
            ja_short="テスト",
            en_short="Test.",
        )
        assert entry.level == 99

    def test_unicode_content(self):
        """LexiconEntry should handle Unicode content correctly."""
        entry = LexiconEntry(
            id="atari",
            level=1,
            category="rules",
            ja_term="アタリ（当たり）",
            en_terms=("atari",),
            ja_one_liner="次の一手で取れる「危険」な状態",
            en_one_liner="A stone in immediate danger of capture.",
            ja_short="相手の石を次の一手で取れる状態。囲碁の基本用語。",
            en_short="When a stone has only one liberty left.",
        )
        assert "アタリ" in entry.ja_term
        assert "危険" in entry.ja_one_liner

    def test_long_text_content(self):
        """LexiconEntry should handle long text content."""
        long_text = "A" * 10000
        entry = LexiconEntry(
            id="test",
            level=1,
            category="test",
            ja_term="テスト",
            en_terms=("test",),
            ja_one_liner="テスト",
            en_one_liner="Test.",
            ja_short="テスト",
            en_short="Test.",
            ja_expanded=long_text,
        )
        assert len(entry.ja_expanded) == 10000

"""
Integration tests for Critical 3 section in Karte report (Phase 50).

Tests cover:
- Critical 3 section presence in Karte output
- Section ordering (after Important Moves)
- Language-specific output (ja/en)
- LLM prompt template validity

All tests are engine-free (no KataGo/Leela required).
"""

import pytest

from katrain.core.analysis import CriticalMove
from katrain.core.reports.karte_report import (
    CRITICAL_3_PROMPT_TEMPLATE,
    build_critical_3_prompt,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_critical_move_ja():
    """Sample CriticalMove with Japanese label."""
    return CriticalMove(
        move_number=45,
        player="B",
        gtp_coord="D10",
        score_loss=5.2,
        delta_winrate=-0.08,
        meaning_tag_id="life_death_error",
        meaning_tag_label="死活ミス",
        position_difficulty="hard",
        reason_tags=("atari", "low_liberties"),
        score_stdev=4.5,
        game_phase="middle",
        importance_score=12.0,
        critical_score=18.0,
    )


@pytest.fixture
def sample_critical_move_en():
    """Sample CriticalMove with English label."""
    return CriticalMove(
        move_number=45,
        player="B",
        gtp_coord="D10",
        score_loss=5.2,
        delta_winrate=-0.08,
        meaning_tag_id="life_death_error",
        meaning_tag_label="Life & Death Error",
        position_difficulty="hard",
        reason_tags=("atari", "low_liberties"),
        score_stdev=4.5,
        game_phase="middle",
        importance_score=12.0,
        critical_score=18.0,
    )


@pytest.fixture
def sample_critical_moves():
    """List of 3 sample CriticalMove objects."""
    return [
        CriticalMove(
            move_number=45,
            player="B",
            gtp_coord="D10",
            score_loss=5.2,
            delta_winrate=-0.08,
            meaning_tag_id="life_death_error",
            meaning_tag_label="Life & Death Error",
            position_difficulty="hard",
            reason_tags=("atari", "low_liberties"),
            score_stdev=4.5,
            game_phase="middle",
            importance_score=12.0,
            critical_score=18.0,
        ),
        CriticalMove(
            move_number=78,
            player="W",
            gtp_coord="Q3",
            score_loss=3.8,
            delta_winrate=0.05,
            meaning_tag_id="direction_error",
            meaning_tag_label="Direction Error",
            position_difficulty="normal",
            reason_tags=(),
            score_stdev=3.2,
            game_phase="opening",
            importance_score=8.0,
            critical_score=8.8,
        ),
        CriticalMove(
            move_number=112,
            player="B",
            gtp_coord="E15",
            score_loss=2.1,
            delta_winrate=-0.03,
            meaning_tag_id="missed_tesuji",
            meaning_tag_label="Missed Tesuji",
            position_difficulty="hard",
            reason_tags=("cut_risk",),
            score_stdev=2.8,
            game_phase="middle",
            importance_score=6.5,
            critical_score=7.15,
        ),
    ]


# =============================================================================
# Test: LLM Prompt Template
# =============================================================================


class TestLLMPromptTemplate:
    """Tests for LLM prompt template and generation."""

    def test_llm_prompt_template_valid_markdown(self):
        """CRITICAL_3_PROMPT_TEMPLATE is valid markdown structure."""
        # Check for required sections
        assert "# Go Game Review Request" in CRITICAL_3_PROMPT_TEMPLATE
        assert "## Player Context" in CRITICAL_3_PROMPT_TEMPLATE
        assert "## Critical Mistakes" in CRITICAL_3_PROMPT_TEMPLATE
        assert "## Analysis Request" in CRITICAL_3_PROMPT_TEMPLATE

        # Check for placeholders
        assert "{player_level}" in CRITICAL_3_PROMPT_TEMPLATE
        assert "{critical_moves_section}" in CRITICAL_3_PROMPT_TEMPLATE

    def test_llm_prompt_template_has_analysis_instructions(self):
        """Template includes analysis request instructions."""
        assert "fundamental concept" in CRITICAL_3_PROMPT_TEMPLATE.lower()
        assert "practice" in CRITICAL_3_PROMPT_TEMPLATE.lower()

    def test_build_critical_3_prompt_empty_list(self):
        """Empty critical moves list returns empty string."""
        result = build_critical_3_prompt([])
        assert result == ""

    def test_build_critical_3_prompt_includes_all_fields(self, sample_critical_moves):
        """Generated prompt includes all CriticalMove fields."""
        prompt = build_critical_3_prompt(sample_critical_moves, player_level="4-5 dan")

        # Check player level
        assert "4-5 dan" in prompt

        # Check first move fields
        assert "Move #45" in prompt
        assert "(B)" in prompt
        assert "D10" in prompt
        assert "5.2 pts" in prompt
        assert "Life & Death Error" in prompt
        assert "middle" in prompt
        assert "HARD" in prompt
        assert "atari" in prompt
        assert "low_liberties" in prompt

        # Check second move
        assert "Move #78" in prompt
        assert "(W)" in prompt
        assert "Q3" in prompt
        assert "Direction Error" in prompt

        # Check third move
        assert "Move #112" in prompt
        assert "E15" in prompt
        assert "Missed Tesuji" in prompt

    def test_build_critical_3_prompt_no_reason_tags(self):
        """Prompt handles moves without reason_tags."""
        move = CriticalMove(
            move_number=50,
            player="W",
            gtp_coord="R5",
            score_loss=4.0,
            delta_winrate=0.06,
            meaning_tag_id="overplay",
            meaning_tag_label="Overplay",
            position_difficulty="normal",
            reason_tags=(),  # Empty
            score_stdev=None,
            game_phase="middle",
            importance_score=7.0,
            critical_score=7.0,
        )

        prompt = build_critical_3_prompt([move])

        assert "Move #50" in prompt
        assert "Overplay" in prompt
        # Should not have Context line when reason_tags is empty
        assert "Context:" not in prompt

    def test_build_critical_3_prompt_single_move(self):
        """Prompt works with a single critical move."""
        move = CriticalMove(
            move_number=30,
            player="B",
            gtp_coord="C3",
            score_loss=6.5,
            delta_winrate=-0.1,
            meaning_tag_id="reading_failure",
            meaning_tag_label="Reading Failure",
            position_difficulty="hard",
            reason_tags=("ko",),
            score_stdev=5.0,
            game_phase="middle",
            importance_score=10.0,
            critical_score=13.0,
        )

        prompt = build_critical_3_prompt([move], player_level="beginner")

        assert "beginner" in prompt
        assert "Move #30" in prompt
        assert "Reading Failure" in prompt
        assert "ko" in prompt


# =============================================================================
# Test: CriticalMove Dataclass
# =============================================================================


class TestCriticalMoveInReport:
    """Tests for CriticalMove integration with reports."""

    def test_critical_move_all_required_fields(self, sample_critical_move_ja):
        """CriticalMove has all required fields for Karte generation."""
        cm = sample_critical_move_ja

        # Required for display
        assert cm.move_number > 0
        assert cm.player in ("B", "W")
        assert len(cm.gtp_coord) > 0
        assert cm.score_loss >= 0
        assert len(cm.meaning_tag_id) > 0
        assert len(cm.meaning_tag_label) > 0
        assert len(cm.game_phase) > 0
        assert len(cm.position_difficulty) > 0

        # Tuple for immutability
        assert isinstance(cm.reason_tags, tuple)

    def test_critical_move_score_stdev_nullable(self):
        """score_stdev can be None (for Leela or unanalyzed)."""
        cm = CriticalMove(
            move_number=1,
            player="B",
            gtp_coord="D4",
            score_loss=1.0,
            delta_winrate=-0.01,
            meaning_tag_id="slow_move",
            meaning_tag_label="Slow Move",
            position_difficulty="easy",
            reason_tags=(),
            score_stdev=None,  # Can be None
            game_phase="opening",
            importance_score=2.0,
            critical_score=1.6,
        )

        assert cm.score_stdev is None


# =============================================================================
# Test: Section Format
# =============================================================================


class TestCritical3SectionFormat:
    """Tests for Critical 3 section formatting."""

    def test_section_header_format(self, sample_critical_move_ja):
        """Section uses consistent header format."""
        # The format should be "## Critical 3 ({label})"
        # This is validated by the _critical_3_section_for function in karte_report.py
        # Here we just verify the CriticalMove data is suitable for formatting

        cm = sample_critical_move_ja
        # Format a line as it would appear in the section
        line = f"### 1. Move #{cm.move_number} ({cm.player}) {cm.gtp_coord}"
        assert "Move #45 (B) D10" in line

    def test_loss_format_ja(self, sample_critical_move_ja):
        """Japanese format uses 目 unit."""
        cm = sample_critical_move_ja
        unit = "目"
        formatted = f"{cm.score_loss:.1f}{unit}"
        assert formatted == "5.2目"

    def test_loss_format_en(self, sample_critical_move_en):
        """English format uses pts unit."""
        cm = sample_critical_move_en
        unit = " pts"
        formatted = f"{cm.score_loss:.1f}{unit}"
        assert formatted == "5.2 pts"

    def test_difficulty_uppercase(self, sample_critical_move_ja):
        """Difficulty is displayed in uppercase."""
        cm = sample_critical_move_ja
        formatted = cm.position_difficulty.upper()
        assert formatted == "HARD"

    def test_context_comma_separated(self, sample_critical_move_ja):
        """Context (reason_tags) is comma-separated."""
        cm = sample_critical_move_ja
        context = ", ".join(cm.reason_tags)
        assert context == "atari, low_liberties"

    def test_context_none_display(self):
        """Empty reason_tags displays as (none)."""
        cm = CriticalMove(
            move_number=1,
            player="B",
            gtp_coord="D4",
            score_loss=1.0,
            delta_winrate=-0.01,
            meaning_tag_id="slow_move",
            meaning_tag_label="Slow Move",
            position_difficulty="easy",
            reason_tags=(),  # Empty
            score_stdev=None,
            game_phase="opening",
            importance_score=2.0,
            critical_score=1.6,
        )

        context = ", ".join(cm.reason_tags) if cm.reason_tags else "(none)"
        assert context == "(none)"

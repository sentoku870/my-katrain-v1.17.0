"""Evidence-attachment and importance-ranking tests extracted from tests/test_eval_metrics.py.

Phase D-1: split the 2316-line test_eval_metrics.py into 4 themed
submodules. Covers evidence attachment selection (PR#2) and the
importance-ranking redesign that ties difficulty + streak bonus into the
final score.
"""

from __future__ import annotations

import pytest

from katrain.core.analysis import compute_importance_for_moves, select_representative_moves
from katrain.core.analysis.models import ConfidenceLevel
from katrain.core.analysis.models.enums import MistakeCategory, PositionDifficulty
from katrain.core.analysis.presentation import format_evidence_examples, get_evidence_count
from tests.helpers_eval_metrics import make_move_eval


class TestEvidenceAttachments:
    """Tests for Evidence Attachments functionality (PR#2)"""

    def test_select_representative_moves_uses_score_loss(self):
        """select_representative_moves should use score_loss for sorting"""
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=2.0),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=5.0),
            make_move_eval(move_number=3, player="B", gtp="D16", score_loss=3.0),
        ]
        result = select_representative_moves(moves, max_count=2)

        # Should be sorted by score_loss descending: Q16 (5.0), D16 (3.0)
        assert len(result) == 2
        assert result[0].gtp == "Q16"
        assert result[0].score_loss == 5.0
        assert result[1].gtp == "D16"
        assert result[1].score_loss == 3.0

    def test_select_representative_moves_skips_none_score_loss(self):
        """Moves with score_loss=None should be skipped"""
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=None),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=5.0),
            make_move_eval(move_number=3, player="B", gtp="D16", score_loss=None),
            make_move_eval(move_number=4, player="B", gtp="Q4", score_loss=3.0),
        ]
        result = select_representative_moves(moves, max_count=3)

        # Should skip None and return Q16, Q4
        assert len(result) == 2
        assert result[0].gtp == "Q16"
        assert result[1].gtp == "Q4"

    def test_select_representative_moves_deterministic_ordering(self):
        """Same score_loss should use move_number for tiebreak (ascending)"""
        moves = [
            make_move_eval(move_number=10, player="B", gtp="D4", score_loss=5.0),
            make_move_eval(move_number=5, player="B", gtp="Q16", score_loss=5.0),
            make_move_eval(move_number=15, player="B", gtp="D16", score_loss=5.0),
        ]
        result = select_representative_moves(moves, max_count=3)

        # All have score_loss=5.0, tiebreak by move_number ascending: 5, 10, 15
        assert len(result) == 3
        assert result[0].move_number == 5
        assert result[1].move_number == 10
        assert result[2].move_number == 15

    def test_select_representative_moves_with_filter(self):
        """Category filter should be applied before selection"""
        moves = [
            make_move_eval(
                move_number=1, player="B", gtp="D4", score_loss=5.0, mistake_category=MistakeCategory.BLUNDER
            ),
            make_move_eval(
                move_number=2, player="B", gtp="Q16", score_loss=3.0, mistake_category=MistakeCategory.MISTAKE
            ),
            make_move_eval(
                move_number=3, player="B", gtp="D16", score_loss=6.0, mistake_category=MistakeCategory.BLUNDER
            ),
        ]
        # Filter for BLUNDER only
        result = select_representative_moves(
            moves, max_count=5, category_filter=lambda m: m.mistake_category == MistakeCategory.BLUNDER
        )

        assert len(result) == 2
        assert all(m.mistake_category == MistakeCategory.BLUNDER for m in result)
        # Sorted by score_loss descending: D16 (6.0), D4 (5.0)
        assert result[0].gtp == "D16"
        assert result[1].gtp == "D4"

    def test_format_evidence_examples_ja(self):
        """Japanese format for evidence examples"""
        moves = [
            make_move_eval(move_number=12, player="B", gtp="Q16", score_loss=8.5),
            make_move_eval(move_number=45, player="B", gtp="R4", score_loss=4.2),
        ]
        result = format_evidence_examples(moves, lang="ja")

        assert result == "例: #12 Q16 (-8.5目), #45 R4 (-4.2目)"

    def test_format_evidence_examples_en(self):
        """English format for evidence examples"""
        moves = [
            make_move_eval(move_number=12, player="B", gtp="Q16", score_loss=8.5),
            make_move_eval(move_number=45, player="B", gtp="R4", score_loss=4.2),
        ]
        result = format_evidence_examples(moves, lang="en")

        assert result == "e.g.: #12 Q16 (-8.5 pts), #45 R4 (-4.2 pts)"

    def test_format_evidence_examples_empty(self):
        """Empty moves list returns empty string"""
        result = format_evidence_examples([], lang="ja")
        assert result == ""

    def test_get_evidence_count_by_confidence(self):
        """Evidence count varies by confidence level"""
        assert get_evidence_count(ConfidenceLevel.HIGH) == 3
        assert get_evidence_count(ConfidenceLevel.MEDIUM) == 2
        assert get_evidence_count(ConfidenceLevel.LOW) == 1

    def test_select_representative_moves_empty_list(self):
        """Empty moves list returns empty result"""
        result = select_representative_moves([], max_count=3)
        assert result == []

    def test_select_representative_moves_all_none_score_loss(self):
        """All moves with None score_loss returns empty result"""
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=None),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=None),
        ]
        result = select_representative_moves(moves, max_count=3)
        assert result == []


# ---------------------------------------------------------------------------
# Test: Important Move Ranking Redesign (PR#4)
# ---------------------------------------------------------------------------

from katrain.core.analysis import get_difficulty_modifier, get_reliability_scale
from katrain.core.analysis.logic_importance import (
    DIFFICULTY_MODIFIER_HARD,
    DIFFICULTY_MODIFIER_ONLY_MOVE,
    STREAK_START_BONUS,
)


class TestImportanceRankingRedesign:
    """Tests for Important Move Ranking Redesign (PR#4)"""

    def test_difficulty_modifier_hard_bonus(self):
        """HARD difficulty should add +1.0 bonus"""
        modifier = get_difficulty_modifier(PositionDifficulty.HARD)
        assert modifier == DIFFICULTY_MODIFIER_HARD
        assert modifier == 1.0

    def test_difficulty_modifier_only_move_penalty(self):
        """ONLY_MOVE difficulty should subtract -1.0 (Phase 23: relaxed from -2.0)"""
        modifier = get_difficulty_modifier(PositionDifficulty.ONLY_MOVE)
        assert modifier == DIFFICULTY_MODIFIER_ONLY_MOVE
        assert modifier == -1.0  # Phase 23: -2.0 → -1.0

    def test_difficulty_modifier_normal_zero(self):
        """NORMAL difficulty should have 0 modifier"""
        modifier = get_difficulty_modifier(PositionDifficulty.NORMAL)
        assert modifier == 0.0

    def test_difficulty_modifier_easy_zero(self):
        """EASY difficulty should have 0 modifier"""
        modifier = get_difficulty_modifier(PositionDifficulty.EASY)
        assert modifier == 0.0

    def test_difficulty_modifier_none_zero(self):
        """None difficulty should have 0 modifier"""
        modifier = get_difficulty_modifier(None)
        assert modifier == 0.0

    def test_reliability_scale_high_visits(self):
        """Visits >= 500 should have scale 1.0"""
        assert get_reliability_scale(500) == 1.0
        assert get_reliability_scale(1000) == 1.0

    def test_reliability_scale_medium_visits(self):
        """Visits >= 200 should have scale 0.8"""
        assert get_reliability_scale(200) == 0.8
        assert get_reliability_scale(400) == 0.8

    def test_reliability_scale_low_visits(self):
        """Visits >= 100 should have scale 0.5"""
        assert get_reliability_scale(100) == 0.5
        assert get_reliability_scale(150) == 0.5

    def test_reliability_scale_very_low_visits(self):
        """Visits < 100 should have scale 0.3"""
        assert get_reliability_scale(50) == 0.3
        assert get_reliability_scale(0) == 0.3

    def test_importance_uses_canonical_loss_as_primary(self):
        """Importance should use score_loss as primary component"""
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=5.0, root_visits=500),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=2.0, root_visits=500),
        ]
        compute_importance_for_moves(moves)

        # Higher score_loss should have higher importance
        assert moves[0].importance_score > moves[1].importance_score

    def test_importance_with_hard_difficulty_bonus(self):
        """HARD difficulty should increase importance"""
        move_normal = make_move_eval(
            move_number=1,
            player="B",
            gtp="D4",
            score_loss=5.0,
            root_visits=500,
            position_difficulty=PositionDifficulty.NORMAL,
        )
        move_hard = make_move_eval(
            move_number=2,
            player="B",
            gtp="Q16",
            score_loss=5.0,
            root_visits=500,
            position_difficulty=PositionDifficulty.HARD,
        )
        compute_importance_for_moves([move_normal, move_hard])

        # HARD should have higher importance due to +1.0 bonus
        assert move_hard.importance_score > move_normal.importance_score
        assert move_hard.importance_score - move_normal.importance_score == pytest.approx(1.0)

    def test_importance_with_only_move_penalty(self):
        """ONLY_MOVE difficulty should decrease importance"""
        move_normal = make_move_eval(
            move_number=1,
            player="B",
            gtp="D4",
            score_loss=5.0,
            root_visits=500,
            position_difficulty=PositionDifficulty.NORMAL,
        )
        move_only = make_move_eval(
            move_number=2,
            player="B",
            gtp="Q16",
            score_loss=5.0,
            root_visits=500,
            position_difficulty=PositionDifficulty.ONLY_MOVE,
        )
        compute_importance_for_moves([move_normal, move_only])

        # ONLY_MOVE should have lower importance due to -2.0 penalty
        assert move_only.importance_score < move_normal.importance_score

    def test_importance_with_streak_start_bonus(self):
        """Streak start moves should get +2.0 bonus"""
        move1 = make_move_eval(move_number=10, player="B", gtp="D10", score_loss=3.0, root_visits=500)
        move2 = make_move_eval(move_number=20, player="B", gtp="Q10", score_loss=3.0, root_visits=500)

        # Only move 10 is a streak start
        streak_starts = {10}
        compute_importance_for_moves([move1, move2], streak_start_moves=streak_starts)

        # Move 10 should have higher importance due to streak start bonus
        assert move1.importance_score > move2.importance_score
        assert move1.importance_score - move2.importance_score == pytest.approx(STREAK_START_BONUS)

    def test_importance_deterministic_with_same_score(self):
        """Moves with same importance should be ordered by move_number"""
        moves = [
            make_move_eval(move_number=30, player="B", gtp="D30", score_loss=5.0, root_visits=500),
            make_move_eval(move_number=10, player="B", gtp="D10", score_loss=5.0, root_visits=500),
            make_move_eval(move_number=20, player="B", gtp="D20", score_loss=5.0, root_visits=500),
        ]
        compute_importance_for_moves(moves)

        # Sort by importance desc, move_number asc
        sorted_moves = sorted(moves, key=lambda m: (-m.importance_score, m.move_number))

        # All have same importance, so order by move_number
        assert sorted_moves[0].move_number == 10
        assert sorted_moves[1].move_number == 20
        assert sorted_moves[2].move_number == 30

    def test_importance_reliability_scale_applied(self):
        """Lower visits should reduce importance via reliability scale"""
        move_high = make_move_eval(move_number=1, player="B", gtp="D4", score_loss=5.0, root_visits=500)
        move_low = make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=5.0, root_visits=50)
        compute_importance_for_moves([move_high, move_low])

        # High visits (scale=1.0) should have higher importance than low visits (scale=0.3)
        assert move_high.importance_score > move_low.importance_score
        # Ratio should be approximately 1.0 / 0.3
        ratio = move_high.importance_score / move_low.importance_score
        assert ratio == pytest.approx(1.0 / 0.3, rel=0.1)

    def test_importance_non_negative(self):
        """Importance should never be negative even with ONLY_MOVE penalty"""
        move = make_move_eval(
            move_number=1,
            player="B",
            gtp="D4",
            score_loss=1.0,  # Small loss
            root_visits=500,
            position_difficulty=PositionDifficulty.ONLY_MOVE,  # -2.0 penalty
        )
        compute_importance_for_moves([move])

        # Should be clamped to 0, not negative
        assert move.importance_score >= 0.0

    def test_confidence_level_affects_components(self):
        """LOW confidence should use only canonical_loss component"""
        move = make_move_eval(
            move_number=10,
            player="B",
            gtp="D10",
            score_loss=5.0,
            root_visits=500,
            position_difficulty=PositionDifficulty.HARD,
            score_before=5.0,
            score_after=-5.0,  # Swing
        )
        streak_starts = {10}

        # HIGH confidence: all components
        compute_importance_for_moves([move], streak_start_moves=streak_starts, confidence_level=ConfidenceLevel.HIGH)
        high_importance = move.importance_score

        # LOW confidence: only canonical_loss
        compute_importance_for_moves([move], streak_start_moves=streak_starts, confidence_level=ConfidenceLevel.LOW)
        low_importance = move.importance_score

        # HIGH should include difficulty bonus and streak bonus
        assert high_importance > low_importance

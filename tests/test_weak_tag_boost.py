"""Phase 248-γ-E1: tests for the weak-tag boost in ``compute_importance_for_moves``.

Locks in the public contract:
- A move whose ``meaning_tag_id`` appears in ``user_weak_tags`` gets a
  multiplicative boost ``1 + weak_tag_boost * log(N + 1)`` applied
  to its post-reliability importance score.
- Higher occurrence count → larger boost (monotonic).
- An empty / missing ``user_weak_tags`` disables the boost.
- ``weak_tag_boost=0.0`` disables the boost even when
  ``user_weak_tags`` is set.
- A move whose tag is *not* in the weak set is unaffected.
- The reliability gate still wins: a low-visits move is still scaled
  down even when boosted.
"""

from __future__ import annotations

import math

import pytest

from katrain.core.analysis import compute_importance_for_moves
from katrain.core.analysis.models import ConfidenceLevel
from tests.helpers_eval_metrics import make_move_eval


def _move(move_number: int, *, tag: str | None, score_loss: float = 5.0, visits: int = 500) -> object:
    """Build a MoveEval with a given meaning_tag_id and a sane baseline."""
    mv = make_move_eval(
        move_number=move_number,
        player="B",
        gtp="D4",
        score_loss=score_loss,
        root_visits=visits,
    )
    mv.meaning_tag_id = tag
    return mv


class TestWeakTagBoostBaseline:
    """When ``user_weak_tags`` is None / empty, behaviour is unchanged."""

    def test_no_weak_tags_keeps_baseline_importance(self):
        m = _move(1, tag="overplay")
        m_baseline = _move(1, tag="overplay")
        # Baseline (no boost) = 5.0 loss * 1.0 reliability = 5.0
        compute_importance_for_moves([m_baseline])
        baseline_score = m_baseline.importance_score
        # With explicit None — same result.
        compute_importance_for_moves([m], user_weak_tags=None)
        assert m.importance_score == pytest.approx(baseline_score)

    def test_empty_dict_keeps_baseline_importance(self):
        m = _move(1, tag="overplay")
        compute_importance_for_moves([m], user_weak_tags={})
        # 5.0 loss * 1.0 reliability = 5.0
        assert m.importance_score == pytest.approx(5.0)


class TestWeakTagBoostApplied:
    """A move whose tag is in ``user_weak_tags`` gets boosted."""

    def test_single_occurrence_boost(self):
        m = _move(1, tag="overplay")
        compute_importance_for_moves([m], user_weak_tags={"overplay": 1}, weak_tag_boost=0.5)
        # Expected: 5.0 * (1 + 0.5 * log(2)) ≈ 5.0 * 1.3466 ≈ 6.733
        expected = 5.0 * (1.0 + 0.5 * math.log(2))
        assert m.importance_score == pytest.approx(expected, rel=1e-4)

    def test_higher_count_yields_larger_boost(self):
        m1 = _move(1, tag="overplay")
        m5 = _move(1, tag="overplay")
        m10 = _move(1, tag="overplay")
        compute_importance_for_moves([m1], user_weak_tags={"overplay": 1}, weak_tag_boost=0.5)
        compute_importance_for_moves([m5], user_weak_tags={"overplay": 5}, weak_tag_boost=0.5)
        compute_importance_for_moves([m10], user_weak_tags={"overplay": 10}, weak_tag_boost=0.5)
        assert m1.importance_score < m5.importance_score < m10.importance_score

    def test_boost_is_multiplicative(self):
        """``boost = base * (1 + 0.5 * log(N + 1))``."""
        m = _move(1, tag="overplay", score_loss=10.0)
        compute_importance_for_moves([m], user_weak_tags={"overplay": 3}, weak_tag_boost=0.5)
        expected = 10.0 * (1.0 + 0.5 * math.log(4))
        assert m.importance_score == pytest.approx(expected, rel=1e-4)

    def test_unrelated_tag_is_unaffected(self):
        """A move whose tag is NOT in ``user_weak_tags`` keeps the baseline."""
        baseline = _move(1, tag="territorial_loss")
        compute_importance_for_moves([baseline])
        baseline_score = baseline.importance_score

        m = _move(1, tag="territorial_loss")
        # user_weak_tags mentions a different tag.
        compute_importance_for_moves([m], user_weak_tags={"overplay": 5}, weak_tag_boost=0.5)
        assert m.importance_score == pytest.approx(baseline_score)

    def test_move_without_tag_is_unaffected(self):
        """A move with ``meaning_tag_id=None`` is never boosted."""
        baseline = _move(1, tag=None)
        compute_importance_for_moves([baseline])
        baseline_score = baseline.importance_score

        m = _move(1, tag=None)
        compute_importance_for_moves([m], user_weak_tags={"overplay": 10}, weak_tag_boost=1.0)
        assert m.importance_score == pytest.approx(baseline_score)


class TestWeakTagBoostBoundaries:
    """Edge cases — extreme boost / count / type-mismatched values."""

    def test_weak_tag_boost_zero_disables_boost(self):
        """``weak_tag_boost=0.0`` with a populated ``user_weak_tags`` → no boost."""
        m = _move(1, tag="overplay")
        compute_importance_for_moves([m], user_weak_tags={"overplay": 100}, weak_tag_boost=0.0)
        # 5.0 * 1.0 reliability = 5.0 (no boost)
        assert m.importance_score == pytest.approx(5.0)

    def test_weak_tag_boost_one_doubles_high_occurrence(self):
        """``weak_tag_boost=1.0`` with N=7 gives ~3.0× importance (log(8)≈2.08)."""
        m = _move(1, tag="overplay", score_loss=5.0)
        compute_importance_for_moves([m], user_weak_tags={"overplay": 7}, weak_tag_boost=1.0)
        expected = 5.0 * (1.0 + 1.0 * math.log(8))
        assert m.importance_score == pytest.approx(expected, rel=1e-4)

    def test_negative_count_ignored(self):
        """``count < 1`` skips the boost (would otherwise log(0)=−inf)."""
        m = _move(1, tag="overplay")
        compute_importance_for_moves([m], user_weak_tags={"overplay": -3}, weak_tag_boost=0.5)
        assert m.importance_score == pytest.approx(5.0)

    def test_zero_count_ignored(self):
        m = _move(1, tag="overplay")
        compute_importance_for_moves([m], user_weak_tags={"overplay": 0}, weak_tag_boost=0.5)
        assert m.importance_score == pytest.approx(5.0)

    def test_non_int_count_ignored(self):
        """String / float values that aren't parseable as ``int`` are skipped."""
        m = _move(1, tag="overplay")
        compute_importance_for_moves([m], user_weak_tags={"overplay": "abc"}, weak_tag_boost=0.5)
        assert m.importance_score == pytest.approx(5.0)

    def test_string_count_parses(self):
        """A numeric string coerces via ``int()``."""
        m = _move(1, tag="overplay")
        compute_importance_for_moves([m], user_weak_tags={"overplay": "5"}, weak_tag_boost=0.5)
        expected = 5.0 * (1.0 + 0.5 * math.log(6))
        assert m.importance_score == pytest.approx(expected, rel=1e-4)

    def test_low_visits_still_get_reliability_scale(self):
        """The reliability gate runs BEFORE the weak-tag boost.

        Concretely: a low-visits move is scaled down to ``0.3`` of
        its (post-boost) score, so the boost cannot bypass the
        reliability check.
        """
        m = _move(1, tag="overplay", score_loss=5.0, visits=50)
        compute_importance_for_moves([m], user_weak_tags={"overplay": 100}, weak_tag_boost=1.0)
        # No reliability scale (50 < 100 → 0.3). Boost then multiplies.
        # Expected: 5.0 * 0.3 * (1 + 1.0 * log(101))
        expected = 5.0 * 0.3 * (1.0 + 1.0 * math.log(101))
        assert m.importance_score == pytest.approx(expected, rel=1e-3)


class TestWeakTagBoostAcrossMultipleMoves:
    """Realistic mix: some moves boosted, others not."""

    def test_boost_only_affects_listed_tags(self):
        moves = [
            _move(1, tag="overplay", score_loss=5.0),
            _move(2, tag="bad_shape", score_loss=5.0),
            _move(3, tag="overplay", score_loss=3.0),
            _move(4, tag="missed_tesuji", score_loss=5.0),
        ]
        weak = {"overplay": 5}  # only "overplay" gets boosted
        compute_importance_for_moves(moves, user_weak_tags=weak, weak_tag_boost=0.5)

        # Move 1 and 3 are boosted; moves 2 and 4 are not.
        baseline_5 = 5.0
        baseline_3 = 3.0
        expected_1 = baseline_5 * (1.0 + 0.5 * math.log(6))
        expected_3 = baseline_3 * (1.0 + 0.5 * math.log(6))
        assert moves[0].importance_score == pytest.approx(expected_1, rel=1e-4)
        assert moves[1].importance_score == pytest.approx(baseline_5, rel=1e-4)
        assert moves[2].importance_score == pytest.approx(expected_3, rel=1e-4)
        assert moves[3].importance_score == pytest.approx(baseline_5, rel=1e-4)

    def test_confidence_level_preserved(self):
        """``confidence_level`` interacts with the existing components; the
        weak-tag boost is applied regardless of confidence level."""
        m = _move(1, tag="overplay", score_loss=5.0)
        compute_importance_for_moves([m], user_weak_tags={"overplay": 5}, confidence_level=ConfidenceLevel.HIGH)
        high = m.importance_score

        m2 = _move(1, tag="overplay", score_loss=5.0)
        compute_importance_for_moves([m2], user_weak_tags={"overplay": 5}, confidence_level=ConfidenceLevel.MEDIUM)
        # MEDIUM and HIGH both apply the boost; HIGH adds a difficulty
        # modifier for the default NORMAL position so HIGH may differ
        # slightly. We only assert the boost is applied (not zero).
        assert m2.importance_score > 5.0  # boosted above baseline
        # And MEDIUM-without-difficulty-modifier ≈ HIGH-with-difficulty-modifier.
        # We don't assert exact equality because HIGH adds a NORMAL=0
        # modifier here, so they should be effectively the same.
        assert m2.importance_score == pytest.approx(high, rel=1e-4)

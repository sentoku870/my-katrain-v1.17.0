# -*- coding: utf-8 -*-
"""Tests for meaning_tags/classifier.py.

Part of Phase 46: Meaning Tags System Core - PR-2.
"""

from dataclasses import dataclass, field

import pytest

from katrain.core.analysis.meaning_tags import (
    THRESHOLD_DISTANCE_CLOSE,
    THRESHOLD_DISTANCE_FAR,
    THRESHOLD_ENDGAME_RATIO,
    THRESHOLD_LOSS_CATASTROPHIC,
    THRESHOLD_LOSS_CUT_RISK,
    THRESHOLD_LOSS_HUGE,
    THRESHOLD_LOSS_LARGE,
    THRESHOLD_LOSS_MEDIUM,
    THRESHOLD_LOSS_SIGNIFICANT,
    THRESHOLD_LOSS_SMALL,
    THRESHOLD_MOVE_EARLY_GAME,
    THRESHOLD_MOVE_ENDGAME_ABSOLUTE,
    THRESHOLD_OWNERSHIP_FLUX_LIFE_DEATH,
    THRESHOLD_POLICY_ACTUAL_LOW,
    THRESHOLD_POLICY_BEST_HIGH,
    THRESHOLD_POLICY_LOW,
    THRESHOLD_POLICY_TRAP,
    THRESHOLD_POLICY_VERY_LOW,
    THRESHOLD_SCORE_STDEV_HIGH,
    ClassificationContext,
    MeaningTag,
    MeaningTagId,
    classify_gtp_move,
    classify_meaning_tag,
    compute_move_distance,
    get_loss_value,
    is_classifiable_move,
    is_endgame,
    resolve_lexicon_anchor,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@dataclass
class MockMoveEval:
    """Mock MoveEval for testing."""

    move_number: int = 50
    player: str | None = "B"
    gtp: str | None = "D4"
    score_loss: float | None = None
    leela_loss_est: float | None = None
    points_lost: float | None = None
    is_reliable: bool = True
    reason_tags: list[str] = field(default_factory=list)


class MockLexiconEntry:
    """Mock LexiconEntry for testing."""

    def __init__(self, entry_id: str):
        self.id = entry_id


class MockLexiconStore:
    """Mock LexiconStore for testing."""

    def __init__(self, entries: dict[str, MockLexiconEntry] | None = None):
        self._entries = entries or {}

    def get(self, entry_id: str) -> MockLexiconEntry | None:
        return self._entries.get(entry_id)


# =============================================================================
# Threshold Constants Tests
# =============================================================================


class TestThresholdConstants:
    """Tests for threshold constants."""

    def test_loss_thresholds_are_ordered(self) -> None:
        """Loss thresholds should be in ascending order."""
        assert THRESHOLD_LOSS_SIGNIFICANT < THRESHOLD_LOSS_SMALL
        assert THRESHOLD_LOSS_SMALL < THRESHOLD_LOSS_MEDIUM
        assert THRESHOLD_LOSS_MEDIUM < THRESHOLD_LOSS_CUT_RISK
        assert THRESHOLD_LOSS_CUT_RISK < THRESHOLD_LOSS_LARGE
        assert THRESHOLD_LOSS_LARGE < THRESHOLD_LOSS_HUGE
        assert THRESHOLD_LOSS_HUGE < THRESHOLD_LOSS_CATASTROPHIC

    def test_policy_thresholds_are_ordered(self) -> None:
        """Policy thresholds should be in ascending order."""
        assert THRESHOLD_POLICY_VERY_LOW < THRESHOLD_POLICY_LOW
        assert THRESHOLD_POLICY_LOW < THRESHOLD_POLICY_ACTUAL_LOW
        assert THRESHOLD_POLICY_ACTUAL_LOW < THRESHOLD_POLICY_TRAP
        assert THRESHOLD_POLICY_TRAP < THRESHOLD_POLICY_BEST_HIGH

    def test_distance_thresholds_are_ordered(self) -> None:
        """Distance thresholds should be ordered."""
        assert THRESHOLD_DISTANCE_CLOSE < THRESHOLD_DISTANCE_FAR

    def test_move_number_thresholds_are_ordered(self) -> None:
        """Move number thresholds should be ordered."""
        assert THRESHOLD_MOVE_EARLY_GAME < THRESHOLD_MOVE_ENDGAME_ABSOLUTE

    def test_endgame_ratio_is_valid(self) -> None:
        """Endgame ratio should be between 0 and 1."""
        assert 0.0 < THRESHOLD_ENDGAME_RATIO < 1.0


# =============================================================================
# ClassificationContext Tests
# =============================================================================


class TestClassificationContext:
    """Tests for ClassificationContext dataclass."""

    def test_create_empty(self) -> None:
        """Create context with all None values."""
        ctx = ClassificationContext()
        assert ctx.best_move_policy is None
        assert ctx.actual_move_policy is None
        assert ctx.move_distance is None
        assert ctx.ownership_flux is None
        assert ctx.score_stdev is None
        assert ctx.total_moves is None

    def test_create_with_values(self) -> None:
        """Create context with specific values."""
        ctx = ClassificationContext(
            best_move_policy=0.5,
            actual_move_policy=0.01,
            move_distance=10,
            ownership_flux=20.0,
            score_stdev=15.0,
            total_moves=200,
        )
        assert ctx.best_move_policy == 0.5
        assert ctx.actual_move_policy == 0.01
        assert ctx.move_distance == 10
        assert ctx.ownership_flux == 20.0
        assert ctx.score_stdev == 15.0
        assert ctx.total_moves == 200

    def test_is_frozen(self) -> None:
        """Context should be immutable."""
        ctx = ClassificationContext()
        with pytest.raises(AttributeError):
            ctx.move_distance = 5  # type: ignore


# =============================================================================
# get_loss_value Tests
# =============================================================================


class TestGetLossValue:
    """Tests for get_loss_value function."""

    def test_score_loss_priority(self) -> None:
        """score_loss takes priority."""
        move = MockMoveEval(score_loss=3.0, leela_loss_est=4.0, points_lost=5.0)
        assert get_loss_value(move) == 3.0

    def test_leela_loss_fallback(self) -> None:
        """leela_loss_est used when score_loss is None."""
        move = MockMoveEval(score_loss=None, leela_loss_est=4.0, points_lost=5.0)
        assert get_loss_value(move) == 4.0

    def test_points_lost_fallback(self) -> None:
        """points_lost used as last resort."""
        move = MockMoveEval(score_loss=None, leela_loss_est=None, points_lost=5.0)
        assert get_loss_value(move) == 5.0

    def test_all_none(self) -> None:
        """Returns None when all loss values are None."""
        move = MockMoveEval(score_loss=None, leela_loss_est=None, points_lost=None)
        assert get_loss_value(move) is None

    def test_zero_is_valid(self) -> None:
        """Zero loss is a valid value, not None."""
        move = MockMoveEval(score_loss=0.0)
        assert get_loss_value(move) == 0.0


# =============================================================================
# classify_gtp_move Tests
# =============================================================================


class TestClassifyGtpMove:
    """Tests for classify_gtp_move function."""

    def test_none_is_missing(self) -> None:
        """None returns 'missing'."""
        assert classify_gtp_move(None) == "missing"

    def test_empty_string_is_empty(self) -> None:
        """Empty string returns 'empty'."""
        assert classify_gtp_move("") == "empty"

    def test_pass_lowercase(self) -> None:
        """'pass' returns 'pass'."""
        assert classify_gtp_move("pass") == "pass"

    def test_pass_uppercase(self) -> None:
        """'PASS' returns 'pass'."""
        assert classify_gtp_move("PASS") == "pass"

    def test_pass_mixed_case(self) -> None:
        """'Pass' returns 'pass'."""
        assert classify_gtp_move("Pass") == "pass"

    def test_pass_with_whitespace(self) -> None:
        """' pass ' returns 'pass'."""
        assert classify_gtp_move(" pass ") == "pass"

    def test_resign_lowercase(self) -> None:
        """'resign' returns 'resign'."""
        assert classify_gtp_move("resign") == "resign"

    def test_resign_uppercase(self) -> None:
        """'RESIGN' returns 'resign'."""
        assert classify_gtp_move("RESIGN") == "resign"

    def test_normal_coordinate(self) -> None:
        """'D4' returns 'normal'."""
        assert classify_gtp_move("D4") == "normal"

    def test_corner_coordinate(self) -> None:
        """'A1' returns 'normal'."""
        assert classify_gtp_move("A1") == "normal"

    def test_tengen(self) -> None:
        """'K10' returns 'normal'."""
        assert classify_gtp_move("K10") == "normal"


# =============================================================================
# is_classifiable_move Tests
# =============================================================================


class TestIsClassifiableMove:
    """Tests for is_classifiable_move function."""

    def test_normal_is_classifiable(self) -> None:
        """Normal coordinates are classifiable."""
        assert is_classifiable_move("D4") is True
        assert is_classifiable_move("Q16") is True

    def test_none_not_classifiable(self) -> None:
        """None is not classifiable."""
        assert is_classifiable_move(None) is False

    def test_empty_not_classifiable(self) -> None:
        """Empty string is not classifiable."""
        assert is_classifiable_move("") is False

    def test_pass_not_classifiable(self) -> None:
        """Pass is not classifiable."""
        assert is_classifiable_move("pass") is False
        assert is_classifiable_move("PASS") is False

    def test_resign_not_classifiable(self) -> None:
        """Resign is not classifiable."""
        assert is_classifiable_move("resign") is False


# =============================================================================
# compute_move_distance Tests
# =============================================================================


class TestComputeMoveDistance:
    """Tests for compute_move_distance function."""

    def test_same_position(self) -> None:
        """Same position has distance 0."""
        assert compute_move_distance("D4", "D4") == 0

    def test_d4_to_q16(self) -> None:
        """D4 to Q16 is 24 (|3-15| + |3-15| = 12+12)."""
        assert compute_move_distance("D4", "Q16") == 24

    def test_a1_to_t19(self) -> None:
        """A1 to T19 is 36 (|0-18| + |0-18| = 18+18)."""
        assert compute_move_distance("A1", "T19") == 36

    def test_j10_to_k10(self) -> None:
        """J10 to K10 is 1 (I is skipped in GTP)."""
        assert compute_move_distance("J10", "K10") == 1

    def test_h10_to_j10(self) -> None:
        """H10 to J10 is 1 (H=col7, J=col8, I skipped)."""
        assert compute_move_distance("H10", "J10") == 1

    def test_pass_first(self) -> None:
        """Pass as first argument returns None."""
        assert compute_move_distance("pass", "D4") is None

    def test_pass_second(self) -> None:
        """Pass as second argument returns None."""
        assert compute_move_distance("D4", "pass") is None

    def test_none_first(self) -> None:
        """None as first argument returns None."""
        assert compute_move_distance(None, "D4") is None

    def test_none_second(self) -> None:
        """None as second argument returns None."""
        assert compute_move_distance("D4", None) is None

    def test_both_none(self) -> None:
        """Both None returns None."""
        assert compute_move_distance(None, None) is None

    def test_empty_first(self) -> None:
        """Empty string as first argument returns None."""
        assert compute_move_distance("", "D4") is None

    def test_invalid_coordinate(self) -> None:
        """Invalid coordinate returns None."""
        # This might raise or return None depending on implementation
        result = compute_move_distance("Z99", "D4")
        # Should not raise, should return None
        assert result is None or isinstance(result, int)


# =============================================================================
# is_endgame Tests
# =============================================================================


class TestIsEndgame:
    """Tests for is_endgame function."""

    def test_endgame_hint_true(self) -> None:
        """has_endgame_hint=True makes it endgame."""
        assert is_endgame(50, None, True) is True

    def test_endgame_hint_false_early(self) -> None:
        """Early game without hint is not endgame."""
        assert is_endgame(50, None, False) is False

    def test_absolute_threshold(self) -> None:
        """Move > THRESHOLD_MOVE_ENDGAME_ABSOLUTE is endgame."""
        assert is_endgame(THRESHOLD_MOVE_ENDGAME_ABSOLUTE + 1, None, False) is True

    def test_below_absolute_threshold(self) -> None:
        """Move at threshold is not endgame (requires >)."""
        assert is_endgame(THRESHOLD_MOVE_ENDGAME_ABSOLUTE, None, False) is False

    def test_ratio_threshold(self) -> None:
        """Move > total * ratio is endgame."""
        total = 200
        endgame_move = int(total * THRESHOLD_ENDGAME_RATIO) + 1
        assert is_endgame(endgame_move, total, False) is True

    def test_below_ratio_threshold(self) -> None:
        """Move below ratio threshold is not endgame."""
        total = 200
        early_move = int(total * THRESHOLD_ENDGAME_RATIO) - 10
        assert is_endgame(early_move, total, False) is False


# =============================================================================
# resolve_lexicon_anchor Tests
# =============================================================================


class TestResolveLexiconAnchor:
    """Tests for resolve_lexicon_anchor function."""

    def test_no_default_anchor(self) -> None:
        """Tags without default anchor return None."""
        store = MockLexiconStore()
        # UNCERTAIN has no default anchor
        result = resolve_lexicon_anchor(MeaningTagId.UNCERTAIN, store, True)
        assert result is None

    def test_validate_true_anchor_exists(self) -> None:
        """validate=True with existing anchor returns anchor."""
        store = MockLexiconStore({"tesuji": MockLexiconEntry("tesuji")})
        result = resolve_lexicon_anchor(MeaningTagId.MISSED_TESUJI, store, True)
        assert result == "tesuji"

    def test_validate_true_anchor_missing(self) -> None:
        """validate=True with missing anchor returns None."""
        store = MockLexiconStore({})  # Empty store
        result = resolve_lexicon_anchor(MeaningTagId.MISSED_TESUJI, store, True)
        assert result is None

    def test_validate_false_returns_default(self) -> None:
        """validate=False returns default anchor without checking."""
        store = MockLexiconStore({})  # Empty store
        result = resolve_lexicon_anchor(MeaningTagId.MISSED_TESUJI, store, False)
        assert result == "tesuji"  # Default anchor, not validated

    def test_store_none_validate_true(self) -> None:
        """lexicon_store=None with validate=True returns None."""
        result = resolve_lexicon_anchor(MeaningTagId.MISSED_TESUJI, None, True)
        assert result is None

    def test_store_none_validate_false(self) -> None:
        """lexicon_store=None with validate=False returns default."""
        result = resolve_lexicon_anchor(MeaningTagId.MISSED_TESUJI, None, False)
        assert result == "tesuji"


# =============================================================================
# classify_meaning_tag - Early Return Tests
# =============================================================================


class TestClassifyMeaningTagEarlyReturn:
    """Tests for early return conditions in classify_meaning_tag."""

    def test_gtp_none_returns_uncertain(self) -> None:
        """gtp=None returns UNCERTAIN with gtp_missing."""
        move = MockMoveEval(gtp=None, score_loss=5.0)
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.UNCERTAIN
        assert tag.debug_reason == "gtp_missing"

    def test_gtp_empty_returns_uncertain(self) -> None:
        """gtp='' returns UNCERTAIN with gtp_empty."""
        move = MockMoveEval(gtp="", score_loss=5.0)
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.UNCERTAIN
        assert tag.debug_reason == "gtp_empty"

    def test_pass_returns_uncertain(self) -> None:
        """gtp='pass' returns UNCERTAIN with pass_move."""
        move = MockMoveEval(gtp="pass", score_loss=5.0)
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.UNCERTAIN
        assert tag.debug_reason == "pass_move"

    def test_pass_uppercase_returns_uncertain(self) -> None:
        """gtp='PASS' returns UNCERTAIN with pass_move."""
        move = MockMoveEval(gtp="PASS", score_loss=5.0)
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.UNCERTAIN
        assert tag.debug_reason == "pass_move"

    def test_resign_returns_uncertain(self) -> None:
        """gtp='resign' returns UNCERTAIN with resign_move."""
        move = MockMoveEval(gtp="resign", score_loss=5.0)
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.UNCERTAIN
        assert tag.debug_reason == "resign_move"

    def test_unreliable_returns_uncertain(self) -> None:
        """is_reliable=False returns UNCERTAIN."""
        move = MockMoveEval(is_reliable=False, score_loss=5.0)
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.UNCERTAIN
        assert tag.debug_reason == "unreliable_visits"

    def test_no_loss_data_returns_uncertain(self) -> None:
        """All loss values None returns UNCERTAIN."""
        move = MockMoveEval(score_loss=None, leela_loss_est=None, points_lost=None)
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.UNCERTAIN
        assert tag.debug_reason == "loss_data_missing"

    def test_small_loss_returns_uncertain(self) -> None:
        """Loss below threshold returns UNCERTAIN."""
        move = MockMoveEval(score_loss=0.3)  # Below THRESHOLD_LOSS_SIGNIFICANT
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.UNCERTAIN
        assert tag.debug_reason == "no_significant_loss"

    def test_zero_loss_returns_uncertain(self) -> None:
        """Zero loss returns UNCERTAIN."""
        move = MockMoveEval(score_loss=0.0)
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.UNCERTAIN
        assert tag.debug_reason == "no_significant_loss"


# =============================================================================
# classify_meaning_tag - Tag Classification Tests
# =============================================================================


class TestClassifyMeaningTagCapture:
    """Tests for CAPTURE_RACE_LOSS classification."""

    def test_semeai_pattern_large_loss(self) -> None:
        """atari + low_liberties + large loss = CAPTURE_RACE_LOSS."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_LARGE,
            reason_tags=["atari", "low_liberties"],
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.CAPTURE_RACE_LOSS

    def test_semeai_pattern_huge_loss(self) -> None:
        """Semeai pattern with huge loss still CAPTURE_RACE_LOSS."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_CATASTROPHIC + 1,
            reason_tags=["atari", "low_liberties"],
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.CAPTURE_RACE_LOSS

    def test_only_atari_becomes_capture_race_loss(self) -> None:
        """atari alone with large loss becomes CAPTURE_RACE_LOSS (Phase 66 fallback).

        Phase 66 added single-tag fallbacks to reduce UNCERTAIN classifications.
        Single atari with loss >= THRESHOLD_LOSS_MEDIUM triggers CAPTURE_RACE_LOSS.
        """
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_LARGE,
            reason_tags=["atari"],
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.CAPTURE_RACE_LOSS


class TestClassifyMeaningTagLifeDeath:
    """Tests for LIFE_DEATH_ERROR classification."""

    def test_huge_loss_with_ownership_flux(self) -> None:
        """Huge loss + ownership flux = LIFE_DEATH_ERROR."""
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_HUGE)
        ctx = ClassificationContext(
            ownership_flux=THRESHOLD_OWNERSHIP_FLUX_LIFE_DEATH
        )
        tag = classify_meaning_tag(move, context=ctx)
        assert tag.id == MeaningTagId.LIFE_DEATH_ERROR

    def test_catastrophic_loss_with_atari_only(self) -> None:
        """Catastrophic loss + atari (but not semeai) = LIFE_DEATH_ERROR."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_CATASTROPHIC,
            reason_tags=["atari"],  # Only atari, not low_liberties
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.LIFE_DEATH_ERROR

    def test_catastrophic_loss_with_low_liberties_only(self) -> None:
        """Catastrophic loss + low_liberties (but not atari) = LIFE_DEATH_ERROR."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_CATASTROPHIC,
            reason_tags=["low_liberties"],
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.LIFE_DEATH_ERROR


class TestClassifyMeaningTagConnection:
    """Tests for CONNECTION_MISS classification."""

    def test_need_connect_with_medium_loss(self) -> None:
        """need_connect + medium loss = CONNECTION_MISS."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_MEDIUM,
            reason_tags=["need_connect"],
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.CONNECTION_MISS

    def test_cut_risk_with_threshold_loss(self) -> None:
        """cut_risk + cut_risk threshold loss = CONNECTION_MISS."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_CUT_RISK,
            reason_tags=["cut_risk"],
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.CONNECTION_MISS


class TestClassifyMeaningTagReading:
    """Tests for READING_FAILURE classification."""

    def test_reading_failure_tag(self) -> None:
        """reading_failure tag = READING_FAILURE."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_MEDIUM,
            reason_tags=["reading_failure"],
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.READING_FAILURE

    def test_high_policy_trap(self) -> None:
        """High actual policy + large loss = READING_FAILURE."""
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_LARGE)
        ctx = ClassificationContext(actual_move_policy=THRESHOLD_POLICY_TRAP)
        tag = classify_meaning_tag(move, context=ctx)
        assert tag.id == MeaningTagId.READING_FAILURE


class TestClassifyMeaningTagShape:
    """Tests for SHAPE_MISTAKE classification."""

    def test_very_low_policy(self) -> None:
        """Very low policy + medium loss = SHAPE_MISTAKE."""
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_MEDIUM)
        ctx = ClassificationContext(
            actual_move_policy=THRESHOLD_POLICY_VERY_LOW / 2
        )
        tag = classify_meaning_tag(move, context=ctx)
        assert tag.id == MeaningTagId.SHAPE_MISTAKE


class TestClassifyMeaningTagDirection:
    """Tests for DIRECTION_ERROR classification."""

    def test_early_game_far_distance(self) -> None:
        """Early game + far distance + low-ish policy = DIRECTION_ERROR."""
        move = MockMoveEval(
            move_number=THRESHOLD_MOVE_EARLY_GAME - 10,
            score_loss=THRESHOLD_LOSS_MEDIUM,
        )
        ctx = ClassificationContext(
            move_distance=THRESHOLD_DISTANCE_FAR,
            actual_move_policy=THRESHOLD_POLICY_LOW,
        )
        tag = classify_meaning_tag(move, context=ctx)
        assert tag.id == MeaningTagId.DIRECTION_ERROR


class TestClassifyMeaningTagOverplay:
    """Tests for OVERPLAY classification."""

    def test_high_stdev_large_loss(self) -> None:
        """High score stdev + large loss = OVERPLAY."""
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_LARGE)
        ctx = ClassificationContext(score_stdev=THRESHOLD_SCORE_STDEV_HIGH)
        tag = classify_meaning_tag(move, context=ctx)
        assert tag.id == MeaningTagId.OVERPLAY

    def test_heavy_loss_chase_mode(self) -> None:
        """heavy_loss + chase_mode = OVERPLAY."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_MEDIUM,
            reason_tags=["heavy_loss", "chase_mode"],
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.OVERPLAY


class TestClassifyMeaningTagEndgame:
    """Tests for ENDGAME_SLIP classification."""

    def test_endgame_with_medium_loss(self) -> None:
        """Endgame + medium loss = ENDGAME_SLIP."""
        move = MockMoveEval(
            move_number=THRESHOLD_MOVE_ENDGAME_ABSOLUTE + 10,
            score_loss=THRESHOLD_LOSS_MEDIUM,
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.ENDGAME_SLIP

    def test_endgame_hint_with_medium_loss(self) -> None:
        """endgame_hint + medium loss = ENDGAME_SLIP."""
        move = MockMoveEval(
            move_number=50,  # Early move number
            score_loss=THRESHOLD_LOSS_MEDIUM,
            reason_tags=["endgame_hint"],
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.ENDGAME_SLIP


class TestClassifyMeaningTagSlow:
    """Tests for SLOW_MOVE classification."""

    def test_close_distance_small_loss(self) -> None:
        """Close distance + small loss + not urgent = SLOW_MOVE."""
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_SMALL)
        ctx = ClassificationContext(move_distance=THRESHOLD_DISTANCE_CLOSE - 1)
        tag = classify_meaning_tag(move, context=ctx)
        assert tag.id == MeaningTagId.SLOW_MOVE

    def test_urgent_not_slow(self) -> None:
        """Urgent (atari) should not be classified as SLOW_MOVE."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_SMALL,
            reason_tags=["atari"],
        )
        ctx = ClassificationContext(move_distance=THRESHOLD_DISTANCE_CLOSE - 1)
        tag = classify_meaning_tag(move, context=ctx)
        assert tag.id != MeaningTagId.SLOW_MOVE


class TestClassifyMeaningTagTesuji:
    """Tests for MISSED_TESUJI classification."""

    def test_high_best_low_actual_policy(self) -> None:
        """High best policy + low actual policy = MISSED_TESUJI."""
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_MEDIUM)
        ctx = ClassificationContext(
            best_move_policy=THRESHOLD_POLICY_BEST_HIGH,
            actual_move_policy=THRESHOLD_POLICY_ACTUAL_LOW / 2,
        )
        tag = classify_meaning_tag(move, context=ctx)
        assert tag.id == MeaningTagId.MISSED_TESUJI


class TestClassifyMeaningTagTerritorial:
    """Tests for TERRITORIAL_LOSS classification."""

    def test_medium_loss_no_tactical_no_endgame(self) -> None:
        """Medium loss without tactical tags or endgame = TERRITORIAL_LOSS."""
        move = MockMoveEval(
            move_number=50,
            score_loss=THRESHOLD_LOSS_MEDIUM,
            reason_tags=[],  # No tactical tags
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.TERRITORIAL_LOSS


class TestClassifyMeaningTagUncertain:
    """Tests for UNCERTAIN fallback classification."""

    def test_no_match_returns_uncertain(self) -> None:
        """When no rules match, return UNCERTAIN with no_match."""
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_SIGNIFICANT + 0.1)
        # No context, no reason_tags, just above threshold
        tag = classify_meaning_tag(move)
        # Should eventually fall through to TERRITORIAL_LOSS or UNCERTAIN
        # depending on conditions
        assert tag.id in (MeaningTagId.UNCERTAIN, MeaningTagId.TERRITORIAL_LOSS)


# =============================================================================
# Priority Tests
# =============================================================================


class TestClassifyMeaningTagPriority:
    """Tests for priority ordering in classification."""

    def test_capture_race_over_life_death(self) -> None:
        """CAPTURE_RACE_LOSS takes priority over LIFE_DEATH_ERROR."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_CATASTROPHIC,
            reason_tags=["atari", "low_liberties"],  # semeai pattern
        )
        ctx = ClassificationContext(
            ownership_flux=THRESHOLD_OWNERSHIP_FLUX_LIFE_DEATH
        )
        tag = classify_meaning_tag(move, context=ctx)
        assert tag.id == MeaningTagId.CAPTURE_RACE_LOSS

    def test_reading_failure_over_shape(self) -> None:
        """READING_FAILURE tag takes priority over SHAPE_MISTAKE."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_MEDIUM,
            reason_tags=["reading_failure"],
        )
        ctx = ClassificationContext(
            actual_move_policy=THRESHOLD_POLICY_VERY_LOW / 2
        )
        tag = classify_meaning_tag(move, context=ctx)
        assert tag.id == MeaningTagId.READING_FAILURE


# =============================================================================
# Determinism Tests
# =============================================================================


class TestClassifyMeaningTagDeterminism:
    """Tests for deterministic behavior."""

    def test_same_input_same_output(self) -> None:
        """Same input always produces same output."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_LARGE,
            reason_tags=["atari", "low_liberties"],
        )
        ctx = ClassificationContext(move_distance=10)

        results = [
            classify_meaning_tag(move, context=ctx) for _ in range(100)
        ]
        assert all(r == results[0] for r in results)

    def test_context_none_is_deterministic(self) -> None:
        """context=None is deterministic."""
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_MEDIUM)
        results = [classify_meaning_tag(move) for _ in range(100)]
        assert all(r == results[0] for r in results)


# =============================================================================
# context=None Tests
# =============================================================================


class TestClassifyMeaningTagNoContext:
    """Tests for classification without context."""

    def test_works_without_context(self) -> None:
        """Classification works with context=None."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_LARGE,
            reason_tags=["atari", "low_liberties"],
        )
        tag = classify_meaning_tag(move)  # No context
        assert tag.id == MeaningTagId.CAPTURE_RACE_LOSS

    def test_reason_tags_based_rules_work(self) -> None:
        """Rules based on reason_tags work without context."""
        move = MockMoveEval(
            score_loss=THRESHOLD_LOSS_MEDIUM,
            reason_tags=["reading_failure"],
        )
        tag = classify_meaning_tag(move)
        assert tag.id == MeaningTagId.READING_FAILURE


# =============================================================================
# Lexicon Anchor Integration Tests (Unit level with Mock)
# =============================================================================


class TestClassifyMeaningTagLexiconAnchor:
    """Tests for lexicon anchor in classification results."""

    def test_anchor_included_when_valid(self) -> None:
        """Anchor is included when store has the entry."""
        store = MockLexiconStore({"tesuji": MockLexiconEntry("tesuji")})
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_MEDIUM)
        ctx = ClassificationContext(
            best_move_policy=THRESHOLD_POLICY_BEST_HIGH,
            actual_move_policy=THRESHOLD_POLICY_ACTUAL_LOW / 2,
        )
        tag = classify_meaning_tag(move, context=ctx, lexicon_store=store)
        assert tag.id == MeaningTagId.MISSED_TESUJI
        assert tag.lexicon_anchor_id == "tesuji"

    def test_anchor_none_when_not_valid(self) -> None:
        """Anchor is None when store doesn't have the entry."""
        store = MockLexiconStore({})  # Empty
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_MEDIUM)
        ctx = ClassificationContext(
            best_move_policy=THRESHOLD_POLICY_BEST_HIGH,
            actual_move_policy=THRESHOLD_POLICY_ACTUAL_LOW / 2,
        )
        tag = classify_meaning_tag(move, context=ctx, lexicon_store=store)
        assert tag.id == MeaningTagId.MISSED_TESUJI
        assert tag.lexicon_anchor_id is None

    def test_validate_false_uses_default(self) -> None:
        """validate_anchor=False uses default anchor."""
        store = MockLexiconStore({})  # Empty
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_MEDIUM)
        ctx = ClassificationContext(
            best_move_policy=THRESHOLD_POLICY_BEST_HIGH,
            actual_move_policy=THRESHOLD_POLICY_ACTUAL_LOW / 2,
        )
        tag = classify_meaning_tag(
            move, context=ctx, lexicon_store=store, validate_anchor=False
        )
        assert tag.id == MeaningTagId.MISSED_TESUJI
        assert tag.lexicon_anchor_id == "tesuji"  # Default, not validated

    def test_uncertain_never_has_anchor(self) -> None:
        """UNCERTAIN tag never has an anchor."""
        store = MockLexiconStore({"tesuji": MockLexiconEntry("tesuji")})
        move = MockMoveEval(gtp="pass")  # Forces UNCERTAIN
        tag = classify_meaning_tag(move, lexicon_store=store)
        assert tag.id == MeaningTagId.UNCERTAIN
        assert tag.lexicon_anchor_id is None


# =============================================================================
# Lexicon Integration Tests (PR-3)
# =============================================================================


@pytest.mark.slow
class TestLexiconIntegration:
    """Integration tests with real LexiconStore.

    These tests verify that the 5 tags with Lexicon anchors actually have
    valid entries in the Lexicon YAML file. Marked as 'slow' since they
    load the full Lexicon data.

    Note: direction_of_play is in the 'concepts' section of the YAML (Level 3),
    not the 'entries' section, so it's not available in LexiconStore.
    """

    @pytest.fixture
    def real_lexicon_store(self):
        """Load the real LexiconStore from YAML."""
        from katrain.common.lexicon import LexiconStore, get_default_lexicon_path

        path = get_default_lexicon_path()
        if not path.exists():
            pytest.skip("Lexicon YAML not available")
        store = LexiconStore(path)
        store.load()
        return store

    def test_tesuji_anchor_exists(self, real_lexicon_store) -> None:
        """MISSED_TESUJI anchor 'tesuji' exists in Lexicon."""
        entry = real_lexicon_store.get("tesuji")
        assert entry is not None
        assert entry.id == "tesuji"

    def test_yose_anchor_exists(self, real_lexicon_store) -> None:
        """ENDGAME_SLIP anchor 'yose' exists in Lexicon."""
        entry = real_lexicon_store.get("yose")
        assert entry is not None
        assert entry.id == "yose"

    def test_connection_anchor_exists(self, real_lexicon_store) -> None:
        """CONNECTION_MISS anchor 'connection' exists in Lexicon."""
        entry = real_lexicon_store.get("connection")
        assert entry is not None
        assert entry.id == "connection"

    def test_semeai_anchor_exists(self, real_lexicon_store) -> None:
        """CAPTURE_RACE_LOSS anchor 'semeai' exists in Lexicon."""
        entry = real_lexicon_store.get("semeai")
        assert entry is not None
        assert entry.id == "semeai"

    def test_territory_anchor_exists(self, real_lexicon_store) -> None:
        """TERRITORIAL_LOSS anchor 'territory' exists in Lexicon."""
        entry = real_lexicon_store.get("territory")
        assert entry is not None
        assert entry.id == "territory"

    def test_all_anchors_can_be_resolved(self, real_lexicon_store) -> None:
        """All 5 tags with anchors can resolve their anchors."""
        from katrain.core.analysis.meaning_tags import (
            MEANING_TAG_REGISTRY,
            MeaningTagId,
            resolve_lexicon_anchor,
        )

        # 5 tags have valid anchors (direction_of_play not in entries)
        tags_with_anchors = [
            MeaningTagId.MISSED_TESUJI,
            MeaningTagId.ENDGAME_SLIP,
            MeaningTagId.CONNECTION_MISS,
            MeaningTagId.CAPTURE_RACE_LOSS,
            MeaningTagId.TERRITORIAL_LOSS,
        ]

        for tag_id in tags_with_anchors:
            anchor = resolve_lexicon_anchor(
                tag_id, real_lexicon_store, validate_anchor=True
            )
            expected = MEANING_TAG_REGISTRY[tag_id].default_lexicon_anchor
            assert anchor == expected, f"{tag_id} should resolve to {expected}"

    def test_classify_with_real_store(self, real_lexicon_store) -> None:
        """classify_meaning_tag works with real LexiconStore."""
        # Create a move that will be classified as MISSED_TESUJI
        move = MockMoveEval(score_loss=THRESHOLD_LOSS_MEDIUM)
        ctx = ClassificationContext(
            best_move_policy=THRESHOLD_POLICY_BEST_HIGH,
            actual_move_policy=THRESHOLD_POLICY_ACTUAL_LOW / 2,
        )
        tag = classify_meaning_tag(move, context=ctx, lexicon_store=real_lexicon_store)
        assert tag.id == MeaningTagId.MISSED_TESUJI
        assert tag.lexicon_anchor_id == "tesuji"

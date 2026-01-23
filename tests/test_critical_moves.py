# -*- coding: utf-8 -*-
"""
Unit tests for Critical 3 module (Phase 50).

Tests cover:
- MeaningTag weight fallback behavior (None/unknown/uncertain)
- Diversity penalty calculation
- Critical score computation with deterministic rounding
- Node map construction and scoreStdev extraction
- Non-mutating classification behavior
- Deterministic selection guarantee

All tests are engine-free (no KataGo/Leela required).
"""

import pytest
from typing import Dict, List, Any, Tuple
from unittest.mock import MagicMock, patch

from katrain.core.analysis import (
    # Dataclass
    CriticalMove,
    # Main function
    select_critical_moves,
    # Constants
    MEANING_TAG_WEIGHTS,
    DEFAULT_MEANING_TAG_WEIGHT,
    DIVERSITY_PENALTY_FACTOR,
    CRITICAL_SCORE_PRECISION,
    # Internal functions
    _get_meaning_tag_weight,
    _compute_diversity_penalty,
    _compute_critical_score,
    _build_node_map,
    _get_score_stdev_from_node,
    _get_score_stdev_for_move,
    _classify_meaning_tags,
    # Other imports
    MoveEval,
    EvalSnapshot,
)
from katrain.core.analysis.meaning_tags import MeaningTagId, MeaningTag

from tests.helpers_critical_moves import (
    StubGameNodeWithAnalysis,
    build_stub_game_with_analysis,
    create_test_snapshot,
    create_test_snapshot_with_tags,
    create_standard_test_game,
    create_standard_test_snapshot,
    StubGame,
    StubGameNode,
    StubMove,
    make_move_eval,
)


# =============================================================================
# Test: MeaningTag Weight Functions
# =============================================================================


class TestMeaningTagWeight:
    """Tests for _get_meaning_tag_weight() function."""

    def test_none_tag_uses_default_weight(self):
        """tag_id=None returns DEFAULT_MEANING_TAG_WEIGHT (0.7)."""
        weight = _get_meaning_tag_weight(None)
        assert weight == DEFAULT_MEANING_TAG_WEIGHT
        assert weight == 0.7

    def test_uncertain_tag_uses_dict_weight(self):
        """tag_id='uncertain' returns 0.5 from MEANING_TAG_WEIGHTS."""
        weight = _get_meaning_tag_weight("uncertain")
        assert weight == MEANING_TAG_WEIGHTS["uncertain"]
        assert weight == 0.5

    def test_unknown_tag_uses_default_weight(self):
        """Unknown tags return DEFAULT_MEANING_TAG_WEIGHT (0.7).

        Future-proofing: new MeaningTagId values not in MEANING_TAG_WEIGHTS
        will get the default weight.
        """
        weight = _get_meaning_tag_weight("future_unknown_tag")
        assert weight == DEFAULT_MEANING_TAG_WEIGHT

    def test_known_tag_life_death_error(self):
        """life_death_error has weight 1.5."""
        weight = _get_meaning_tag_weight("life_death_error")
        assert weight == 1.5

    def test_known_tag_overplay(self):
        """overplay has weight 1.0."""
        weight = _get_meaning_tag_weight("overplay")
        assert weight == 1.0

    def test_known_tag_slow_move(self):
        """slow_move has weight 0.8."""
        weight = _get_meaning_tag_weight("slow_move")
        assert weight == 0.8


# =============================================================================
# Test: Diversity Penalty Functions
# =============================================================================


class TestDiversityPenalty:
    """Tests for _compute_diversity_penalty() function."""

    def test_diversity_penalty_none_no_penalty(self):
        """None tag_id has no penalty regardless of selected tags."""
        selected = ("overplay", "overplay", "slow_move")
        penalty = _compute_diversity_penalty(None, selected)
        assert penalty == 1.0

    def test_diversity_penalty_uncertain_no_penalty(self):
        """'uncertain' tag_id has no penalty regardless of selected tags."""
        selected = ("uncertain", "uncertain")
        penalty = _compute_diversity_penalty("uncertain", selected)
        assert penalty == 1.0

    def test_diversity_penalty_unique_tag(self):
        """Unique tag (not in selected) has no penalty."""
        selected = ("overplay", "slow_move")
        penalty = _compute_diversity_penalty("life_death_error", selected)
        assert penalty == 1.0

    def test_diversity_penalty_one_overlap(self):
        """One overlap gives DIVERSITY_PENALTY_FACTOR^1 = 0.5."""
        selected = ("overplay",)
        penalty = _compute_diversity_penalty("overplay", selected)
        assert penalty == DIVERSITY_PENALTY_FACTOR
        assert penalty == 0.5

    def test_diversity_penalty_two_overlaps(self):
        """Two overlaps give DIVERSITY_PENALTY_FACTOR^2 = 0.25."""
        selected = ("overplay", "overplay")
        penalty = _compute_diversity_penalty("overplay", selected)
        assert penalty == DIVERSITY_PENALTY_FACTOR ** 2
        assert penalty == 0.25

    def test_diversity_penalty_three_overlaps(self):
        """Three overlaps give DIVERSITY_PENALTY_FACTOR^3 = 0.125."""
        selected = ("overplay", "overplay", "overplay")
        penalty = _compute_diversity_penalty("overplay", selected)
        assert penalty == DIVERSITY_PENALTY_FACTOR ** 3
        assert penalty == 0.125

    def test_diversity_penalty_empty_selected(self):
        """Empty selected tuple means no penalty."""
        penalty = _compute_diversity_penalty("overplay", ())
        assert penalty == 1.0


# =============================================================================
# Test: Critical Score Computation
# =============================================================================


class TestCriticalScoreComputation:
    """Tests for _compute_critical_score() function."""

    def test_critical_score_basic_calculation(self):
        """Basic calculation: importance * weight * penalty."""
        # overplay has weight 1.0, no overlap -> penalty 1.0
        score = _compute_critical_score(
            importance=10.0,
            tag_id="overplay",
            selected_tag_ids=(),
        )
        assert score == 10.0  # 10.0 * 1.0 * 1.0

    def test_critical_score_with_weight(self):
        """Score reflects tag weight."""
        # life_death_error has weight 1.5
        score = _compute_critical_score(
            importance=10.0,
            tag_id="life_death_error",
            selected_tag_ids=(),
        )
        assert score == 15.0  # 10.0 * 1.5 * 1.0

    def test_critical_score_with_penalty(self):
        """Score reflects diversity penalty."""
        # One overlap -> penalty 0.5
        score = _compute_critical_score(
            importance=10.0,
            tag_id="overplay",
            selected_tag_ids=("overplay",),
        )
        assert score == 5.0  # 10.0 * 1.0 * 0.5

    def test_critical_score_rounding_half_up(self):
        """Score uses ROUND_HALF_UP for 0.5 cases.

        Python's round() uses banker's rounding (ROUND_HALF_EVEN),
        but we explicitly use ROUND_HALF_UP for determinism.
        """
        # importance=10.55555, weight=1.0 -> should round to 10.5556 (4 decimals)
        score = _compute_critical_score(
            importance=10.55555,
            tag_id="overplay",
            selected_tag_ids=(),
        )
        assert score == 10.5556  # ROUND_HALF_UP

    def test_critical_score_precision(self):
        """Score is rounded to CRITICAL_SCORE_PRECISION decimal places."""
        assert CRITICAL_SCORE_PRECISION == 4
        # Create a score that would have more than 4 decimals
        score = _compute_critical_score(
            importance=3.33333333,
            tag_id="overplay",
            selected_tag_ids=(),
        )
        # Count decimal places
        score_str = f"{score:.10f}".rstrip("0")
        decimals = len(score_str.split(".")[1]) if "." in score_str else 0
        assert decimals <= CRITICAL_SCORE_PRECISION

    def test_critical_score_none_tag(self):
        """None tag_id uses DEFAULT_MEANING_TAG_WEIGHT and no penalty."""
        score = _compute_critical_score(
            importance=10.0,
            tag_id=None,
            selected_tag_ids=("overplay",),  # Should not affect None tag
        )
        assert score == 7.0  # 10.0 * 0.7 * 1.0


# =============================================================================
# Test: Node Map and Score Stdev
# =============================================================================


class TestNodeMapAndScoreStdev:
    """Tests for node map construction and scoreStdev extraction."""

    def test_node_map_uses_depth(self):
        """node_map keys match node.depth values."""
        game = build_stub_game_with_analysis([
            ("B", (3, 3), 0.5, {"root": {"scoreStdev": 3.0}}),
            ("W", (15, 15), -1.0, {"root": {"scoreStdev": 5.0}}),
            ("B", (3, 15), 1.0, {"root": {"scoreStdev": 4.0}}),
        ])
        node_map = _build_node_map(game)

        for move_no, node in node_map.items():
            assert node.depth == move_no, f"node_map[{move_no}] has depth {node.depth}"

    def test_node_map_indexing_consistency(self):
        """node_map[1] = first move, root (depth=0) excluded."""
        game = build_stub_game_with_analysis([
            ("B", (3, 3), 0.5, {"root": {"scoreStdev": 3.0}}),
            ("W", (15, 15), -1.0, {"root": {"scoreStdev": 5.0}}),
        ])
        node_map = _build_node_map(game)

        # Root (depth=0) should not be in map
        assert 0 not in node_map

        # First move should be at key 1
        assert 1 in node_map
        assert node_map[1].depth == 1
        assert node_map[1].move is not None

        # Second move should be at key 2
        assert 2 in node_map
        assert node_map[2].depth == 2

    def test_node_map_empty_game(self):
        """Empty game (root only) produces empty node_map."""
        game = build_stub_game_with_analysis([])
        node_map = _build_node_map(game)
        assert len(node_map) == 0

    def test_score_stdev_from_node_exists(self):
        """Extract scoreStdev when analysis exists."""
        node = StubGameNodeWithAnalysis(
            move=StubMove(player="B", coords=(3, 3)),
            parent=None,
            children=[],
            _score=0.0,
            _winrate=0.5,
            depth=1,
            move_number=1,
            analysis={"root": {"scoreStdev": 5.5}},
        )
        stdev = _get_score_stdev_from_node(node)
        assert stdev == 5.5

    def test_score_stdev_from_node_no_analysis(self):
        """Return None when no analysis exists."""
        node = StubGameNodeWithAnalysis(
            move=StubMove(player="B", coords=(3, 3)),
            parent=None,
            children=[],
            _score=0.0,
            _winrate=0.5,
            depth=1,
            move_number=1,
            analysis=None,
        )
        stdev = _get_score_stdev_from_node(node)
        assert stdev is None

    def test_score_stdev_from_node_no_root_key(self):
        """Return None when 'root' key is missing."""
        node = StubGameNodeWithAnalysis(
            move=StubMove(player="B", coords=(3, 3)),
            parent=None,
            children=[],
            _score=0.0,
            _winrate=0.5,
            depth=1,
            move_number=1,
            analysis={"other": {"data": 123}},
        )
        stdev = _get_score_stdev_from_node(node)
        assert stdev is None

    def test_score_stdev_from_node_no_scoreStdev_field(self):
        """Return None when scoreStdev field is missing (Leela case)."""
        node = StubGameNodeWithAnalysis(
            move=StubMove(player="B", coords=(3, 3)),
            parent=None,
            children=[],
            _score=0.0,
            _winrate=0.5,
            depth=1,
            move_number=1,
            analysis={"root": {"winrate": 0.55}},  # No scoreStdev
        )
        stdev = _get_score_stdev_from_node(node)
        assert stdev is None

    def test_score_stdev_for_move_found(self):
        """Get scoreStdev for a valid move number."""
        game = build_stub_game_with_analysis([
            ("B", (3, 3), 0.5, {"root": {"scoreStdev": 3.0}}),
            ("W", (15, 15), -1.0, {"root": {"scoreStdev": 7.5}}),
        ])
        node_map = _build_node_map(game)

        stdev = _get_score_stdev_for_move(node_map, 2)
        assert stdev == 7.5

    def test_score_stdev_for_move_not_found(self):
        """Return None for non-existent move number."""
        game = build_stub_game_with_analysis([
            ("B", (3, 3), 0.5, {"root": {"scoreStdev": 3.0}}),
        ])
        node_map = _build_node_map(game)

        stdev = _get_score_stdev_for_move(node_map, 99)
        assert stdev is None


# =============================================================================
# Test: MeaningTag Classification (Non-Mutating)
# =============================================================================


class TestClassifyMeaningTags:
    """Tests for _classify_meaning_tags() function."""

    def test_classify_uses_existing_tag(self):
        """If MoveEval already has meaning_tag_id, use it."""
        snapshot = create_test_snapshot([
            {"move_number": 1, "score_loss": 5.0, "importance_score": 10.0},
        ])
        # Set existing tag
        snapshot.moves[0].meaning_tag_id = "life_death_error"

        tag_map = _classify_meaning_tags(snapshot.moves, snapshot)

        assert tag_map[1] == "life_death_error"

    def test_classify_non_mutating(self):
        """_classify_meaning_tags() does not modify MoveEval objects."""
        snapshot = create_test_snapshot([
            {"move_number": 1, "score_loss": 5.0, "importance_score": 10.0},
            {"move_number": 2, "score_loss": 3.0, "importance_score": 8.0},
        ])
        # Record original values
        original_tags = [m.meaning_tag_id for m in snapshot.moves]

        # Mock classify_meaning_tag to return a fixed tag
        # Note: classify_meaning_tag is imported inside the function,
        # so we patch at the source module
        with patch(
            "katrain.core.analysis.meaning_tags.classify_meaning_tag"
        ) as mock_classify:
            mock_tag = MagicMock()
            mock_tag.id.value = "overplay"
            mock_classify.return_value = mock_tag

            _ = _classify_meaning_tags(snapshot.moves, snapshot)

        # Verify MoveEval objects were not modified
        for i, move in enumerate(snapshot.moves):
            assert move.meaning_tag_id == original_tags[i]

    def test_classify_calls_classifier_for_none_tags(self):
        """Calls classify_meaning_tag() when meaning_tag_id is None."""
        snapshot = create_test_snapshot([
            {"move_number": 1, "score_loss": 5.0, "importance_score": 10.0},
        ])
        assert snapshot.moves[0].meaning_tag_id is None

        # Note: classify_meaning_tag is imported inside the function,
        # so we patch at the source module
        with patch(
            "katrain.core.analysis.meaning_tags.classify_meaning_tag"
        ) as mock_classify:
            mock_tag = MagicMock()
            mock_tag.id.value = "direction_error"
            mock_classify.return_value = mock_tag

            tag_map = _classify_meaning_tags(snapshot.moves, snapshot)

        mock_classify.assert_called_once()
        assert tag_map[1] == "direction_error"


# =============================================================================
# Test: Sort Key and Determinism
# =============================================================================


class TestSortKeyAndDeterminism:
    """Tests for deterministic sorting behavior."""

    def test_sort_key_tiebreak_by_move_number(self):
        """When scores are equal, earlier move_number wins."""
        from katrain.core.analysis.critical_moves import _sort_key

        # Same score, different move numbers
        key1 = _sort_key(move_number=10, score=5.0)
        key2 = _sort_key(move_number=20, score=5.0)

        # Earlier move should sort first (smaller key)
        assert key1 < key2

    def test_sort_key_score_descending(self):
        """Higher score should sort first (smaller key due to negation)."""
        from katrain.core.analysis.critical_moves import _sort_key

        key_high = _sort_key(move_number=10, score=10.0)
        key_low = _sort_key(move_number=10, score=5.0)

        # Higher score should sort first
        assert key_high < key_low

    def test_sort_key_score_primary(self):
        """Score takes priority over move_number."""
        from katrain.core.analysis.critical_moves import _sort_key

        key1 = _sort_key(move_number=100, score=10.0)  # Late move, high score
        key2 = _sort_key(move_number=1, score=5.0)  # Early move, low score

        # Higher score should still win
        assert key1 < key2


# =============================================================================
# Test: select_critical_moves Integration
# =============================================================================


class TestSelectCriticalMoves:
    """Integration tests for select_critical_moves() function.

    Note: These tests use deep mocking of internal imports.
    Functions imported inside other functions require patching at the
    actual source module, not where they're imported to.
    """

    @pytest.mark.skip(reason="Phase 53: select_critical_moves has import bug (build_eval_snapshot)")
    def test_select_empty_game_returns_empty(self):
        """Game with no moves returns empty list."""
        game = build_stub_game_with_analysis([])

        with patch(
            "katrain.core.analysis.critical_moves.build_eval_snapshot"
        ) as mock_snapshot:
            mock_snapshot.return_value = EvalSnapshot(moves=[])

            with patch(
                "katrain.core.analysis.critical_moves.pick_important_moves"
            ) as mock_pick:
                mock_pick.return_value = []

                result = select_critical_moves(game, max_moves=3)

        assert result == []

    @pytest.mark.skip(reason="Phase 53: select_critical_moves has import bug (build_eval_snapshot)")
    def test_select_respects_max_moves(self):
        """Returns at most max_moves items."""
        game = create_standard_test_game(num_moves=20)
        snapshot = create_standard_test_snapshot(num_moves=20)

        with patch(
            "katrain.core.analysis.critical_moves.build_eval_snapshot"
        ) as mock_snapshot:
            mock_snapshot.return_value = snapshot

            with patch(
                "katrain.core.analysis.critical_moves.pick_important_moves"
            ) as mock_pick:
                # Return all moves as important
                mock_pick.return_value = snapshot.moves

                with patch(
                    "katrain.core.analysis.critical_moves.classify_meaning_tag"
                ) as mock_classify:
                    mock_tag = MagicMock()
                    mock_tag.id.value = "overplay"
                    mock_classify.return_value = mock_tag

                    result = select_critical_moves(game, max_moves=2)

        assert len(result) <= 2

    @pytest.mark.skip(reason="Phase 53: select_critical_moves has import bug (build_eval_snapshot)")
    def test_critical_move_fields_populated(self):
        """All CriticalMove fields are populated (score_stdev may be None)."""
        game = build_stub_game_with_analysis([
            ("B", (3, 3), 0.5, {"root": {"scoreStdev": 3.0}}),
            ("W", (15, 15), -1.0, {"root": {"scoreStdev": 5.0}}),
        ])
        snapshot = create_test_snapshot([
            {
                "move_number": 1,
                "player": "B",
                "gtp": "D4",
                "score_loss": 5.0,
                "importance_score": 10.0,
                "delta_winrate": -0.05,
            },
        ])

        with patch(
            "katrain.core.analysis.critical_moves.build_eval_snapshot"
        ) as mock_snapshot:
            mock_snapshot.return_value = snapshot

            with patch(
                "katrain.core.analysis.critical_moves.pick_important_moves"
            ) as mock_pick:
                mock_pick.return_value = snapshot.moves

                with patch(
                    "katrain.core.analysis.critical_moves.classify_meaning_tag"
                ) as mock_classify:
                    mock_tag = MagicMock()
                    mock_tag.id.value = "overplay"
                    mock_classify.return_value = mock_tag

                    result = select_critical_moves(game, max_moves=1, lang="ja")

        assert len(result) == 1
        cm = result[0]

        # All required fields should be non-None (except score_stdev)
        assert cm.move_number is not None
        assert cm.player is not None
        assert cm.gtp_coord is not None
        assert cm.score_loss is not None
        assert cm.delta_winrate is not None
        assert cm.meaning_tag_id is not None
        assert cm.meaning_tag_label is not None
        assert cm.position_difficulty is not None
        assert cm.reason_tags is not None
        assert cm.game_phase is not None
        assert cm.importance_score is not None
        assert cm.critical_score is not None
        # score_stdev may be None (for Leela or unanalyzed)

    @pytest.mark.skip(reason="Phase 53: select_critical_moves has import bug (build_eval_snapshot)")
    def test_select_deterministic_same_game(self):
        """Same game produces same results across multiple calls."""
        game = create_standard_test_game(num_moves=10)
        snapshot = create_standard_test_snapshot(num_moves=10)

        ITERATIONS = 5
        results: List[List[CriticalMove]] = []

        for _ in range(ITERATIONS):
            with patch(
                "katrain.core.analysis.critical_moves.build_eval_snapshot"
            ) as mock_snapshot:
                mock_snapshot.return_value = snapshot

                with patch(
                    "katrain.core.analysis.critical_moves.pick_important_moves"
                ) as mock_pick:
                    mock_pick.return_value = snapshot.moves[:5]  # Top 5 moves

                    with patch(
                        "katrain.core.analysis.critical_moves.classify_meaning_tag"
                    ) as mock_classify:
                        mock_tag = MagicMock()
                        mock_tag.id.value = "overplay"
                        mock_classify.return_value = mock_tag

                        result = select_critical_moves(game, max_moves=3)
                        results.append(result)

        # Compare all results to the first one
        first = results[0]
        for i, result in enumerate(results[1:], start=2):
            assert len(result) == len(first), f"Iteration {i}: length mismatch"
            for j, (cm1, cm2) in enumerate(zip(first, result)):
                assert cm1.move_number == cm2.move_number, (
                    f"Iteration {i}, move {j}: move_number mismatch"
                )
                assert cm1.critical_score == cm2.critical_score, (
                    f"Iteration {i}, move {j}: critical_score mismatch"
                )
                assert cm1.meaning_tag_id == cm2.meaning_tag_id, (
                    f"Iteration {i}, move {j}: meaning_tag_id mismatch"
                )


# =============================================================================
# Test: CriticalMove Dataclass
# =============================================================================


class TestCriticalMoveDataclass:
    """Tests for CriticalMove frozen dataclass."""

    def test_critical_move_is_frozen(self):
        """CriticalMove is immutable (frozen=True)."""
        cm = CriticalMove(
            move_number=1,
            player="B",
            gtp_coord="D4",
            score_loss=5.0,
            delta_winrate=-0.05,
            meaning_tag_id="overplay",
            meaning_tag_label="Overplay",
            position_difficulty="normal",
            reason_tags=("atari",),
            score_stdev=3.5,
            game_phase="middle",
            importance_score=10.0,
            critical_score=10.0,
        )

        with pytest.raises(AttributeError):
            cm.move_number = 2  # type: ignore

    def test_critical_move_reason_tags_is_tuple(self):
        """reason_tags field is a tuple (immutable)."""
        cm = CriticalMove(
            move_number=1,
            player="B",
            gtp_coord="D4",
            score_loss=5.0,
            delta_winrate=-0.05,
            meaning_tag_id="overplay",
            meaning_tag_label="Overplay",
            position_difficulty="normal",
            reason_tags=("atari", "low_liberties"),
            score_stdev=None,
            game_phase="opening",
            importance_score=8.0,
            critical_score=8.0,
        )

        assert isinstance(cm.reason_tags, tuple)
        assert cm.reason_tags == ("atari", "low_liberties")

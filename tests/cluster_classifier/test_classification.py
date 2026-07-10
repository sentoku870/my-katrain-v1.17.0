"""Cluster classification tests (Phase G-1).

Extracted from tests/test_cluster_classifier.py. Covers the
:func:`classify_cluster` dispatcher and the three concrete
classifiers: :func:`_detect_group_death`, :func:`_detect_territory_loss`,
:func:`_detect_missed_kill`. Also covers mainline-resolution failure
handling and ownership-grid orientation.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from katrain.core.analysis.board_context import OwnershipContext
from katrain.core.analysis.cluster_classifier import (
    BASE_CONFIDENCE,
    DELTA_SCALING_FACTOR,
    ClassifiedCluster,
    ClusterClassificationContext,
    ClusterSemantics,
    StoneCache,
    StoneSet,
    _detect_group_death,
    _detect_missed_kill,
    _detect_territory_loss,
    _find_group,
    _has_liberty,
    classify_cluster,
    compute_cluster_ownership_avg,
    compute_confidence,
    should_inject,
)
from tests.cluster_classifier._helpers import (
    MockMove,
    create_mock_cluster,
    create_mock_node,
    create_mock_ownership_context,
)


class TestDetectGroupDeath:
    """Test GROUP_DEATH detection."""

    def test_stone_captured(self):
        """Actor's stone disappears -> GROUP_DEATH."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
        )
        parent_stones: StoneSet = frozenset([(0, 0, "B"), (1, 1, "W")])
        child_stones: StoneSet = frozenset([(1, 1, "W")])  # Black gone

        is_death, affected, reason = _detect_group_death(cluster, "B", parent_stones, child_stones)

        assert is_death is True
        assert (0, 0, "B") in affected
        assert "lost 1 stone" in reason

    def test_multiple_stones_captured(self):
        """Multiple actor stones disappear."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0), (1, 0)]),
        )
        parent_stones: StoneSet = frozenset([(0, 0, "B"), (1, 0, "B")])
        child_stones: StoneSet = frozenset()  # All gone

        is_death, affected, reason = _detect_group_death(cluster, "B", parent_stones, child_stones)

        assert is_death is True
        assert len(affected) == 2
        assert "lost 2 stone" in reason

    def test_no_capture(self):
        """No actor stones disappear -> not GROUP_DEATH."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
        )
        parent_stones: StoneSet = frozenset([(0, 0, "B")])
        child_stones: StoneSet = frozenset([(0, 0, "B")])  # Still there

        is_death, affected, reason = _detect_group_death(cluster, "B", parent_stones, child_stones)

        assert is_death is False
        assert affected == ()


# =====================================================================
# TestDetectTerritoryLoss
# =====================================================================


class TestDetectTerritoryLoss:
    """Test TERRITORY_LOSS detection."""

    def test_territory_loss_detected(self):
        """Territory loss with opponent gain."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0), (1, 0), (2, 0)]),
            sum_delta=-3.0,  # White gains
        )
        parent_stones: StoneSet = frozenset()
        child_stones: StoneSet = frozenset()  # No stone changes

        is_loss, reason = _detect_territory_loss(cluster, "B", parent_stones, child_stones)

        assert is_loss is True
        assert "Territory loss" in reason

    def test_below_min_delta(self):
        """sum_delta below threshold -> not TERRITORY_LOSS."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            sum_delta=-0.5,  # Below 1.0 threshold
        )
        parent_stones: StoneSet = frozenset()
        child_stones: StoneSet = frozenset()

        is_loss, reason = _detect_territory_loss(cluster, "B", parent_stones, child_stones)

        assert is_loss is False
        assert "< 1.0" in reason

    def test_stone_capture_detected(self):
        """Stone capture -> not TERRITORY_LOSS (would be GROUP_DEATH)."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            sum_delta=-3.0,
        )
        parent_stones: StoneSet = frozenset([(0, 0, "B")])
        child_stones: StoneSet = frozenset()  # Stone removed

        is_loss, reason = _detect_territory_loss(cluster, "B", parent_stones, child_stones)

        assert is_loss is False
        assert "capture" in reason.lower()


# =====================================================================
# TestDetectMissedKill
# =====================================================================


class TestDetectMissedKill:
    """Test MISSED_KILL detection."""

    def test_missed_kill_detected(self):
        """Actor had advantage, opponent now has advantage."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
        )
        # Parent: actor (B) has +0.4 advantage in cluster
        parent_ctx = create_mock_ownership_context(
            board_size=(5, 5),
            ownership_grid=[[0.4] * 5 for _ in range(5)],
        )
        # Child: opponent (W) has advantage (-0.4 from B perspective)
        child_ctx = create_mock_ownership_context(
            board_size=(5, 5),
            ownership_grid=[[-0.4] * 5 for _ in range(5)],
        )

        is_missed, reason = _detect_missed_kill(cluster, "B", parent_ctx, child_ctx)

        assert is_missed is True
        assert "Missed kill" in reason

    def test_actor_never_had_advantage(self):
        """Actor didn't have advantage -> not MISSED_KILL."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
        )
        # Parent: actor (B) has -0.2 (below threshold)
        parent_ctx = create_mock_ownership_context(
            board_size=(5, 5),
            ownership_grid=[[0.2] * 5 for _ in range(5)],  # Below 0.3
        )
        child_ctx = create_mock_ownership_context(
            board_size=(5, 5),
            ownership_grid=[[-0.4] * 5 for _ in range(5)],
        )

        is_missed, reason = _detect_missed_kill(cluster, "B", parent_ctx, child_ctx)

        assert is_missed is False

    def test_white_actor_missed_kill(self):
        """White actor missed kill (sign inversion)."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
        )
        # Parent: actor (W) has advantage (-0.4 from B perspective = +0.4 from W)
        parent_ctx = create_mock_ownership_context(
            board_size=(5, 5),
            ownership_grid=[[-0.4] * 5 for _ in range(5)],
        )
        # Child: opponent (B) has advantage (+0.4 from B perspective = -0.4 from W)
        child_ctx = create_mock_ownership_context(
            board_size=(5, 5),
            ownership_grid=[[0.4] * 5 for _ in range(5)],
        )

        is_missed, reason = _detect_missed_kill(cluster, "W", parent_ctx, child_ctx)

        assert is_missed is True


# =====================================================================
# TestComputeConfidence
# =====================================================================


class TestComputeConfidence:
    """Test confidence computation."""

    def test_group_death_base(self):
        """GROUP_DEATH has base 0.7."""
        conf = compute_confidence(ClusterSemantics.GROUP_DEATH, 0.0, 0)
        assert conf == BASE_CONFIDENCE[ClusterSemantics.GROUP_DEATH]

    def test_delta_bonus(self):
        """Delta bonus is added."""
        base = BASE_CONFIDENCE[ClusterSemantics.GROUP_DEATH]  # 0.7
        # Use a small delta so it doesn't hit the 1.0 cap
        conf = compute_confidence(ClusterSemantics.GROUP_DEATH, 2.0, 0)
        expected = base + 2.0 * DELTA_SCALING_FACTOR  # 0.7 + 0.2 = 0.9
        assert conf == pytest.approx(expected)

    def test_stone_bonus(self):
        """Stone bonus is added (capped at 0.2)."""
        base = BASE_CONFIDENCE[ClusterSemantics.GROUP_DEATH]
        # 4 stones * 0.05 = 0.2 (max)
        conf = compute_confidence(ClusterSemantics.GROUP_DEATH, 0.0, 4)
        expected = base + 0.2
        assert conf == expected

        # 10 stones still caps at 0.2
        conf2 = compute_confidence(ClusterSemantics.GROUP_DEATH, 0.0, 10)
        assert conf2 == expected

    def test_capped_at_1(self):
        """Confidence is capped at 1.0."""
        conf = compute_confidence(ClusterSemantics.GROUP_DEATH, 10.0, 10)
        assert conf == 1.0

    def test_ambiguous_zero(self):
        """AMBIGUOUS has base 0."""
        conf = compute_confidence(ClusterSemantics.AMBIGUOUS, 0.0, 0)
        assert conf == 0.0


# =====================================================================
# TestShouldInject
# =====================================================================


class TestShouldInject:
    """Test injection threshold logic."""

    def test_group_death_low_threshold(self):
        """GROUP_DEATH has low threshold (0.3)."""
        classified = ClassifiedCluster(
            cluster=create_mock_cluster(coords=frozenset([(0, 0)])),
            semantics=ClusterSemantics.GROUP_DEATH,
            confidence=0.3,  # At threshold
            affected_stones=(),
            debug_reason="test",
        )
        assert should_inject(classified) is True

    def test_territory_loss_needs_min_delta(self):
        """TERRITORY_LOSS requires min delta."""
        classified = ClassifiedCluster(
            cluster=create_mock_cluster(
                coords=frozenset([(0, 0)]),
                sum_delta=-0.5,  # Below 1.0
            ),
            semantics=ClusterSemantics.TERRITORY_LOSS,
            confidence=0.6,  # Above threshold
            affected_stones=(),
            debug_reason="test",
        )
        assert should_inject(classified) is False

    def test_territory_loss_with_sufficient_delta(self):
        """TERRITORY_LOSS with sufficient delta is injected."""
        classified = ClassifiedCluster(
            cluster=create_mock_cluster(
                coords=frozenset([(0, 0), (1, 0), (2, 0)]),
                sum_delta=-3.0,  # >= 1.0
            ),
            semantics=ClusterSemantics.TERRITORY_LOSS,
            confidence=0.6,  # >= 0.5
            affected_stones=(),
            debug_reason="test",
        )
        assert should_inject(classified) is True

    def test_ambiguous_never_injected(self):
        """AMBIGUOUS is never injected (threshold 1.0)."""
        classified = ClassifiedCluster(
            cluster=create_mock_cluster(coords=frozenset([(0, 0)])),
            semantics=ClusterSemantics.AMBIGUOUS,
            confidence=0.9,  # High but < 1.0
            affected_stones=(),
            debug_reason="test",
        )
        assert should_inject(classified) is False


# =====================================================================
# TestGetSemanticsLabel
# =====================================================================


class TestMainlineResolutionFailure:
    """Test mainline resolution failure handling (Rev.6)."""

    def test_move_number_beyond_mainline(self):
        """move_number beyond mainline returns None."""
        root = create_mock_node(board_size=(5, 5))
        child = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(0, 0), player="B")],
            parent=root,
        )
        child.nodes_from_root = [root, child]
        root.children = [child]

        mock_game = MagicMock()
        mock_game.root = root
        mock_game.board_size = (5, 5)

        cache = StoneCache(mock_game)

        # Move 10 doesn't exist on mainline (only 1 move)
        node = cache._find_node_by_move_number(10)
        assert node is None

    def test_move_number_zero_returns_root(self):
        """move_number=0 returns root."""
        root = create_mock_node(board_size=(5, 5))
        mock_game = MagicMock()
        mock_game.root = root
        mock_game.board_size = (5, 5)

        cache = StoneCache(mock_game)
        stones = cache.get_stones_at_move(0)
        assert len(stones) == 0  # Root has no stones


# =====================================================================
# TestClassifyCluster
# =====================================================================


class TestClassifyCluster:
    """Test full classification flow."""

    def test_group_death_priority(self):
        """GROUP_DEATH has highest priority."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            sum_delta=-2.0,
        )
        parent_stones: StoneSet = frozenset([(0, 0, "B")])
        child_stones: StoneSet = frozenset()  # Black captured

        ctx = ClusterClassificationContext(
            actor="B",
            parent_stones=parent_stones,
            child_stones=child_stones,
            parent_ownership_ctx=create_mock_ownership_context(),
            child_ownership_ctx=create_mock_ownership_context(),
            board_size=(5, 5),
        )

        classified = classify_cluster(cluster, ctx)
        assert classified.semantics == ClusterSemantics.GROUP_DEATH

    def test_missed_kill_second_priority(self):
        """MISSED_KILL is checked after GROUP_DEATH."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            sum_delta=-2.0,
        )
        parent_stones: StoneSet = frozenset()  # No stones
        child_stones: StoneSet = frozenset()

        # Setup for missed kill
        parent_ctx = create_mock_ownership_context(
            ownership_grid=[[0.4] * 5 for _ in range(5)],  # Actor advantage
        )
        child_ctx = create_mock_ownership_context(
            ownership_grid=[[-0.4] * 5 for _ in range(5)],  # Opponent advantage
        )

        ctx = ClusterClassificationContext(
            actor="B",
            parent_stones=parent_stones,
            child_stones=child_stones,
            parent_ownership_ctx=parent_ctx,
            child_ownership_ctx=child_ctx,
            board_size=(5, 5),
        )

        classified = classify_cluster(cluster, ctx)
        assert classified.semantics == ClusterSemantics.MISSED_KILL

    def test_territory_loss_fallback(self):
        """TERRITORY_LOSS is fallback when no stones and no missed kill."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0), (1, 0), (2, 0)]),
            sum_delta=-3.0,  # Above 1.0 threshold
        )
        parent_stones: StoneSet = frozenset()
        child_stones: StoneSet = frozenset()

        ctx = ClusterClassificationContext(
            actor="B",
            parent_stones=parent_stones,
            child_stones=child_stones,
            parent_ownership_ctx=create_mock_ownership_context(),
            child_ownership_ctx=create_mock_ownership_context(),
            board_size=(5, 5),
        )

        classified = classify_cluster(cluster, ctx)
        assert classified.semantics == ClusterSemantics.TERRITORY_LOSS

    def test_ambiguous_when_nothing_matches(self):
        """AMBIGUOUS when no conditions are met."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            sum_delta=-0.5,  # Below territory loss threshold
        )
        parent_stones: StoneSet = frozenset()
        child_stones: StoneSet = frozenset()

        ctx = ClusterClassificationContext(
            actor="B",
            parent_stones=parent_stones,
            child_stones=child_stones,
            parent_ownership_ctx=create_mock_ownership_context(),
            child_ownership_ctx=create_mock_ownership_context(),
            board_size=(5, 5),
        )

        classified = classify_cluster(cluster, ctx)
        assert classified.semantics == ClusterSemantics.AMBIGUOUS


# =====================================================================
# TestFindGroupAndHasLiberty
# =====================================================================


class TestFindGroupAndHasLiberty:
    """Test internal BFS functions."""

    def test_find_group_single_stone(self):
        """Single stone forms a group of 1."""
        board = [[None] * 5 for _ in range(5)]
        board[0][0] = "B"

        group = _find_group(board, 0, 0, 5, 5)
        assert group == {(0, 0)}

    def test_find_group_connected(self):
        """Connected stones form a group."""
        board = [[None] * 5 for _ in range(5)]
        board[0][0] = "B"
        board[0][1] = "B"
        board[1][0] = "B"

        group = _find_group(board, 0, 0, 5, 5)
        assert group == {(0, 0), (1, 0), (0, 1)}

    def test_find_group_empty_cell(self):
        """Empty cell returns empty set."""
        board = [[None] * 5 for _ in range(5)]

        group = _find_group(board, 0, 0, 5, 5)
        assert group == set()

    def test_has_liberty_with_liberty(self):
        """Group with adjacent empty cell has liberty."""
        board = [[None] * 5 for _ in range(5)]
        board[0][0] = "B"  # Has liberty at (1,0) and (0,1)

        group = {(0, 0)}
        assert _has_liberty(board, group, 5, 5) is True

    def test_has_liberty_no_liberty(self):
        """Surrounded group has no liberty."""
        board = [[None] * 5 for _ in range(5)]
        board[0][0] = "B"
        board[0][1] = "W"
        board[1][0] = "W"

        group = {(0, 0)}
        assert _has_liberty(board, group, 5, 5) is False


# =====================================================================
# TestOwnershipGridOrientation
# =====================================================================


class TestOwnershipGridOrientation:
    """Test ownership grid coordinate consistency."""

    def test_ownership_context_get_at(self):
        """OwnershipContext.get_ownership_at uses (col, row)."""
        # grid[0][0] = bottom-left
        ownership_grid = [[0.0] * 5 for _ in range(5)]
        ownership_grid[0][0] = 0.9  # Bottom-left

        ctx = OwnershipContext(
            ownership_grid=ownership_grid,
            score_stdev=5.0,
            board_size=(5, 5),
        )

        # (0, 0) = bottom-left
        assert ctx.get_ownership_at((0, 0)) == 0.9
        # (4, 4) = top-right
        assert ctx.get_ownership_at((4, 4)) == 0.0

    def test_compute_cluster_ownership_avg(self):
        """Average is computed correctly using get_ownership_at."""
        ownership_grid = [[0.0] * 5 for _ in range(5)]
        ownership_grid[0][0] = 0.6
        ownership_grid[0][1] = 0.4
        # coords (0,0) and (1,0) -> grid[0][0] and grid[0][1]

        ctx = OwnershipContext(
            ownership_grid=ownership_grid,
            score_stdev=5.0,
            board_size=(5, 5),
        )

        cluster = create_mock_cluster(
            coords=frozenset([(0, 0), (1, 0)]),
        )

        avg = compute_cluster_ownership_avg(cluster, ctx)
        assert avg == pytest.approx(0.5)  # (0.6 + 0.4) / 2

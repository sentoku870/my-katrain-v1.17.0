# tests/test_cluster_classifier.py
"""Unit tests for Phase 82 cluster classifier.

Tests cover:
- ClusterSemantics enum
- Stone reconstruction (compute_stones_at_node)
- Cluster classification (GROUP_DEATH, TERRITORY_LOSS, MISSED_KILL)
- Confidence computation
- Injection thresholds
- Localized labels
- StoneCache
- Edge cases (suicide, AE ordering, mainline resolution)
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from katrain.core.analysis.cluster_classifier import (
    # Enums
    ClusterSemantics,
    # Dataclasses
    ClassifiedCluster,
    ClusterClassificationContext,
    # Stone reconstruction
    compute_stones_at_node,
    StoneCache,
    # Classification helpers
    is_opponent_gain,
    get_stones_in_cluster,
    compute_cluster_ownership_avg,
    compute_confidence,
    should_inject,
    get_semantics_label,
    # Classification
    classify_cluster,
    # Context
    build_classification_context,
    _get_cluster_context_for_move,
    # Internal (for testing)
    _detect_group_death,
    _detect_territory_loss,
    _detect_missed_kill,
    _find_group,
    _has_liberty,
    # Constants
    BASE_CONFIDENCE,
    INJECTION_THRESHOLD,
    TERRITORY_LOSS_MIN_DELTA,
    DELTA_SCALING_FACTOR,
    # Type aliases
    StoneSet,
)
from katrain.core.analysis.ownership_cluster import (
    ClusterType,
    OwnershipCluster,
)
from katrain.core.analysis.board_context import (
    BoardArea,
    OwnershipContext,
)


# =====================================================================
# Test Fixtures and Helpers
# =====================================================================


@dataclass
class MockMove:
    """Mock Move for testing."""
    coords: Optional[Tuple[int, int]]
    player: str

    @property
    def is_pass(self) -> bool:
        return self.coords is None


@dataclass
class MockGameNode:
    """Mock GameNode for testing."""
    placements: List[MockMove]
    moves: List[MockMove]
    clear_placements: List[MockMove]
    nodes_from_root: List["MockGameNode"]
    children: List["MockGameNode"]
    parent: Optional["MockGameNode"]
    move: Optional[MockMove]
    board_size: Tuple[int, int]

    @property
    def ordered_children(self) -> List["MockGameNode"]:
        return self.children


def create_mock_node(
    board_size: Tuple[int, int] = (5, 5),
    placements: Optional[List[MockMove]] = None,
    moves: Optional[List[MockMove]] = None,
    clears: Optional[List[MockMove]] = None,
    parent: Optional[MockGameNode] = None,
) -> MockGameNode:
    """Create a mock node for testing."""
    node = MockGameNode(
        placements=placements or [],
        moves=moves or [],
        clear_placements=clears or [],
        nodes_from_root=[],
        children=[],
        parent=parent,
        move=moves[0] if moves else None,
        board_size=board_size,
    )
    node.nodes_from_root = [node]
    return node


def create_mock_cluster(
    coords: frozenset,
    cluster_type: ClusterType = ClusterType.TO_WHITE,
    sum_delta: float = -3.0,
    avg_delta: float = -1.0,
    max_abs_delta: float = 1.0,
    primary_area: Optional[BoardArea] = BoardArea.CORNER,
    cell_count: int = 3,
) -> OwnershipCluster:
    """Create a mock cluster for testing."""
    return OwnershipCluster(
        coords=coords,
        cluster_type=cluster_type,
        sum_delta=sum_delta,
        avg_delta=avg_delta,
        max_abs_delta=max_abs_delta,
        primary_area=primary_area,
        cell_count=cell_count,
    )


def create_mock_ownership_context(
    board_size: Tuple[int, int] = (5, 5),
    ownership_grid: Optional[List[List[float]]] = None,
) -> OwnershipContext:
    """Create a mock OwnershipContext for testing."""
    if ownership_grid is None:
        # Default: neutral grid
        ownership_grid = [[0.0] * board_size[0] for _ in range(board_size[1])]
    return OwnershipContext(
        ownership_grid=ownership_grid,
        score_stdev=5.0,
        board_size=board_size,
    )


# =====================================================================
# TestClusterSemantics
# =====================================================================


class TestClusterSemantics:
    """Test ClusterSemantics enum."""

    def test_enum_values(self):
        assert ClusterSemantics.GROUP_DEATH.value == "group_death"
        assert ClusterSemantics.TERRITORY_LOSS.value == "territory_loss"
        assert ClusterSemantics.MISSED_KILL.value == "missed_kill"
        assert ClusterSemantics.AMBIGUOUS.value == "ambiguous"

    def test_str_conversion(self):
        # str(Enum) gives value because ClusterSemantics inherits from str
        assert ClusterSemantics.GROUP_DEATH.value == "group_death"


# =====================================================================
# TestIsOpponentGain
# =====================================================================


class TestIsOpponentGain:
    """Test is_opponent_gain helper."""

    def test_black_actor_white_gains(self):
        """sum_delta < 0 means white gains (opponent of black)."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            sum_delta=-2.0,  # White gains
        )
        assert is_opponent_gain(cluster, "B") is True

    def test_black_actor_no_gain(self):
        """sum_delta > 0 means black gains (actor's gain, not opponent)."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            sum_delta=2.0,  # Black gains
        )
        assert is_opponent_gain(cluster, "B") is False

    def test_white_actor_black_gains(self):
        """sum_delta > 0 means black gains (opponent of white)."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            cluster_type=ClusterType.TO_BLACK,
            sum_delta=2.0,  # Black gains
        )
        assert is_opponent_gain(cluster, "W") is True

    def test_white_actor_no_gain(self):
        """sum_delta < 0 means white gains (actor's gain)."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            sum_delta=-2.0,  # White gains
        )
        assert is_opponent_gain(cluster, "W") is False


# =====================================================================
# TestComputeStonesAtNode
# =====================================================================


class TestComputeStonesAtNode:
    """Test stone reconstruction from nodes_from_root (Rev.6: internal coords)."""

    def test_setup_stones_no_capture(self):
        """Placements (AB/AW) do NOT trigger captures.

        5x5 Board (row 0 = bottom):

           0 1 2 3 4  (col)
        4  . . . . .   (row 4, top)
        3  . . . . .
        2  . . . . .
        1  W . . . .   (row 1) - (0,1)=W
        0  B B . . .   (row 0, bottom) - (0,0)=B, (1,0)=B
        """
        node = create_mock_node(
            board_size=(5, 5),
            placements=[
                MockMove(coords=(0, 0), player="B"),  # Bottom-left
                MockMove(coords=(1, 0), player="B"),  # Right of it
                MockMove(coords=(0, 1), player="W"),  # Above
            ],
        )
        stones = compute_stones_at_node(node, (5, 5))

        assert len(stones) == 3
        assert (0, 0, "B") in stones
        assert (1, 0, "B") in stones
        assert (0, 1, "W") in stones

    def test_setup_stones_corner_surrounded_not_captured(self):
        """AB/AW stones are NOT captured even if surrounded.

        5x5 Board:

           0 1 2 3 4
        4  . . . . .
        3  . . . . .
        2  . . . . .
        1  W . . . .   (0,1)=W
        0  B W . . .   (0,0)=B, (1,0)=W

        Black at (0,0) has 0 liberties but is placed with AB, NOT captured.
        """
        node = create_mock_node(
            board_size=(5, 5),
            placements=[
                MockMove(coords=(0, 0), player="B"),  # Surrounded
                MockMove(coords=(0, 1), player="W"),
                MockMove(coords=(1, 0), player="W"),
            ],
        )
        stones = compute_stones_at_node(node, (5, 5))

        # All 3 stones remain (setup doesn't capture)
        assert len(stones) == 3
        assert (0, 0, "B") in stones  # Still there!

    def test_move_captures_opponent(self):
        """Moves (B/W) DO trigger captures.

        Initial (after setup):
           0 1 2 3 4
        4  . . . . .
        3  . . . . .
        2  . . . . .
        1  . . . . .
        0  W B . . .   (0,0)=W, (1,0)=B (setup)

        After B plays (0,1):
           0 1 2 3 4
        4  . . . . .
        3  . . . . .
        2  . . . . .
        1  B . . . .   (0,1)=B (capturing move)
        0  . B . . .   W at (0,0) captured!
        """
        node = create_mock_node(
            board_size=(5, 5),
            placements=[
                MockMove(coords=(0, 0), player="W"),  # Will be captured
                MockMove(coords=(1, 0), player="B"),  # Right of W
            ],
            moves=[
                MockMove(coords=(0, 1), player="B"),  # Above W -> completes encirclement
            ],
        )
        stones = compute_stones_at_node(node, (5, 5))

        # White is captured, only 2 black stones remain
        assert len(stones) == 2
        assert (0, 0, "W") not in stones  # Captured!
        assert (1, 0, "B") in stones
        assert (0, 1, "B") in stones

    def test_ae_clears_stones(self):
        """AE (clear) removes stones.

        Setup: (0,0)=B, (1,0)=B
        AE: (0,0) cleared
        Result: (1,0)=B only
        """
        node = create_mock_node(
            board_size=(5, 5),
            placements=[
                MockMove(coords=(0, 0), player="B"),
                MockMove(coords=(1, 0), player="B"),
            ],
            clears=[MockMove(coords=(0, 0), player="B")],  # AE
        )
        stones = compute_stones_at_node(node, (5, 5))

        assert len(stones) == 1
        assert (1, 0, "B") in stones
        assert (0, 0, "B") not in stones  # Cleared

    def test_suicide_move_removes_self(self):
        """Suicide move removes self-group (Rev.6 unified).

        Setup:
           0 1 2 3 4
        4  . . . . .
        3  . . . . .
        2  . . . . .
        1  W . . . .   (0,1)=W
        0  . W . . .   (1,0)=W

        B plays (0,0) -> suicide (no liberties) -> removed
        """
        node = create_mock_node(
            board_size=(5, 5),
            placements=[
                MockMove(coords=(0, 1), player="W"),
                MockMove(coords=(1, 0), player="W"),
            ],
            moves=[
                MockMove(coords=(0, 0), player="B"),  # Suicide
            ],
        )
        stones = compute_stones_at_node(node, (5, 5))

        # Black is removed due to suicide, only 2 white stones remain
        assert len(stones) == 2
        assert (0, 0, "B") not in stones  # Suicide removed
        assert (0, 1, "W") in stones
        assert (1, 0, "W") in stones

    def test_ae_order_after_placements(self):
        """AE is applied after AB/AW (Rev.6 added).

        SGF spec: setup properties are applied simultaneously.
        Implementation: AB/AW -> AE (AE can clear stones set by AB/AW).

        Setup: (0,0)=B, (1,0)=B
        AE: (0,0)
        Result: (1,0)=B only
        """
        node = create_mock_node(
            board_size=(5, 5),
            placements=[
                MockMove(coords=(0, 0), player="B"),
                MockMove(coords=(1, 0), player="B"),
            ],
            clears=[MockMove(coords=(0, 0), player="B")],  # AE same node
        )
        stones = compute_stones_at_node(node, (5, 5))

        # AE applied after AB/AW, (0,0) is cleared
        assert len(stones) == 1
        assert (0, 0, "B") not in stones
        assert (1, 0, "B") in stones

    def test_empty_node(self):
        """Empty node has no stones."""
        node = create_mock_node(board_size=(5, 5))
        stones = compute_stones_at_node(node, (5, 5))
        assert len(stones) == 0

    def test_pass_moves_ignored(self):
        """Pass moves are ignored."""
        node = create_mock_node(
            board_size=(5, 5),
            placements=[
                MockMove(coords=(0, 0), player="B"),
            ],
            moves=[
                MockMove(coords=None, player="W"),  # Pass
            ],
        )
        stones = compute_stones_at_node(node, (5, 5))
        assert len(stones) == 1
        assert (0, 0, "B") in stones


# =====================================================================
# TestGetStonesInCluster
# =====================================================================


class TestGetStonesInCluster:
    """Test coordinate mapping between cluster and stones."""

    def test_mapping_deterministic(self):
        """Mapping is deterministic (sorted)."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0), (1, 0), (0, 1)]),  # 3 points
        )
        stones: StoneSet = frozenset([
            (0, 0, "B"),  # In cluster
            (1, 0, "B"),  # In cluster
            (2, 0, "W"),  # Outside cluster
            (0, 1, "B"),  # In cluster
        ])

        result = get_stones_in_cluster(cluster, stones)

        # Sorted by (col, row, player)
        assert result == ((0, 0, "B"), (0, 1, "B"), (1, 0, "B"))

    def test_empty_cluster(self):
        """Empty cluster returns empty tuple."""
        cluster = create_mock_cluster(coords=frozenset())
        stones: StoneSet = frozenset([(0, 0, "B")])

        result = get_stones_in_cluster(cluster, stones)
        assert result == ()

    def test_no_stones_in_cluster(self):
        """Cluster with no matching stones returns empty tuple."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0), (1, 0)]),
        )
        stones: StoneSet = frozenset([(2, 2, "B")])  # Outside cluster

        result = get_stones_in_cluster(cluster, stones)
        assert result == ()


# =====================================================================
# TestDetectGroupDeath
# =====================================================================


class TestDetectGroupDeath:
    """Test GROUP_DEATH detection."""

    def test_stone_captured(self):
        """Actor's stone disappears -> GROUP_DEATH."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
        )
        parent_stones: StoneSet = frozenset([(0, 0, "B"), (1, 1, "W")])
        child_stones: StoneSet = frozenset([(1, 1, "W")])  # Black gone

        is_death, affected, reason = _detect_group_death(
            cluster, "B", parent_stones, child_stones
        )

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

        is_death, affected, reason = _detect_group_death(
            cluster, "B", parent_stones, child_stones
        )

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

        is_death, affected, reason = _detect_group_death(
            cluster, "B", parent_stones, child_stones
        )

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

        is_loss, reason = _detect_territory_loss(
            cluster, "B", parent_stones, child_stones
        )

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

        is_loss, reason = _detect_territory_loss(
            cluster, "B", parent_stones, child_stones
        )

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

        is_loss, reason = _detect_territory_loss(
            cluster, "B", parent_stones, child_stones
        )

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

        is_missed, reason = _detect_missed_kill(
            cluster, "B", parent_ctx, child_ctx
        )

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

        is_missed, reason = _detect_missed_kill(
            cluster, "B", parent_ctx, child_ctx
        )

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

        is_missed, reason = _detect_missed_kill(
            cluster, "W", parent_ctx, child_ctx
        )

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


class TestGetSemanticsLabel:
    """Test localized labels."""

    def test_none_falls_back_to_en(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, None)
        assert label == "Group captured"

    def test_empty_falls_back_to_en(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "")
        assert label == "Group captured"

    def test_jp(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "jp")
        assert label == "石が取られた"

    def test_ja_normalized_to_jp(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "ja")
        assert label == "石が取られた"

    def test_en(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "en")
        assert label == "Group captured"

    def test_unknown_falls_back_to_en(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "fr")
        assert label == "Group captured"

    def test_all_semantics_have_labels(self):
        """All semantics have labels for both languages."""
        for semantics in ClusterSemantics:
            en_label = get_semantics_label(semantics, "en")
            jp_label = get_semantics_label(semantics, "jp")
            assert en_label, f"Missing en label for {semantics}"
            assert jp_label, f"Missing jp label for {semantics}"


# =====================================================================
# TestStoneCache
# =====================================================================


class TestStoneCache:
    """Test StoneCache for efficient stone retrieval."""

    def test_cache_hit(self):
        """Cached value is returned on second call."""
        # Create a mock game with root node
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

        # First call computes
        stones1 = cache.get_stones_at_move(1)
        assert len(stones1) == 1

        # Second call returns cached (same object)
        stones2 = cache.get_stones_at_move(1)
        assert stones1 is stones2

    def test_mainline_traversal(self):
        """Cache uses ordered_children[0] for mainline."""
        root = create_mock_node(board_size=(5, 5))
        main = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(0, 0), player="B")],
            parent=root,
        )
        main.nodes_from_root = [root, main]
        variation = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(1, 1), player="B")],
            parent=root,
        )
        variation.nodes_from_root = [root, variation]

        # Main is first (mainline)
        root.children = [main, variation]

        mock_game = MagicMock()
        mock_game.root = root
        mock_game.board_size = (5, 5)

        cache = StoneCache(mock_game)
        stones = cache.get_stones_at_move(1)

        # Should find (0,0) not (1,1)
        assert (0, 0, "B") in stones
        assert (1, 1, "B") not in stones


# =====================================================================
# TestMainlineResolutionFailure
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

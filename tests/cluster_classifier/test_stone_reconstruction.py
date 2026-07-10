"""Stone-reconstruction tests (Phase G-1).

Extracted from tests/test_cluster_classifier.py. Covers
:func:`compute_stones_at_node` (the placement-vs-clearing logic),
:func:`get_stones_in_cluster` (the cell filter), and the
:class:`StoneCache` performance wrapper.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from katrain.core.analysis.cluster_classifier import (
    StoneCache,
    StoneSet,
    compute_stones_at_node,
    get_stones_in_cluster,
)
from tests.cluster_classifier._helpers import (
    MockMove,
    create_mock_cluster,
    create_mock_node,
)


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
        stones: StoneSet = frozenset(
            [
                (0, 0, "B"),  # In cluster
                (1, 0, "B"),  # In cluster
                (2, 0, "W"),  # Outside cluster
                (0, 1, "B"),  # In cluster
            ]
        )

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

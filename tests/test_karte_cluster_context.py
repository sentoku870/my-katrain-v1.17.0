# tests/test_karte_cluster_context.py
"""Integration tests for Phase 82 Karte cluster context injection.

Tests verify that cluster classification is correctly injected
into Karte's Critical 3 section when reason_tags is empty.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from katrain.core.analysis.cluster_classifier import (
    ClusterSemantics,
    StoneCache,
    _get_cluster_context_for_move,
    compute_stones_at_node,
)
from katrain.core.analysis.board_context import OwnershipContext


# =====================================================================
# Mock Fixtures
# =====================================================================


@dataclass
class MockMove:
    """Mock Move for testing."""
    coords: tuple[int, int] | None
    player: str

    @property
    def is_pass(self) -> bool:
        return self.coords is None


@dataclass
class MockGameNode:
    """Mock GameNode for testing."""
    placements: list[MockMove]
    moves: list[MockMove]
    clear_placements: list[MockMove]
    nodes_from_root: list[MockGameNode]
    children: list[MockGameNode]
    parent: MockGameNode | None
    move: MockMove | None
    board_size: tuple[int, int]
    analysis: dict | None

    @property
    def ordered_children(self) -> list[MockGameNode]:
        return self.children


def create_mock_node(
    board_size: tuple[int, int] = (5, 5),
    placements: list[MockMove] | None = None,
    moves: list[MockMove] | None = None,
    clears: list[MockMove] | None = None,
    parent: MockGameNode | None = None,
    analysis: dict | None = None,
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
        analysis=analysis,
    )
    node.nodes_from_root = [node]
    return node


def create_mock_game(
    root: MockGameNode,
    board_size: tuple[int, int] = (5, 5),
) -> MagicMock:
    """Create a mock Game object."""
    game = MagicMock()
    game.root = root
    game.board_size = board_size
    return game


# =====================================================================
# Test _get_cluster_context_for_move
# =====================================================================


class TestGetClusterContextForMove:
    """Test cluster context retrieval for moves."""

    def test_returns_none_for_move_number_zero(self):
        """move_number=0 (root) returns None (no parent)."""
        root = create_mock_node(board_size=(5, 5))
        game = create_mock_game(root)

        result = _get_cluster_context_for_move(game, 0, "en")
        assert result is None

    def test_returns_none_when_mainline_resolution_fails(self):
        """Returns None when move_number is beyond mainline."""
        root = create_mock_node(board_size=(5, 5))
        child = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(0, 0), player="B")],
            parent=root,
        )
        child.nodes_from_root = [root, child]
        root.children = [child]

        game = create_mock_game(root)

        # Only 1 move exists, asking for move 10
        result = _get_cluster_context_for_move(game, 10, "en")
        assert result is None

    def test_returns_none_when_child_node_has_no_move(self):
        """Returns None when child node has no move (e.g., setup-only node)."""
        root = create_mock_node(board_size=(5, 5))
        child = create_mock_node(
            board_size=(5, 5),
            placements=[MockMove(coords=(0, 0), player="B")],  # No moves
            parent=root,
        )
        child.move = None  # No move
        child.nodes_from_root = [root, child]
        root.children = [child]

        game = create_mock_game(root)

        result = _get_cluster_context_for_move(game, 1, "en")
        assert result is None

    def test_returns_none_when_no_clusters(self):
        """Returns None when no ownership clusters are extracted."""
        root = create_mock_node(board_size=(5, 5))
        child = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(2, 2), player="B")],
            parent=root,
        )
        child.nodes_from_root = [root, child]
        root.children = [child]

        game = create_mock_game(root)

        # Patch extract_clusters_from_nodes to return None
        with patch(
            "katrain.core.analysis.cluster_classifier.extract_clusters_from_nodes",
            return_value=None,
        ):
            result = _get_cluster_context_for_move(game, 1, "en")
            assert result is None

    def test_returns_none_when_ownership_missing(self):
        """Returns None when ownership is missing for either node."""
        root = create_mock_node(
            board_size=(5, 5),
            analysis=None,  # No ownership
        )
        child = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(2, 2), player="B")],
            parent=root,
            analysis=None,  # No ownership
        )
        child.nodes_from_root = [root, child]
        root.children = [child]

        game = create_mock_game(root)

        # Patch extract_ownership_context to return None grid
        with patch(
            "katrain.core.analysis.cluster_classifier.extract_ownership_context"
        ) as mock_extract:
            mock_extract.return_value = OwnershipContext(
                ownership_grid=None,  # Missing
                score_stdev=5.0,
                board_size=(5, 5),
            )
            result = _get_cluster_context_for_move(game, 1, "en")
            assert result is None

    def test_catches_exceptions_returns_none(self):
        """All exceptions are caught and return None."""
        root = create_mock_node(board_size=(5, 5))
        child = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(2, 2), player="B")],
            parent=root,
        )
        child.nodes_from_root = [root, child]
        root.children = [child]

        game = create_mock_game(root)

        # Patch to raise exception
        with patch(
            "katrain.core.analysis.cluster_classifier.extract_clusters_from_nodes",
            side_effect=RuntimeError("Test exception"),
        ):
            result = _get_cluster_context_for_move(game, 1, "en")
            assert result is None


class TestCacheReuse:
    """Test that StoneCache is reused across moves."""

    def test_cache_stores_computed_stones(self):
        """Cache stores computed stones for reuse."""
        root = create_mock_node(board_size=(5, 5))
        child1 = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(0, 0), player="B")],
            parent=root,
        )
        child1.nodes_from_root = [root, child1]
        child2 = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(1, 1), player="W")],
            parent=child1,
        )
        child2.nodes_from_root = [root, child1, child2]
        root.children = [child1]
        child1.children = [child2]

        game = create_mock_game(root)
        cache = StoneCache(game)

        # First call computes
        stones1 = cache.get_stones_at_move(1)
        assert len(stones1) == 1
        assert (0, 0, "B") in stones1

        # Verify it's cached (same object returned)
        stones1_again = cache.get_stones_at_move(1)
        assert stones1 is stones1_again

        # Second move
        stones2 = cache.get_stones_at_move(2)
        assert len(stones2) == 2
        assert (0, 0, "B") in stones2
        assert (1, 1, "W") in stones2


class TestClusterContextLabels:
    """Test that correct labels are returned for different languages."""

    def test_english_label(self):
        """English label for GROUP_DEATH."""
        from katrain.core.analysis.cluster_classifier import get_semantics_label
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "en")
        assert label == "Group captured"

    def test_japanese_label(self):
        """Japanese label for GROUP_DEATH."""
        from katrain.core.analysis.cluster_classifier import get_semantics_label
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "jp")
        assert label == "石が取られた"

    def test_ja_normalized_to_jp(self):
        """'ja' is normalized to 'jp'."""
        from katrain.core.analysis.cluster_classifier import get_semantics_label
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "ja")
        assert label == "石が取られた"


class TestInjectionThresholds:
    """Test injection threshold behavior."""

    def test_low_impact_territory_not_injected(self):
        """Small territory change (sum_delta < 1.0) is not injected."""
        from katrain.core.analysis.cluster_classifier import (
            should_inject,
            ClassifiedCluster,
            TERRITORY_LOSS_MIN_DELTA,
        )
        from katrain.core.analysis.ownership_cluster import (
            OwnershipCluster,
            ClusterType,
        )
        from katrain.core.analysis.board_context import BoardArea

        # sum_delta = -0.5 < 1.0
        cluster = OwnershipCluster(
            coords=frozenset([(0, 0)]),
            cluster_type=ClusterType.TO_WHITE,
            sum_delta=-0.5,
            avg_delta=-0.5,
            max_abs_delta=0.5,
            primary_area=BoardArea.CENTER,
            cell_count=1,
        )

        classified = ClassifiedCluster(
            cluster=cluster,
            semantics=ClusterSemantics.TERRITORY_LOSS,
            confidence=0.35,  # Above base but below threshold
            affected_stones=(),
            debug_reason="test",
        )

        assert abs(cluster.sum_delta) < TERRITORY_LOSS_MIN_DELTA
        assert not should_inject(classified)

    def test_significant_territory_injected(self):
        """Large territory change (sum_delta >= 1.0) is injected."""
        from katrain.core.analysis.cluster_classifier import (
            should_inject,
            ClassifiedCluster,
        )
        from katrain.core.analysis.ownership_cluster import (
            OwnershipCluster,
            ClusterType,
        )
        from katrain.core.analysis.board_context import BoardArea

        # sum_delta = -3.0 >= 1.0
        cluster = OwnershipCluster(
            coords=frozenset([(0, 0), (1, 0), (2, 0)]),
            cluster_type=ClusterType.TO_WHITE,
            sum_delta=-3.0,
            avg_delta=-1.0,
            max_abs_delta=1.0,
            primary_area=BoardArea.CORNER,
            cell_count=3,
        )

        classified = ClassifiedCluster(
            cluster=cluster,
            semantics=ClusterSemantics.TERRITORY_LOSS,
            confidence=0.6,  # Above threshold (0.5)
            affected_stones=(),
            debug_reason="test",
        )

        assert should_inject(classified)

    def test_group_death_low_threshold(self):
        """GROUP_DEATH has low injection threshold (0.3)."""
        from katrain.core.analysis.cluster_classifier import (
            should_inject,
            ClassifiedCluster,
            INJECTION_THRESHOLD,
        )
        from katrain.core.analysis.ownership_cluster import (
            OwnershipCluster,
            ClusterType,
        )
        from katrain.core.analysis.board_context import BoardArea

        cluster = OwnershipCluster(
            coords=frozenset([(0, 0)]),
            cluster_type=ClusterType.TO_WHITE,
            sum_delta=-1.0,
            avg_delta=-1.0,
            max_abs_delta=1.0,
            primary_area=BoardArea.CORNER,
            cell_count=1,
        )

        classified = ClassifiedCluster(
            cluster=cluster,
            semantics=ClusterSemantics.GROUP_DEATH,
            confidence=0.3,  # At threshold
            affected_stones=((0, 0, "B"),),
            debug_reason="test",
        )

        assert INJECTION_THRESHOLD[ClusterSemantics.GROUP_DEATH] == 0.3
        assert should_inject(classified)

    def test_ambiguous_never_injected(self):
        """AMBIGUOUS is never injected."""
        from katrain.core.analysis.cluster_classifier import (
            should_inject,
            ClassifiedCluster,
        )
        from katrain.core.analysis.ownership_cluster import (
            OwnershipCluster,
            ClusterType,
        )
        from katrain.core.analysis.board_context import BoardArea

        cluster = OwnershipCluster(
            coords=frozenset([(0, 0)]),
            cluster_type=ClusterType.TO_WHITE,
            sum_delta=-1.0,
            avg_delta=-1.0,
            max_abs_delta=1.0,
            primary_area=BoardArea.CENTER,
            cell_count=1,
        )

        classified = ClassifiedCluster(
            cluster=cluster,
            semantics=ClusterSemantics.AMBIGUOUS,
            confidence=0.99,  # Very high but still < 1.0
            affected_stones=(),
            debug_reason="test",
        )

        assert not should_inject(classified)


class TestMoveNumberIndexingConsistency:
    """Test 1-indexed move number consistency."""

    def test_move_number_1_is_first_move(self):
        """move_number=1 corresponds to first move after root."""
        root = create_mock_node(board_size=(5, 5))
        child = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(2, 2), player="B")],
            parent=root,
        )
        child.nodes_from_root = [root, child]
        root.children = [child]

        game = create_mock_game(root)
        cache = StoneCache(game)

        # move_number=0 -> root (no stones)
        stones_0 = cache.get_stones_at_move(0)
        assert len(stones_0) == 0

        # move_number=1 -> first move
        stones_1 = cache.get_stones_at_move(1)
        assert len(stones_1) == 1
        assert (2, 2, "B") in stones_1

    def test_mainline_traversal_uses_ordered_children(self):
        """Mainline uses ordered_children[0]."""
        root = create_mock_node(board_size=(5, 5))
        main = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(0, 0), player="B")],
            parent=root,
        )
        main.nodes_from_root = [root, main]
        variation = create_mock_node(
            board_size=(5, 5),
            moves=[MockMove(coords=(4, 4), player="B")],
            parent=root,
        )
        variation.nodes_from_root = [root, variation]

        # Main is first in children -> mainline
        root.children = [main, variation]

        game = create_mock_game(root)
        cache = StoneCache(game)

        stones = cache.get_stones_at_move(1)

        # Should be main (0,0), not variation (4,4)
        assert (0, 0, "B") in stones
        assert (4, 4, "B") not in stones

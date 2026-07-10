"""Shared mocks and factories for cluster-classifier tests (Phase G-1).

Extracted from tests/test_cluster_classifier.py. Provides
:class:`MockMove` and :class:`MockGameNode` plus three factory
functions: :func:`create_mock_node`, :func:`create_mock_cluster`,
and :func:`create_mock_ownership_context`.
"""

from __future__ import annotations

from dataclasses import dataclass

from katrain.core.analysis.board_context import (
    BoardArea,
    OwnershipContext,
)
from katrain.core.analysis.ownership_cluster import (
    ClusterType,
    OwnershipCluster,
)


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

    @property
    def ordered_children(self) -> list[MockGameNode]:
        return self.children


def create_mock_node(
    board_size: tuple[int, int] = (5, 5),
    placements: list[MockMove] | None = None,
    moves: list[MockMove] | None = None,
    clears: list[MockMove] | None = None,
    parent: MockGameNode | None = None,
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
    primary_area: BoardArea | None = BoardArea.CORNER,
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
    board_size: tuple[int, int] = (5, 5),
    ownership_grid: list[list[float]] | None = None,
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

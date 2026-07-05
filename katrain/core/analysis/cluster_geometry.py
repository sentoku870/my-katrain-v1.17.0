# katrain/core/analysis/cluster_geometry.py
"""Phase 173: Pure-geometry helpers for cluster classification.

Extracted from ``cluster_classifier.py`` so the heavier detection and
classification pipeline can stay focused on logic while these board-geometry
routines live on their own.

Provides:

- :func:`_find_group`  — BFS connectivity extraction (private)
- :func:`_has_liberty` — at-liberty check (private)
- :class:`StoneCache`  — caches ``compute_stones_at_node`` results across one
  Karte generation pass.

Dependencies
------------
This module re-uses :func:`compute_stones_at_node` defined in
``cluster_classifier``. The reference is intentionally one-directional
(geometry -> classifier) so that no module-level cycle is introduced; the
classifier only imports geometry symbols that it actually needs.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, cast

from katrain.core.analysis.cluster_classifier import compute_stones_at_node

if TYPE_CHECKING:
    from katrain.core.game import Game
    from katrain.core.game_node import GameNode
    from katrain.core.sgf_parser import SGFNode

    from katrain.core.analysis.cluster_classifier import StoneSet


# =====================================================================
# Pure Geometry (BFS / liberties)
# =====================================================================


def _find_group(
    board: list[list[str | None]],
    start_col: int,
    start_row: int,
    width: int,
    height: int,
) -> set[tuple[int, int]]:
    """Find connected stones of the same color using BFS (O(1) with deque)."""
    player = board[start_row][start_col]
    if player is None:
        return set()

    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque([(start_col, start_row)])

    while queue:
        col, row = queue.popleft()  # O(1) with deque
        if (col, row) in visited:
            continue
        if not (0 <= col < width and 0 <= row < height):
            continue
        if board[row][col] != player:
            continue

        visited.add((col, row))
        for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            queue.append((col + dc, row + dr))

    return visited


def _has_liberty(
    board: list[list[str | None]],
    group: set[tuple[int, int]],
    width: int,
    height: int,
) -> bool:
    """Check if a group has any liberties."""
    for col, row in group:
        for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nc, nr = col + dc, row + dr
            if 0 <= nc < width and 0 <= nr < height and board[nr][nc] is None:
                return True
    return False


# =====================================================================
# Stone Cache
# =====================================================================


class StoneCache:
    """Cache for stone positions during Karte generation (one game)."""

    def __init__(self, game: "Game"):
        self._game = game
        self._board_size = game.board_size
        self._cache: dict[int, "StoneSet"] = {}  # move_number -> stones

    def get_stones_at_move(self, move_number: int) -> "StoneSet":
        """Get stones at a move number (cached).

        Args:
            move_number: 1-indexed move number (0=root)

        Returns:
            FrozenSet of (col, row, player) tuples
        """
        if move_number in self._cache:
            return self._cache[move_number]

        node = self._find_node_by_move_number(move_number)
        if node is None:
            return frozenset()

        stones = compute_stones_at_node(node, self._board_size)
        self._cache[move_number] = stones
        return stones

    def _find_node_by_move_number(self, move_number: int) -> "GameNode | None":
        """Find node by move number on mainline.

        Uses ordered_children[0] for mainline traversal
        (KaTrain convention, game.py:841 pattern).
        """
        node = self._game.root
        for _ in range(move_number):
            if not node.children:
                return None
            # ordered_children[0] = mainline
            node = cast("GameNode", node.ordered_children[0])
        return node

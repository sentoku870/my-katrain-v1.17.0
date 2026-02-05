"""
Test helpers for Critical 3 module tests.

Extends helpers_eval_metrics.py patterns with analysis-aware stubs.
All helpers are engine-free (no KataGo/Leela required).

Part of Phase 50: Critical 3 Focused Review Mode.
"""

from dataclasses import dataclass
from typing import Any

from katrain.core.analysis.models import EvalSnapshot, MoveEval
from tests.helpers_eval_metrics import (
    StubGame,
    StubGameNode,
    StubMove,
    make_move_eval,
)

# =============================================================================
# Extended Stub Classes
# =============================================================================


@dataclass
class StubGameNodeWithAnalysis(StubGameNode):
    """StubGameNode with analysis data support.

    Extends StubGameNode to include KataGo-style analysis dict.

    Note: analysis_exists is inherited from StubGameNode.
    When creating an instance with analysis data, set analysis_exists
    appropriately based on whether analysis["root"] exists.
    """

    analysis: dict[str, Any] | None = None

    def __post_init__(self):
        """Update analysis_exists based on analysis data."""
        # analysis_exists is a field in parent class
        # We need to update it based on analysis content
        self.analysis_exists = self.analysis is not None and self.analysis.get("root") is not None


# =============================================================================
# Game Tree Builder
# =============================================================================


def build_stub_game_with_analysis(
    moves: list[tuple[str, tuple[int, int] | None, float, dict[str, Any] | None]],
) -> StubGame:
    """Build a stub game with analysis data.

    Args:
        moves: List of (player, coords, score, analysis_dict) tuples.
               - player: "B" or "W"
               - coords: (row, col) or None for pass
               - score: Black-perspective score
               - analysis_dict: Optional analysis data (e.g., {"root": {"scoreStdev": 5.0}})

    Returns:
        StubGame with linear main branch and analysis data.

    Example:
        >>> game = build_stub_game_with_analysis([
        ...     ("B", (3, 3), 0.5, {"root": {"scoreStdev": 3.0}}),
        ...     ("W", (15, 15), -1.0, {"root": {"scoreStdev": 5.0}}),
        ... ])
    """
    # Create root node (no move, depth=0)
    root = StubGameNodeWithAnalysis(
        move=None,
        parent=None,
        children=[],
        _score=0.0,
        _winrate=0.5,
        depth=0,
        move_number=0,
        analysis=None,
    )

    current = root
    for i, (player, coords, score, analysis_data) in enumerate(moves):
        move_number = i + 1
        node = StubGameNodeWithAnalysis(
            move=StubMove(player=player, coords=coords) if coords else None,
            parent=current,
            children=[],
            _score=score,
            _winrate=0.5 + score / 100.0,
            depth=move_number,
            move_number=move_number,
            analysis=analysis_data,
        )
        if current.children is None:
            current.children = []
        current.children.append(node)
        current = node

    return StubGame(root=root)


# =============================================================================
# Snapshot Builder
# =============================================================================


def create_test_snapshot(
    move_data: list[dict[str, Any]],
) -> EvalSnapshot:
    """Create a test EvalSnapshot from move data dictionaries.

    Args:
        move_data: List of dicts with MoveEval fields.
                   Required: "move_number"
                   Optional: "player", "gtp", "score_loss", "importance_score",
                            "meaning_tag_id", "position_difficulty", "reason_tags", etc.

    Returns:
        EvalSnapshot with constructed MoveEval objects.

    Example:
        >>> snapshot = create_test_snapshot([
        ...     {"move_number": 1, "player": "B", "gtp": "D4", "score_loss": 0.5},
        ...     {"move_number": 2, "player": "W", "gtp": "Q16", "score_loss": 3.0},
        ... ])
    """
    from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty

    moves: list[MoveEval] = []

    for data in move_data:
        move_number = data["move_number"]
        player = data.get("player", "B" if move_number % 2 == 1 else "W")
        gtp = data.get("gtp", f"A{move_number}")

        # Create MoveEval using helper
        move = make_move_eval(
            move_number=move_number,
            player=player,
            gtp=gtp,
            score_loss=data.get("score_loss"),
            importance_score=data.get("importance_score"),
            points_lost=data.get("points_lost"),
            delta_winrate=data.get("delta_winrate"),
            winrate_before=data.get("winrate_before"),
            winrate_after=data.get("winrate_after"),
            score_before=data.get("score_before"),
            score_after=data.get("score_after"),
            delta_score=data.get("delta_score"),
        )

        # Set optional fields
        if "meaning_tag_id" in data:
            move.meaning_tag_id = data["meaning_tag_id"]

        if "position_difficulty" in data:
            pd = data["position_difficulty"]
            if isinstance(pd, str):
                move.position_difficulty = PositionDifficulty(pd)
            else:
                move.position_difficulty = pd

        if "reason_tags" in data:
            move.reason_tags = list(data["reason_tags"])

        if "mistake_category" in data:
            mc = data["mistake_category"]
            if isinstance(mc, str):
                move.mistake_category = MistakeCategory[mc.upper()]
            else:
                move.mistake_category = mc

        moves.append(move)

    return EvalSnapshot(moves=moves)


def create_test_snapshot_with_tags(
    move_data: list[dict[str, Any]],
) -> tuple[EvalSnapshot, dict[int, str]]:
    """Create test EvalSnapshot and meaning_tag_map.

    Convenience function that returns both the snapshot and a pre-built
    meaning_tag_map for testing _classify_meaning_tags().

    Args:
        move_data: List of dicts with "move_number" and optionally "tag_id".

    Returns:
        (snapshot, meaning_tag_map) tuple

    Example:
        >>> snapshot, tag_map = create_test_snapshot_with_tags([
        ...     {"move_number": 1, "score_loss": 5.0, "tag_id": "overplay"},
        ...     {"move_number": 2, "score_loss": 3.0, "tag_id": "slow_move"},
        ... ])
    """
    snapshot = create_test_snapshot(move_data)
    tag_map: dict[int, str] = {}

    for data in move_data:
        if "tag_id" in data:
            tag_map[data["move_number"]] = data["tag_id"]

    return snapshot, tag_map


# =============================================================================
# Fixture Helpers
# =============================================================================


def create_standard_test_game(num_moves: int = 10) -> StubGame:
    """Create a standard test game with analysis data.

    Creates a game with num_moves moves, alternating B/W players,
    with varying scores and analysis data.

    Args:
        num_moves: Number of moves to create (default: 10)

    Returns:
        StubGame with analysis data suitable for most tests.
    """
    moves: list[tuple[str, tuple[int, int] | None, float, dict[str, Any] | None]] = []

    for i in range(num_moves):
        player = "B" if i % 2 == 0 else "W"
        coords = (3 + i, 3 + (i % 19))
        # Vary scores to create interesting patterns
        score = (i - num_moves // 2) * 0.5
        analysis = {"root": {"scoreStdev": 2.0 + i * 0.5}}
        moves.append((player, coords, score, analysis))

    return build_stub_game_with_analysis(moves)


def create_standard_test_snapshot(
    num_moves: int = 10,
    include_importance: bool = True,
) -> EvalSnapshot:
    """Create a standard test snapshot with varied importance scores.

    Args:
        num_moves: Number of moves
        include_importance: Whether to set importance_score

    Returns:
        EvalSnapshot suitable for testing critical move selection.
    """
    move_data: list[dict[str, Any]] = []

    for i in range(num_moves):
        move_number = i + 1
        data: dict[str, Any] = {
            "move_number": move_number,
            "player": "B" if move_number % 2 == 1 else "W",
            "gtp": f"D{move_number + 3}",
            "score_loss": 1.0 + (move_number % 5),  # 1.0 to 5.0
            "delta_winrate": -0.01 * (move_number % 5),
        }

        if include_importance:
            # Vary importance to create selection differences
            data["importance_score"] = 2.0 + (move_number % 7)  # 2.0 to 8.0

        move_data.append(data)

    return create_test_snapshot(move_data)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Extended stub classes
    "StubGameNodeWithAnalysis",
    # Game builders
    "build_stub_game_with_analysis",
    "create_standard_test_game",
    # Snapshot builders
    "create_test_snapshot",
    "create_test_snapshot_with_tags",
    "create_standard_test_snapshot",
    # Re-exports from helpers_eval_metrics
    "StubGame",
    "StubGameNode",
    "StubMove",
    "make_move_eval",
]

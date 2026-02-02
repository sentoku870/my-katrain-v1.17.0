"""
Mock analysis injection for E2E golden tests.

This module provides utilities to inject deterministic mock analysis data
into Game objects for testing karte/summary generation without KataGo.

The mock analysis follows the same internal schema as real KataGo analysis,
allowing production code paths to be tested accurately.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Deterministic loss pattern
# ---------------------------------------------------------------------------

# Loss values are chosen to cross classification thresholds reliably:
# - GOOD: < 2.0
# - INACCURACY: 2.0 <= loss < 5.0
# - MISTAKE: 5.0 <= loss < 10.0
# - BLUNDER: >= 10.0
#
# Move indices are kept low (5, 17, 34) to work with all test SGFs.
LOSS_AT_MOVE: dict[int, float] = {
    5:  2.5,   # INACCURACY (2.0 <= loss < 5.0)
    17: 6.0,   # MISTAKE (5.0 <= loss < 10.0)
    34: 12.0,  # BLUNDER (>= 10.0)
    # All other moves: 0.3 (GOOD)
}

DEFAULT_LOSS = 0.3  # GOOD category


def create_mock_analysis_dict(
    move_gtp: str,
    cumulative_score: float,
    visits: int = 500,
) -> dict[str, Any]:
    """
    Create mock analysis dict in the internal schema format.

    This creates the format that node.analysis uses internally after
    set_analysis() processes the KataGo response. Direct assignment
    to node.analysis uses this format.

    Internal schema (after set_analysis):
        {
            "root": {"visits": ..., "winrate": ..., "scoreLead": ...},
            "moves": {gtp: {...}},
            "completed": True
        }

    Args:
        move_gtp: GTP coordinate (e.g., "D4", "Q16")
        cumulative_score: Score from black's perspective after this move
        visits: Number of visits for this analysis

    Returns:
        Dict suitable for direct assignment to node.analysis
    """
    return {
        "root": {
            "visits": visits,
            "winrate": 0.5,
            "scoreLead": cumulative_score,
        },
        "moves": {
            move_gtp: {
                "move": move_gtp,
                "visits": visits,
                "winrate": 0.5,
                "scoreLead": cumulative_score,
                "order": 0,
                "pv": [],
            }
        },
        "completed": True,
    }


def inject_mock_analysis(game: Any) -> None:
    """
    Inject mock analysis into all nodes of a Game object.

    This directly sets node.analysis to bypass set_analysis() conversion,
    following the same pattern used in summary_stats.py:229.

    The cumulative score is tracked to ensure correct points_lost calculation:
    - Black's loss: prev_score - current_score (score decreases)
    - White's loss: current_score - prev_score (score increases from black's view)

    Args:
        game: Game object with a root node containing nodes_in_tree property
    """
    cumulative_score = 0.0
    move_num = 0

    for node in game.root.nodes_in_tree:
        if node.move is None:
            # Root node: set initial score
            node.analysis = {
                "root": {"visits": 500, "winrate": 0.5, "scoreLead": 0.0},
                "moves": {},
                "completed": True,
            }
            continue

        move_num += 1
        loss = LOSS_AT_MOVE.get(move_num, DEFAULT_LOSS)
        player = node.move.player  # "B" or "W"

        # Calculate score change based on player
        # Black losing points means score decreases (from black's view)
        # White losing points means score increases (from black's view)
        if player == "B":
            cumulative_score = cumulative_score - loss
        else:
            cumulative_score = cumulative_score + loss

        node.analysis = create_mock_analysis_dict(
            node.move.gtp(), cumulative_score
        )

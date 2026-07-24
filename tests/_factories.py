"""Non-fixture helper classes and factory functions used by conftest.

Not prefixed with ``test_`` so pytest does not try to collect this
module. Imported by ``tests/_fixtures.py`` which wraps them as
pytest fixtures.

Exports:

- :class:`MockKaTrainStub` — minimal KaTrain stub.
- :class:`MockEngine` — engine stub with call tracking.
- :func:`make_analysis` — build an analysis dict with explicit state.
- :func:`setup_analyzed_node` — attach analysis to a node + parent.
- :func:`make_player_info` — build a Karte player_info dict.
- :func:`make_karte_with_player_info` — build a full Karte meta dict.
- :func:`make_moves` — build a list of MoveEval objects.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from katrain.core.analysis.models.move_eval import MoveEval
from katrain.core.constants import PLAYER_HUMAN, PLAYING_NORMAL

# ---------------------------------------------------------------------------
# Game/Engine stub classes
# ---------------------------------------------------------------------------


class MockKaTrainStub:
    """Lightweight stub for KaTrain.

    Provides minimal interface needed by Game without KaTrainBase inheritance.

    MINIMAL REQUIRED INTERFACE (v6):
    --------------------------------
    Attributes:
        pondering: bool            - Used by STOP mode (set to False)
        controls: object           - Needs .set_status() method for status messages

    Methods:
        config(key, default=None)  - Used by Game for thresholds/rules lookup
        log(*args, **kwargs)       - Called for debug output (can be no-op)
    """

    def __init__(self):
        self.pondering = False
        self.controls = MagicMock()
        self._config = {
            "trainer/eval_thresholds": [0, 0.5, 1.0, 2.0, 5.0],
            "game/handicap": 0,
            "game/rules": "japanese",
        }
        self.players_info = {
            "B": MagicMock(name="B_player", player_type=PLAYER_HUMAN, player_subtype=PLAYING_NORMAL),
            "W": MagicMock(name="W_player", player_type=PLAYER_HUMAN, player_subtype=PLAYING_NORMAL),
        }
        # State notifier is optional; tests that need it should set it explicitly

    def update_state(self, *args, **kwargs):
        """No-op update_state for tests that don't need state propagation."""
        pass

    def config(self, key, default=None):
        return self._config.get(key, default)

    def log(self, *args, **kwargs):
        pass


class MockEngine:
    """Mock engine with call tracking.

    MINIMAL REQUIRED INTERFACE (v7):
    --------------------------------
    Attributes:
        config: dict               - Needs "max_visits", "fast_visits" keys

    Methods:
        request_analysis(*args, **kwargs)  - Called by node.analyze()
        stop_pondering()                   - Called by STOP mode
        terminate_queries()                - Called by STOP mode
        has_query_capacity(headroom)       - Called by analyze_all_nodes() for throttling

    Tracking (test-only):
        stop_pondering_called: bool
        terminate_queries_called: bool
        request_analysis_calls: list[dict]
        reset_tracking()
    """

    def __init__(self, config=None):
        self.config = config or {"max_visits": 100, "fast_visits": 50}
        self.stop_pondering_called = False
        self.terminate_queries_called = False
        self.request_analysis_calls = []

    def request_analysis(self, *args, **kwargs):
        """Track analysis requests for assertion."""
        self.request_analysis_calls.append({"args": args, "kwargs": kwargs})

    def stop_pondering(self):
        self.stop_pondering_called = True

    def terminate_queries(self):
        self.terminate_queries_called = True

    def has_query_capacity(self, headroom: int = 10) -> bool:
        """Mock always has capacity (no throttling in tests)."""
        return True

    def check_alive(self, *args, **kwargs):
        """Mock engine is always alive (used by AI strategies)."""
        return True

    def reset_tracking(self):
        """Reset call tracking for fresh assertions."""
        self.stop_pondering_called = False
        self.terminate_queries_called = False
        self.request_analysis_calls = []


# ---------------------------------------------------------------------------
# Analysis state factories (v6)
# ---------------------------------------------------------------------------


def make_analysis(
    *,
    root_present: bool = True,
    completed: bool = True,
    moves: dict = None,
    score: float = 0.0,
    visits: int = 500,
) -> dict:
    """Factory for creating analysis dict with explicit state control.

    Args:
        root_present: If True, include "root" dict; if False, set to None
        completed: Value for "completed" flag
        moves: Dict of move candidates (default: {"D4": {...}})
        score: scoreLead value (used if root_present=True)
        visits: visits value for root and moves

    Returns:
        Analysis dict matching GameNode.analysis structure

    Examples:
        # Complete analysis with moves
        make_analysis(score=5.0)

        # Incomplete analysis (analysis_complete=False)
        make_analysis(completed=False)

        # No root (analysis_exists=False when root is None)
        make_analysis(root_present=False)

        # Empty moves (triggers LOCAL mode bug)
        make_analysis(moves={})
    """
    if moves is None:
        moves = {"D4": {"visits": visits // 5, "scoreLead": score}}

    return {
        "root": {"scoreLead": score, "visits": visits} if root_present else None,
        "moves": moves,
        "completed": completed,
        "ownership": None,
        "policy": None,
    }


def setup_analyzed_node(node, score, parent_score=None, *, force_parent=False):
    """Setup analysis data on a node for testing.

    For points_lost to work correctly, both node and parent need analysis.

    BEHAVIOR (v6 - fixed):
    - Always sets node.analysis
    - Only sets parent.analysis if:
      a) parent_score is provided, AND
      b) parent exists, AND
      c) parent.analysis is not already set (or force_parent=True)

    Args:
        node: GameNode to setup
        score: scoreLead for this node
        parent_score: scoreLead for parent (optional)
        force_parent: If True, overwrite parent.analysis even if already set

    Example:
        # Simple: just set node analysis
        setup_analyzed_node(node, score=5.0)

        # With parent for points_lost calculation
        setup_analyzed_node(node, score=5.0, parent_score=0.0)

        # Chain setup (preserves earlier parent analysis)
        setup_analyzed_node(node1, score=0.0)
        setup_analyzed_node(node2, score=3.0, parent_score=0.0)  # Sets node2's parent
        setup_analyzed_node(node3, score=5.0)  # node2 already has analysis, not overwritten
    """
    node.analysis = make_analysis(score=score)

    if node.parent and parent_score is not None:
        # Only set parent analysis if not already set (or forced)
        parent_has_analysis = (
            node.parent.analysis.get("root") is not None if isinstance(node.parent.analysis, dict) else False
        )
        if force_parent or not parent_has_analysis:
            node.parent.analysis = make_analysis(score=parent_score, moves={})


# ---------------------------------------------------------------------------
# Karte / Summary shared factories
# ---------------------------------------------------------------------------


def make_player_info(
    black_name: str = "P1",
    black_rank: str | None = "4d",
    white_name: str = "P2",
    white_rank: str | None = "3d",
) -> dict:
    """Build a ``player_info`` dict for Karte meta / detect_player_info().

    Returns:
        ``{"black": {"name": ..., "rank": ...}, "white": {"name": ..., "rank": ...}}``
    """
    return {
        "black": {"name": black_name, "rank": black_rank},
        "white": {"name": white_name, "rank": white_rank},
    }


def make_karte_with_player_info(
    black_name: str = "P1",
    black_rank: str | None = "4d",
    white_name: str = "P2",
    white_rank: str | None = "3d",
) -> dict:
    """Build a minimal Karte JSON dict with ``meta.player_info`` populated.

    Convenience wrapper for the file-write pattern:

        karte.write_text(json.dumps(make_karte_with_player_info()), encoding="utf-8")
    """
    return {"meta": {"player_info": make_player_info(black_name, black_rank, white_name, white_rank)}}


# ---------------------------------------------------------------------------
# MoveEval factory
# ---------------------------------------------------------------------------


def make_moves(
    count: int = 10,
    *,
    player: str = "B",
    visits: int = 500,
    loss_pattern: list[float] | None = None,
) -> list[MoveEval]:
    """Factory fixture body to create a list of ``MoveEval`` objects.

    Args:
        count: Number of moves to create
        player: Player for all moves (or alternating if "BW")
        visits: Root visits for all moves
        loss_pattern: List of score_loss values (cycled if shorter than count)
    """
    moves = []
    if loss_pattern is None:
        loss_pattern = [0.5]  # Default: small loss

    for i in range(count):
        p = player if player in ("B", "W") else ("B" if i % 2 == 0 else "W")
        loss = loss_pattern[i % len(loss_pattern)]

        move = MoveEval(
            move_number=i + 1,
            player=p,
            gtp=f"D{i + 1}" if i < 19 else f"Q{i - 18}",
            score_before=0.0,
            score_after=-loss if p == "B" else loss,
            delta_score=-loss if p == "B" else loss,
            winrate_before=0.5,
            winrate_after=0.5,
            delta_winrate=0.0,
            points_lost=loss,
            realized_points_lost=None,
            root_visits=visits,
        )
        move.score_loss = max(0.0, loss)
        moves.append(move)

    return moves

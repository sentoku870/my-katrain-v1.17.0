"""
Shared test fixtures and stubs for eval_metrics tests.
"""

from dataclasses import dataclass

from katrain.core.eval_metrics import (
    MistakeCategory,
    MoveEval,
    PositionDifficulty,
)

# ---------------------------------------------------------------------------
# Helper function to create MoveEval with defaults
# ---------------------------------------------------------------------------


def make_move_eval(
    move_number: int = 1,
    player: str = "B",
    gtp: str = "D4",
    score_before: float | None = None,
    score_after: float | None = None,
    delta_score: float | None = None,
    winrate_before: float | None = None,
    winrate_after: float | None = None,
    delta_winrate: float | None = None,
    points_lost: float | None = None,
    realized_points_lost: float | None = None,
    root_visits: int = 1000,
    score_loss: float | None = None,
    winrate_loss: float | None = None,
    mistake_category: MistakeCategory = MistakeCategory.GOOD,
    position_difficulty: PositionDifficulty | None = None,
    importance_score: float | None = None,
    leela_loss_est: float | None = None,  # Phase 32: Leela support
) -> MoveEval:
    """Helper to create MoveEval with sensible defaults"""
    m = MoveEval(
        move_number=move_number,
        player=player,
        gtp=gtp,
        score_before=score_before,
        score_after=score_after,
        delta_score=delta_score,
        winrate_before=winrate_before,
        winrate_after=winrate_after,
        delta_winrate=delta_winrate,
        points_lost=points_lost,
        realized_points_lost=realized_points_lost,
        root_visits=root_visits,
    )
    m.score_loss = score_loss
    m.winrate_loss = winrate_loss
    m.mistake_category = mistake_category
    m.position_difficulty = position_difficulty
    m.importance_score = importance_score
    m.leela_loss_est = leela_loss_est  # Phase 32: Leela support
    return m


# ---------------------------------------------------------------------------
# Stub classes for testing without real GameNode
# ---------------------------------------------------------------------------


@dataclass
class StubMove:
    """Minimal stub for a move (coordinates + player)"""

    player: str  # "B" or "W"
    coords: tuple  # (row, col)

    def gtp(self) -> str:
        if self.coords is None:
            return "pass"
        col_letter = "ABCDEFGHJKLMNOPQRST"[self.coords[1]]  # skip I
        return f"{col_letter}{self.coords[0] + 1}"


@dataclass
class StubGameNode:
    """
    Minimal stub for GameNode that mimics KaTrain's perspective conventions.

    score/winrate: BLACK-PERSPECTIVE (from KataGo)
    points_lost: SIDE-TO-MOVE perspective (computed with player_sign)
    """

    move: StubMove | None = None
    parent: "StubGameNode | None" = None
    children: "list[StubGameNode] | None" = None
    _score: float | None = None  # Black-perspective
    _winrate: float | None = None  # Black-perspective
    analysis_exists: bool = True
    root_visits: int = 1000
    depth: int = 1
    move_number: int = 0

    @property
    def score(self) -> float | None:
        """BLACK-PERSPECTIVE: positive = black ahead"""
        return self._score

    @property
    def winrate(self) -> float | None:
        """BLACK-PERSPECTIVE: > 0.5 = black winning"""
        return self._winrate

    @staticmethod
    def player_sign(player: str) -> int:
        """Returns +1 for Black, -1 for White"""
        return {"B": 1, "W": -1, None: 0}[player]

    @property
    def points_lost(self) -> float | None:
        """
        SIDE-TO-MOVE perspective: positive = loss for the moving player.

        Formula: player_sign(player) * (parent_score - current_score)
        """
        if self.move is None or self.parent is None:
            return None
        if self._score is None or self.parent._score is None:
            return None
        parent_score = self.parent._score
        current_score = self._score
        return self.player_sign(self.move.player) * (parent_score - current_score)


# ---------------------------------------------------------------------------
# Helper to build game trees for integration tests
# ---------------------------------------------------------------------------


@dataclass
class StubGame:
    """Minimal stub for Game object with a root node"""

    root: StubGameNode | None = None


def build_stub_game_tree(
    moves: list[tuple],
) -> StubGame:
    """
    Build a simple game tree from a list of moves.

    Args:
        moves: List of (player, coords, score) tuples.
               Example: [("B", (3, 3), 0.5), ("W", (15, 15), -1.0), ...]

    Returns:
        StubGame with a linear main branch.
    """
    # Create root node (no move)
    root = StubGameNode(
        move=None,
        parent=None,
        children=[],
        _score=0.0,
        _winrate=0.5,
        depth=0,
        move_number=0,
    )

    current = root
    for i, (player, coords, score) in enumerate(moves):
        move_number = i + 1
        node = StubGameNode(
            move=StubMove(player=player, coords=coords),
            parent=current,
            children=[],
            _score=score,
            _winrate=0.5 + score / 100.0,  # Simple winrate approximation
            depth=move_number,
            move_number=move_number,
        )
        if current.children is None:
            current.children = []
        current.children.append(node)
        current = node

    return StubGame(root=root)

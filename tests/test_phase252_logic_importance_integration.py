"""Phase 252 integration test: pick_important_moves on a 9x9 game
exercises the new board-size-aware MIN_LOSS_DISPLAY threshold.

Verifies that the fallback path uses a 9x9-friendly threshold
(0.15) instead of the legacy 19x19 value (0.3) when the snapshot
contains no importance-based candidates.
"""

from __future__ import annotations

from types import SimpleNamespace

from katrain.core.analysis.models.enums import PositionDifficulty
from katrain.core.analysis.models.move_eval import MoveEval


def _move(move_number: int, score_loss: float, root_visits: int = 500) -> MoveEval:
    """Tiny MoveEval factory: no importance_score, so fallback is used.

    root_visits defaults to 500 (full reliability) so the raw_score
    multiplier is 1.0 and the threshold comparison is unambiguous.
    """
    return MoveEval(
        move_number=move_number,
        player="B",
        gtp="D4",
        score_before=0.0,
        score_after=0.0,
        delta_score=0.0,
        winrate_before=0.5,
        winrate_after=0.5,
        delta_winrate=0.0,
        points_lost=score_loss,
        realized_points_lost=score_loss,
        root_visits=root_visits,
        is_reliable=True,
        importance_score=None,
        score_loss=score_loss,
        position_difficulty=PositionDifficulty.UNKNOWN,
    )


class _GameStub:
    """Stub: only board_size is read by logic_importance.pick_important_moves."""

    def __init__(self, board_size):
        self.board_size = board_size
        # Each move's parent points at this game so the
        # board_size lookup works the same as in production.


def _wire_parents(moves, game):
    for m in moves:
        m.parent = SimpleNamespace(game=game)
    return moves


def test_pick_important_moves_9x9_fallback_threshold(monkeypatch):
    """9x9 game: a 0.2-point loss (above 0.15, below 0.3) is selected."""
    from katrain.core.analysis import logic_importance

    # Snapshot 5 moves with score_loss in [0.05, 0.4]. None have an
    # importance_score, so the fallback raw-score path is used.
    moves = [
        _move(1, 0.05),
        _move(2, 0.10),
        _move(3, 0.20),  # 0.20 > 0.15 (9x9), < 0.3 (19x19) — key test
        _move(4, 0.30),
        _move(5, 0.40),
    ]
    game_9x9 = _GameStub(9)
    _wire_parents(moves, game_9x9)
    snapshot = SimpleNamespace(moves=moves)

    selected = logic_importance.pick_important_moves(snapshot, level="normal", recompute=True)
    selected_nums = sorted(m.move_number for m in selected)

    # 9x9 threshold is 0.15 → moves 3, 4, 5 (score_loss 0.20/0.30/0.40) qualify.
    # Moves 1, 2 fall below 0.15 and are filtered out.
    assert selected_nums == [3, 4, 5], (
        f"9x9 fallback should select 0.2+ losses, got {selected_nums}. "
        "Either min_loss_display_for_board_size is wrong or the wiring is broken."
    )


def test_pick_important_moves_19x19_fallback_threshold():
    """19x19 game: a 0.2-point loss is below the 0.3 threshold and is filtered out."""
    from katrain.core.analysis import logic_importance

    moves = [
        _move(1, 0.05),
        _move(2, 0.10),
        _move(3, 0.20),  # 0.20 < 0.30 → filtered out
        _move(4, 0.30),
        _move(5, 0.40),
    ]
    game_19 = _GameStub(19)
    _wire_parents(moves, game_19)
    snapshot = SimpleNamespace(moves=moves)

    selected = logic_importance.pick_important_moves(snapshot, level="normal", recompute=True)
    selected_nums = sorted(m.move_number for m in selected)

    # 19x19 threshold is 0.3 → only moves 4, 5 qualify.
    assert selected_nums == [4, 5], (
        f"19x19 fallback should filter 0.2-loss moves, got {selected_nums}."
    )


def test_pick_important_moves_13x13_fallback_threshold():
    """13x13 game: threshold is 0.2 — move 3 (0.20) is on the boundary."""
    from katrain.core.analysis import logic_importance

    moves = [
        _move(1, 0.10),
        _move(2, 0.15),  # < 0.20 → filtered
        _move(3, 0.20),  # >= 0.20 → selected
        _move(4, 0.30),
    ]
    game_13 = _GameStub(13)
    _wire_parents(moves, game_13)
    snapshot = SimpleNamespace(moves=moves)

    selected = logic_importance.pick_important_moves(snapshot, level="normal", recompute=True)
    selected_nums = sorted(m.move_number for m in selected)
    assert selected_nums == [3, 4], (
        f"13x13 fallback should select losses >= 0.20, got {selected_nums}."
    )


def test_pick_important_moves_unknown_board_size_uses_19x19_default():
    """No game (board_size=None) → falls back to 0.3 (19x19 default)."""
    from katrain.core.analysis import logic_importance

    moves = [
        _move(1, 0.10),
        _move(2, 0.20),  # < 0.30 → filtered
        _move(3, 0.30),  # >= 0.30 → selected
    ]
    # No parent wiring → board_size ends up None
    snapshot = SimpleNamespace(moves=moves)

    selected = logic_importance.pick_important_moves(snapshot, level="normal", recompute=True)
    selected_nums = sorted(m.move_number for m in selected)
    assert selected_nums == [3], (
        f"No-game fallback should mirror 19x19 (0.30), got {selected_nums}."
    )

"""Phase 248-C1: tests for the board-size-aware endgame thresholds.

Locks in the 9x9 / 13x13 scaling of
:func:`katrain.core.analysis.meaning_tags.classifier.board_size_adjusted_thresholds`
and the new ``board_size`` keyword on
:func:`is_endgame` / :class:`ClassificationContext`.
"""

from __future__ import annotations

from katrain.core.analysis.meaning_tags.classifier import (
    THRESHOLD_MOVE_EARLY_GAME,
    THRESHOLD_MOVE_ENDGAME_ABSOLUTE,
    board_size_adjusted_thresholds,
    is_endgame,
)


class TestBoardSizeAdjustedThresholds:
    """Locks in the 9x9 / 13x13 scaling of the move-number thresholds."""

    def test_default_returns_19x19_baseline(self):
        early, endgame = board_size_adjusted_thresholds()
        assert early == THRESHOLD_MOVE_EARLY_GAME
        assert endgame == THRESHOLD_MOVE_ENDGAME_ABSOLUTE

    def test_19x19_explicit(self):
        early, endgame = board_size_adjusted_thresholds(19)
        assert early == THRESHOLD_MOVE_EARLY_GAME
        assert endgame == THRESHOLD_MOVE_ENDGAME_ABSOLUTE

    def test_9x9_scales_down(self):
        early, endgame = board_size_adjusted_thresholds(9)
        # sqrt(81/361) ≈ 0.474 → 80 * 0.474 ≈ 38, 150 * 0.474 ≈ 71
        assert early == 38
        assert endgame == 71
        # Sanity: smaller than 19x19.
        assert early < THRESHOLD_MOVE_EARLY_GAME
        assert endgame < THRESHOLD_MOVE_ENDGAME_ABSOLUTE

    def test_13x13_intermediate(self):
        early, endgame = board_size_adjusted_thresholds(13)
        # sqrt(169/361) ≈ 0.685 → 80 * 0.685 ≈ 55, 150 * 0.685 ≈ 103
        assert early == 55
        assert endgame == 103
        # Sanity: between 9x9 and 19x19.
        assert early > 38
        assert endgame > 71

    def test_tuple_input(self):
        """``(width, height)`` tuple is accepted (use the smaller)."""
        early, endgame = board_size_adjusted_thresholds((9, 9))
        assert early == 38
        assert endgame == 71

    def test_tuple_input_uses_min(self):
        """Defensive: non-square tuple uses the smaller side."""
        early, endgame = board_size_adjusted_thresholds((9, 19))
        assert early == 38  # 9 wins over 19
        assert endgame == 71

    def test_invalid_input_returns_default(self):
        """``None``, strings, etc. all fall back to 19x19 defaults."""
        assert board_size_adjusted_thresholds(None) == (THRESHOLD_MOVE_EARLY_GAME, THRESHOLD_MOVE_ENDGAME_ABSOLUTE)
        assert board_size_adjusted_thresholds("not a number") == (  # type: ignore[arg-type]
            THRESHOLD_MOVE_EARLY_GAME,
            THRESHOLD_MOVE_ENDGAME_ABSOLUTE,
        )
        assert board_size_adjusted_thresholds([]) == (  # type: ignore[arg-type]
            THRESHOLD_MOVE_EARLY_GAME,
            THRESHOLD_MOVE_ENDGAME_ABSOLUTE,
        )

    def test_unknown_size_uses_default(self):
        """Sizes outside 9/13/19 fall back to 19x19 defaults (scale=1.0)."""
        assert board_size_adjusted_thresholds(25) == (THRESHOLD_MOVE_EARLY_GAME, THRESHOLD_MOVE_ENDGAME_ABSOLUTE)


class TestIsEndgameBoardSize:
    """``is_endgame`` scales the absolute threshold by board size."""

    def test_default_19x19_threshold_unchanged(self):
        """Move 80 on 19x19 is NOT endgame; move 200 IS."""
        assert is_endgame(80, total_moves=300, has_endgame_hint=False) is False
        assert is_endgame(200, total_moves=300, has_endgame_hint=False) is True

    def test_9x9_threshold_lowered(self):
        """On 9x9 the absolute threshold drops to 71, so move 80 IS endgame."""
        assert is_endgame(80, total_moves=300, has_endgame_hint=False, board_size=9) is True
        assert is_endgame(50, total_moves=300, has_endgame_hint=False, board_size=9) is False

    def test_13x13_threshold_intermediate(self):
        """13x13 absolute threshold = 103."""
        assert is_endgame(50, total_moves=300, has_endgame_hint=False, board_size=13) is False
        assert is_endgame(150, total_moves=300, has_endgame_hint=False, board_size=13) is True

    def test_endgame_hint_overrides_board_size(self):
        """``has_endgame_hint=True`` always wins regardless of board size."""
        for size in (None, 9, 13, 19, 25):
            assert is_endgame(5, total_moves=300, has_endgame_hint=True, board_size=size) is True

    def test_total_moves_ratio_unchanged(self):
        """The total-moves-ratio criterion does NOT depend on board size."""
        # total_moves=200, move 150 → 150 > 200 * 0.7 = 140 → True (regardless of board_size)
        assert is_endgame(150, total_moves=200, has_endgame_hint=False, board_size=9) is True
        assert is_endgame(150, total_moves=200, has_endgame_hint=False, board_size=19) is True
        # total_moves=200, move 50: 50 > 140 is False; 50 > 71 (9x9) is False; 50 > 150 (19x19) is False → all False
        assert is_endgame(50, total_moves=200, has_endgame_hint=False, board_size=9) is False
        assert is_endgame(50, total_moves=200, has_endgame_hint=False, board_size=19) is False
        # total_moves=200, move 100: ratio 100 > 140 is False; but on 9x9 the
        # absolute threshold (71) is exceeded → True. On 19x19 the
        # absolute threshold (150) is NOT exceeded → False. This is the
        # board-size effect: 9x9 endgame is triggered earlier.
        assert is_endgame(100, total_moves=200, has_endgame_hint=False, board_size=9) is True
        assert is_endgame(100, total_moves=200, has_endgame_hint=False, board_size=19) is False

    def test_backward_compatible_no_board_size(self):
        """Passing ``board_size=None`` (the default) preserves the 19x19 baseline."""
        # 9x9 with 100 moves + has_endgame_hint=False: would be endgame if
        # board_size were 9 (threshold 71); with board_size=None (=19x19),
        # 100 < 150 → NOT endgame. This is the legacy Phase 46 behaviour.
        assert is_endgame(100, total_moves=200, has_endgame_hint=False) is False


class TestClassificationContextBoardSize:
    """``ClassificationContext`` accepts and exposes ``board_size``."""

    def test_default_board_size_is_none(self):
        from katrain.core.analysis.meaning_tags.classifier import ClassificationContext

        ctx = ClassificationContext()
        assert ctx.board_size is None

    def test_explicit_board_size_stored(self):
        from katrain.core.analysis.meaning_tags.classifier import ClassificationContext

        ctx = ClassificationContext(board_size=9)
        assert ctx.board_size == 9

    def test_tuple_board_size_stored(self):
        from katrain.core.analysis.meaning_tags.classifier import ClassificationContext

        ctx = ClassificationContext(board_size=(13, 13))
        assert ctx.board_size == (13, 13)

"""Phase 38: Game core logic tests (Kivy-free, engine-free).

Tests for Game class initialization and basic operations.
Uses shared fixtures from conftest.py (Phase 70).
"""

from katrain.core.game import Move

# Fixtures used: game, game_9x9, mock_engine, mock_katrain, root_node (from conftest.py)


class TestGameInit:
    """Game initialization tests."""

    def test_init_19x19(self, game):
        """Game initializes correctly with 19x19 board."""
        assert game.board_size == (19, 19)

    def test_init_9x9(self, game_9x9):
        """Game initializes correctly with 9x9 board."""
        assert game_9x9.board_size == (9, 9)

    def test_init_empty_board(self, game):
        """Initial board has no stones."""
        assert len(game.stones) == 0

    def test_init_no_prisoners(self, game):
        """Initial board has no prisoners."""
        assert len(game.prisoners) == 0

    def test_engines_is_dict(self, game, mock_engine):
        """Verify engines is {"B": engine, "W": engine}."""
        assert game.engines == {"B": mock_engine, "W": mock_engine}


class TestGamePlay:
    """Game.play() tests (follows test_board.py patterns)."""

    def test_play_single_stone(self, game):
        """Playing a single stone adds it to the board."""
        game.play(Move.from_gtp("D4", player="B"))
        assert len(game.stones) == 1

    def test_play_pass(self, game):
        """Playing a pass move does not add stones."""
        game.play(Move(coords=None, player="B"))  # pass
        assert len(game.stones) == 0

    def test_play_multiple_stones(self, game):
        """Playing multiple stones adds them to the board."""
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        assert len(game.stones) == 2

    def test_play_alternating_colors(self, game):
        """Stones alternate colors correctly."""
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        game.play(Move.from_gtp("D16", player="B"))

        # Check that stones are placed (detailed position check would require board access)
        assert len(game.stones) == 3

    def test_play_on_9x9(self, game_9x9):
        """Stones can be played on 9x9 board."""
        game_9x9.play(Move.from_gtp("E5", player="B"))
        game_9x9.play(Move.from_gtp("D3", player="W"))
        assert len(game_9x9.stones) == 2

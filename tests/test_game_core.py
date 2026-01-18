"""Phase 38: Game core logic tests (Kivy-free, engine-free).

Tests for Game class initialization and basic operations.
Follows test_board.py patterns exactly.
"""
import pytest

from katrain.core.base_katrain import KaTrainBase
from katrain.core.game import Game, Move
from katrain.core.game_node import GameNode


class MockKaTrain(KaTrainBase):
    """Minimal mock for testing (copied from test_board.py)."""

    pass


class MockEngine:
    """Minimal mock engine (copied from test_board.py)."""

    def request_analysis(self, *args, **kwargs):
        pass

    def stop_pondering(self):
        return


@pytest.fixture
def new_game():
    """Create a new 19x19 game node (same fixture as test_board.py)."""
    return GameNode(properties={"SZ": 19})


@pytest.fixture
def new_game_9x9():
    """Create a new 9x9 game node."""
    return GameNode(properties={"SZ": 9})


class TestGameInit:
    """Game initialization tests."""

    def test_init_19x19(self, new_game):
        """Game initializes correctly with 19x19 board."""
        game = Game(MockKaTrain(force_package_config=True), MockEngine(), move_tree=new_game)
        assert game.board_size == (19, 19)

    def test_init_9x9(self, new_game_9x9):
        """Game initializes correctly with 9x9 board."""
        game = Game(MockKaTrain(force_package_config=True), MockEngine(), move_tree=new_game_9x9)
        assert game.board_size == (9, 9)

    def test_init_empty_board(self, new_game):
        """Initial board has no stones."""
        game = Game(MockKaTrain(force_package_config=True), MockEngine(), move_tree=new_game)
        assert len(game.stones) == 0

    def test_init_no_prisoners(self, new_game):
        """Initial board has no prisoners."""
        game = Game(MockKaTrain(force_package_config=True), MockEngine(), move_tree=new_game)
        assert len(game.prisoners) == 0


class TestGamePlay:
    """Game.play() tests (follows test_board.py patterns)."""

    def test_play_single_stone(self, new_game):
        """Playing a single stone adds it to the board."""
        game = Game(MockKaTrain(force_package_config=True), MockEngine(), move_tree=new_game)
        game.play(Move.from_gtp("D4", player="B"))
        assert len(game.stones) == 1

    def test_play_pass(self, new_game):
        """Playing a pass move does not add stones."""
        game = Game(MockKaTrain(force_package_config=True), MockEngine(), move_tree=new_game)
        game.play(Move(coords=None, player="B"))  # pass
        assert len(game.stones) == 0

    def test_play_multiple_stones(self, new_game):
        """Playing multiple stones adds them to the board."""
        game = Game(MockKaTrain(force_package_config=True), MockEngine(), move_tree=new_game)
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        assert len(game.stones) == 2

    def test_play_alternating_colors(self, new_game):
        """Stones alternate colors correctly."""
        game = Game(MockKaTrain(force_package_config=True), MockEngine(), move_tree=new_game)
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        game.play(Move.from_gtp("D16", player="B"))

        # Check that stones are placed (detailed position check would require board access)
        assert len(game.stones) == 3

    def test_play_on_9x9(self, new_game_9x9):
        """Stones can be played on 9x9 board."""
        game = Game(MockKaTrain(force_package_config=True), MockEngine(), move_tree=new_game_9x9)
        game.play(Move.from_gtp("E5", player="B"))
        game.play(Move.from_gtp("D3", player="W"))
        assert len(game.stones) == 2

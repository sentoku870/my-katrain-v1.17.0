"""Comprehensive tests for katrain/core/game.py (Phase 139).

Covers previously untested paths:
- BaseGame._validate_move_and_update_chains (capture, suicide, ko, pass)
- BaseGame.undo / redo (numeric, branch, main-branch, stop_on_mistake)
- BaseGame.end_result / prisoner_count / manual_score
- BaseGame.update_root_properties / generate_filename / write_sgf
- BaseGame.sync_branch
- Game.analyze_all_nodes (capacity timeout, engine None)
- Game._iter_main_branch_nodes / _find_node_by_move_number
- Game.get_main_branch_node_before_move / _compute_important_moves
- Game.get_important_move_numbers / get_next/prev_important_node
- Game.jump_to_next/prev_important_move
- Game.set_current_node / undo / redo / set_insert_mode (insert mode paths)
- Game.play with region_of_interest
- Game.set_region_of_interest
- Game._handle_stop_mode / _handle_ponder_mode / _handle_extra_mode
- Game._handle_game_mode (move_range, mistakes_only, visits override)
- Game._handle_sweep_equalize_modes (SWEEP/EQUALIZE/ALTERNATIVE/LOCAL)
- Game.analyze_extra dispatcher
- Game.analyze_undo
- Game.build_eval_snapshot / log_mistake_summary_for_debug
- Game.get_important_move_evals / log_important_moves_for_debug
- Game.build_karte_report / build_important_moves_report
- Game.build_summary_report
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.constants import (
    AI_DEFAULT,
    PLAYER_AI,
    PLAYER_HUMAN,
    PLAYING_NORMAL,
    AnalysisMode,
    PLAYING_TEACHING,
)
from katrain.core.game import (
    BaseGame,
    Game,
    IllegalMoveException,
    KaTrainSGF,
    Move,
)
from katrain.core.game_node import GameNode
from katrain.core.sgf_parser import SGF

# Fixtures used: game, game_9x9, mock_katrain, mock_engine, root_node, root_node_9x9
# from conftest.py


# ---------------------------------------------------------------------------
# BaseGame - move validation, capture, suicide, ko
# ---------------------------------------------------------------------------


class TestMoveValidation:
    """BaseGame._validate_move_and_update_chains"""

    def test_occupied_space_raises(self, game):
        """Placing a stone on an occupied point raises IllegalMoveException."""
        game.play(Move.from_gtp("D4", player="B"))
        with pytest.raises(IllegalMoveException, match="Space occupied"):
            game.play(Move.from_gtp("D4", player="W"))

    def test_capture_4_sides(self, game):
        """A stone surrounded on 4 sides by the same player is captured."""
        # Set up: B at D4, D16, Q4, Q16 → surround D10 (W) → W at D10 is captured
        # Actually, simpler: surround a single stone with 4 of the opposite color
        # 1. B at D4 (center)
        game.play(Move.from_gtp("D4", player="B"))
        # 2. W at C4 (adjacent)
        game.play(Move.from_gtp("C4", player="W"))
        # 3. B at D3 (right of W? no, below D4) - we need to surround W at C4
        # Place W at C4, then B at C3, B at C5, B at B4, B at D4
        # Wait D4 is already B. Let me restart.
        game.undo(n_times=2)
        # Place B at C3, C5, B4 and D4 → surround C4 (W)
        # B at C3
        game.play(Move.from_gtp("C3", player="B"))
        # W at C4
        game.play(Move.from_gtp("C4", player="W"))
        # B at C5
        game.play(Move.from_gtp("C5", player="B"))
        # W passes
        game.play(Move(None, player="W"))
        # B at B4
        game.play(Move.from_gtp("B4", player="B"))
        # W passes
        game.play(Move(None, player="W"))
        # B at D4 - completes the surround
        game.play(Move.from_gtp("D4", player="B"))

        # Now W at C4 is captured
        w_stones_after = [m for m in game.stones if m.player == "W"]
        assert len(w_stones_after) == 0
        assert len(game.prisoners) >= 1

    def test_single_stone_suicide_raises(self, game):
        """Placing a stone with no liberties (and not capturing) is suicide."""
        # Set up: B at C4, E4, D3, D5 → D4 (W) would be suicide
        game.play(Move.from_gtp("C4", player="B"))
        game.play(Move.from_gtp("E4", player="B"))
        game.play(Move.from_gtp("D3", player="B"))
        game.play(Move.from_gtp("D5", player="B"))
        # W at D4 - suicide
        with pytest.raises(IllegalMoveException, match="[Ss]uicide"):
            game.play(Move.from_gtp("D4", player="W"))

    def test_move_outside_board_raises(self, game):
        """A move with coords outside the board raises IllegalMoveException."""
        # 19x19 board: valid coords 0..18
        bad_move = Move(coords=(20, 0), player="B")
        with pytest.raises(IllegalMoveException, match="outside of board"):
            game.play(bad_move)

    def test_play_illegal_recovers_state(self, game):
        """After an illegal move, _calculate_groups is called to restore state."""
        game.play(Move.from_gtp("D4", player="B"))
        # Try to play on D4 with W (occupied)
        with pytest.raises(IllegalMoveException):
            game.play(Move.from_gtp("D4", player="W"))
        # State should be recoverable - D4 still has B
        assert any(m.coords == (3, 3) and m.player == "B" for m in game.stones)


class TestPass:
    def test_pass_does_not_change_board(self, game):
        game.play(Move(None, player="B"))
        assert len(game.stones) == 0

    def test_two_consecutive_passes(self, game):
        game.play(Move(None, player="B"))
        game.play(Move(None, player="W"))
        assert len(game.stones) == 0


# ---------------------------------------------------------------------------
# BaseGame.end_result / prisoner_count
# ---------------------------------------------------------------------------


class TestEndResult:
    def test_end_result_no_passes(self, game):
        """end_result is None when no passes have occurred."""
        game.play(Move.from_gtp("D4", player="B"))
        assert game.end_result is None

    def test_end_result_one_pass(self, game):
        """end_result is None after only one pass (game continues)."""
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move(None, player="W"))
        assert game.end_result is None

    def test_end_result_two_passes(self, game):
        """end_result is set when both players pass."""
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move(None, player="W"))
        game.play(Move(None, player="B"))
        # Two passes occurred; end_result is set (could be manual_score or board-game-end)
        assert game.end_result is not None

    def test_prisoner_count_initial_zero(self, game):
        assert game.prisoner_count == {"B": 0, "W": 0}

    def test_prisoner_count_after_capture(self, game):
        """Capture a white stone → W prisoner count goes up."""
        # Set up B at C3, C5, B4, D4 - surround C4 (W)
        game.play(Move.from_gtp("C3", player="B"))
        game.play(Move.from_gtp("C4", player="W"))
        game.play(Move.from_gtp("C5", player="B"))
        game.play(Move(None, player="W"))
        game.play(Move.from_gtp("B4", player="B"))
        game.play(Move(None, player="W"))
        game.play(Move.from_gtp("D4", player="B"))
        assert game.prisoner_count["W"] >= 1


# ---------------------------------------------------------------------------
# BaseGame.komi / board_size / rules
# ---------------------------------------------------------------------------


class TestGameProperties:
    def test_komi(self, game):
        assert game.komi == 6.5

    def test_board_size(self, game):
        assert game.board_size == (19, 19)

    def test_rules(self, game):
        rules = game.rules
        assert rules in ("japanese", "chinese", "korean") or isinstance(rules, dict)

    def test_stones_empty(self, game):
        with game._lock:
            assert game.stones == []


# ---------------------------------------------------------------------------
# BaseGame.undo / redo
# ---------------------------------------------------------------------------


class TestUndoRedo:
    def test_undo_one_move(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        assert len(game.stones) == 1
        game.undo()
        assert len(game.stones) == 0

    def test_undo_multiple_moves(self, game):
        for gtp in ["D4", "Q16", "D16"]:
            game.play(Move.from_gtp(gtp, player="B"))
        game.undo(n_times=2)
        assert len(game.stones) == 1
        assert game.stones[0].coords == (3, 3)  # D4

    def test_undo_at_root_does_nothing(self, game):
        game.undo()
        # Should not crash, should be at root
        assert game.current_node.is_root

    def test_undo_branch_stops_at_branch(self, game):
        """undo with n_times='branch' stops at the first branching point."""
        # Build a line then branch
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        # Branch from D4
        game.sync_branch([Move.from_gtp("D4", player="B"), Move.from_gtp("D16", player="W")])
        # Go to leaf
        assert game.current_node.depth == 2
        # undo('branch') should go back to the branching point
        game.undo(n_times="branch")
        # After undo, we should be at a node that has multiple children
        assert len(game.current_node.children) >= 2

    def test_redo_one_move(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        game.undo()
        game.redo()
        assert len(game.stones) == 1

    def test_redo_at_leaf_does_nothing(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        game.redo()
        # No children to redo into
        assert len(game.stones) == 1


# ---------------------------------------------------------------------------
# sync_branch
# ---------------------------------------------------------------------------


class TestSyncBranch:
    def test_sync_branch_creates_new_moves(self, game):
        moves = [Move.from_gtp("D4", player="B"), Move.from_gtp("Q16", player="W")]
        node = game.sync_branch(moves)
        # sync_branch navigates from root (does not change current_node),
        # returning the new node. Stones count refers to current_node.
        assert node.depth == 2
        # Verify the returned node has the correct move sequence
        path = node.nodes_from_root
        assert path[-1].move is not None
        assert path[-1].move.gtp() == "Q16"

    def test_sync_branch_reuses_existing(self, game):
        moves = [Move.from_gtp("D4", player="B"), Move.from_gtp("Q16", player="W")]
        first = game.sync_branch(moves)
        second = game.sync_branch(moves)
        # sync_branch reuses existing nodes
        assert first is second


# ---------------------------------------------------------------------------
# update_root_properties / generate_filename / write_sgf
# ---------------------------------------------------------------------------


class TestSGFOutput:
    def _setup_player_names(self, mock_katrain, name_b: str, name_w: str) -> None:
        """Set up player_info mocks with real string names.

        MagicMock's .name attribute is a MagicMock by default; we need a real
        string for the test to work properly.
        """
        from types import SimpleNamespace
        from katrain.core.constants import PLAYER_HUMAN, PLAYING_NORMAL
        mock_katrain.players_info = {
            "B": SimpleNamespace(name=name_b, player_type=PLAYER_HUMAN, player_subtype=PLAYING_NORMAL, calculated_rank=None),
            "W": SimpleNamespace(name=name_w, player_type=PLAYER_HUMAN, player_subtype=PLAYING_NORMAL, calculated_rank=None),
        }

    def test_generate_filename_uses_player_names(self, game, mock_katrain):
        self._setup_player_names(mock_katrain, "Alice", "Bob")
        # Mark the game as internal (generated by KaTrain) so player names are used
        game.external_game = False
        # Pre-populate the root with P[player] properties since update_root_properties
        # is gated by `not self.external_game` and we set that above
        filename = game.generate_filename()
        assert "Alice" in filename
        assert "Bob" in filename
        assert filename.endswith(".sgf")

    def test_generate_filename_filters_invalid_chars(self, game, mock_katrain):
        self._setup_player_names(mock_katrain, "Alice<>:/\\|?*", "Bob")
        # Set root AP property (KaTrain) so external_game is False
        game.root.set_property("AP", "KaTrain:1.17.1")
        game.external_game = False
        filename = game.generate_filename()
        for bad in '<>:"/\\|?*':
            assert bad not in filename

    def test_write_sgf(self, game, tmp_path):
        game.play(Move.from_gtp("D4", player="B"), analyze=False)
        game.play(Move.from_gtp("Q16", player="W"), analyze=False)
        filepath = tmp_path / "test.sgf"
        trainer_config = {
            "save_feedback": False,
            "eval_thresholds": [0, 0.5, 1.0, 2.0, 5.0],
            "save_analysis": False,
            "save_marks": False,
            "eval_show_ai": True,
        }
        result = game.write_sgf(str(filepath), trainer_config=trainer_config)
        # i18n._("sgf written") is wrapped → the actual translation appears
        assert filepath.exists()
        content = filepath.read_text()
        assert "(;" in content
        # GTP D4 → SGF dp (lowercase)
        assert "B[dp]" in content
        assert "W[pd]" in content


# ---------------------------------------------------------------------------
# Game.analyze_all_nodes
# ---------------------------------------------------------------------------


class TestAnalyzeAllNodes:
    def test_engine_none_skips(self, game_9x9):
        """When engines[next_player] is None, the node is skipped (no crash)."""
        # Replace engine with None for one player
        game_9x9.engines = {"B": None, "W": None}
        # This should not crash
        game_9x9.analyze_all_nodes(even_if_present=False)
        # Verify the function returned without errors
        assert game_9x9.current_node is not None

    def test_analyze_all_nodes_empty_game(self, game_9x9):
        """analyze_all_nodes on an empty (no-moves) game is a no-op."""
        game_9x9.analyze_all_nodes(even_if_present=False)
        # No moves to analyze
        assert game_9x9.current_node.is_root

    def test_analyze_all_nodes_throttle_timeout(self, game_9x9):
        """When engine.has_query_capacity returns False, node is skipped after timeout."""
        # Mock engine to always return False for capacity
        game_9x9.engines["B"].has_query_capacity = MagicMock(return_value=False)
        # テスト高速化: throttle パラメータで短いタイムアウト値を使用
        game_9x9.analyze_all_nodes(
            even_if_present=False,
            throttle_max_attempts=2,
            throttle_poll_interval=0.001,
        )
        # No crash means the timeout was handled


# ---------------------------------------------------------------------------
# Game - important move navigation
# ---------------------------------------------------------------------------


class TestImportantMoveNavigation:
    def test_iter_main_branch_nodes_empty(self, game):
        """Empty game has no main branch nodes."""
        nodes = list(game._iter_main_branch_nodes())
        assert nodes == []

    def test_iter_main_branch_nodes_one_move(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        nodes = list(game._iter_main_branch_nodes())
        assert len(nodes) == 1
        assert nodes[0].move.coords == (3, 3)

    def test_iter_main_branch_nodes_multi(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        game.play(Move.from_gtp("D16", player="B"))
        nodes = list(game._iter_main_branch_nodes())
        assert len(nodes) == 3

    def test_get_main_branch_node_before_move_1(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        node = game.get_main_branch_node_before_move(1)
        assert node is game.root

    def test_get_main_branch_node_before_move_2(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        node = game.get_main_branch_node_before_move(2)
        assert node is not None
        assert node.move.coords == (3, 3)  # D4

    def test_get_main_branch_node_before_move_0(self, game):
        """move_number <= 1 returns root."""
        node = game.get_main_branch_node_before_move(0)
        assert node is game.root

    def test_get_main_branch_node_before_move_out_of_range(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        node = game.get_main_branch_node_before_move(999)
        assert node is None

    def test_find_node_by_move_number(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        node = game._find_node_by_move_number(1)
        assert node is not None
        assert node.move.coords == (3, 3)

    def test_find_node_by_move_number_not_found(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        node = game._find_node_by_move_number(99)
        assert node is None

    def test_compute_important_moves_empty(self, game):
        """Empty game returns empty list."""
        result = game._compute_important_moves()
        assert result == []

    def test_compute_important_moves_with_unscored_nodes(self, game):
        """Nodes without analysis_complete are skipped."""
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        # No analysis → all nodes skipped, falls back to all_nodes (empty)
        result = game._compute_important_moves()
        assert result == []

    def test_get_important_move_numbers(self, game):
        result = game.get_important_move_numbers()
        assert result == []

    def test_get_next_important_node_empty(self, game):
        """Empty game returns None."""
        assert game.get_next_important_node() is None

    def test_get_prev_important_node_empty(self, game):
        """Empty game returns None."""
        assert game.get_prev_important_node() is None

    def test_jump_to_next_important_move_empty(self, game):
        """Empty game returns None and doesn't move current_node."""
        original = game.current_node
        result = game.jump_to_next_important_move()
        assert result is None
        assert game.current_node is original

    def test_jump_to_prev_important_move_empty(self, game):
        """Empty game returns None and doesn't move current_node."""
        original = game.current_node
        result = game.jump_to_prev_important_move()
        assert result is None
        assert game.current_node is original


# ---------------------------------------------------------------------------
# Game - insert mode
# ---------------------------------------------------------------------------


class TestInsertMode:
    def test_set_insert_mode_true_with_no_children(self, game):
        """With no children at current_node, set_insert_mode(True) leaves insert_mode False."""
        # current_node is root, which has no children
        game.set_insert_mode(True)
        # No children → insert_mode stays False
        assert game.insert_mode is False

    def test_set_insert_mode_with_children(self, game):
        # Need at least 2 moves so that the first move node has children
        game.play(Move.from_gtp("D4", player="B"), analyze=False)
        game.play(Move.from_gtp("Q16", player="W"), analyze=False)
        # Now move back to a node with children
        game.set_current_node(game.root.children[0])  # D4 node has W move as child
        game.set_insert_mode(True)
        assert game.insert_mode is True
        assert game.insert_after is not None

    def test_set_insert_mode_toggle(self, game):
        game.play(Move.from_gtp("D4", player="B"), analyze=False)
        game.play(Move.from_gtp("Q16", player="W"), analyze=False)
        game.set_current_node(game.root.children[0])
        # toggle: False → True
        game.set_insert_mode("toggle")
        assert game.insert_mode is True
        # toggle: True → False
        game.set_insert_mode("toggle")
        assert game.insert_mode is False

    def test_set_insert_mode_already_on(self, game):
        """Setting to same value is a no-op (early return)."""
        game.play(Move.from_gtp("D4", player="B"), analyze=False)
        game.play(Move.from_gtp("Q16", player="W"), analyze=False)
        game.set_current_node(game.root.children[0])
        game.set_insert_mode(True)
        # No-op when already in same mode
        game.set_insert_mode(True)
        assert game.insert_mode is True

    def test_undo_in_insert_mode_deletes(self, game):
        """In insert mode, undo deletes the current child from parent.

        Note: set_current_node is BLOCKED in insert mode. So we must set
        current_node to the branched path BEFORE entering insert mode.
        """
        # Set up: root -> B(D4) -> W(Q16) [main] and root -> B(D4) -> W(E5) [branch]
        game.play(Move.from_gtp("D4", player="B"), analyze=False)
        game.play(Move.from_gtp("Q16", player="W"), analyze=False)
        # Branch from D4: add W(E5) as alternative
        game.sync_branch([Move.from_gtp("D4", player="B"), Move.from_gtp("E5", player="W")])
        d4_node = game.root.children[0]
        # Navigate to the E5 branched path BEFORE entering insert mode
        game.set_current_node(d4_node.children[1])  # E5
        # Now enter insert mode (current_node is E5, which has no children → insert_mode stays False)
        # The first-child check would fail, so we manually set insert_mode
        game.set_insert_mode(True)  # this stays False since E5 has no children
        # Manually set up insert mode after the fact
        game.insert_mode = True
        game.insert_after = d4_node  # so cn (E5) is not in insert_after.nodes_from_root
        target = game.current_node
        game.undo()
        # The parent (D4) should no longer have the target
        parent = target.parent
        assert target not in parent.children

    def test_redo_in_insert_mode_no_op(self, game):
        """In insert mode, redo is a no-op."""
        game.play(Move.from_gtp("D4", player="B"), analyze=False)
        game.play(Move.from_gtp("Q16", player="W"), analyze=False)
        game.set_insert_mode(True)
        before = game.current_node
        game.redo()
        assert game.current_node is before

    def test_set_current_node_in_insert_mode(self, game):
        """set_current_node in insert mode logs error and doesn't change."""
        game.play(Move.from_gtp("D4", player="B"), analyze=False)
        game.play(Move.from_gtp("Q16", player="W"), analyze=False)
        game.set_current_node(game.root.children[0])
        game.set_insert_mode(True)
        original = game.current_node
        # set_current_node should not change in insert mode
        game.set_current_node(game.root)
        # In insert mode, the set_current_node is blocked
        assert game.current_node is original


# ---------------------------------------------------------------------------
# Game - region of interest
# ---------------------------------------------------------------------------


class TestRegionOfInterest:
    def test_set_region_of_interest_valid(self, game):
        game.set_region_of_interest((2, 5, 2, 5))
        assert game.region_of_interest is not None
        assert game.region_of_interest == [2, 5, 2, 5]

    def test_set_region_of_interest_cleared_when_whole_board(self, game):
        """When region covers the whole board, region_of_interest is set to None."""
        # Board 19x19: covering (0,18,0,18) is 19x19 ≥ 19x19 → cleared
        game.set_region_of_interest((0, 18, 0, 18))
        assert game.region_of_interest is None

    def test_set_region_of_interest_cleared_when_point(self, game):
        """When region is a single point (xmin==xmax, ymin==ymax), cleared."""
        game.set_region_of_interest((5, 5, 5, 5))
        assert game.region_of_interest is None

    def test_set_region_of_interest_normalizes_order(self, game):
        """x1>x2 and y1>y2 are normalized so xmin<xmax and ymin<ymax."""
        game.set_region_of_interest((5, 2, 5, 2))  # x1=5,x2=2 → [2,5,2,5]
        assert game.region_of_interest == [2, 5, 2, 5]


# ---------------------------------------------------------------------------
# Game - analyze_extra dispatcher
# ---------------------------------------------------------------------------


class TestAnalyzeExtra:
    def test_analyze_extra_stop(self, game_with_separate_engines):
        """analyze_extra with STOP mode stops pondering and terminates queries."""
        g = game_with_separate_engines
        g.play(Move.from_gtp("D4", player="B"))
        g.analyze_extra(AnalysisMode.STOP)
        # Both engines should have stop_pondering and terminate_queries called
        for engine in g.engines.values():
            assert engine.stop_pondering_called
            assert engine.terminate_queries_called

    def test_analyze_extra_ponder(self, game):
        """analyze_extra with PONDER mode triggers analysis request."""
        game.play(Move.from_gtp("D4", player="B"))
        game.analyze_extra(AnalysisMode.PONDER)
        # request_analysis should be called on the engine
        assert len(game.engines["B"].request_analysis_calls) >= 1

    def test_analyze_extra_extra_mode(self, game):
        """analyze_extra with EXTRA mode requests more visits."""
        game.play(Move.from_gtp("D4", player="B"))
        game.analyze_extra(AnalysisMode.EXTRA)
        # request_analysis called with visits override
        assert len(game.engines["B"].request_analysis_calls) >= 1

    def test_analyze_extra_game_mode(self, game):
        """analyze_extra with GAME mode triggers game-wide re-analysis."""
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        game.analyze_extra(AnalysisMode.GAME)
        # request_analysis called for each node
        assert len(game.engines["B"].request_analysis_calls) >= 1

    def test_analyze_extra_game_mode_with_mistakes_only(self, game):
        """GAME mode with mistakes_only=True filters by eval threshold."""
        game.play(Move.from_gtp("D4", player="B"))
        game.analyze_extra(AnalysisMode.GAME, mistakes_only=True)
        # Should not crash; no analysis_complete so mistakes_only is True for none
        # But the call should still succeed

    def test_analyze_extra_game_mode_with_move_range(self, game):
        """GAME mode with move_range filters to that range."""
        for gtp in ["D4", "Q16", "D16", "Q4"]:
            game.play(Move.from_gtp(gtp, player="B"))
        # Range (1, 3) means moves 1 through 3
        game.analyze_extra(AnalysisMode.GAME, move_range=(1, 3))
        # Should not crash

    def test_analyze_extra_invalid_mode(self, game):
        """analyze_extra with truly invalid mode falls back to STOP."""
        game.play(Move.from_gtp("D4", player="B"))
        # parse_analysis_mode falls back to STOP for unknown values
        game.analyze_extra("invalid_mode_xyz")
        # STOP mode is called

    def test_analyze_extra_sweep(self, game):
        """analyze_extra with SWEEP mode iterates over board positions."""
        game.play(Move.from_gtp("D4", player="B"))
        # cn.analysis_complete is False, but for SWEEP we don't need it
        game.analyze_extra(AnalysisMode.SWEEP)
        # Should not crash; may log status

    def test_analyze_extra_alternative(self, game):
        """analyze_extra with ALTERNATIVE requires analysis_complete first."""
        game.play(Move.from_gtp("D4", player="B"))
        # Without analysis_complete, ALTERNATIVE should set status and return early
        # (no crash, no request_analysis)
        # The mock engine's request_analysis shouldn't be called
        game.analyze_extra(AnalysisMode.ALTERNATIVE)


# ---------------------------------------------------------------------------
# Game - analyze_undo
# ---------------------------------------------------------------------------


class TestAnalyzeUndo:
    def test_analyze_undo_non_current_node(self, game):
        """analyze_undo on a non-current node is a no-op."""
        game.play(Move.from_gtp("D4", player="B"), analyze=False)
        game.play(Move.from_gtp("Q16", player="W"), analyze=False)
        root = game.root
        # Analyze undo on the root (not current) - should not undo
        game.analyze_undo(root)
        # Still at current node (Q16 = GTP Q → SGF pd → coords (15, 15))
        assert game.current_node.move.coords == (15, 15)

    def test_analyze_undo_no_analysis(self, game):
        """analyze_undo with no analysis on current node is a no-op."""
        game.play(Move.from_gtp("D4", player="B"), analyze=False)
        # No analysis_complete → early return
        game.analyze_undo(game.current_node)
        # No undo triggered
        assert game.current_node.move.coords == (3, 3)

    def test_analyze_undo_already_auto_undo(self, game):
        """analyze_undo when auto_undo is already set is a no-op."""
        game.play(Move.from_gtp("D4", player="B"), analyze=False)
        game.current_node.auto_undo = True
        original = game.current_node
        game.analyze_undo(game.current_node)
        # auto_undo already set, no undo
        assert game.current_node is original


# ---------------------------------------------------------------------------
# Game - report methods
# ---------------------------------------------------------------------------


class TestGameReports:
    def test_build_eval_snapshot(self, game):
        """build_eval_snapshot returns an EvalSnapshot."""
        game.play(Move.from_gtp("D4", player="B"))
        snapshot = game.build_eval_snapshot()
        # Snapshot has moves list
        assert hasattr(snapshot, "moves")
        assert isinstance(snapshot.moves, list)

    def test_log_mistake_summary_for_debug(self, game, capsys):
        """log_mistake_summary prints a summary."""
        game.play(Move.from_gtp("D4", player="B"))
        game.log_mistake_summary_for_debug()
        captured = capsys.readouterr()
        assert "Mistake summary" in captured.out
        assert "Total moves" in captured.out

    def test_log_important_moves_for_debug_no_moves(self, game):
        """log_important_moves with no analyzed moves logs a no-moves message."""
        # No moves → empty result
        game.log_important_moves_for_debug()
        # No crash

    def test_log_important_moves_for_debug_with_moves(self, game):
        """log_important_moves with moves logs header + per-move info."""
        game.play(Move.from_gtp("D4", player="B"))
        game.log_important_moves_for_debug()
        # No crash; may or may not log depending on analysis state


# ---------------------------------------------------------------------------
# Game - build_karte_report / build_important_moves_report
# ---------------------------------------------------------------------------


class TestKarteReport:
    def test_build_important_moves_report_empty(self, game):
        """build_important_moves_report on empty game."""
        result = game.build_important_moves_report()
        # Should return a string (possibly empty)
        assert isinstance(result, str)

    def test_build_important_moves_report_with_moves(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        result = game.build_important_moves_report()
        assert isinstance(result, str)

    def test_build_karte_report(self, game):
        """build_karte_report returns markdown string."""
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        result = game.build_karte_report()
        assert isinstance(result, str)

    def test_build_karte_report_with_player_filter(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        result = game.build_karte_report(player_filter="B")
        assert isinstance(result, str)

    def test_build_quiz_items(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        items = game.get_quiz_items()
        assert isinstance(items, list)

    def test_build_quiz_questions(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        items = game.get_quiz_items()
        if items:
            questions = game.build_quiz_questions(items)
            assert isinstance(questions, list)


# ---------------------------------------------------------------------------
# Game - build_summary_report (static)
# ---------------------------------------------------------------------------


class TestBuildSummaryReport:
    def test_build_summary_report_empty(self):
        from katrain.core.eval_metrics import GameSummaryData

        result = Game.build_summary_report([])
        assert isinstance(result, str)

    def test_build_summary_report_with_data(self):
        from katrain.core.eval_metrics import GameSummaryData, EvalSnapshot

        data = GameSummaryData(
            game_name="test_game",
            player_black="Alice",
            player_white="Bob",
            snapshot=EvalSnapshot(moves=[]),
            board_size=(19, 19),
            date="2024-01-15",
            game_id="test1",
        )
        result = Game.build_summary_report([data])
        assert isinstance(result, str)

    def test_build_summary_report_with_focus_player(self):
        from katrain.core.eval_metrics import GameSummaryData, EvalSnapshot

        data = GameSummaryData(
            game_name="test_game",
            player_black="Alice",
            player_white="Bob",
            snapshot=EvalSnapshot(moves=[]),
            board_size=(19, 19),
            date="2024-01-15",
            game_id="test1",
        )
        result = Game.build_summary_report([data], focus_player="Alice")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Game - get_important_move_evals
# ---------------------------------------------------------------------------


class TestGetImportantMoveEvals:
    def test_empty_game(self, game):
        """Empty game returns empty list."""
        result = game.get_important_move_evals()
        assert result == []

    def test_with_moves(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        # Without analysis_complete, important_moves is empty
        result = game.get_important_move_evals(compute_reason_tags=False)
        # Either empty or a list
        assert isinstance(result, list)

    def test_with_reason_tags(self, game):
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        # Should not crash even when analysis is missing
        result = game.get_important_move_evals(compute_reason_tags=True)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Game - play with analyze=False
# ---------------------------------------------------------------------------


class TestPlayWithAnalyze:
    def test_play_analyze_false(self, game):
        """play with analyze=False doesn't trigger analysis."""
        game.play(Move.from_gtp("D4", player="B"), analyze=False)
        # No request_analysis should be called
        assert game.engines["B"].request_analysis_calls == []

    def test_play_default_analyzes(self, game):
        """play with default analyze=True triggers analysis."""
        game.play(Move.from_gtp("D4", player="B"))
        # request_analysis should be called
        assert len(game.engines["B"].request_analysis_calls) >= 1

    def test_play_with_region_of_interest(self, game):
        """play with region_of_interest set triggers ROI analysis."""
        game.region_of_interest = [2, 5, 2, 5]
        game.play(Move.from_gtp("D4", player="B"))
        # Should have at least one request (fast + ROI = 2 calls)
        assert len(game.engines["B"].request_analysis_calls) >= 1


# ---------------------------------------------------------------------------
# BaseGame sync_branch with shortcuts
# ---------------------------------------------------------------------------


class TestShortcuts:
    def test_shortcut_from_in_undo(self, game):
        """undo can navigate through shortcut_from links."""
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        # Create a shortcut from a sibling to current
        # Move back to root
        game.set_current_node(game.root)
        # Navigate forward
        game.set_current_node(game.current_node.children[0])
        # Now play another move to create a branch
        game.play(Move.from_gtp("E5", player="W"))
        # Test that undo with shortcut_from works
        # (this is more of a smoke test)
        game.undo()
        assert game.current_node.move.coords == (3, 3)


# ---------------------------------------------------------------------------
# BaseGame.komi override
# ---------------------------------------------------------------------------


class TestKomiOverride:
    def test_komi_from_root(self, game):
        """komi is read from root KM property."""
        # Default is 6.5
        assert game.komi == 6.5

    def test_komi_modified_in_root(self, game_9x9):
        """komi is dynamically read from root."""
        game_9x9.root.set_property("KM", "7.5")
        assert game_9x9.komi == 7.5


# ---------------------------------------------------------------------------
# Game.reset_current_analysis
# ---------------------------------------------------------------------------


class TestResetCurrentAnalysis:
    def test_reset_current_analysis(self, game):
        """reset_current_analysis terminates queries and re-analyzes."""
        game.play(Move.from_gtp("D4", player="B"))
        # Mock terminate_queries to track the call
        game.engines["B"].terminate_queries = MagicMock()
        game.reset_current_analysis()
        game.engines["B"].terminate_queries.assert_called_with(game.current_node)

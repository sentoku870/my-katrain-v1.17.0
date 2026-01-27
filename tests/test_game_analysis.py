"""Phase 70: Game analysis method tests.

Tests for Game.analyze_extra() and Game._compute_important_moves().
Uses shared fixtures from conftest.py.
"""
import pytest

from katrain.core.constants import AnalysisMode
from katrain.core.game import Game, Move
from katrain.core.game_node import GameNode


# ---------------------------------------------------------------------------
# Analysis State Factories (copied from conftest.py for import convenience)
# ---------------------------------------------------------------------------

def make_analysis(
    *,
    root_present: bool = True,
    completed: bool = True,
    moves: dict = None,
    score: float = 0.0,
    visits: int = 500,
) -> dict:
    """Factory for creating analysis dict with explicit state control."""
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
    """Setup analysis data on a node for testing."""
    node.analysis = make_analysis(score=score)

    if node.parent and parent_score is not None:
        parent_has_analysis = (
            node.parent.analysis.get("root") is not None
            if isinstance(node.parent.analysis, dict)
            else False
        )
        if force_parent or not parent_has_analysis:
            node.parent.analysis = make_analysis(score=parent_score, moves={})


# ---------------------------------------------------------------------------
# TestAnalyzeExtraStopMode
# ---------------------------------------------------------------------------

class TestAnalyzeExtraStopMode:
    """Tests for analyze_extra(AnalysisMode.STOP)."""

    def test_stop_sets_pondering_false(self, game, mock_katrain):
        """STOP mode sets katrain.pondering to False."""
        mock_katrain.pondering = True
        game.analyze_extra(AnalysisMode.STOP)
        assert mock_katrain.pondering is False

    def test_stop_calls_stop_pondering_on_both_engines(self, game_with_separate_engines, mock_engines):
        """STOP mode calls stop_pondering() on both engines."""
        game_with_separate_engines.analyze_extra(AnalysisMode.STOP)
        assert mock_engines["B"].stop_pondering_called
        assert mock_engines["W"].stop_pondering_called

    def test_stop_calls_terminate_queries_on_both_engines(self, game_with_separate_engines, mock_engines):
        """STOP mode calls terminate_queries() on both engines."""
        game_with_separate_engines.analyze_extra(AnalysisMode.STOP)
        assert mock_engines["B"].terminate_queries_called
        assert mock_engines["W"].terminate_queries_called


# ---------------------------------------------------------------------------
# TestAnalyzeExtraPonderMode
# ---------------------------------------------------------------------------

class TestAnalyzeExtraPonderMode:
    """Tests for analyze_extra(AnalysisMode.PONDER)."""

    def test_ponder_starts_analysis(self, game, mock_engine):
        """PONDER mode starts analysis on current node."""
        game.analyze_extra(AnalysisMode.PONDER)
        assert len(mock_engine.request_analysis_calls) > 0

    def test_ponder_uses_ponder_flag(self, game, mock_engine):
        """PONDER mode passes ponder=True."""
        game.analyze_extra(AnalysisMode.PONDER)
        assert len(mock_engine.request_analysis_calls) > 0
        call = mock_engine.request_analysis_calls[0]
        assert call["kwargs"].get("ponder") is True


# ---------------------------------------------------------------------------
# TestAnalyzeExtraExtraMode
# ---------------------------------------------------------------------------

class TestAnalyzeExtraExtraMode:
    """Tests for analyze_extra(AnalysisMode.EXTRA)."""

    def test_extra_starts_analysis(self, game, mock_engine):
        """EXTRA mode starts analysis on current node."""
        game.analyze_extra(AnalysisMode.EXTRA)
        assert len(mock_engine.request_analysis_calls) > 0

    def test_extra_sets_status_message(self, game, mock_katrain):
        """EXTRA mode sets a status message."""
        game.analyze_extra(AnalysisMode.EXTRA)
        assert mock_katrain.controls.set_status.called


# ---------------------------------------------------------------------------
# TestAnalyzeExtraGameMode
# ---------------------------------------------------------------------------

class TestAnalyzeExtraGameMode:
    """Tests for analyze_extra(AnalysisMode.GAME)."""

    def test_game_analyzes_root_node(self, game, mock_engine):
        """GAME mode analyzes at least the root node."""
        game.analyze_extra(AnalysisMode.GAME)
        assert len(mock_engine.request_analysis_calls) >= 1

    def test_game_analyzes_all_nodes_in_tree(self, game, mock_engine):
        """GAME mode analyzes all nodes in the game tree."""
        # Add some moves first
        game.play(Move.from_gtp("D4", player="B"))
        game.play(Move.from_gtp("Q16", player="W"))
        mock_engine.reset_tracking()

        game.analyze_extra(AnalysisMode.GAME)
        # Should have at least 3 analysis calls (root + 2 moves)
        assert len(mock_engine.request_analysis_calls) >= 3

    def test_game_respects_visits_kwarg(self, game, mock_engine):
        """GAME mode respects visits kwarg."""
        game.analyze_extra(AnalysisMode.GAME, visits=999)
        assert len(mock_engine.request_analysis_calls) > 0
        call = mock_engine.request_analysis_calls[0]
        assert call["kwargs"].get("visits") == 999


# ---------------------------------------------------------------------------
# TestAnalyzeExtraSweepMode
# ---------------------------------------------------------------------------

class TestAnalyzeExtraSweepMode:
    """Tests for analyze_extra(AnalysisMode.SWEEP)."""

    def test_sweep_generates_candidates(self, game, mock_engine):
        """SWEEP mode generates analysis for candidate moves."""
        game.analyze_extra(AnalysisMode.SWEEP)
        # SWEEP analyzes many empty board positions
        assert len(mock_engine.request_analysis_calls) > 0

    def test_sweep_sets_status_message(self, game, mock_katrain):
        """SWEEP mode sets a status message."""
        game.analyze_extra(AnalysisMode.SWEEP)
        assert mock_katrain.controls.set_status.called


# ---------------------------------------------------------------------------
# TestAnalyzeExtraEqualizeMode
# ---------------------------------------------------------------------------

class TestAnalyzeExtraEqualizeMode:
    """Tests for analyze_extra(AnalysisMode.EQUALIZE)."""

    def test_equalize_requires_analysis_complete(self, game, mock_engine):
        """EQUALIZE mode early returns when analysis not complete."""
        # analysis_complete=False → early return
        game.current_node.analysis = make_analysis(completed=False)
        mock_engine.reset_tracking()
        game.analyze_extra(AnalysisMode.EQUALIZE)
        assert len(mock_engine.request_analysis_calls) == 0

    def test_equalize_refines_undervisited_moves(self, game, mock_engine):
        """EQUALIZE mode refines under-visited moves."""
        # Complete analysis with moves to refine
        game.current_node.analysis = make_analysis(
            completed=True,
            moves={
                "D4": {"visits": 100, "scoreLead": 2.0},
                "E5": {"visits": 50, "scoreLead": 1.5},
            },
        )
        mock_engine.reset_tracking()
        game.analyze_extra(AnalysisMode.EQUALIZE)
        # Should request more visits for under-visited moves
        assert len(mock_engine.request_analysis_calls) > 0


# ---------------------------------------------------------------------------
# TestAnalyzeExtraAlternativeMode
# ---------------------------------------------------------------------------

class TestAnalyzeExtraAlternativeMode:
    """Tests for analyze_extra(AnalysisMode.ALTERNATIVE)."""

    def test_alternative_requires_analysis_complete(self, game, mock_engine):
        """ALTERNATIVE mode early returns when analysis not complete."""
        game.current_node.analysis = make_analysis(completed=False)
        mock_engine.reset_tracking()
        game.analyze_extra(AnalysisMode.ALTERNATIVE)
        assert len(mock_engine.request_analysis_calls) == 0

    def test_alternative_starts_analysis_when_complete(self, game, mock_engine):
        """ALTERNATIVE mode starts analysis when analysis is complete."""
        game.current_node.analysis = make_analysis(completed=True)
        mock_engine.reset_tracking()
        game.analyze_extra(AnalysisMode.ALTERNATIVE)
        # Should call request_analysis
        assert len(mock_engine.request_analysis_calls) > 0


# ---------------------------------------------------------------------------
# TestAnalyzeExtraLocalMode
# ---------------------------------------------------------------------------

class TestAnalyzeExtraLocalMode:
    """Tests for analyze_extra(AnalysisMode.LOCAL)."""

    def test_local_skips_analysis_complete_check(self, game, mock_engine):
        """LOCAL mode does NOT require analysis_complete (unlike EQUALIZE/ALTERNATIVE)."""
        # LOCAL mode should NOT require analysis_complete
        # But it DOES require non-empty moves with varying visits for equalization
        game.current_node.analysis = make_analysis(
            completed=False,  # analysis_complete=False
            root_present=True,
            moves={
                "D4": {"visits": 100, "scoreLead": 2.0},  # Max visits = 100
                "E5": {"visits": 50, "scoreLead": 1.5},   # Under-visited, will be refined
            },
        )
        mock_engine.reset_tracking()
        game.analyze_extra(AnalysisMode.LOCAL)
        # Should still process (unlike EQUALIZE/ALTERNATIVE)
        # E5 has visits < 100 so should trigger refinement
        assert len(mock_engine.request_analysis_calls) > 0

    def test_local_refines_existing_moves(self, game, mock_engine):
        """LOCAL mode refines within existing candidate moves."""
        game.current_node.analysis = make_analysis(
            completed=True,
            moves={
                "D4": {"visits": 100, "scoreLead": 2.0},
                "E5": {"visits": 80, "scoreLead": 1.8},
            },
        )
        mock_engine.reset_tracking()
        game.analyze_extra(AnalysisMode.LOCAL)
        assert len(mock_engine.request_analysis_calls) > 0

    @pytest.mark.xfail(
        reason="Known bug: LOCAL mode crashes with empty moves at game.py:1187. Out of scope for Phase 70.",
        strict=True,
        raises=ValueError,
    )
    def test_local_with_empty_moves_crashes(self, game):
        """Document known bug: LOCAL mode crashes when analysis["moves"] is empty.

        EXACT FAILING LINE (v6 anchor):
        game.py line 1187:
            visits = max(d["visits"] for d in cn.analysis["moves"].values())

        Exception: ValueError: max() arg is an empty sequence

        Code path (game.py):
        1. Line 1178: elif mode in (..., LOCAL): ← enters branch
        2. Line 1179: if not cn.analysis_complete and mode != LOCAL: ← skipped (LOCAL exempted)
        3. Line 1182: if mode == ALTERNATIVE: ← not taken
        4. Line 1186: else:  # equalize ← LOCAL enters here (comment is misleading)
        5. Line 1187: visits = max(...) ← ValueError when moves is empty

        Verification command:
            Select-String -Path katrain/core/game.py -Pattern 'max\\(d\\["visits"\\]' -Context 2,0
        """
        # Use make_analysis factory for explicit state
        game.current_node.analysis = make_analysis(
            root_present=False,  # analysis_complete will be False
            completed=False,
            moves={},  # Empty moves triggers the bug
        )
        game.analyze_extra(AnalysisMode.LOCAL)


# ---------------------------------------------------------------------------
# TestComputeImportantMoves
# ---------------------------------------------------------------------------

class TestComputeImportantMoves:
    """Tests for Game._compute_important_moves()."""

    def test_empty_game_returns_empty_list(self, game):
        """Empty game (no analyzed moves) returns empty list."""
        result = game._compute_important_moves(max_moves=10)
        assert result == []

    def test_nodes_without_analysis_skipped(self, game):
        """Nodes without complete analysis are skipped."""
        # Add a move but don't set up analysis
        game.play(Move.from_gtp("D4", player="B"))
        result = game._compute_important_moves(max_moves=10)
        assert result == []

    def test_max_moves_limit_respected(self, game):
        """Result length is limited by max_moves parameter."""
        # Add several moves with analysis
        for i, coord in enumerate(["D4", "Q16", "D16", "Q4", "K10"]):
            player = "B" if i % 2 == 0 else "W"
            game.play(Move.from_gtp(coord, player=player))
            # Set up analysis with significant loss
            setup_analyzed_node(game.current_node, score=float(i * 2), parent_score=0.0)

        result = game._compute_important_moves(max_moves=2)
        assert len(result) <= 2

    def test_result_sorted_by_move_number(self, game):
        """Result is sorted by move number (ascending)."""
        # Add several moves with analysis
        for i, coord in enumerate(["D4", "Q16", "D16"]):
            player = "B" if i % 2 == 0 else "W"
            game.play(Move.from_gtp(coord, player=player))
            setup_analyzed_node(game.current_node, score=float(i * 3), parent_score=0.0)

        result = game._compute_important_moves(max_moves=10)

        # Check that move numbers are in ascending order
        for i in range(len(result) - 1):
            assert result[i][0] <= result[i + 1][0], "Results should be sorted by move number"

    def test_high_importance_prioritized(self, game):
        """Moves with importance > 0.5 are prioritized."""
        # Add a move with significant loss (importance > 0.5)
        # For Black: score going from 0 to -5 means Black lost 5 points
        # points_lost = player_sign("B") * (parent_score - score) = 1 * (0 - (-5)) = 5
        game.play(Move.from_gtp("D4", player="B"))
        setup_analyzed_node(game.current_node, score=-5.0, parent_score=0.0)  # Loss of 5

        result = game._compute_important_moves(max_moves=10)
        assert len(result) > 0
        # The importance should be > 0.5
        _, importance, _ = result[0]
        assert importance > 0.5

    def test_fallback_when_all_below_threshold(self, game):
        """Fallback to all nodes when all importance < 0.5."""
        # Add a move with tiny loss (importance < 0.5)
        game.play(Move.from_gtp("D4", player="B"))
        setup_analyzed_node(game.current_node, score=0.1, parent_score=0.0)  # Loss of 0.1

        result = game._compute_important_moves(max_moves=10)
        # Should still return the node as fallback
        assert len(result) > 0

    def test_return_tuple_shape(self, game):
        """Verify return tuple shape: (move_no: int, importance: float, node: GameNode)."""
        # Setup: add a move with analysis
        game.play(Move.from_gtp("D4", player="B"))
        setup_analyzed_node(game.current_node, score=5.0, parent_score=0.0)

        result = game._compute_important_moves(max_moves=10)

        # Verify tuple shape for each result
        for item in result:
            assert len(item) == 3, "Tuple must have 3 elements"
            move_no, importance, node = item
            assert isinstance(move_no, int), "move_no must be int"
            assert isinstance(importance, (int, float)), "importance must be numeric"
            assert isinstance(node, GameNode), "node must be GameNode"

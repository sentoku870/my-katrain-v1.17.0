
import json
import os
from unittest.mock import MagicMock
from katrain.core.game import Game
from katrain.core.analysis.models import GameSummaryData, EvalSnapshot, MoveEval, MistakeCategory, PositionDifficulty
from katrain.core.reports.karte.json_export import build_karte_json
from katrain.core.reports.summary_json_export import build_summary_json

def test_v6_refinements():
    print("Testing Phase v6 Refinements...")
    
    # Setup mock game
    game = MagicMock()
    game.game_id = "test_game_123"
    game.sgf_filename = "path/to/my_test_game_001.sgf"
    game.board_size = (19, 19)
    game.komi = 6.5
    game.root.get_property.side_effect = lambda p, d=None: {"PB": "Black", "PW": "White", "DT": "2024-01-01"}.get(p, d)
    game.root.handicap = 0
    
    # 1. Test game_id stability (Unit test for BaseGame logic would be better but let's check what Karte uses)
    # Actually build_karte_json uses game.game_id
    
    # 2. Test Reason Normalization
    move = MoveEval(
        move_number=10, 
        player="B", 
        gtp="Q16", 
        score_before=0.5, 
        score_after=-2.5,
        delta_score=-3.0,
        winrate_before=0.5,
        winrate_after=0.4,
        delta_winrate=-0.1,
        points_lost=3.0,
        realized_points_lost=3.0,
        root_visits=1000
    )
    move.reason_tags = {"reading_failure", "shape_mistake"}
    move.importance_score = 5.0
    move.mistake_category = MistakeCategory.MISTAKE
    move.position_difficulty = PositionDifficulty.NORMAL
    
    snapshot = EvalSnapshot(moves=[move])
    game.build_eval_snapshot.return_value = snapshot
    game.get_important_move_evals.return_value = [move]
    
    karte = build_karte_json(game)
    
    # Check Normalized codes
    mv = karte["important_moves"][0]
    print(f"Karte Reason Codes: {mv['reason_codes']}")
    assert "reading" in mv["reason_codes"]
    assert "shape" in mv["reason_codes"]
    assert "reading_failure" not in mv["reason_codes"]
    assert "shape_mistake" not in mv["reason_codes"]
    
    # Check Structured Importance
    imp_def = karte["meta"]["definitions"]["importance"]
    print(f"Importance Definition: {imp_def}")
    assert isinstance(imp_def, dict)
    assert imp_def["scale"] == "0.0 to 10.0+"
    
    # 3. Test Summary Reason Tag Aggregation
    gsd = GameSummaryData(
        game_name="test_game.sgf",
        player_black="Black",
        player_white="White",
        snapshot=snapshot,
        board_size=(19, 19)
    )
    
    summary_json_str = build_summary_json([gsd])
    summary = summary_json_str # build_summary_json now returns dict in current export? Wait.
    # Check if build_summary_json returns a dict or str.
    # Looking at summary_json_export.py, it returns dict[str, Any].
    
    blk_tags = summary["players"]["Black"]["reason_tags"]
    print(f"Summary Reason Tags (Black): {blk_tags}")
    assert "reading" in blk_tags
    assert "shape" in blk_tags
    assert blk_tags["reading"]["count"] == 1
    
    print("\n[SUCCESS] Phase v6 Refinements Verified.")

if __name__ == "__main__":
    test_v6_refinements()

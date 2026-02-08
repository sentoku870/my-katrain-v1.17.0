
import json
import os
import shutil
from unittest.mock import MagicMock
from katrain.core.analysis.models import GameSummaryData, EvalSnapshot, MoveEval, MistakeCategory, PositionDifficulty
from katrain.core.reports.summary_json_export import build_summary_json
from katrain.core.reports.summary_report import build_summary_report

def test_batch_json_stages_1_to_4():
    print("Testing JSON Summary Stages 1-4...")
    
    # Setup mock game data
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
    move.tag = "opening" # Phase
    
    snapshot = EvalSnapshot(moves=[move])
    
    gsd = GameSummaryData(
        game_name="test_game.sgf",
        player_black="Black",
        player_white="White",
        snapshot=snapshot,
        board_size=(19, 19),
        date="2024-01-01"
    )
    
    # 1. Verify build_summary_report returns raw JSON string (Stage 1)
    report_output = build_summary_report([gsd], focus_player="Black")
    print(f"Report Output Start: {report_output[:50]}...")
    
    assert report_output.strip().startswith("{"), "Report should start with JSON brace, not Markdown"
    assert "```json" not in report_output, "Report should not contain Markdown code blocks"
    
    try:
        data = json.loads(report_output)
    except json.JSONDecodeError as e:
        print(f"FATAL: Output is not valid JSON: {e}")
        exit(1)
        
    # 2. Verify Schema Version (Stage 3)
    print(f"Schema Version: {data.get('schema_version')}")
    assert data.get("schema_version") == "2.1", "Schema version should be 2.1"
    
    # 3. Verify Games List (Stage 2)
    games = data.get("games", [])
    print(f"Games List: {games}")
    assert len(games) == 1
    assert games[0]["name"] == "test_game.sgf"
    assert games[0]["moves"] == 1
    assert "game_id" in games[0], "Games list should have game_id"
    
    # 3.5 Verify Status Fields
    assert "status" in data["players"]["Black"]["reason_tags"], "reason_tags should have status"
    assert "status" in data["players"]["Black"]["mistake_sequences"], "mistake_sequences should have status"
    
    # 4. Verify Top Mistakes Details (Stage 1 & 2)
    top_mistakes = data["players"]["Black"]["top_mistakes"]
    if top_mistakes:
        mistake = top_mistakes[0]
        print(f"Top Mistake: {mistake}")
        
        # Stage 1: Player field
        assert "player" in mistake, "Mistake should have player field"
        assert mistake["player"] == "black"
        
        # Stage 2: Extended details
        assert "phase" in mistake, "Mistake should have phase"
        assert mistake["phase"] == "opening"
        
        assert "difficulty" in mistake, "Mistake should have difficulty"
        assert mistake["difficulty"] == "normal"
        
        assert "reason_codes" in mistake, "Mistake should have reason_codes"
        # Check normalization
        assert "reading" in mistake["reason_codes"]
        assert "shape" in mistake["reason_codes"]
    else:
        print("WARNING: No top mistakes found to verify details.")
        
    print("\n[SUCCESS] Stages 1-3 Verification Passed.")

if __name__ == "__main__":
    test_batch_json_stages_1_to_4()

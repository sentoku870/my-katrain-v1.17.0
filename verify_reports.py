import sys
import os
import re
import json
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from katrain.core.game import Game
from katrain.core.reports.karte.builder import build_karte_report
from katrain.core.reports.summary_report import build_summary_report
from katrain.core.reports.summary_logic import GameSummaryData
from katrain.core import eval_metrics

def extract_json(report_md):
    # Try parsing as raw JSON first (Stage 4 change)
    try:
        return json.loads(report_md)
    except json.JSONDecodeError:
        # Fallback to extracting from Markdown code block
        match = re.search(r"```json\n(.*?)\n```", report_md, re.DOTALL)
        if not match:
            raise ValueError("No JSON code block found in report")
        return json.loads(match.group(1))

def test_karte_report_json():
    print("Testing Karte Report JSON...")
    
    # Mock Game
    game = MagicMock(spec=Game)
    game.katrain = MagicMock()
    game.katrain.config.return_value = {} # Mock config
    game.root = MagicMock()
    game.root.handicap = 0 # Explicitly set to int to avoid MagicMock
    game.root.get_property.return_value = "TestValue"
    game.game_id = "game_123"
    game.sgf_filename = "test_game.sgf"
    game.board_size = (19, 19)
    game.komi = 6.5
    game.handicap = 0
    
    # Mock moves and snapshot
    mock_moves = []
    for i in range(10):
        m = MagicMock()
        m.move_number = i + 1
        m.player = "B" if i % 2 == 0 else "W"
        m.points_lost = 0.5 * i
        m.score_loss = 0.5 * i
        m.leela_loss_est = None # Explicitly set to None to avoid MagicMock returning a value
        m.winrate_lost = 0.01 * i
        m.importance_score = 0.5 # Float
        m.meaning_tag_id = "test_tag" # String to avoid classification logic which might fail or return mock
        m.mistake_category = None
        m.position_difficulty = eval_metrics.PositionDifficulty.NORMAL
        m.reason_tags = ["reason1"]
        m.gtp = "D4"
        mock_moves.append(m)
        
    snapshot = MagicMock()
    snapshot.moves = mock_moves
    game.build_eval_snapshot.return_value = snapshot
    
    # Mock important moves
    # We need to return objects that have attributes accessed by json_export
    # json_export accesses: move_number, player, points_lost, score_loss, importance_score, reason_tags, gtp, meaning_tag_id, position_difficulty
    # The mock_moves above have these.
    game.get_important_move_evals.return_value = mock_moves[:3]
    
    # Check if SkillPreset needs mocking
    # eval_metrics.get_skill_preset might be called. It reads from global dict. Should be fine.
    
    # Patch internal functions that might trip on mocks
    with patch("katrain.core.reports.karte.builder._compute_style_safe", return_value=None), \
         patch("katrain.core.reports.karte.builder.eval_metrics.compute_confidence_level", return_value=eval_metrics.ConfidenceLevel.HIGH):
        # Generate Report
        report = build_karte_report(game, skill_preset="standard")
    print("  [INFO] Karte Report generated.")
    
    # Verify
    try:
        data = extract_json(report)
    except ValueError:
        print(f"FAILED to extract JSON. Report content:\n{report}")
        raise

    # Check Meta
    assert data["schema_version"] == "2.0", f"schema_version mismatch: {data.get('schema_version')}"
    assert data["meta"]["loss_unit"] == "territory_points", "loss_unit missing or incorrect"
    assert "definitions" in data["meta"], "definitions missing"
    assert "thresholds" in data["meta"]["definitions"], "thresholds missing"
    assert "run_id" in data["meta"], "run_id missing"
    assert "primary_tags" in data["meta"]["definitions"], "primary_tags definition missing"
    assert "phases" in data["meta"]["definitions"], "phases enum missing"
    assert "phase_aliases" in data["meta"]["definitions"], "phase_aliases missing"
    assert data["meta"]["definitions"]["phases"] == ["opening", "middle", "endgame"], "phases enum incorrect"
    assert "endgame_min" in data["meta"]["definitions"]["thresholds"]["phase"], "endgame_min threshold missing"
    assert "generated_at" in data["meta"], "generated_at missing"
    assert "reason_code_aliases" in data["meta"]["definitions"], "reason_code_aliases missing"
    assert data["meta"]["definitions"]["reason_code_aliases"]["low_liberties"] == "liberties"
    assert "chase_mode" in data["meta"]["definitions"]["reason_code_aliases"], "chase_mode alias missing"
    
    # Check Important Moves
    if len(data["important_moves"]) > 0:
        im = data["important_moves"][0]
        assert isinstance(im["loss_clamped"], (int, float)), "loss_clamped not numeric"
        assert isinstance(im["move_number"], int), "move_number not int"
        assert "reason_codes" in im, "reason_codes missing"
        assert isinstance(im["reason_codes"], list), "reason_codes not list"
        assert "mistake_type" in im, "mistake_type missing"
        # Verify phase is one of canonical values
        assert im["phase"] in ["opening", "middle", "endgame", "unknown"], f"Invalid phase: {im['phase']}"
    
    print("  [PASS] Karte Report JSON valid.")


def test_summary_report_json():
    print("Testing Summary Report JSON...")
    
    # Mock Game Data
    gd = MagicMock(spec=GameSummaryData)
    gd.game_name = "test_game_1"
    gd.player_black = "Player1"
    gd.player_white = "Player2"
    gd.player_white = "Player2"
    gd.date = "2024-01-01"
    gd.game_id = "game_123"
    
    # Mock Snapshot for Summary
    mock_moves = []
    for i in range(5):
        m = MagicMock()
        m.move_number = i + 1
        m.player = "B"
        m.points_lost = 10.0 # big loss
        m.score_loss = 10.0
        m.mistake_category = eval_metrics.MistakeCategory.BLUNDER
        m.position_difficulty = eval_metrics.PositionDifficulty.NORMAL
        m.tag = "middle"
        m.gtp = "D10"
        m.reason_tags = []
        # Added for reliability calc
        m.root_visits = 100 # Correct attribute for compute_reliability_stats
        m.importance_score = 0.5 # Updated for v128+ attribute name
        mock_moves.append(m)
        
    snapshot = MagicMock()
    snapshot.moves = mock_moves
    gd.snapshot = snapshot
    
    # Mock attributes for v3 aggregation
    gd.reason_tags_by_player = {"B": {"reason1": 2}}
    gd.important_moves_stats_by_player = {"B": {
        "important_count": 5,
        "tagged_count": 2,
        "tag_occurrences": 2
    }}
    
    game_data_list = [gd]
    
    # Generate Report
    report = build_summary_report(game_data_list)
    print("  [INFO] Summary Report generated.")
    
    # Verify
    # Verify
    try:
        # Phase v6 Stage 1: Summary report is now raw JSON
        data = json.loads(report)
    except json.JSONDecodeError as e:
        print(f"FAILED to extract JSON. Report content:\n{report}")
        raise ValueError(f"Invalid JSON: {e}")
    
    # Check Meta
    assert data["schema_version"] == "2.1", f"schema_version mismatch: {data.get('schema_version')}"
    assert data["meta"]["games_analyzed"] == 1
    assert data["meta"]["loss_unit"] == "territory_points"
    assert "definitions" in data["meta"]
    assert "run_id" in data["meta"]
    assert "phases" in data["meta"]["definitions"], "phases enum missing in summary"
    assert data["meta"]["definitions"]["phases"] == ["opening", "middle", "endgame"], "phases enum incorrect in summary"
    
    # Check Player Data
    # Keys in players dict are player names
    assert "Player1" in data["players"]
    pdata = data["players"]["Player1"]
    
    assert pdata["overall"]["total_moves"] == 5
    assert pdata["overall"]["total_loss"] == 50.0
    
    assert "mistake_sequences" in pdata, "mistake_sequences missing in summary"
    assert "status" in pdata["mistake_sequences"]
    assert "data" in pdata["mistake_sequences"]
    assert isinstance(pdata["mistake_sequences"]["data"], list)
    assert "urgent_misses" not in pdata, "Old urgent_misses field should be removed"

    # Check for removal of coaching text
    assert "identified_weaknesses" not in pdata, "identified_weaknesses should be removed from pure data"

    # Check for denominators
    assert "denominator" in pdata["mistakes"]["blunder"], "denominator missing in mistakes"
    assert "denominator" in pdata["difficulty"]["normal"], "denominator missing in difficulty"
    
    # Check for reason tags (v3)
    # Check for reason tags (v3)
    assert "reason_tags" in pdata, "reason_tags section missing in summary"
    assert "status" in pdata["reason_tags"]
    assert "data" in pdata["reason_tags"]
    rt_data = pdata["reason_tags"]["data"]
    assert "reason1" in rt_data, "reason1 tag missing in summary"
    assert rt_data["reason1"]["count"] == 2
    assert rt_data["reason1"]["denominator_type"] == "tag_occurrences"
    
    print("  [PASS] Summary Report JSON valid.")


def test_phase_boundary():
    """Test that move 50 on 19x19 is classified as opening."""
    print("Testing Phase Boundary Logic...")
    
    from katrain.core.analysis.logic import classify_game_phase
    
    # Test move 50 on 19x19 board
    assert classify_game_phase(50, 19) == "opening", "Move 50 should be 'opening' on 19x19"
    assert classify_game_phase(51, 19) == "middle", "Move 51 should be 'middle' on 19x19"
    assert classify_game_phase(200, 19) == "middle", "Move 200 should be 'middle' on 19x19"
    assert classify_game_phase(201, 19) == "yose", "Move 201 should be 'yose' on 19x19"
    
    print("  [PASS] Phase boundary logic correct.")

if __name__ == "__main__":
    try:
        test_karte_report_json()
        test_summary_report_json()
        test_phase_boundary()
        print("\nAll JSON verification tests passed!")
    except Exception as e:
        print(f"\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

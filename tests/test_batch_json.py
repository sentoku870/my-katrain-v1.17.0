
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
    assert data.get("schema_version") == "3.4", "Schema version should be 3.4 (Phase 157: summary-side even/handicapped split + top-level win_loss_analysis removed)"

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

    # 3.6 Phase 157-D: top-level win_loss_analysis was removed.
    assert "win_loss_analysis" not in data, (
        "Top-level win_loss_analysis must be removed (Phase 157-D); "
        "per-player aggregation lives under players[...].win_loss_analysis."
    )

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

        # Phase 153-A: `difficulty` field removed from MistakeItem
        assert "difficulty" not in mistake, "Mistake should NOT have difficulty (removed in Phase 153-A)"

        assert "reason_codes" in mistake, "Mistake should have reason_codes"
        # Check normalization
        assert "reading" in mistake["reason_codes"]
        assert "shape" in mistake["reason_codes"]
    else:
        print("WARNING: No top mistakes found to verify details.")

    print("\n[SUCCESS] Stages 1-3 Verification Passed.")


def test_batch_json_no_top_level_win_loss_analysis():
    """Phase 157-D: ``win_loss_analysis`` must not appear at the top level.

    Historically the Summary JSON emitted ``"win_loss_analysis": null`` at
    the top level, which is redundant with ``players[...].win_loss_analysis``
    and confuses downstream LLM consumers. Phase 157-D deletes the field
    entirely so the JSON is unambiguous.
    """
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
        root_visits=1000,
    )
    move.mistake_category = MistakeCategory.MISTAKE
    move.tag = "opening"

    snapshot = EvalSnapshot(moves=[move])
    gsd = GameSummaryData(
        game_name="phase157d.sgf",
        player_black="Alice",
        player_white="Bob",
        snapshot=snapshot,
        board_size=(19, 19),
        date="2026-06-28",
        result="B+R",
    )

    data = json.loads(build_summary_report([gsd], focus_player="Alice"))

    assert "win_loss_analysis" not in data
    # Per-player view is unaffected.
    assert "win_loss_analysis" in data["players"]["Alice"]
    assert data["players"]["Alice"]["win_loss_analysis"]["win"]["games"] == 1


def test_batch_json_loss_progression_is_dict_by_type():
    """Phase 157-C: ``loss_progression`` is now a dict, not a list.

    The dict carries the cross-game ``all`` aggregate plus optional
    ``even`` / ``handicapped`` sub-lists. The previous flat list shape
    made it impossible to compare even vs. handicapped loss curves
    without re-running the whole summary pipeline.
    """
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
        root_visits=1000,
    )
    move.mistake_category = MistakeCategory.MISTAKE
    move.tag = "opening"
    snapshot = EvalSnapshot(moves=[move])

    # Single even game (defaults).
    gsd = GameSummaryData(
        game_name="phase157c.sgf",
        player_black="Alice",
        player_white="Bob",
        snapshot=snapshot,
        board_size=(19, 19),
        handicap=0,
        komi=6.5,
    )
    data = json.loads(build_summary_report([gsd], focus_player="Alice"))

    lp = data["loss_progression"]
    assert isinstance(lp, dict), "loss_progression must be a dict (Phase 157-C)"
    assert "all" in lp
    # Only ``even`` should be present (single even game).
    assert "even" in lp
    assert "handicapped" not in lp


def test_batch_json_games_by_type_in_meta():
    """Phase 157-C: meta carries ``games_by_type`` (counts by regime)."""
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
        root_visits=1000,
    )
    move.mistake_category = MistakeCategory.MISTAKE
    move.tag = "opening"
    snapshot = EvalSnapshot(moves=[move])

    even_g = GameSummaryData(
        game_name="even.sgf", player_black="A", player_white="B",
        snapshot=snapshot, board_size=(19, 19),
        handicap=0, komi=7.5, result="B+R",
    )
    hcap_g = GameSummaryData(
        game_name="hcap.sgf", player_black="A", player_white="B",
        snapshot=snapshot, board_size=(19, 19),
        handicap=2, komi=0.5, result="B+R",
    )

    data = json.loads(build_summary_report([even_g, hcap_g], focus_player="A"))

    assert data["meta"]["games_by_type"] == {"even": 1, "handicapped": 1, "unknown": 0}
    # both regimes present
    assert "even" in data["loss_progression"]
    assert "handicapped" in data["loss_progression"]
    assert "A" in data["players"]
    assert "even" in data["players"]["A"]
    assert "handicapped" in data["players"]["A"]


def test_batch_json_even_handicapped_substats():
    """Phase 157-C: per-player ``even`` / ``handicapped`` blocks are populated."""
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
        root_visits=1000,
    )
    move.mistake_category = MistakeCategory.MISTAKE
    move.tag = "opening"
    snapshot = EvalSnapshot(moves=[move])

    hcap_g = GameSummaryData(
        game_name="hcap.sgf", player_black="A", player_white="B",
        snapshot=snapshot, board_size=(19, 19),
        handicap=2, komi=0.5, result="B+R",
    )

    data = json.loads(build_summary_report([hcap_g], focus_player="A"))

    # Even block absent (no even games), handicapped block present.
    player_block = data["players"]["A"]
    assert "even" not in player_block
    assert "handicapped" in player_block
    assert player_block["handicapped"]["overall"]["total_games"] == 1
    assert player_block["handicapped"]["win_loss_analysis"]["win"]["games"] == 1

if __name__ == "__main__":
    test_batch_json_stages_1_to_4()

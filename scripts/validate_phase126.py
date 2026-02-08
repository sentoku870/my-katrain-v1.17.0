import sys
import unittest
from unittest.mock import MagicMock, patch
import json

# Add project root to path
sys.path.append("d:/github/katrain-1.17.0")

from katrain.core.reports.summary_json_export import build_summary_json
from katrain.core.reports.karte.json_export import build_karte_json
from katrain.core.eval_metrics import GameSummaryData, PositionDifficulty, MistakeCategory, MoveEval

class TestPhase126Refinements(unittest.TestCase):
    def test_refinements(self):
        """Test Phase 126 refinements."""
        # Mock move with 'easy' difficulty
        mock_move = MagicMock()
        mock_move.move_number = 10
        mock_move.player = "B"
        mock_move.points_lost = 5.0
        mock_move.score_loss = 5.0
        mock_move.mistake_category = MistakeCategory.MISTAKE
        mock_move.position_difficulty = PositionDifficulty.EASY # Should map to 'simple'
        mock_move.reason_tags = ["shape"]
        mock_move.root_visits = 100
        mock_move.importance_score = 4.5
        mock_move.meaning_tag_id = "shape_mistake"
        mock_move.tag = "this_should_be_ignored" # Phase should be computed from move_number
        
        mock_snapshot = MagicMock()
        mock_snapshot.moves = [mock_move]
        
        gd = GameSummaryData(
            game_name="test_game",
            player_black="Hero",
            player_white="Villain",
            snapshot=mock_snapshot,
            board_size=(19, 19),
            game_id="game_123",
            date="2023-01-01",
            result="B+R",
            komi=6.5,
            handicap=0,
            skill_preset="pro"
        )
        
        # Test Summary
        summary = build_summary_json([gd], focus_player="Hero")
        
        # 1. Check skill_preset in meta
        self.assertEqual(summary["meta"]["skill_preset"], "pro")
        
        # 2. Check difficulty mapping ('easy' -> 'simple')
        hero_stats = summary["players"]["Hero"]
        # In difficulty distribution, 'easy' should be present but extracted data should use 'simple'?
        # Wait, the extractor maps it to 'simple'. The distribution uses PositionDifficulty labels.
        # Summary distribution uses: key = diff.value.lower()
        # PositionDifficulty.EASY.value is 'EASY' -> 'easy'.
        # The user wants to standardize the set. 
        # definitions.difficulty_levels has 'simple'.
        # If I want the distribution to match definitions, I should change PositionDifficulty labels or map them.
        self.assertIn("simple", summary["meta"]["definitions"]["difficulty_levels"])
        self.assertIn("unknown", summary["meta"]["definitions"]["difficulty_levels"])
        
        # Check mistake item difficulty
        mistake = hero_stats["top_mistakes"][0]
        self.assertEqual(mistake["difficulty"], "simple") # Standardized!
        
        # 3. Check phase computation
        self.assertEqual(mistake["phase"], "opening") # move 10 on 19x19 is opening
        
        # Test Karte
        mock_game = MagicMock()
        mock_game.board_size = (19, 19)
        mock_game.komi = 6.5
        mock_game.game_id = "game_123"
        mock_game.root.get_property.side_effect = lambda key, default=None: "Player" if key in ["PB", "PW"] else default
        mock_game.build_eval_snapshot.return_value = mock_snapshot
        mock_game.get_important_move_evals.return_value = [mock_move]
        
        karte = build_karte_json(mock_game, skill_preset="pro")
        
        # Check karte move phase
        karte_move = karte["important_moves"][0]
        self.assertEqual(karte_move["phase"], "opening")
        self.assertEqual(karte_move["difficulty"], "simple")

if __name__ == "__main__":
    unittest.main()

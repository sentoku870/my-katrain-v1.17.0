"""Shared data extraction logic for KaTrain JSON reports.

This module provides the 'Adapter' layer that converts internal KaTrain
objects (GameNode, AnalysisResult, GameSummaryData) into the standardized
dictionaries defined in `schema.py`.
"""
from typing import Optional, List, Any, Dict

from katrain.core.game_node import GameNode
from katrain.core.eval_metrics import (
    MistakeCategory,
    PositionDifficulty,
    classify_game_phase,
)
from katrain.core.reports.definitions import (
    PHASES,
    PHASE_ALIASES,
    DIFFICULTY_LEVELS,
    REASON_CODE_ALIASES,
    CATEGORY_ALIASES,
)
from katrain.core.reports.schema import MistakeItem, GameMeta


class MoveExtractor:
    """Extracts standardized data from a GameNode."""

    @staticmethod
    def extract(
        node: GameNode, 
        game_id: Optional[str] = None, 
        game_name: str = "",
        board_size: int = 19
    ) -> MistakeItem:
        """Convert a GameNode into a MistakeItem dict."""
        
        # 1. Basic Info
        move_number = node.move_number
        player = "black" if node.player == "B" else "white" if node.player == "W" else "unknown"
        coords = node.gtp or "-"
        
        # 2. Loss & Score
        loss = node.points_lost if node.points_lost is not None else node.score_loss
        loss_clamped = max(0.0, loss) if loss is not None else 0.0
        importance = node.importance_score or 0.0

        # 3. Phase Normalization
        try:
            phase = classify_game_phase(move_number, board_size)
            phase = PHASE_ALIASES.get(phase, phase)
        except Exception:
            phase = "unknown"
        
        if phase not in PHASES and phase != "unknown":
             phase = "unknown"

        # 4. Difficulty
        difficulty = node.position_difficulty.value.lower() if node.position_difficulty else "unknown"
        if difficulty == "easy":
            difficulty = "simple"
        elif difficulty not in DIFFICULTY_LEVELS:
            difficulty = "unknown"

        # 5. Mistake Type
        mistake_type = node.mistake_category.value.lower() if node.mistake_category else "unknown"
        # Optional: Map to short codes if needed, but schema uses full names usually.
        # category_short = CATEGORY_ALIASES.get(mistake_type, mistake_type)

        # 6. Reason Codes Normalization
        raw_tags = list(node.reason_tags) if node.reason_tags else []
        reason_codes = sorted(list(set(REASON_CODE_ALIASES.get(t, t) for t in raw_tags)))

        # 7. Primary Tag
        primary_tag = node.meaning_tag_id

        return {
            "game_name": game_name,
            "game_id": game_id,
            "move_number": move_number,
            "player": player,
            "coords": coords,
            "phase": phase,
            "difficulty": difficulty,
            "loss_clamped": round(loss_clamped, 2),
            "loss_raw": round(loss, 2) if loss is not None else None,
            "importance": round(importance, 2),
            "mistake_type": mistake_type,
            "reason_codes": reason_codes,
            "primary_tag": primary_tag,
        }


class MetaExtractor:
    """Extracts standardized metadata."""
    
    @staticmethod
    def extract_game_meta(
        game_data: Any, # Can be Game or GameSummaryData
        game_id: Optional[str] = None
    ) -> GameMeta:
        """Extract metadata from Game or GameSummaryData object."""
        
        # Duck typing to handle both Game and GameSummaryData
        # Game object has 'root', GameSummaryData has attributes directly or in snapshot
        
        root = getattr(game_data, 'root', None)
        
        # Result
        if hasattr(game_data, 'result'):
            result = game_data.result
        elif root:
            result = root.get_property("RE")
        else:
            result = None
            
        # Komi
        if hasattr(game_data, 'komi'):
            komi = game_data.komi
        elif root:
            try:
                komi = float(root.get_property("KM", 0.0))
            except:
                komi = 0.0
        else:
            komi = 0.0
            
        # Handicap
        if hasattr(game_data, 'handicap'):
            handicap = game_data.handicap
        elif root:
            handicap = int(root.get_property("HA", 0))
        else:
            handicap = 0

        # Names
        if hasattr(game_data, 'player_black'):
            pb = game_data.player_black
            pw = game_data.player_white
        elif root:
            pb = root.get_property("PB", "Black")
            pw = root.get_property("PW", "White")
        else:
            pb, pw = "Black", "White"
            
        # Size
        board_size = getattr(game_data, 'board_size', [19, 19])
        if isinstance(board_size, int):
            board_size = [board_size, board_size]
            
        # Moves count
        if hasattr(game_data, 'snapshot'):
             moves_count = len(game_data.snapshot.moves)
        elif hasattr(game_data, 'moves'):
             moves_count = len(game_data.moves)
        elif root:
             # Expensive to count if not cached?
             # For Karte reuse existing count if passed, otherwise leave 0 or calc?
             # Assuming context usually has it.
             moves_count = 0 
        else:
             moves_count = 0
             
        # Game ID
        gid = game_id or getattr(game_data, 'game_id', "unknown_id")
        
        # Name
        # GameSummaryData has game_name, Game usually doesn't store a 'name' per se unless external
        name = getattr(game_data, 'game_name', f"Game {gid}")
        
        # Date
        # GameSummaryData has date, Game has root date
        if hasattr(game_data, 'date'):
            date = game_data.date
        elif root:
            date = root.get_property("DT", "")
        else:
            date = ""

        return {
            "name": name,
            "date": date,
            "game_id": gid,
            "moves": moves_count,
            "result": result,
            "handicap": handicap,
            "komi": komi,
            "board_size": board_size,
            "players": {
                "black": pb,
                "white": pw
            }
        }

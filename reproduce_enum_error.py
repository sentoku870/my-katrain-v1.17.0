
import sys
import unittest
from unittest.mock import MagicMock
from enum import Enum

# Mock PositionDifficulty enum as it exists in the codebase
class PositionDifficulty(Enum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"
    ONLY_MOVE = "only"
    UNKNOWN = "unknown"

# Mock MoveEval
class MoveEval:
    def __init__(self, position_difficulty=None):
        self.position_difficulty = position_difficulty

def test_enum_usage():
    print("Testing PositionDifficulty enum usage...")
    mv = MoveEval(position_difficulty=PositionDifficulty.EASY)
    
    try:
        # Reproduce the bug: attempting to call .lower() on an Enum member
        difficulty = mv.position_difficulty.lower() if mv.position_difficulty else "unknown"
        print(f"Success? Difficulty: {difficulty}")
    except AttributeError as e:
        print(f"Caught expected AttributeError: {e}")
        return True
    except Exception as e:
        print(f"Caught unexpected exception: {e}")
        return False
        
    return False

if __name__ == "__main__":
    if test_enum_usage():
        print("Scenerio reproduced successfully.")
        sys.exit(0)
    else:
        print("Failed to reproduce scenario (or it didn't crash as expected).")
        sys.exit(1)

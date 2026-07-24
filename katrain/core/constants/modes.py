"""Game / player mode constants.

Phase PR1: Extracted from ``katrain.core.constants`` to limit blast
radius. All symbols are re-exported from the package root for
backward compatibility.

Categories:
    MODE_*      Top-level app mode (play vs analyze)
    PLAYER_*    Player type (human vs AI)
    PLAYING_*   Playing style (normal vs teaching)
    GAME_TYPES  Tuple-like list of valid PLAYING_* values
"""

# --- App mode ---
MODE_PLAY = "play"
MODE_ANALYZE = "analyze"

# --- Player type ---
PLAYER_HUMAN, PLAYER_AI = "player:human", "player:ai"
PLAYER_TYPES = [PLAYER_HUMAN, PLAYER_AI]

# --- Playing style ---
PLAYING_NORMAL, PLAYING_TEACHING = "game:normal", "game:teach"
GAME_TYPES = [PLAYING_NORMAL, PLAYING_TEACHING]

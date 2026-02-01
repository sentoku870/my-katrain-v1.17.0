"""Karte report exceptions and constants.

This module is the bottom layer of the karte package.
It MUST NOT import any other karte modules.
"""

class KarteGenerationError(Exception):
    """Exception raised when karte generation fails.

    Attributes:
        game_id: Identifier of the game being processed
        focus_player: Player filter if any ("B", "W", or None)
        context: Additional context about where the error occurred
        original_error: The underlying exception that caused this error
    """

    def __init__(
        self,
        message: str,
        game_id: str = "",
        focus_player: str | None = None,
        context: str = "",
        original_error: Exception | None = None,
    ):
        super().__init__(message)
        self.game_id = game_id
        self.focus_player = focus_player
        self.context = context
        self.original_error = original_error

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.game_id:
            parts.append(f"game_id={self.game_id}")
        if self.focus_player:
            parts.append(f"focus_player={self.focus_player}")
        if self.context:
            parts.append(f"context={self.context}")
        return " | ".join(parts)


class MixedEngineSnapshotError(ValueError):
    """Mixed-engine snapshot detection exception.

    Raised by build_karte_report() when raise_on_error=True and the snapshot
    contains analysis data from both KataGo and Leela engines.

    This is a dedicated exception to avoid catching unrelated ValueErrors.
    """

    pass


# Error code constants for stable test assertions
KARTE_ERROR_CODE_MIXED_ENGINE = "KARTE_ERROR_CODE: MIXED_ENGINE"
KARTE_ERROR_CODE_GENERATION_FAILED = "KARTE_ERROR_CODE: GENERATION_FAILED"

# Style confidence threshold (Phase 66)
# Below this threshold, style name is shown as "Unknown" and 勝負術 section is hidden
STYLE_CONFIDENCE_THRESHOLD = 0.2


# Critical 3 LLM Prompt (Phase 50)
CRITICAL_3_PROMPT_TEMPLATE = """# Go Game Review Request

## Player Context
- Level: {player_level}
- Focus: Learning from critical mistakes

## Critical Mistakes

{critical_moves_section}

## Analysis Request
Please analyze each mistake and provide:
1. What fundamental concept or pattern was missed?
2. A simple rule or mental check for similar positions
3. One recommended practice pattern or exercise

Keep explanations concise and actionable.
"""

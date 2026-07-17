"""Karte report exceptions and constants.

This module is the bottom layer of the karte package.
It MUST NOT import any other karte modules.
"""

import re
from typing import Final

# ---------------------------------------------------------------------------
# Phase 235: Error message sanitiser
# ---------------------------------------------------------------------------
# Internal exception messages often leak file paths, stack-trace excerpts, or
# temporary-directory names that have no business appearing in the LLM
# prompt or in a user-facing Popup. :func:`sanitize_error_message` is a tiny
# pure helper that strips those bits before the string is shown to the user
# or pasted into the Karte JSON / LLM prompt. The full unsanitised message
# is preserved in :attr:`KarteGenerationError.original_error` and the log.

_PATH_LIKE: Final[re.Pattern[str]] = re.compile(
    r"""
    (?:
        # Unix absolute path: /usr/local/...
        /[A-Za-z0-9_./-]+
        |
        # Windows drive path: C:\Users\... or D:/path
        [A-Za-z]:[\\/][A-Za-z0-9_.\\/-]+
        |
        # Home-relative: ~/...
        ~[A-Za-z0-9_./-]+
        |
        # Posix relative with too many separators
        \.{1,2}[/\\][A-Za-z0-9_./-]+
    )
    """,
    re.VERBOSE,
)

_MAX_USER_SAFE_LEN: Final[int] = 200


def sanitize_error_message(msg: str | None) -> str:
    """Return a user-safe / LLM-safe version of an exception message.

    Phase 235: the Karte error karte and the export Popup both used to
    embed the raw ``str(exc)`` value, which can leak absolute paths,
    temp-dir names, internal stack-frame text, or (in extreme cases)
    data from the SGF being analysed. This helper strips those bits
    so the surfaced text is safe to ship in an LLM prompt.

    The full original message remains available via
    :attr:`KarteGenerationError.original_error` and the application
    log; sanitisation is purely about the user-facing surface.

    Rules:
        1. ``None`` / empty → ``"Unknown error."``.
        2. Take only the first line of multi-line messages.
        3. Replace any path-like substring with ``"<path>"``.
        4. Truncate to 200 characters (append ``"..."`` when cut).
        5. Ensure the result ends with ``"."``, ``"!"`` or ``"?"``.

    Args:
        msg: The original exception message (``str(exc)`` or similar).

    Returns:
        A sanitised string safe to embed in a Karte JSON error block
        or in a Kivy Popup / LLM prompt.
    """
    if not msg:
        return "Unknown error."

    # 1. first line only
    text = str(msg).split("\n", 1)[0].strip()
    if not text:
        return "Unknown error."

    # 2. strip path-like substrings
    text = _PATH_LIKE.sub("<path>", text)

    # 3. truncate
    if len(text) > _MAX_USER_SAFE_LEN:
        text = text[: _MAX_USER_SAFE_LEN - 3] + "..."

    # 4. trailing punctuation
    if not text.endswith((".", "!", "?")):
        text += "."

    return text


class KarteGenerationError(Exception):
    """Exception raised when karte generation fails.

    Attributes:
        game_id: Identifier of the game being processed
        focus_player: Player filter if any ("B", "W", or None)
        context: Additional context about where the error occurred
        original_error: The underlying exception that caused this error
        user_message: Phase 235: a sanitised message safe to embed in a
            Karte error karte / LLM prompt / user-facing Popup. The full
            unsanitised text is preserved in :attr:`original_error`.
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
        # Phase 235: pre-compute the user-safe variant so call sites
        # don't have to remember to call the sanitiser.
        self.user_message: str = sanitize_error_message(message)

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.game_id:
            parts.append(f"game_id={self.game_id}")
        if self.focus_player:
            parts.append(f"focus_player={self.focus_player}")
        if self.context:
            parts.append(f"context={self.context}")
        return " | ".join(parts)


# Phase 171: MixedEngineSnapshotError / KARTE_ERROR_CODE_NON_KATAGO は
# KataGo 専用化により不要となったため削除。


# Error code constants for stable test assertions
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

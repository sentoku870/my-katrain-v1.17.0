"""RE (Result) string parser.

Parses the SGF ``RE`` property and derives per-player outcomes for the
summary report (Phase 154-A).

Supported RE formats:

- ``B+R`` / ``W+R`` — resignation
- ``B+T`` / ``W+T`` — time forfeit
- ``B+5.5`` / ``W+5.5`` — score difference (komi-style)
- ``0`` / ``Draw`` / ``Jigo`` — draw / jigo (treated as non-loss for both)
- ``?`` / empty / unknown — undetermined
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Final


class PlayerOutcome(enum.StrEnum):
    """Per-player outcome of a game."""

    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# "B+R", "W+T", "b+r" (case-insensitive)
_RE_RESIGN_TIME: Final[re.Pattern[str]] = re.compile(r"^([BW])\s*\+\s*([RT])$", re.IGNORECASE)

# "B+5.5", "W+12.5", "b+0.5" (case-insensitive)
_RE_SCORE: Final[re.Pattern[str]] = re.compile(r"^([BW])\s*\+\s*([\d.]+)$", re.IGNORECASE)

# "0", "Draw", "Jigo" (case-insensitive, with optional whitespace)
_RE_DRAW: Final[re.Pattern[str]] = re.compile(r"^(0|Draw|Jigo)$", re.IGNORECASE)


@dataclass(frozen=True)
class GameOutcome:
    """Parsed game outcome.

    Attributes:
        black: Outcome for the black player.
        white: Outcome for the white player.
        score_diff: Signed score difference (positive = black winning,
            negative = white winning). ``None`` when not derivable (e.g.
            ``B+R``).
        raw: Original RE string.
    """

    black: PlayerOutcome
    white: PlayerOutcome
    score_diff: float | None
    raw: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_result(result_str: str | None) -> GameOutcome:
    """Parse an SGF ``RE`` string into a :class:`GameOutcome`.

    Args:
        result_str: Raw value of the ``RE`` property (may be ``None`` or
            empty).

    Returns:
        Parsed outcome. Unknown inputs yield ``PlayerOutcome.UNKNOWN`` for
        both players with ``score_diff=None``.
    """
    if not result_str:
        return GameOutcome(
            black=PlayerOutcome.UNKNOWN,
            white=PlayerOutcome.UNKNOWN,
            score_diff=None,
            raw=result_str or "",
        )

    raw = result_str.strip()
    if not raw:
        return GameOutcome(
            black=PlayerOutcome.UNKNOWN,
            white=PlayerOutcome.UNKNOWN,
            score_diff=None,
            raw="",
        )

    upper = raw.upper()

    # Draw / jigo
    if _RE_DRAW.match(upper):
        return GameOutcome(
            black=PlayerOutcome.DRAW,
            white=PlayerOutcome.DRAW,
            score_diff=0.0,
            raw=raw,
        )

    # Resignation or time forfeit: "B+R", "W+T", etc.
    m = _RE_RESIGN_TIME.match(upper)
    if m:
        winner = m.group(1).upper()
        return GameOutcome(
            black=PlayerOutcome.WIN if winner == "B" else PlayerOutcome.LOSS,
            white=PlayerOutcome.WIN if winner == "W" else PlayerOutcome.LOSS,
            score_diff=None,
            raw=raw,
        )

    # Score difference: "B+5.5", "W+12.5"
    m = _RE_SCORE.match(upper)
    if m:
        winner = m.group(1).upper()
        try:
            diff = float(m.group(2))
        except ValueError:
            return GameOutcome(
                black=PlayerOutcome.UNKNOWN,
                white=PlayerOutcome.UNKNOWN,
                score_diff=None,
                raw=raw,
            )
        signed = diff if winner == "B" else -diff
        return GameOutcome(
            black=PlayerOutcome.WIN if winner == "B" else PlayerOutcome.LOSS,
            white=PlayerOutcome.WIN if winner == "W" else PlayerOutcome.LOSS,
            score_diff=signed,
            raw=raw,
        )

    # Unrecognized
    return GameOutcome(
        black=PlayerOutcome.UNKNOWN,
        white=PlayerOutcome.UNKNOWN,
        score_diff=None,
        raw=raw,
    )


def outcome_for_player(outcome: GameOutcome, player: str) -> PlayerOutcome:
    """Convenience: get the outcome for a single player.

    Args:
        outcome: Parsed game outcome.
        player: ``"B"`` or ``"W"``.

    Returns:
        Outcome for the requested player; ``UNKNOWN`` for invalid input.
    """
    if player == "B":
        return outcome.black
    if player == "W":
        return outcome.white
    return PlayerOutcome.UNKNOWN

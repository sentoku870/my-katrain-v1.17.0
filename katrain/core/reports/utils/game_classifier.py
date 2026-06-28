"""Game-type classifier (Phase 157-C).

Splits a multi-game run into ``even`` (no handicap, normal komi) vs
``handicapped`` (handicap stones or zero / reduced komi) groups so the
Summary JSON can report side-by-side statistics for each regime.

Why this exists:
    Coaching feedback differs sharply between an even game (``HA=0``,
    ``KM>=6.0``) and a handicap game (``HA>=2`` or ``KM<6.0``). Conflating
    them hides whether a player's errors come from competitive play or
    from set-piece (honte / fuseki) execution under a komi / handicap
    disadvantage.

Classification rules:
    - ``even``       — ``handicap == 0 AND komi >= 6.0`` (also covers
      Chinese ``KM=7.5`` and the default Japanese ``KM=6.5``).
    - ``handicapped`` — ``handicap >= 2 OR komi < 6.0`` (set handicap
      stones or no-komi / reduced-komi games).
    - ``unknown``    — neither side applies (rare; e.g. ``HA=0`` with
      unusual komi values like ``3.5``). Reported as a third bucket so
      downstream code can detect it explicitly instead of silently
      dropping the game.
"""
from __future__ import annotations

from typing import Final, Literal

from katrain.core.analysis.models import GameSummaryData

GameType = Literal["even", "handicapped", "unknown"]

# Threshold below which komi is treated as a handicap-game marker (no-komi /
# reduced-komi handicaps common on some Asian platforms). Phase 157-C.
EVEN_KOMI_FLOOR: Final[float] = 6.0


def classify_game(game: GameSummaryData) -> GameType:
    """Classify a single game into one of ``"even"``, ``"handicapped"``, ``"unknown"``.

    Args:
        game: Per-game summary; only ``handicap`` and ``komi`` are read.

    Returns:
        The literal type tag for this game. See module docstring for
        rules.
    """
    handicap = game.handicap or 0
    komi = game.komi if game.komi is not None else 6.5

    if handicap >= 2 or komi < EVEN_KOMI_FLOOR:
        return "handicapped"
    if handicap == 0 and komi >= EVEN_KOMI_FLOOR:
        return "even"
    return "unknown"


def classify_games(
    game_data_list: list[GameSummaryData],
) -> dict[GameType, list[GameSummaryData]]:
    """Split a list of games into the three ``GameType`` buckets.

    Args:
        game_data_list: Source games (each must carry ``handicap`` /
            ``komi``).

    Returns:
        Dict with keys ``"even"``, ``"handicapped"``, ``"unknown"``;
        values are non-overlapping lists of the input games. The
        ``"unknown"`` list is always present (possibly empty) so callers
        can always iterate without ``KeyError``.
    """
    buckets: dict[GameType, list[GameSummaryData]] = {
        "even": [],
        "handicapped": [],
        "unknown": [],
    }
    for gd in game_data_list:
        buckets[classify_game(gd)].append(gd)
    return buckets

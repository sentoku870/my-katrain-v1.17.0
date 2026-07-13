"""Phase 186: Curator profile loader.

Lightweight utilities for reading the curator profile JSON output produced
by ``batch.curator.generate_curator_outputs`` and exposing the bits the
Beginner Hint system needs:

- ``weak_tags`` — per MeaningTag occurrence count across the user's
  analysed games (see ``core/curator/scoring._extract_user_weak_tags``).
- ``total_games`` — number of games that contributed to the profile.

The Hint detector (``core.beginner.detector_curator``) only needs the
``weak_tags`` mapping; this module keeps the loader small and avoids
dragging in the heavier scoring imports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Phase 186: minimum games required for the curator hint to be
# meaningful. Below this the profile is too thin to talk about user
# weaknesses.
DEFAULT_MIN_GAMES = 5

# Phase 186: minimum tag occurrences inside ``weak_tags`` before a
# matching move can fire CURATOR_WEAK_AXIS. Phase 86's pattern miner
# already filters at 3 for statistical significance; we reuse that
# number to keep the per-game and the curator hint thresholds in
# alignment.
DEFAULT_MIN_TAG_OCCURRENCES = 3


@dataclass(frozen=True)
class CuratorProfile:
    """Lightweight snapshot of the user's curator profile (Phase 186).

    Attributes:
        weak_tags: ``{meaning_tag_id: occurrence_count}`` aggregated
            across all analysed games. Tags below the configured
            ``min_occurrences`` are excluded at construction time.
        total_games: Number of games that contributed to this profile.
        source_path: Optional path to the curator JSON file the profile
            was loaded from. Useful for debugging / status messages.
    """

    weak_tags: dict[str, int]
    total_games: int = 0
    source_path: str | None = None

    def is_loaded(self, *, min_games: int = DEFAULT_MIN_GAMES) -> bool:
        """Return True if the profile has enough games to be useful."""
        return self.total_games >= int(min_games) and bool(self.weak_tags)

    def lookup(self, tag_id: str | None, *, min_occurrences: int = DEFAULT_MIN_TAG_OCCURRENCES) -> int:
        """Return the occurrence count for ``tag_id`` (0 if missing/below threshold).

        Args:
            tag_id: MeaningTagId value, e.g. ``"overplay"``. ``None`` returns 0.
            min_occurrences: Minimum count to consider a real weakness.
                Tags below this are reported as 0 to suppress noisy hints
                for tags that only fired once or twice.

        Returns:
            Integer count, or 0 if the tag isn't in the profile or
            doesn't reach ``min_occurrences``.
        """
        if not tag_id:
            return 0
        count = int(self.weak_tags.get(str(tag_id), 0))
        if count < int(min_occurrences):
            return 0
        return count


def load_curator_profile(
    path: str | Path | None,
    *,
    min_occurrences: int = DEFAULT_MIN_TAG_OCCURRENCES,
) -> CuratorProfile | None:
    """Load a CuratorProfile from a curator_ranking.json file (Phase 186).

    The file is the JSON produced by ``CuratorBatchResult`` /
    ``generate_curator_outputs``; this loader is intentionally permissive
    and reads only the fields it needs.

    Args:
        path: Path to the curator_ranking.json file (or None for "no profile").
        min_occurrences: Tags below this count are excluded from
            ``weak_tags`` so the hint detector only fires on statistically
            meaningful patterns.

    Returns:
        CuratorProfile, or ``None`` when the file is missing /
        malformed / has no useful data.
    """
    if path is None:
        return None
    path_obj = Path(path)
    if not path_obj.is_file():
        return None
    try:
        with path_obj.open(encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    return curator_profile_from_payload(payload, min_occurrences=min_occurrences, source_path=str(path_obj))


def curator_profile_from_payload(
    payload: Any,
    *,
    min_occurrences: int = DEFAULT_MIN_TAG_OCCURRENCES,
    source_path: str | None = None,
) -> CuratorProfile | None:
    """Build a CuratorProfile from an arbitrary curator-ranking payload.

    Accepts the shape produced by ``CuratorBatchResult.to_dict()``
    (``{"rankings": [...], "user_weak_tags": [...]}``) or any dict with a
    ``user_weak_tags`` list. A list-of-pairs ``[[tag, count], ...]`` is
    also supported for forward-compatibility with newer Curator output.

    Args:
        payload: Loaded JSON (dict) or any value that exposes the
            ``user_weak_tags`` field.
        min_occurrences: Same as :func:`load_curator_profile`.
        source_path: Optional source identifier for the profile.

    Returns:
        CuratorProfile, or ``None`` when the payload cannot be parsed.
    """
    if not isinstance(payload, dict):
        return None
    raw = payload.get("user_weak_tags")
    if raw is None:
        # Older curator shape: nested under "user_aggregate".
        agg = payload.get("user_aggregate")
        if isinstance(agg, dict):
            raw = agg.get("weak_tags") or agg.get("meaning_tags")
    weak_tags: dict[str, int] = {}
    if isinstance(raw, dict):
        for tag, count in raw.items():
            try:
                c = int(count)
            except (TypeError, ValueError):
                continue
            if c >= int(min_occurrences):
                weak_tags[str(tag)] = c
    elif isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                tag, count = entry[0], entry[1]
                try:
                    c = int(count)
                except (TypeError, ValueError):
                    continue
                if c >= int(min_occurrences):
                    weak_tags[str(tag)] = c
            elif isinstance(entry, str):
                weak_tags[entry] = int(min_occurrences)

    total_games = payload.get("total_games") or payload.get("num_games")
    try:
        total_games_int = int(total_games) if total_games is not None else 0
    except (TypeError, ValueError):
        total_games_int = 0

    if not weak_tags and total_games_int == 0:
        return None
    return CuratorProfile(
        weak_tags=weak_tags,
        total_games=total_games_int,
        source_path=source_path,
    )


__all__ = [
    "CuratorProfile",
    "DEFAULT_MIN_GAMES",
    "DEFAULT_MIN_TAG_OCCURRENCES",
    "load_curator_profile",
    "curator_profile_from_payload",
]

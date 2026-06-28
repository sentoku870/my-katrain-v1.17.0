"""Rank classifier (Phase 155-A).

Maps an SGF ``BR``/``WR`` rank string into one of four coarse buckets:

- ``kyu`` — amateur kyu ranks (30k..1k)
- ``dan`` — amateur dan ranks (1d..6d, "weak amateur")
- ``high_dan`` — high dan ranks (7d+, including pro)
- ``unknown`` — empty / unparseable input

Why this exists:
    SGF rank strings are noisy. Common formats include ``"5k"``, ``"3d"``,
    ``"7d"``, ``"?"``, ``"30k"``, ``""`` (KGS / Fox / Tygem conventions
    differ). The summary JSON exposes only the bucket, so downstream
    consumers (LLMs, dashboards) do not have to re-parse.

Examples:
    >>> classify_rank_to_bucket("5k")
    <RankBucket.KYU: 'kyu'>
    >>> classify_rank_to_bucket("3d")
    <RankBucket.DAN: 'dan'>
    >>> classify_rank_to_bucket("7d")
    <RankBucket.HIGH_DAN: 'high_dan'>
    >>> classify_rank_to_bucket("")
    <RankBucket.UNKNOWN: 'unknown'>
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Final


class RankBucket(str, enum.Enum):
    """Coarse rank bucket for opponent-strength correlation (Phase 155-A)."""

    KYU = "kyu"
    DAN = "dan"
    HIGH_DAN = "high_dan"
    UNKNOWN = "unknown"


# "5k", "30K", "1d", "7D", with optional whitespace
_RE_RANK: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{1,2})\s*([kKdD])\s*$")


@dataclass(frozen=True)
class RankInfo:
    """Parsed rank information.

    Attributes:
        bucket: Coarse bucket (kyu / dan / high_dan / unknown).
        numeric: Numeric portion of the rank (e.g. ``5`` for ``"5k"``).
            ``None`` when the rank could not be parsed.
        is_dan: ``True`` when the original token was a dan rank.
        is_pro: ``True`` when the rank is at or above the pro threshold
            (default 7d; configurable via :func:`classify_rank_to_bucket`).
    """

    bucket: RankBucket
    numeric: int | None
    is_dan: bool
    is_pro: bool


# Threshold above which a dan rank is considered "high dan" (pro tier).
# 7d is the conventional professional threshold in amateur conventions.
PRO_THRESHOLD: Final[int] = 7


def classify_rank_to_bucket(
    rank_str: str | None,
    *,
    pro_threshold: int = PRO_THRESHOLD,
) -> RankInfo:
    """Classify a rank string into a bucket.

    Args:
        rank_str: Raw SGF ``BR``/``WR`` value (may be ``None`` or empty).
        pro_threshold: Minimum dan value considered "high dan" / pro.
            Defaults to 7d.

    Returns:
        :class:`RankInfo` with the coarse bucket and parsed metadata.
    """
    if not rank_str:
        return RankInfo(bucket=RankBucket.UNKNOWN, numeric=None, is_dan=False, is_pro=False)

    m = _RE_RANK.match(rank_str.strip())
    if not m:
        # Common non-numeric tokens: "?", "pro", "P", "30k?"
        return RankInfo(bucket=RankBucket.UNKNOWN, numeric=None, is_dan=False, is_pro=False)

    numeric = int(m.group(1))
    letter = m.group(2).lower()

    if letter == "k":
        return RankInfo(bucket=RankBucket.KYU, numeric=numeric, is_dan=False, is_pro=False)
    # letter == "d"
    is_pro = numeric >= pro_threshold
    bucket = RankBucket.HIGH_DAN if is_pro else RankBucket.DAN
    return RankInfo(bucket=bucket, numeric=numeric, is_dan=True, is_pro=is_pro)


def bucket_for_player(
    rank_black: str | None,
    rank_white: str | None,
    player: str,
) -> RankBucket:
    """Get the rank bucket of a player's opponent.

    Args:
        rank_black: SGF ``BR`` value.
        rank_white: SGF ``WR`` value.
        player: ``"B"`` or ``"W"``.

    Returns:
        The opponent's rank bucket (when ``player == "B"`` returns the
        white player's rank, and vice versa).
    """
    if player == "B":
        return classify_rank_to_bucket(rank_white).bucket
    if player == "W":
        return classify_rank_to_bucket(rank_black).bucket
    return RankBucket.UNKNOWN
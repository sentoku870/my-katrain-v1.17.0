"""Phase 229: Shared Rank type for both analysis and LLM coach subsystems.

Before Phase 229, two parallel rank-handling stacks existed:

* ``katrain.core.coach.master_db`` had ``_canonical_rank_key`` /
  ``_normalise_rank_str`` / ``_RANK_ORDER`` / ``_RANK_ALIASES`` to feed
  :func:`estimate_mode_from_rank` (LLM Coach tone selection).
* ``katrain.core.analysis.models.skill`` had ``SKILL_PRESETS`` keyed by
  ``"relaxed" / "beginner" / "standard" / "advanced" / "pro"`` (misjudgment
  threshold tuning).

Both stacks expressed the same domain concept ("how strong is the player?")
but in different vocabularies, and the mapping between them lived nowhere
in code.  This module is the single source of truth for *parsing* and
*comparing* rank strings.  Downstream modules import the ``Rank`` dataclass
and the conversion helpers; the legacy ``_canonical_rank_key`` /
``_normalise_rank_str`` functions in ``master_db`` are preserved as thin
re-export shims for backward compatibility.

Canonical numeric encoding (``Rank.kyu_dan``)
---------------------------------------------
* 0=30k, 1=25k, 2=20k, 3=15k, 4=11k
* 5=10k, 6=9k, ..., 14=1k
* 15=1d, 16=2d, ..., 23=9d
* 99=99d (sentinel for "9d or stronger")

``99段`` / ``10段`` are aliased to ``9d`` (Phase 226-C C1) because the
upstream data sources (野狐 / KGS) sometimes write these but we only model
up to 9d in the rank order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

# --- Rank order -----------------------------------------------------------

# Internal numeric encoding of player rank.
# Smaller ``kyu_dan`` = weaker player.
#
#   30k-11k -> 0..4  (BEGINNER band, master doc §0-1)
#   10k-5k  -> 5..10 (INTERMEDIATE band)
#   4k-1d   -> 11..15 (DAN band, includes 1d)
#   2d-5d   -> 16..19 (ADVANCED band)
#   6d-9d+  -> 20..23, 99 (EXPERT band)
#
# Exposed with a single-underscore prefix to flag "internal-ish" but kept
# importable so the legacy ``master_db`` module can reuse the same tables
# for ``estimate_mode_from_rank`` (CoachMode range lookup).
_RANK_ORDER: Final[dict[str, int]] = {
    "30k": 0,
    "25k": 1,
    "20k": 2,
    "15k": 3,
    "11k": 4,
    "10k": 5,
    "9k": 6,
    "8k": 7,
    "7k": 8,
    "6k": 9,
    "5k": 10,
    "4k": 11,
    "3k": 12,
    "2k": 13,
    "1k": 14,
    "1d": 15,
    "2d": 16,
    "3d": 17,
    "4d": 18,
    "5d": 19,
    "6d": 20,
    "7d": 21,
    "8d": 22,
    "9d": 23,
    "99d": 99,
}

# Build a reverse mapping once: kyu_dan int -> canonical ASCII key.
# Spelled out as a literal so the project architecture test
# (``tests/test_architecture.py::TestLayerBoundaries::test_common_no_side_effects``)
# does not flag the dict-comprehension's ``_RANK_ORDER.items()`` call.
_INVERSE_RANK_ORDER: Final[dict[int, str]] = {
    0: "30k",
    1: "25k",
    2: "20k",
    3: "15k",
    4: "11k",
    5: "10k",
    6: "9k",
    7: "8k",
    8: "7k",
    9: "6k",
    10: "5k",
    11: "4k",
    12: "3k",
    13: "2k",
    14: "1k",
    15: "1d",
    16: "2d",
    17: "3d",
    18: "4d",
    19: "5d",
    20: "6d",
    21: "7d",
    22: "8d",
    23: "9d",
    99: "99d",
}

# Kanji / full-width aliases. Each alias points at the same numeric value as
# its ASCII counterpart; we don't add new ranks, just new spellings.  Users
# from 野狐 / KGS often have these notations in their SGF BR/WR properties.
#
# Lookup order matters: Phase 226-C (C1) established that ``_normalise_rank_str``
# collapses ``"10段"`` to ``"10d"`` (which does not exist in ``_RANK_ORDER``),
# so the alias for ``"10段"`` must run *before* normalisation.
_RANK_ALIASES: Final[dict[str, str]] = {
    "30級": "30k",
    "25級": "25k",
    "20級": "20k",
    "15級": "15k",
    "11級": "11k",
    "10級": "10k",
    "9級": "9k",
    "8級": "8k",
    "7級": "7k",
    "6級": "6k",
    "5級": "5k",
    "4級": "4k",
    "3級": "3k",
    "2級": "2k",
    "1級": "1k",
    "初段": "1d",
    "1段": "1d",
    "2段": "2d",
    "3段": "3d",
    "4段": "4d",
    "5段": "5d",
    "6段": "6d",
    "7段": "7d",
    "8段": "8d",
    "9段": "9d",
    "10段": "9d",
    "99段": "99d",
}


# --- Public dataclass -----------------------------------------------------


@dataclass(frozen=True, order=True)
class Rank:
    """Canonical representation of a player's rank.

    The ``kyu_dan`` field is the single source of truth for comparison.
    Use the class methods (:py:meth:`parse`, :py:meth:`from_canonical`) to
    construct instances rather than the constructor directly so future
    encoding changes stay backward compatible.

    Example:
        >>> Rank.parse("5k")
        Rank(kyu_dan=10)
        >>> Rank.parse("4段")
        Rank(kyu_dan=18)
        >>> Rank.parse("5k") < Rank.parse("4段")
        True
        >>> Rank.from_canonical("5d").is_dan
        True
    """

    kyu_dan: int

    # --- Factories ------------------------------------------------------

    @classmethod
    def parse(cls, rank_str: str | None) -> Rank | None:
        """Parse a rank string in any supported notation.

        Accepts ASCII (``"5k"``, ``"7d"``), kanji (``"4段"``, ``"6級"``),
        full-width digits (``"４段"``), synonyms (``"4kyu"``, ``"5dan"``,
        ``"初段"``), and trailing punctuation (``"4d?"``).

        Returns ``None`` for empty / ``None`` / unrecognised input rather
        than raising, so callers can chain with ``or`` cleanly.
        """
        key = canonical_rank_key(rank_str)
        if not key:
            return None
        return cls.from_canonical(key)

    @classmethod
    def from_canonical(cls, canonical: str) -> Rank:
        """Build a ``Rank`` from an already-canonicalised ASCII key.

        Raises ``KeyError`` if the key is not in the rank table.  Prefer
        :py:meth:`parse` for user-supplied input.
        """
        return cls(kyu_dan=_RANK_ORDER[canonical])

    # --- Properties -----------------------------------------------------

    @property
    def is_dan(self) -> bool:
        """``True`` when this rank is at dan level (>= 1d, kyu_dan >= 15)."""
        return self.kyu_dan >= 15

    @property
    def canonical(self) -> str:
        """The ASCII canonical key (e.g. ``"5k"`` / ``"4d"``)."""
        return _INVERSE_RANK_ORDER[self.kyu_dan]

    @property
    def display_ascii(self) -> str:
        """Same as :py:attr:`canonical` — explicit alias for clarity."""
        return self.canonical

    @property
    def display_jp(self) -> str:
        """Kanji / kana notation, e.g. ``"5級"`` / ``"4段"`` / ``"初段"`` for 1d."""
        if self.kyu_dan == 99:
            # 99d is a sentinel for "9d or stronger" — keep its label
            # explicit so users can see "we don't know how strong exactly".
            return "99段"
        if self.is_dan:
            if self.kyu_dan == 15:
                return "初段"
            return f"{self.kyu_dan - 14}段"
        return f"{_kyu_number_from_index(self.kyu_dan)}級"

    # --- Repr for debugging --------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"Rank(kyu_dan={self.kyu_dan})"


def _kyu_number_from_index(kyu_dan: int) -> int:
    """Inverse of the rank table: kyu_dan int -> visible kyu number.

    The rank table has non-contiguous entries (30k, 25k, 20k, 15k, 11k, 10k...)
    so we look up the canonical key and parse its digit prefix rather than
    doing arithmetic on the int.
    """
    canonical = _INVERSE_RANK_ORDER[kyu_dan]
    return int(canonical.rstrip("k"))


# --- Parsing helpers (module-level so master_db can reuse them) ----------


def normalise_rank_str(rank_str: str | None) -> str:
    """Normalise a rank string to its canonical ASCII key form.

    Handles:
    * whitespace + case (``"4D"`` → ``"4d"``)
    * full-width digits (``"４段"`` → ``"4段"``)
    * full-width / ideographic spaces (``"４\u3000段"`` → ``"4段"``)
    * kanji suffix (``"4段"`` → ``"4d"``, ``"5級"`` → ``"5k"``)
    * ASCII suffix synonyms (``"4kyu"`` → ``"4k"``, ``"5dan"`` → ``"5d"``)
    * ``"初段"`` (shodan) as an alias for ``"1段"``
    * trailing decoration (``"4d ?"`` → ``"4d"``)

    Returns ``""`` for ``None`` / empty / unrecognised input.
    """
    if not rank_str:
        return ""
    s = rank_str.strip().lower()
    # Strip both ASCII and full-width / ideographic spaces.
    s = s.replace(" ", "").replace("\u3000", "")
    fullwidth = str.maketrans("０１２３４５６７８９", "0123456789")
    s = s.translate(fullwidth)
    if s == "初段":
        return "1d"
    if s.endswith("段"):
        s = s[:-1] + "d"
    elif s.endswith("級"):
        s = s[:-1] + "k"
    elif s.endswith("kyu"):
        s = s[:-3] + "k"
    elif s.endswith("dan"):
        s = s[:-3] + "d"
    s = s.rstrip("?.!#")
    return s


def canonical_rank_key(rank_str: str | None) -> str:
    """Resolve ``rank_str`` to its canonical ASCII key in :data:`_RANK_ORDER`.

    Lookup order (Phase 226-C C1):

    1. ``_RANK_ALIASES`` against the *trimmed* raw input — this catches
       kanji / full-width notations whose ASCII normalisation would
       otherwise produce a key that does not exist (e.g. ``"10段"`` →
       ``"10d"`` → not present → ``"9d"`` alias).
    2. ``_RANK_ALIASES`` against the *normalised* input — kept for
       symmetry and future aliases that survive normalisation.
    3. ``_RANK_ORDER`` against the normalised input.

    Returns ``""`` when no match.
    """
    if not rank_str:
        return ""
    stripped = rank_str.strip()
    if stripped in _RANK_ALIASES:
        return _RANK_ALIASES[stripped]
    normalised = normalise_rank_str(rank_str)
    if not normalised:
        return ""
    if normalised in _RANK_ALIASES:
        return _RANK_ALIASES[normalised]
    if normalised in _RANK_ORDER:
        return normalised
    return ""


# --- Comparison ----------------------------------------------------------


def cmp_rank(a: Rank, b: Rank) -> int:
    """Compare two ranks.  Returns negative / 0 / positive (like ``cmp``)."""
    if a.kyu_dan < b.kyu_dan:
        return -1
    if a.kyu_dan > b.kyu_dan:
        return 1
    return 0


RankStyle = Literal["ascii", "jp"]


def format_rank(rank: Rank, style: RankStyle = "ascii") -> str:
    """Render a :py:class:`Rank` in the requested notation."""
    if style == "ascii":
        return rank.display_ascii
    if style == "jp":
        return rank.display_jp
    raise ValueError(f"Unknown rank style: {style!r}")


# --- Re-export for legacy master_db compatibility shims ------------------


# Public names that the legacy ``master_db`` module re-imports to share
# the same lookup tables.  Single-underscore-prefixed names above remain
# the canonical definitions; these are public aliases.
RANK_ORDER: Final[dict[str, int]] = _RANK_ORDER
RANK_ALIASES: Final[dict[str, str]] = _RANK_ALIASES


__all__ = [
    "Rank",
    "RankStyle",
    "RANK_ALIASES",
    "RANK_ORDER",
    "canonical_rank_key",
    "cmp_rank",
    "format_rank",
    "normalise_rank_str",
]

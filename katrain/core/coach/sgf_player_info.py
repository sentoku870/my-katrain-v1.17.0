"""Phase 225.6: SGF player-info extraction helpers.

Pure / Kivy-free helpers that read a ``.sgf`` file and return the
``PlayerInfo`` for the black and white stones (name + rank from the
``PB/PW`` and ``BR/WR`` properties).

Why this lives outside :mod:`katrain.core.sgf_parser`:

* ``sgf_parser`` operates on raw SGF text and returns a
  ``KaTrainSGF`` / ``GameNode`` tree. Calling it just to read four
  property strings is overkill and forces Kivy-free code to depend on
  the parser's parser tree (which pulls in :class:`GameNode`).
* LLM Coach (Phase 225) only needs the **names + ranks**. A small
  string-level parser keeps the dependency surface minimal and the
  test suite headless-friendly.

SGF format reference (the parts we parse):

* ``PB`` — Black player name (free text)
* ``PW`` — White player name
* ``BR`` — Black rank (kyu/dan string, e.g. ``5k``, ``4d``)
* ``WR`` — White rank

Many SGF producers (野狐, KGS, GoKGS, ...) emit these properties. When
they're absent we return ``None`` and the caller falls back to manual
input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlayerInfo:
    """Per-color player info extracted from an SGF file.

    Attributes:
        name: The ``PB`` / ``PW`` value (player name), or ``None`` when
            the SGF doesn't carry it.
        rank: The ``BR`` / ``WR`` value (rank string), or ``None`` when
            missing.
    """

    name: str | None = None
    rank: str | None = None


@dataclass(frozen=True)
class SgfPlayerInfo:
    """Black + white player info extracted from a single SGF file.

    Attributes:
        black: Black player info.
        white: White player info.
        sgf_path: The path the data was extracted from (echo for debug).
    """

    black: PlayerInfo
    white: PlayerInfo
    sgf_path: str | None = None


# --- Internal helpers --------------------------------------------------


# A property line looks like: ``PB[醉舞]`` or ``PW[sentoku]`` or
# ``BR[5k]``. The value can contain any printable character except
# the closing bracket. SGF escape sequences (``\\]``, ``\\\\``) are
# rare in player names but we tolerate them.
#
# ``re.MULTILINE`` lets ``^``/``$`` anchor against per-line boundaries
# so we can scan a multi-line root window line-by-line. Without it
# the regex would only match a string that consists of a single
# property (real SGF roots always carry several, separated by ``;``).
_PROP_LINE_RE = re.compile(
    r"^(PB|PW|BR|WR)\[((?:\\.|[^\]\\])*)\]\s*$",
    re.MULTILINE,
)


def _strip_sgf_escapes(value: str) -> str:
    """Undo SGF property escape sequences (``\\]`` → ``]``, etc.)."""
    # Order matters: process the longer escapes first.
    return (
        value.replace("\\\\", "\x00")
        .replace("\\]", "]")
        .replace("\\[", "[")
        .replace("\x00", "\\")
    )


def _parse_properties(text: str) -> dict[str, str]:
    """Parse SGF root properties into ``{name: value}``.

    The root looks like ``(;GM[1]FF[4]PB[醉舞]BR[4d]PW[仙得]WR[4d]SZ[19]...)`` —
    multiple ``KEY[value]`` pairs crammed together on the same line and
    separated by ``;``. We use ``re.finditer`` to scan the whole root
    window for any ``KEY[value]`` match.

    We only care about ``PB/PW/BR/WR`` here so we ignore everything
    else — the loop is intentionally cheap and doesn't try to build a
    full parser.
    """
    result: dict[str, str] = {}
    # Strip '(' so the regex doesn't have to special-case the opening
    # delimiter; '' or '(' alone won't match the property pattern.
    text = text.replace("(", " ").replace(")", " ")
    for m in re.finditer(r"(PB|PW|BR|WR)\[((?:\\.|[^\]\\])*)\]", text):
        key, raw = m.group(1), m.group(2)
        if key not in result:
            result[key] = _strip_sgf_escapes(raw)
    return result


def _find_root_window(text: str) -> str:
    """Return the substring containing the SGF root properties.

    SGF roots look like ``(;GM[1]FF[4]PB[醉舞]BR[4d]PW[仙得]WR[4d]...)``.
    We scan for the FIRST ``(;`` and grab up to the next balanced ``)``
    so we don't pick up properties set on later game-tree nodes.
    """
    start = text.find("(;")
    if start < 0:
        return ""

    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


# --- Public API --------------------------------------------------------


def parse_sgf_player_info(sgf_text: str, *, sgf_path: str | None = None) -> SgfPlayerInfo:
    """Parse a raw SGF text and return black/white player info.

    Args:
        sgf_text: The full SGF file contents.
        sgf_path: Optional path string for the returned ``SgfPlayerInfo``.

    Returns:
        :class:`SgfPlayerInfo` with ``black`` and ``white`` populated.
        Missing fields default to ``PlayerInfo(name=None, rank=None)``.
    """
    root = _find_root_window(sgf_text)
    if not root:
        return SgfPlayerInfo(
            black=PlayerInfo(),
            white=PlayerInfo(),
            sgf_path=sgf_path,
        )
    props = _parse_properties(root)
    return SgfPlayerInfo(
        black=PlayerInfo(name=props.get("PB"), rank=props.get("BR")),
        white=PlayerInfo(name=props.get("PW"), rank=props.get("WR")),
        sgf_path=sgf_path,
    )


def extract_player_info_from_sgf(sgf_path: str | Path) -> SgfPlayerInfo:
    """Read an SGF file from disk and return its black/white player info.

    Args:
        sgf_path: Path to the SGF file. The file must exist; missing or
            unreadable files raise :class:`FileNotFoundError`.

    Returns:
        :class:`SgfPlayerInfo` for the file's root node.
    """
    path = Path(sgf_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_sgf_player_info(text, sgf_path=str(path))


def extract_player_info_for_user(
    sgf_info: SgfPlayerInfo,
    username: str | None,
) -> tuple[str | None, str | None]:
    """Return ``(color, rank)`` for the side whose name matches ``username``.

    Args:
        sgf_info: Already-parsed :class:`SgfPlayerInfo`.
        username: Default username from mykatrain settings. When empty
            or ``None``, no preference is expressed.

    Returns:
        Tuple ``(color, rank)`` where ``color`` is ``"B"`` / ``"W"`` /
        ``None`` and ``rank`` is the matching rank string or ``None``.
        Matching is case-folded and ignores whitespace / punctuation /
        brackets so ``"sentoku"`` matches ``"sentoku870"`` and
        ``"醉舞"`` matches ``"醉舞(野狐)"``.
    """
    if not username:
        return None, None
    norm = _normalize_name(username)
    if not norm:
        return None, None
    for color, info in (("B", sgf_info.black), ("W", sgf_info.white)):
        if not info.name:
            continue
        other = _normalize_name(info.name)
        if not other:
            continue
        if norm in other or other in norm:
            return color, info.rank
    return None, None


def _normalize_name(name: str) -> str:
    """Normalise a player name for fuzzy matching.

    Keeps ASCII alphanumerics AND CJK characters (kanji / hiragana /
    katakana). Strips whitespace, punctuation and brackets. Lowercases
    ASCII so ``Sentoku`` and ``sentoku`` match.
    """
    lowered = name.casefold()
    return re.sub(r"[^0-9a-z぀-ヿ一-鿿]+", "", lowered)


__all__ = [
    "PlayerInfo",
    "SgfPlayerInfo",
    "parse_sgf_player_info",
    "extract_player_info_from_sgf",
    "extract_player_info_for_user",
]
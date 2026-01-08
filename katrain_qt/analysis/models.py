"""
Models for KaTrain Qt Analysis.

Data structures for KataGo integration:
- CandidateMove: Parsed candidate move from KataGo response
- PositionSnapshot: Position data for KataGo queries
- AnalysisResult: Complete analysis result from KataGo
- GTP coordinate conversion utilities

Score Convention:
    All score_lead values are normalized to BLACK's perspective:
    - Positive = Black is ahead
    - Negative = White is ahead

    KataGo returns scores from the to-play perspective, so we flip
    the sign when White is to play.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


# =============================================================================
# GTP Coordinate Conversion
# =============================================================================

# GTP column letters: A-H, J-T (skips 'I')
GTP_COLUMNS = "ABCDEFGHJKLMNOPQRST"


def internal_to_gtp(col: int, row: int, size: int = 19) -> str:
    """
    Convert internal (col, row) to GTP coordinate.

    Internal coordinates: col=0..size-1 (left to right), row=0..size-1 (top to bottom)
    GTP coordinates: "A1" = bottom-left, "T19" = top-right

    Examples (19x19):
        (3, 15) -> "D4"   (row 15 from top = row 4 from bottom)
        (0, 0)  -> "A19"  (top-left)
        (18, 18) -> "T1"  (bottom-right)
        (-1, -1) -> "pass"
    """
    if col < 0 or row < 0:
        return "pass"
    if col >= size or row >= size:
        return "pass"
    if col >= len(GTP_COLUMNS):
        return "pass"
    letter = GTP_COLUMNS[col]
    number = size - row  # row=0 -> size, row=size-1 -> 1
    return f"{letter}{number}"


def gtp_to_internal(gtp: str, size: int = 19) -> Tuple[int, int]:
    """
    Convert GTP coordinate to internal (col, row).

    Examples (19x19):
        "D4"   -> (3, 15)
        "A19"  -> (0, 0)
        "T1"   -> (18, 18)
        "pass" -> (-1, -1)
    """
    gtp = gtp.strip()
    if gtp.lower() == "pass":
        return (-1, -1)
    if len(gtp) < 2:
        return (-1, -1)

    letter = gtp[0].upper()
    if letter not in GTP_COLUMNS:
        return (-1, -1)

    try:
        number = int(gtp[1:])
    except ValueError:
        return (-1, -1)

    col = GTP_COLUMNS.index(letter)
    row = size - number

    if not (0 <= col < size and 0 <= row < size):
        return (-1, -1)

    return (col, row)


def coord_to_display(col: int, row: int, board_size: int = 19) -> str:
    """
    Convert internal (col, row) to display string like 'D4'.

    This is the canonical function for converting Qt coordinates to
    human-readable GTP-style display strings (for status bar, hover, etc.).

    Internal coordinates: col=0..size-1 (left to right), row=0..size-1 (top to bottom)
    Display: "A1" = bottom-left, "T19" = top-right

    Examples (19x19):
        (3, 15) -> "D4"
        (0, 0)  -> "A19"
        (18, 18) -> "T1"
    """
    if col < 0 or col >= board_size or row < 0 or row >= board_size:
        return "??"
    if col >= len(GTP_COLUMNS):
        return "??"
    letter = GTP_COLUMNS[col]
    # row=0 is top in Qt, which is board_size in GTP numbering
    number = board_size - row
    return f"{letter}{number}"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CandidateMove:
    """
    Candidate move data from KataGo analysis.

    Note: score_lead is from KataGo's perspective (to-play player).
    Use AnalysisResult.score_lead_black for normalized Black perspective.
    """
    col: int            # Column (0..size-1, left to right)
    row: int            # Row (0..size-1, top to bottom in Qt coords)
    rank: int           # 1-indexed (1 = best)
    score_lead: float   # Score lead in points (positive = good for next_player)
    visits: int         # Search visits
    winrate: float = 0.5  # Winrate for to-play player (0.0-1.0)
    pv: List[str] = field(default_factory=list)  # Principal variation as GTP coords

    def to_gtp(self, size: int = 19) -> str:
        """Convert to GTP coordinate string."""
        return internal_to_gtp(self.col, self.row, size)

    def pv_string(self, max_moves: int = 10) -> str:
        """Return PV as space-separated string (max moves)."""
        if not self.pv:
            return ""
        return " ".join(self.pv[:max_moves])


@dataclass
class PositionSnapshot:
    """
    Position snapshot for KataGo query.

    Uses initialStones approach: all stones are sent as setup,
    moves[] is empty. This works for both SGF playback and new games.

    Coordinates are in Qt convention:
        col: 0..size-1 (left to right)
        row: 0..size-1 (top to bottom, 0 = top row)
    """
    stones: Dict[Tuple[int, int], str]  # {(col, row): "B"/"W"}
    next_player: str  # "B" or "W"
    board_size: int = 19
    komi: float = 6.5

    def to_initial_stones(self) -> List[List[str]]:
        """
        Convert to KataGo initialStones format.

        Returns: [["B", "D4"], ["W", "Q16"], ...]
        """
        return [
            [color, internal_to_gtp(col, row, self.board_size)]
            for (col, row), color in self.stones.items()
        ]


@dataclass
class AnalysisResult:
    """
    Complete analysis result from KataGo.

    Score Convention:
        score_lead_black: Normalized to BLACK's perspective
            - Positive = Black is ahead
            - Negative = White is ahead

        winrate_black: Black's winrate (0.0-1.0)
            - 0.6 means Black has 60% chance to win

    Ownership:
        ownership: Optional 2D list representing territory ownership.
            - ownership[row][col] where row=0 is TOP (Qt convention)
            - Values: -1.0 (strong White) to +1.0 (strong Black)
            - None if ownership not requested or unavailable

    This normalization ensures the score graph displays consistently
    regardless of whose turn it is.
    """
    query_id: str                           # Query ID for stale response filtering
    candidates: List[CandidateMove]         # Top candidate moves
    score_lead_black: Optional[float]       # Root score lead (Black perspective)
    winrate_black: Optional[float]          # Root winrate (Black perspective, 0.0-1.0)
    next_player: str                        # "B" or "W" - who was to play
    root_visits: int = 0                    # Total visits in root
    ownership: Optional[List[List[float]]] = None  # Ownership grid (row=0 is top)

    def best_move(self) -> Optional[CandidateMove]:
        """Return best candidate move, or None if no candidates."""
        return self.candidates[0] if self.candidates else None

    def score_lead_to_play(self) -> Optional[float]:
        """Return score lead from to-play perspective (original KataGo value)."""
        if self.score_lead_black is None:
            return None
        if self.next_player == "B":
            return self.score_lead_black
        else:
            return -self.score_lead_black

    def winrate_to_play(self) -> Optional[float]:
        """Return winrate from to-play perspective."""
        if self.winrate_black is None:
            return None
        if self.next_player == "B":
            return self.winrate_black
        else:
            return 1.0 - self.winrate_black

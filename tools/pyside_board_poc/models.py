"""
Models for PySide6 Go Board PoC+

- BoardModel: SGF loading, move navigation, stone state
- AnalysisModel: Candidate moves storage
- SGF parsing utilities
- GTP coordinate conversion (for KataGo integration)
- PositionSnapshot: Unified position data for KataGo queries
- CandidateMove: Parsed candidate move from KataGo response
"""

import re
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal


# =============================================================================
# GTP Coordinate Conversion (for KataGo)
# =============================================================================

# GTP column letters: A-H, J-T (skips 'I')
GTP_COLUMNS = "ABCDEFGHJKLMNOPQRST"


def internal_to_gtp(col: int, row: int, size: int = 19) -> str:
    """
    Convert internal (col, row) to GTP coordinate.

    Examples:
        (3, 15) -> "D4"
        (0, 0)  -> "A19"
        (-1, -1) -> "pass"
    """
    if col < 0 or row < 0:
        return "pass"
    if col >= size or row >= size:
        return "pass"
    letter = GTP_COLUMNS[col]
    number = size - row  # row=0 -> size, row=size-1 -> 1
    return f"{letter}{number}"


def gtp_to_internal(gtp: str, size: int = 19) -> tuple[int, int]:
    """
    Convert GTP coordinate to internal (col, row).

    Examples:
        "D4"   -> (3, 15)
        "A19"  -> (0, 0)
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


# =============================================================================
# Data Classes for KataGo Integration
# =============================================================================

@dataclass
class CandidateMove:
    """Candidate move data from KataGo analysis."""
    col: int
    row: int
    rank: int           # 1-indexed (1 = best)
    score_lead: float   # Score lead in points
    visits: int         # Search visits

    def to_gtp(self, size: int = 19) -> str:
        """Convert to GTP coordinate string."""
        return internal_to_gtp(self.col, self.row, size)


@dataclass
class PositionSnapshot:
    """
    Position snapshot for KataGo query.

    Uses initialStones approach: all stones are sent as setup,
    moves[] is empty. This works for both SGF playback and edit mode.
    """
    stones: dict  # {(col, row): "B"/"W"}
    next_player: str  # "B" or "W"
    board_size: int = 19
    komi: float = 6.5

    def to_initial_stones(self) -> list[list[str]]:
        """
        Convert to KataGo initialStones format.

        Returns: [["B", "D4"], ["W", "Q16"], ...]
        """
        return [
            [color, internal_to_gtp(col, row, self.board_size)]
            for (col, row), color in self.stones.items()
        ]


# =============================================================================
# SGF Coordinate Utilities
# =============================================================================

def sgf_to_coord(sgf_coord: str) -> tuple[int, int]:
    """
    Convert SGF coordinate to internal (col, row).
    SGF: "aa" = top-left = (0, 0)
    Internal: col=0..18 (left to right), row=0..18 (top to bottom)
    """
    if len(sgf_coord) != 2:
        return (-1, -1)  # Invalid or pass
    col = ord(sgf_coord[0]) - ord('a')
    row = ord(sgf_coord[1]) - ord('a')
    if not (0 <= col <= 18 and 0 <= row <= 18):
        return (-1, -1)
    return (col, row)


def coord_to_display(col: int, row: int) -> str:
    """
    Convert internal (col, row) to display format "D16".
    Note: Does NOT skip 'I' (simplified for PoC).
    """
    if col < 0 or row < 0:
        return "pass"
    letter = chr(ord('A') + col)
    number = 19 - row  # row=0 -> 19, row=18 -> 1
    return f"{letter}{number}"


# =============================================================================
# SGF Parser (Minimal)
# =============================================================================

def parse_sgf(content: str) -> tuple[list, dict, dict]:
    """
    Parse SGF content (main sequence only, ignore variations).

    Returns:
        moves: [(color, col, row), ...] where pass = (color, -1, -1)
        setup_stones: {(col, row): "B"/"W"}
        metadata: {"SZ": 19, "PB": ..., "PW": ..., ...}
    """
    moves = []
    setup_stones = {}
    metadata = {"SZ": 19}

    # Remove newlines and normalize
    content = content.replace('\n', '').replace('\r', '')

    # Track parentheses depth (ignore variations at depth > 1)
    depth = 0
    i = 0
    in_root_node = True

    while i < len(content):
        char = content[i]

        if char == '(':
            depth += 1
            i += 1
            continue
        elif char == ')':
            depth -= 1
            i += 1
            continue

        # Only process main sequence (depth == 1)
        if depth != 1:
            i += 1
            continue

        # Node separator
        if char == ';':
            in_root_node = (len(moves) == 0 and not setup_stones)
            i += 1
            continue

        # Property parsing
        # Match property name (uppercase letters)
        prop_match = re.match(r'([A-Z]+)', content[i:])
        if not prop_match:
            i += 1
            continue

        prop_name = prop_match.group(1)
        i += len(prop_name)

        # Collect all values for this property
        values = []
        while i < len(content) and content[i] == '[':
            i += 1  # Skip '['
            value_start = i
            # Find closing ']' (handle escaped \])
            while i < len(content):
                if content[i] == '\\' and i + 1 < len(content):
                    i += 2  # Skip escaped char
                elif content[i] == ']':
                    break
                else:
                    i += 1
            values.append(content[value_start:i])
            if i < len(content) and content[i] == ']':
                i += 1  # Skip ']'

        # Process property
        if prop_name == 'SZ' and values:
            try:
                metadata['SZ'] = int(values[0])
            except ValueError:
                pass
        elif prop_name in ('PB', 'PW', 'DT', 'RE', 'KM'):
            if values:
                metadata[prop_name] = values[0]
        elif prop_name == 'B':
            # Black move
            for v in values:
                if v == '' or v.lower() == 'tt':  # Pass
                    moves.append(('B', -1, -1))
                else:
                    col, row = sgf_to_coord(v)
                    moves.append(('B', col, row))
        elif prop_name == 'W':
            # White move
            for v in values:
                if v == '' or v.lower() == 'tt':  # Pass
                    moves.append(('W', -1, -1))
                else:
                    col, row = sgf_to_coord(v)
                    moves.append(('W', col, row))
        elif prop_name == 'AB' and in_root_node:
            # Add Black setup stones
            for v in values:
                col, row = sgf_to_coord(v)
                if col >= 0 and row >= 0:
                    setup_stones[(col, row)] = 'B'
        elif prop_name == 'AW' and in_root_node:
            # Add White setup stones
            for v in values:
                col, row = sgf_to_coord(v)
                if col >= 0 and row >= 0:
                    setup_stones[(col, row)] = 'W'

    return moves, setup_stones, metadata


# =============================================================================
# BoardModel
# =============================================================================

class BoardModel(QObject):
    """
    Model for board state with SGF navigation.

    Attributes:
        sgf_moves: List of (color, col, row) from SGF
        setup_stones: Dict of initial setup stones {(col, row): "B"/"W"}
        current_idx: -1 = initial position (setup only), 0 = after move 1, etc.
    """
    position_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sgf_moves: list[tuple[str, int, int]] = []
        self.setup_stones: dict[tuple[int, int], str] = {}
        self.metadata: dict = {"SZ": 19}
        self.current_idx: int = -1

        # Cached current position
        self._current_stones: dict[tuple[int, int], str] = {}

        # Edit mode additions (not persisted to SGF)
        self._edit_stones: dict[tuple[int, int], str] = {}

    def load_sgf(self, content: str):
        """Load SGF content and reset to initial position."""
        self.sgf_moves, self.setup_stones, self.metadata = parse_sgf(content)
        self.current_idx = -1
        self._edit_stones.clear()
        self._rebuild_stones()
        self.position_changed.emit()

    def clear(self):
        """Clear all state."""
        self.sgf_moves.clear()
        self.setup_stones.clear()
        self.metadata = {"SZ": 19}
        self.current_idx = -1
        self._current_stones.clear()
        self._edit_stones.clear()
        self.position_changed.emit()

    def _rebuild_stones(self):
        """Rebuild _current_stones from setup + moves up to current_idx."""
        self._current_stones = dict(self.setup_stones)
        for i in range(self.current_idx + 1):
            if i < len(self.sgf_moves):
                color, col, row = self.sgf_moves[i]
                if col >= 0 and row >= 0:  # Not a pass
                    self._current_stones[(col, row)] = color

    def stones_at_current(self) -> dict[tuple[int, int], str]:
        """Return current position stones (including edits if any)."""
        result = dict(self._current_stones)
        result.update(self._edit_stones)
        return result

    def next_color(self) -> str:
        """Return the color of the next move to play."""
        # Count actual moves (not passes) or just use move count
        total_moves = self.current_idx + 1 + len(self._edit_stones)
        return "B" if total_moves % 2 == 0 else "W"

    def move_count(self) -> int:
        """Return total number of moves in SGF."""
        return len(self.sgf_moves)

    def current_move_number(self) -> int:
        """Return current move number (1-indexed), 0 if at initial position."""
        return self.current_idx + 1

    # Navigation methods
    def go_first(self):
        """Go to initial position (before any moves)."""
        if self.current_idx != -1:
            self.current_idx = -1
            self._edit_stones.clear()
            self._rebuild_stones()
            self.position_changed.emit()

    def go_prev(self):
        """Go to previous move."""
        if self.current_idx >= 0:
            self.current_idx -= 1
            self._edit_stones.clear()
            self._rebuild_stones()
            self.position_changed.emit()

    def go_next(self):
        """Go to next move."""
        if self.current_idx < len(self.sgf_moves) - 1:
            self.current_idx += 1
            self._edit_stones.clear()
            # Incremental update
            color, col, row = self.sgf_moves[self.current_idx]
            if col >= 0 and row >= 0:
                self._current_stones[(col, row)] = color
            self.position_changed.emit()

    def go_last(self):
        """Go to last move."""
        if self.current_idx != len(self.sgf_moves) - 1:
            self.current_idx = len(self.sgf_moves) - 1
            self._edit_stones.clear()
            self._rebuild_stones()
            self.position_changed.emit()

    def go_to(self, idx: int):
        """Go to specific move index."""
        idx = max(-1, min(idx, len(self.sgf_moves) - 1))
        if idx != self.current_idx:
            self.current_idx = idx
            self._edit_stones.clear()
            self._rebuild_stones()
            self.position_changed.emit()

    # Edit mode methods
    def place_edit_stone(self, col: int, row: int, color: str):
        """Place a stone in edit mode (not persisted to SGF)."""
        key = (col, row)
        if key not in self._current_stones:
            self._edit_stones[key] = color
            self.position_changed.emit()

    def remove_edit_stone(self, col: int, row: int):
        """Remove a stone in edit mode."""
        key = (col, row)
        if key in self._edit_stones:
            del self._edit_stones[key]
            self.position_changed.emit()

    def clear_edits(self):
        """Clear all edit stones."""
        if self._edit_stones:
            self._edit_stones.clear()
            self.position_changed.emit()

    def last_move(self) -> tuple[int, int] | None:
        """Return the last move coordinate, or None if at initial position."""
        if self.current_idx >= 0 and self.current_idx < len(self.sgf_moves):
            color, col, row = self.sgf_moves[self.current_idx]
            if col >= 0 and row >= 0:
                return (col, row)
        return None

    @property
    def board_size(self) -> int:
        """Return board size from metadata."""
        return self.metadata.get("SZ", 19)

    @property
    def komi(self) -> float:
        """Return komi from metadata."""
        try:
            return float(self.metadata.get("KM", 6.5))
        except (ValueError, TypeError):
            return 6.5

    def get_position_snapshot(self) -> PositionSnapshot:
        """
        Get current position as PositionSnapshot for KataGo query.

        Works for both SGF playback and edit mode - all stones are
        sent as initialStones, moves[] is empty.
        """
        return PositionSnapshot(
            stones=dict(self.stones_at_current()),  # Copy
            next_player=self.next_color(),
            board_size=self.board_size,
            komi=self.komi,
        )


# =============================================================================
# AnalysisModel
# =============================================================================

# Type alias for candidate items (supports both KataGo and dummy formats)
CandidateItem = CandidateMove | tuple[int, int, int, float]


class AnalysisModel(QObject):
    """
    Model for analysis candidates.

    Attributes:
        candidates: List of CandidateMove (KataGo) or tuple (dummy)
    """
    candidates_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.candidates: list[CandidateItem] = []

    def set_candidates(self, candidates: list[CandidateItem]):
        """Set new candidates and emit signal."""
        self.candidates = candidates
        self.candidates_changed.emit(candidates)

    def clear(self):
        """Clear candidates."""
        self.candidates = []
        self.candidates_changed.emit([])

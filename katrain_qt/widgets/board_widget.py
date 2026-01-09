"""
GoBoardWidget - Qt widget for rendering a Go board.

Renders the board based on stone positions from GameAdapter.
This widget is purely for display; all game logic is in KaTrain core.

Coordinate System (Qt convention):
  - col: 0..size-1 (left to right)
  - row: 0 at TOP, size-1 at BOTTOM

Features:
  - 19x19, 13x13, 9x9 board support
  - Stone rendering with anti-aliasing
  - Last move marker
  - Hoshi (star points)
  - Hover coordinate display
"""

import math
from typing import Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from katrain_qt.analysis.models import CandidateMove

# Import coord_to_display from canonical location (models.py)
# Note: We also keep a local GTP_COLUMNS for coordinate label drawing
from katrain_qt.analysis.models import coord_to_display  # noqa: F401 (re-exported)


# =============================================================================
# Constants
# =============================================================================

# Hoshi (star points) for different board sizes
HOSHI_POINTS = {
    19: [
        (3, 3), (3, 9), (3, 15),
        (9, 3), (9, 9), (9, 15),
        (15, 3), (15, 9), (15, 15),
    ],
    13: [
        (3, 3), (3, 9),
        (6, 6),
        (9, 3), (9, 9),
    ],
    9: [
        (2, 2), (2, 6),
        (4, 4),
        (6, 2), (6, 6),
    ],
}

# Tunable parameters
MARGIN_RATIO = 0.05          # Margin as ratio of widget size
MARGIN_MIN = 20              # Minimum margin in pixels
STONE_RADIUS_RATIO = 0.45    # Stone radius as ratio of grid spacing
HOSHI_RADIUS_RATIO = 0.12    # Hoshi radius as ratio of grid spacing
HIT_THRESHOLD_RATIO = 0.45   # Click valid if within this ratio of spacing

# Colors
BOARD_COLOR = QColor("#DEB887")      # Burlywood (wood-like)
LINE_COLOR = QColor("#000000")       # Black
BLACK_STONE = QColor("#000000")
WHITE_STONE = QColor("#FFFFFF")
MARKER_BLACK = QColor("#FFFFFF")     # White marker on black stone
MARKER_WHITE = QColor("#000000")     # Black marker on white stone

# Candidate overlay colors (by loss amount - Kivy 6-stage style)
# Thresholds: 0.2 (best), 0.5, 2.0, 5.0, 8.0+ (worst)
EVAL_COLORS_6STAGE = [
    QColor(30, 150, 0),          # Green: Best (loss <= 0.2)
    QColor(171, 230, 46),        # Yellow-green: Small (0.2 < loss <= 0.5)
    QColor(242, 242, 0),         # Yellow: Inaccuracy (0.5 < loss <= 2.0)
    QColor(230, 102, 25),        # Orange: Mistake (2.0 < loss <= 5.0)
    QColor(204, 0, 0),           # Red: Blunder (5.0 < loss <= 8.0)
    QColor(114, 33, 107),        # Purple: Worst (loss > 8.0)
]
EVAL_THRESHOLDS_6STAGE = [0.2, 0.5, 2.0, 5.0, 8.0]  # 6-stage thresholds

# Low visits handling (Kivy style)
LOW_VISITS_THRESHOLD = 25       # Visits below this are "uncertain"
HINT_SCALE = 0.98               # Normal candidate size ratio
UNCERTAIN_HINT_SCALE = 0.7      # Low visits candidate size ratio
HINTS_ALPHA = 0.8               # Normal candidate alpha (0-1)
HINTS_LO_ALPHA = 0.6            # Low visits candidate alpha (0-1)

# Best move border
BEST_MOVE_BORDER_COLOR = QColor(0, 100, 255)  # Blue border for rank=1

# Mistake classification ring colors (for last move stone)
# These match the 6-stage eval colors for consistency
MISTAKE_RING_COLORS = {
    "good": None,                         # No ring for good moves
    "inaccuracy": QColor(242, 242, 0),    # Yellow
    "mistake": QColor(230, 102, 25),      # Orange
    "blunder": QColor(204, 0, 0),         # Red
    "terrible": QColor(114, 33, 107),     # Purple (worst)
}
MISTAKE_RING_WIDTH = 3.0  # Ring line width
CANDIDATE_LABEL_COLOR = QColor("#FFFFFF")
CANDIDATE_LABEL_SHADOW = QColor(0, 0, 0, 180)  # Shadow for better readability

# Ownership overlay colors
OWNERSHIP_BLACK_COLOR = QColor(0, 0, 0)     # Black territory
OWNERSHIP_WHITE_COLOR = QColor(255, 255, 255)  # White territory
OWNERSHIP_ALPHA_MAX = 160  # Maximum alpha for strong ownership
OWNERSHIP_THRESHOLD = 0.05  # Minimum abs(ownership) to display

# GTP column letters (skips 'I') - used for coordinate label drawing
GTP_COLUMNS = "ABCDEFGHJKLMNOPQRST"

# Note: coord_to_display is imported from models.py (canonical location)
# and re-exported for backward compatibility


# =============================================================================
# GoBoardWidget
# =============================================================================

# Hover ghost color
HOVER_ALPHA = 100  # Alpha for hover ghost


class GoBoardWidget(QWidget):
    """
    Widget for rendering a Go board.

    The widget is render-only; it displays stones from callback functions
    and emits signals for user input. All game logic is in KaTrain core.

    Signals:
        hover_changed(int, int, bool): Emitted when hover position changes (col, row, valid)
        intersection_clicked(int, int): Emitted when user clicks a valid intersection (col, row)
    """

    hover_changed = Signal(int, int, bool)
    intersection_clicked = Signal(int, int)  # (col, row) in Qt coords

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(400, 400)

        # Board size (default 19, updated when stones provider changes)
        self._board_size: int = 19

        # Callbacks for getting data (set externally)
        self._stone_provider: Optional[Callable[[], Dict[Tuple[int, int], str]]] = None
        self._last_move_provider: Optional[Callable[[], Optional[Tuple[int, int, str]]]] = None
        self._board_size_provider: Optional[Callable[[], int]] = None
        self._next_player_provider: Optional[Callable[[], str]] = None

        # Hover state
        self._hover_pos: Optional[Tuple[int, int]] = None
        self._hover_valid: bool = False

        # Interactive mode (show hover ghost, accept clicks)
        self._interactive: bool = True

        # Analysis candidates (set externally)
        self._candidates: List["CandidateMove"] = []
        self._show_candidates: bool = False

        # Ownership overlay (set externally)
        self._ownership: Optional[List[List[float]]] = None
        self._show_ownership: bool = False

        # PV preview overlay (for hover on candidates)
        self._pv_preview: List[str] = []  # List of GTP coordinates
        self._pv_starting_color: str = "B"  # Who plays first PV move

        # Last move mistake classification (for colored ring)
        # Values: "good", "inaccuracy", "mistake", "blunder", "terrible", or None
        self._last_move_mistake: Optional[str] = None

    def set_stone_provider(self, provider: Callable[[], Dict[Tuple[int, int], str]]):
        """Set callback to get stone positions: () -> {(col, row): 'B'/'W'}"""
        self._stone_provider = provider

    def set_last_move_provider(self, provider: Callable[[], Optional[Tuple[int, int, str]]]):
        """Set callback to get last move: () -> (col, row, player) or None"""
        self._last_move_provider = provider

    def set_board_size_provider(self, provider: Callable[[], int]):
        """Set callback to get board size: () -> int"""
        self._board_size_provider = provider

    def set_next_player_provider(self, provider: Callable[[], str]):
        """Set callback to get next player: () -> 'B' or 'W'"""
        self._next_player_provider = provider

    def set_interactive(self, interactive: bool):
        """Enable/disable interactive mode (hover ghost + click handling)."""
        self._interactive = interactive
        self.update()

    def set_candidates(self, candidates: List["CandidateMove"]):
        """Set analysis candidates to display as overlay."""
        self._candidates = candidates
        self.update()

    def set_show_candidates(self, show: bool):
        """Enable/disable candidate overlay display."""
        self._show_candidates = show
        self.update()

    def clear_candidates(self):
        """Clear all candidates."""
        self._candidates = []
        self.update()

    def set_ownership(self, ownership: Optional[List[List[float]]]):
        """
        Set ownership grid to display as overlay.

        Args:
            ownership: 2D list [row][col] where row=0 is top (Qt convention).
                       Values: -1.0 (White) to +1.0 (Black), or None to clear.
        """
        self._ownership = ownership
        self.update()

    def set_show_ownership(self, show: bool):
        """Enable/disable ownership overlay display."""
        self._show_ownership = show
        self.update()

    def clear_ownership(self):
        """Clear ownership overlay."""
        self._ownership = None
        self.update()

    def set_pv_preview(self, pv: List[str], starting_color: str):
        """
        Set PV (principal variation) preview to display as semi-transparent stones.

        Args:
            pv: List of GTP coordinates (e.g., ["D4", "Q16", "R5"])
            starting_color: "B" or "W" - who plays the first move in PV
        """
        self._pv_preview = pv
        self._pv_starting_color = starting_color
        self.update()

    def clear_pv_preview(self):
        """Clear PV preview overlay."""
        self._pv_preview = []
        self.update()

    def set_last_move_mistake(self, classification: Optional[str]):
        """
        Set mistake classification for the last move.

        Args:
            classification: One of "good", "inaccuracy", "mistake", "blunder", "terrible", or None
        """
        self._last_move_mistake = classification
        self.update()

    @property
    def board_size(self) -> int:
        """Current board size."""
        if self._board_size_provider:
            return self._board_size_provider()
        return self._board_size

    def _board_rect(self) -> QRectF:
        """Compute the square board area centered in widget, with dynamic margin."""
        w, h = self.width(), self.height()
        margin = max(MARGIN_MIN, min(w, h) * MARGIN_RATIO)
        available = min(w, h) - 2 * margin
        # Center the square board
        x = (w - available) / 2
        y = (h - available) / 2
        return QRectF(x, y, available, available)

    def _grid_spacing(self) -> float:
        """Return spacing between grid lines."""
        board = self._board_rect()
        return board.width() / (self.board_size - 1)

    def _mouse_to_grid(self, pos: QPointF) -> Tuple[int, int, bool]:
        """Convert mouse position to grid coordinates and validity."""
        board = self._board_rect()
        spacing = self._grid_spacing()
        size = self.board_size

        # Relative coordinates
        rx = pos.x() - board.left()
        ry = pos.y() - board.top()

        # Float grid indices
        fi = rx / spacing
        fj = ry / spacing

        # Nearest intersection (clamped to 0..size-1)
        col = max(0, min(size - 1, round(fi)))
        row = max(0, min(size - 1, round(fj)))

        # Distance check
        dist = math.sqrt((fi - col) ** 2 + (fj - row) ** 2) * spacing
        valid = dist <= spacing * HIT_THRESHOLD_RATIO

        return (col, row, valid)

    def _grid_to_pixel(self, col: int, row: int) -> QPointF:
        """Convert grid coordinates to pixel position."""
        board = self._board_rect()
        spacing = self._grid_spacing()
        x = board.left() + col * spacing
        y = board.top() + row * spacing
        return QPointF(x, y)

    # -------------------------------------------------------------------------
    # Painting
    # -------------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        size = self.board_size
        board = self._board_rect()
        spacing = self._grid_spacing()

        # 1. Background
        painter.fillRect(self.rect(), BOARD_COLOR)

        # 2. Grid lines
        pen = QPen(LINE_COLOR, 1)
        painter.setPen(pen)
        for k in range(size):
            # Vertical lines
            x = board.left() + k * spacing
            painter.drawLine(QPointF(x, board.top()), QPointF(x, board.bottom()))
            # Horizontal lines
            y = board.top() + k * spacing
            painter.drawLine(QPointF(board.left(), y), QPointF(board.right(), y))

        # 3. Hoshi (star points)
        hoshi_points = HOSHI_POINTS.get(size, [])
        hoshi_radius = spacing * HOSHI_RADIUS_RATIO
        painter.setBrush(QBrush(LINE_COLOR))
        painter.setPen(Qt.NoPen)
        for hi, hj in hoshi_points:
            center = self._grid_to_pixel(hi, hj)
            painter.drawEllipse(center, hoshi_radius, hoshi_radius)

        # 4. Stones
        stones = self._stone_provider() if self._stone_provider else {}
        stone_radius = spacing * STONE_RADIUS_RATIO

        for (col, row), color in stones.items():
            center = self._grid_to_pixel(col, row)
            stone_color = BLACK_STONE if color == "B" else WHITE_STONE
            painter.setBrush(QBrush(stone_color))
            painter.setPen(QPen(LINE_COLOR, 1))
            painter.drawEllipse(center, stone_radius, stone_radius)

        # 5. Last move marker (square, Kivy style)
        last_move = self._last_move_provider() if self._last_move_provider else None
        if last_move:
            lc, lr, lp = last_move
            center = self._grid_to_pixel(lc, lr)
            marker_color = MARKER_BLACK if lp == "B" else MARKER_WHITE
            # Square marker: size is 80% of stone (Kivy uses stone_size * 0.8 with inner texture)
            marker_size = stone_radius * 0.8
            half_size = marker_size / 2
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(marker_color, 2))
            marker_rect = QRectF(
                center.x() - half_size,
                center.y() - half_size,
                marker_size,
                marker_size,
            )
            painter.drawRect(marker_rect)

            # 5b. Mistake classification ring (around last move stone)
            if self._last_move_mistake and self._last_move_mistake in MISTAKE_RING_COLORS:
                ring_color = MISTAKE_RING_COLORS[self._last_move_mistake]
                if ring_color is not None:
                    # Draw colored ring slightly larger than stone
                    ring_radius = stone_radius * 1.1
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(ring_color, MISTAKE_RING_WIDTH))
                    painter.drawEllipse(center, ring_radius, ring_radius)

        # 6. Hover ghost (semi-transparent next color stone)
        if self._interactive and self._hover_pos and self._hover_valid:
            hc, hr = self._hover_pos
            if (hc, hr) not in stones:
                # Get next player color
                next_player = "B"
                if self._next_player_provider:
                    next_player = self._next_player_provider()

                center = self._grid_to_pixel(hc, hr)
                ghost_color = QColor(BLACK_STONE if next_player == "B" else WHITE_STONE)
                ghost_color.setAlpha(HOVER_ALPHA)
                painter.setBrush(QBrush(ghost_color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(center, stone_radius, stone_radius)

        # 7. Ownership overlay (territory display)
        if self._show_ownership and self._ownership:
            self._draw_ownership(painter, stones, spacing)

        # 8. Candidate overlay (analysis results)
        if self._show_candidates and self._candidates:
            self._draw_candidates(painter, stones, stone_radius, spacing)

        # 9. PV preview overlay (hover on candidate)
        if self._pv_preview:
            self._draw_pv_preview(painter, stones, stone_radius)

        # 10. Coordinate labels (optional, around edges)
        self._draw_coordinates(painter, board, spacing, size)

        painter.end()

    def _draw_coordinates(self, painter: QPainter, board: QRectF, spacing: float, size: int):
        """Draw coordinate labels around the board edges."""
        font = painter.font()
        font.setPointSizeF(max(8, spacing * 0.25))
        painter.setFont(font)
        painter.setPen(QPen(LINE_COLOR))

        margin = 15  # Distance from board edge

        for i in range(size):
            # Column letters (top and bottom)
            letter = GTP_COLUMNS[i] if i < len(GTP_COLUMNS) else "?"
            x = board.left() + i * spacing

            # Top
            painter.drawText(
                QRectF(x - spacing/2, board.top() - margin - 12, spacing, 12),
                Qt.AlignCenter,
                letter
            )
            # Bottom
            painter.drawText(
                QRectF(x - spacing/2, board.bottom() + margin, spacing, 12),
                Qt.AlignCenter,
                letter
            )

            # Row numbers (left and right)
            # row=0 is top, so number = size - row
            number = str(size - i)
            y = board.top() + i * spacing

            # Left
            painter.drawText(
                QRectF(board.left() - margin - 20, y - 6, 20, 12),
                Qt.AlignRight | Qt.AlignVCenter,
                number
            )
            # Right
            painter.drawText(
                QRectF(board.right() + margin, y - 6, 20, 12),
                Qt.AlignLeft | Qt.AlignVCenter,
                number
            )

    def _draw_ownership(
        self,
        painter: QPainter,
        stones: Dict[Tuple[int, int], str],
        spacing: float,
    ):
        """
        Draw ownership overlay as semi-transparent squares.

        Black ownership (positive) = black squares
        White ownership (negative) = white squares
        Alpha varies with ownership strength.
        """
        size = self.board_size
        ownership = self._ownership

        if not ownership or len(ownership) != size:
            return

        # Square size (slightly smaller than grid cell)
        square_size = spacing * 0.7

        painter.setPen(Qt.NoPen)

        for row in range(size):
            if row >= len(ownership) or len(ownership[row]) != size:
                continue
            for col in range(size):
                # Skip intersections with stones
                if (col, row) in stones:
                    continue

                value = ownership[row][col]
                abs_value = abs(value)

                # Skip weak ownership
                if abs_value < OWNERSHIP_THRESHOLD:
                    continue

                # Determine color and alpha
                if value > 0:
                    # Black territory
                    color = QColor(OWNERSHIP_BLACK_COLOR)
                else:
                    # White territory
                    color = QColor(OWNERSHIP_WHITE_COLOR)

                # Alpha proportional to ownership strength
                alpha = int(abs_value * OWNERSHIP_ALPHA_MAX)
                alpha = min(alpha, OWNERSHIP_ALPHA_MAX)
                color.setAlpha(alpha)

                # Draw filled square centered on intersection
                center = self._grid_to_pixel(col, row)
                half = square_size / 2
                rect = QRectF(center.x() - half, center.y() - half, square_size, square_size)
                painter.fillRect(rect, color)

    def _draw_candidates(
        self,
        painter: QPainter,
        stones: Dict[Tuple[int, int], str],
        stone_radius: float,
        spacing: float,
    ):
        """
        Draw candidate move overlay with Kivy-style 6-stage colors.

        Features:
        - 6-stage color gradation (green → yellow-green → yellow → orange → red → purple)
        - Low visits handling (smaller size, lower alpha, no text)
        - Best move (rank=1) blue border
        - 2-line text display (score + visits) for normal candidates
        """
        # Find best score for loss calculation
        best_score = None
        if self._candidates:
            for c in self._candidates:
                if c.rank == 1:
                    best_score = c.score_lead
                    break
            if best_score is None:
                best_score = max(c.score_lead for c in self._candidates)

        for cand in self._candidates:
            # Skip if there's already a stone at this position
            if (cand.col, cand.row) in stones:
                continue

            center = self._grid_to_pixel(cand.col, cand.row)

            # Calculate loss
            loss = 0.0 if best_score is None else best_score - cand.score_lead
            loss = max(0.0, loss)  # Ensure non-negative

            # Determine if low visits (uncertain)
            is_low_visits = cand.visits < LOW_VISITS_THRESHOLD

            # Determine size and alpha based on visits
            if is_low_visits:
                scale = UNCERTAIN_HINT_SCALE
                alpha = HINTS_LO_ALPHA
            else:
                scale = HINT_SCALE
                alpha = HINTS_ALPHA

            # Determine color index based on 6-stage thresholds
            color_idx = 0
            for i, threshold in enumerate(EVAL_THRESHOLDS_6STAGE):
                if loss > threshold:
                    color_idx = i + 1
            color_idx = min(color_idx, len(EVAL_COLORS_6STAGE) - 1)

            # Get base color and apply alpha
            base_color = EVAL_COLORS_6STAGE[color_idx]
            fill_color = QColor(base_color)
            fill_color.setAlphaF(alpha)

            # Calculate candidate circle radius
            cand_radius = stone_radius * 0.85 * scale

            # Draw filled circle
            painter.setBrush(QBrush(fill_color))
            painter.setPen(QPen(QColor(0, 0, 0, int(150 * alpha)), 1))
            painter.drawEllipse(center, cand_radius, cand_radius)

            # Best move (rank=1): draw blue border
            if cand.rank == 1:
                border_pen = QPen(BEST_MOVE_BORDER_COLOR, 2.5)
                painter.setPen(border_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(center, cand_radius + 1, cand_radius + 1)

            # Skip text for low visits candidates
            if is_low_visits:
                continue

            # 2-line text: score (top) and visits (bottom)
            # Line 1: Score lead (with sign)
            score_text = f"{cand.score_lead:+.1f}"
            # Line 2: Visits (abbreviated if large)
            if cand.visits >= 1000:
                visits_text = f"{cand.visits // 1000}k"
            else:
                visits_text = str(cand.visits)

            # Font setup - smaller for 2-line display
            font = painter.font()
            line_height = spacing * 0.22
            font.setPointSizeF(max(6, line_height))
            font.setBold(True)
            painter.setFont(font)

            # Draw score (top line)
            score_rect = QRectF(
                center.x() - cand_radius,
                center.y() - cand_radius * 0.7,
                cand_radius * 2,
                cand_radius * 0.7,
            )
            # Shadow
            painter.setPen(QPen(CANDIDATE_LABEL_SHADOW))
            painter.drawText(score_rect.translated(1, 1), Qt.AlignCenter, score_text)
            # Main text
            painter.setPen(QPen(CANDIDATE_LABEL_COLOR))
            painter.drawText(score_rect, Qt.AlignCenter, score_text)

            # Draw visits (bottom line)
            visits_rect = QRectF(
                center.x() - cand_radius,
                center.y(),
                cand_radius * 2,
                cand_radius * 0.7,
            )
            # Shadow
            painter.setPen(QPen(CANDIDATE_LABEL_SHADOW))
            painter.drawText(visits_rect.translated(1, 1), Qt.AlignCenter, visits_text)
            # Main text
            painter.setPen(QPen(CANDIDATE_LABEL_COLOR))
            painter.drawText(visits_rect, Qt.AlignCenter, visits_text)

    def _draw_pv_preview(
        self,
        painter: QPainter,
        stones: Dict[Tuple[int, int], str],
        stone_radius: float,
    ):
        """
        Draw PV (principal variation) preview as semi-transparent stones.

        Shows the sequence of moves in the PV, alternating colors starting
        from starting_color.
        """
        from katrain_qt.analysis.models import gtp_to_internal

        PV_ALPHA = 150  # Semi-transparent
        board_size = self.board_size

        # Track positions used in PV to avoid overlap
        pv_positions: Dict[Tuple[int, int], int] = {}  # (col, row) -> move_number

        current_color = self._pv_starting_color

        for i, gtp_move in enumerate(self._pv_preview):
            col, row = gtp_to_internal(gtp_move, board_size)
            if col < 0 or row < 0:
                # Skip pass moves
                continue

            # Skip if real stone exists at this position
            if (col, row) in stones:
                # Still alternate color for next move
                current_color = "W" if current_color == "B" else "B"
                continue

            # Check if we've already placed a PV stone here (re-capture scenario)
            if (col, row) in pv_positions:
                # Replace with later move
                pass

            pv_positions[(col, row)] = i + 1  # 1-indexed move number

            center = self._grid_to_pixel(col, row)

            # Semi-transparent stone
            stone_base = BLACK_STONE if current_color == "B" else WHITE_STONE
            stone_color = QColor(stone_base)
            stone_color.setAlpha(PV_ALPHA)
            painter.setBrush(QBrush(stone_color))
            painter.setPen(QPen(QColor(100, 100, 100, PV_ALPHA), 1))
            painter.drawEllipse(center, stone_radius, stone_radius)

            # Alternate color for next move
            current_color = "W" if current_color == "B" else "B"

    # -------------------------------------------------------------------------
    # Mouse Events
    # -------------------------------------------------------------------------

    def mouseMoveEvent(self, event):
        pos = event.position()
        col, row, valid = self._mouse_to_grid(pos)
        self._hover_pos = (col, row)
        self._hover_valid = valid
        self.hover_changed.emit(col, row, valid)
        # Repaint to show/hide hover ghost
        if self._interactive:
            self.update()

    def mousePressEvent(self, event):
        """Handle mouse clicks to play moves."""
        if not self._interactive:
            return

        if event.button() == Qt.LeftButton:
            pos = event.position()
            col, row, valid = self._mouse_to_grid(pos)
            if valid:
                # Emit click signal with Qt coordinates
                self.intersection_clicked.emit(col, row)

    def leaveEvent(self, event):
        self._hover_pos = None
        self._hover_valid = False
        # Emit invalid hover
        self.hover_changed.emit(-1, -1, False)
        # Repaint to hide hover ghost
        if self._interactive:
            self.update()

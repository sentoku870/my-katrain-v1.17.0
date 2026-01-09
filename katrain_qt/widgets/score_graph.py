"""
ScoreGraphWidget - Qt widget for displaying score lead over move number.

Features:
- Line graph of score lead vs move number using QPainter
- Handles missing values (None) as gaps in the line
- Highlights current move with vertical line + marker
- Click to navigate: emits move_selected(int) signal
- Zero line to show even position
"""

from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import QWidget


# =============================================================================
# Constants
# =============================================================================

# Colors
BACKGROUND_COLOR = QColor("#F5F5F5")
GRID_COLOR = QColor("#E0E0E0")
ZERO_LINE_COLOR = QColor("#AAAAAA")
LINE_COLOR = QColor("#2196F3")  # Blue
MARKER_COLOR = QColor("#FF5722")  # Orange-red for current move
POSITIVE_FILL = QColor(33, 150, 243, 50)  # Light blue, semi-transparent
NEGATIVE_FILL = QColor(244, 67, 54, 50)  # Light red, semi-transparent
# Important position marker colors (6-stage, matching board_widget)
MARKER_COLORS_BY_LOSS = {
    "good": None,                           # No marker
    "inaccuracy": QColor(242, 242, 0, 180), # Yellow
    "mistake": QColor(230, 102, 25, 180),   # Orange
    "blunder": QColor(204, 0, 0, 180),      # Red
    "terrible": QColor(114, 33, 107, 180),  # Purple
}
# Legacy constant for backward compatibility
BLUNDER_LINE_COLOR = QColor(255, 140, 0, 180)  # Orange for blunder markers

# Layout
PADDING_LEFT = 40  # Space for Y-axis labels
PADDING_RIGHT = 15
PADDING_TOP = 15
PADDING_BOTTOM = 25  # Space for X-axis labels

# Graph styling
LINE_WIDTH = 2
MARKER_RADIUS = 5
CURRENT_MOVE_LINE_WIDTH = 2


# =============================================================================
# ScoreGraphWidget
# =============================================================================

class ScoreGraphWidget(QWidget):
    """
    Widget for displaying score lead over move number.

    Signals:
        move_selected(int): Emitted when user clicks on the graph (move number)
    """

    move_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 100)
        self.setMouseTracking(True)

        # Data
        self._series: List[Optional[float]] = []
        self._current_move: int = 0

        # Blunder markers (move numbers where large mistakes occurred)
        self._blunder_moves: List[int] = []

        # Important position markers with classification
        # Dict: move_no -> classification ("inaccuracy", "mistake", "blunder", "terrible")
        self._important_positions: dict = {}

        # Y-axis range (auto-computed or fixed)
        self._y_min: float = -10.0
        self._y_max: float = 10.0
        self._auto_range: bool = True

        # Hover state
        self._hover_move: Optional[int] = None

    def set_series(self, series: List[Optional[float]]):
        """
        Set the score series data.

        Args:
            series: List where index = move number, value = score lead (or None for missing)
        """
        self._series = series
        if self._auto_range:
            self._compute_y_range()
        self.update()

    def set_current_move(self, move_no: int):
        """Set the current move number to highlight."""
        self._current_move = move_no
        self.update()

    def set_blunder_moves(self, moves: List[int]):
        """
        Set the list of move numbers that are blunders (large mistakes).

        Args:
            moves: List of move numbers where blunders occurred
        """
        self._blunder_moves = moves
        self.update()

    def set_important_positions(self, positions: dict):
        """
        Set important positions with their classifications.

        Args:
            positions: Dict mapping move_no -> classification
                       Classification is one of: "inaccuracy", "mistake", "blunder", "terrible"
        """
        self._important_positions = positions
        self.update()

    def set_y_range(self, y_min: float, y_max: float):
        """Set fixed Y-axis range."""
        self._y_min = y_min
        self._y_max = y_max
        self._auto_range = False
        self.update()

    def set_auto_range(self, auto: bool = True):
        """Enable/disable automatic Y-axis range computation."""
        self._auto_range = auto
        if auto:
            self._compute_y_range()
        self.update()

    def clear(self):
        """Clear all data."""
        self._series = []
        self._current_move = 0
        self._blunder_moves = []
        self._important_positions = {}
        self._y_min = -10.0
        self._y_max = 10.0
        self.update()

    def set_theme_colors(self, background: str, line: str, zero_line: str):
        """Set theme colors for the graph."""
        global BACKGROUND_COLOR, LINE_COLOR, ZERO_LINE_COLOR
        BACKGROUND_COLOR = QColor(background)
        LINE_COLOR = QColor(line)
        ZERO_LINE_COLOR = QColor(zero_line)
        self.update()

    def _compute_y_range(self):
        """Compute Y-axis range from data."""
        values = [v for v in self._series if v is not None]
        if not values:
            self._y_min = -10.0
            self._y_max = 10.0
            return

        min_val = min(values)
        max_val = max(values)

        # Add some padding and ensure zero is visible
        padding = max(abs(min_val), abs(max_val)) * 0.1 + 2.0
        self._y_min = min(min_val - padding, -5.0)
        self._y_max = max(max_val + padding, 5.0)

        # Ensure symmetric range around zero for better visualization
        abs_max = max(abs(self._y_min), abs(self._y_max))
        self._y_min = -abs_max
        self._y_max = abs_max

    def _graph_rect(self) -> QRectF:
        """Return the rectangle for the graph area (excluding padding)."""
        return QRectF(
            PADDING_LEFT,
            PADDING_TOP,
            self.width() - PADDING_LEFT - PADDING_RIGHT,
            self.height() - PADDING_TOP - PADDING_BOTTOM,
        )

    def _move_to_x(self, move_no: int) -> float:
        """Convert move number to X coordinate."""
        rect = self._graph_rect()
        n_moves = max(len(self._series) - 1, 1)
        return rect.left() + (move_no / n_moves) * rect.width()

    def _score_to_y(self, score: float) -> float:
        """Convert score to Y coordinate (inverted: positive at top)."""
        rect = self._graph_rect()
        y_range = self._y_max - self._y_min
        if y_range == 0:
            return rect.center().y()
        # Map score to 0..1, then invert for screen coordinates
        normalized = (score - self._y_min) / y_range
        return rect.bottom() - normalized * rect.height()

    def _x_to_move(self, x: float) -> int:
        """Convert X coordinate to move number."""
        rect = self._graph_rect()
        if rect.width() == 0:
            return 0
        n_moves = max(len(self._series) - 1, 1)
        relative = (x - rect.left()) / rect.width()
        move = int(round(relative * n_moves))
        return max(0, min(move, len(self._series) - 1))

    # -------------------------------------------------------------------------
    # Painting
    # -------------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self._graph_rect()

        # 1. Background
        painter.fillRect(self.rect(), BACKGROUND_COLOR)

        # 2. Grid lines (horizontal)
        self._draw_grid(painter, rect)

        # 3. Zero line
        self._draw_zero_line(painter, rect)

        # 4. Blunder markers (before score line so they're behind)
        self._draw_blunder_markers(painter, rect)

        # 5. Score line and fill
        if len(self._series) > 0:
            self._draw_score_line(painter, rect)

        # 6. Current move indicator
        if 0 <= self._current_move < len(self._series):
            self._draw_current_move(painter, rect)

        # 7. Hover indicator
        if self._hover_move is not None and 0 <= self._hover_move < len(self._series):
            self._draw_hover(painter, rect)

        # 8. Axis labels
        self._draw_labels(painter, rect)

        painter.end()

    def _draw_grid(self, painter: QPainter, rect: QRectF):
        """Draw horizontal grid lines."""
        pen = QPen(GRID_COLOR, 1, Qt.DotLine)
        painter.setPen(pen)

        # Draw a few horizontal lines
        n_lines = 5
        for i in range(n_lines + 1):
            y = rect.top() + (i / n_lines) * rect.height()
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

    def _draw_zero_line(self, painter: QPainter, rect: QRectF):
        """Draw the zero (even) line."""
        if self._y_min <= 0 <= self._y_max:
            y = self._score_to_y(0)
            pen = QPen(ZERO_LINE_COLOR, 1, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

    def _draw_blunder_markers(self, painter: QPainter, rect: QRectF):
        """Draw vertical lines at important positions with classification-based colors."""
        if len(self._series) < 2:
            return

        # First, draw from important_positions (new API with classification)
        for move_no, classification in self._important_positions.items():
            if 0 <= move_no < len(self._series):
                color = MARKER_COLORS_BY_LOSS.get(classification)
                if color is not None:
                    pen = QPen(color, 2, Qt.SolidLine)
                    painter.setPen(pen)
                    x = self._move_to_x(move_no)
                    painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        # Legacy: draw from blunder_moves (backward compatibility)
        # Only draw if not already in important_positions
        if self._blunder_moves:
            pen = QPen(BLUNDER_LINE_COLOR, 2, Qt.SolidLine)
            painter.setPen(pen)
            for move_no in self._blunder_moves:
                if 0 <= move_no < len(self._series) and move_no not in self._important_positions:
                    x = self._move_to_x(move_no)
                    painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

    def _draw_score_line(self, painter: QPainter, rect: QRectF):
        """Draw the score line with fill."""
        if len(self._series) < 1:
            return

        zero_y = self._score_to_y(0)

        # Build path for the line
        line_path = QPainterPath()
        fill_path_positive = QPainterPath()
        fill_path_negative = QPainterPath()

        first_point = True
        prev_point: Optional[QPointF] = None

        for move_no, score in enumerate(self._series):
            if score is None:
                # Gap in data - start new segment
                first_point = True
                prev_point = None
                continue

            x = self._move_to_x(move_no)
            y = self._score_to_y(score)
            point = QPointF(x, y)

            if first_point:
                line_path.moveTo(point)
                first_point = False
            else:
                line_path.lineTo(point)

            prev_point = point

        # Draw line
        pen = QPen(LINE_COLOR, LINE_WIDTH)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(line_path)

    def _draw_current_move(self, painter: QPainter, rect: QRectF):
        """Draw current move indicator (vertical line + marker)."""
        x = self._move_to_x(self._current_move)

        # Vertical line
        pen = QPen(MARKER_COLOR, CURRENT_MOVE_LINE_WIDTH, Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        # Marker on the score point if we have data
        score = self._series[self._current_move] if self._current_move < len(self._series) else None
        if score is not None:
            y = self._score_to_y(score)
            painter.setPen(QPen(MARKER_COLOR, 2))
            painter.setBrush(QBrush(MARKER_COLOR))
            painter.drawEllipse(QPointF(x, y), MARKER_RADIUS, MARKER_RADIUS)

    def _draw_hover(self, painter: QPainter, rect: QRectF):
        """Draw hover indicator."""
        if self._hover_move is None:
            return

        x = self._move_to_x(self._hover_move)
        score = self._series[self._hover_move] if self._hover_move < len(self._series) else None

        # Light vertical line
        pen = QPen(QColor(100, 100, 100, 100), 1)
        painter.setPen(pen)
        painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        # Small marker if we have a value
        if score is not None:
            y = self._score_to_y(score)
            painter.setPen(QPen(LINE_COLOR, 1))
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            painter.drawEllipse(QPointF(x, y), 4, 4)

    def _draw_labels(self, painter: QPainter, rect: QRectF):
        """Draw axis labels."""
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#666666")))

        # Y-axis labels (score)
        labels_y = [self._y_max, 0, self._y_min]
        for score in labels_y:
            if self._y_min <= score <= self._y_max:
                y = self._score_to_y(score)
                text = f"{score:+.0f}" if score != 0 else "0"
                text_rect = QRectF(0, y - 8, PADDING_LEFT - 5, 16)
                painter.drawText(text_rect, Qt.AlignRight | Qt.AlignVCenter, text)

        # X-axis labels (move number)
        n_moves = len(self._series) - 1 if len(self._series) > 1 else 0
        if n_moves > 0:
            # Show start, end, and maybe middle
            label_moves = [0]
            if n_moves > 10:
                label_moves.append(n_moves // 2)
            label_moves.append(n_moves)

            for move in label_moves:
                x = self._move_to_x(move)
                text_rect = QRectF(x - 20, rect.bottom() + 3, 40, 20)
                painter.drawText(text_rect, Qt.AlignCenter, str(move))

        # Title / empty state
        if len(self._series) == 0:
            painter.setPen(QPen(QColor("#999999")))
            painter.drawText(rect, Qt.AlignCenter, "No score data")

    # -------------------------------------------------------------------------
    # Mouse Events
    # -------------------------------------------------------------------------

    def mouseMoveEvent(self, event):
        """Track mouse for hover effect."""
        rect = self._graph_rect()
        pos = event.position()

        if rect.contains(pos):
            self._hover_move = self._x_to_move(pos.x())
        else:
            self._hover_move = None

        self.update()

    def mousePressEvent(self, event):
        """Handle click to select move."""
        if event.button() == Qt.LeftButton:
            rect = self._graph_rect()
            pos = event.position()

            if rect.contains(pos) and len(self._series) > 0:
                move_no = self._x_to_move(pos.x())
                self.move_selected.emit(move_no)

    def leaveEvent(self, event):
        """Clear hover when mouse leaves."""
        self._hover_move = None
        self.update()

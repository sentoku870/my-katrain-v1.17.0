"""
PySide6 Go Board PoC - Minimal 19x19 Go board UI proof-of-concept.

This is a standalone PoC to validate feasibility of moving KaTrain's board UI from Kivy to Qt.
"""

import math
import sys
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QStatusBar

# =============================================================================
# Constants
# =============================================================================

BOARD_SIZE = 19
HOSHI_POINTS = [
    (3, 3), (3, 9), (3, 15),
    (9, 3), (9, 9), (9, 15),
    (15, 3), (15, 9), (15, 15),
]

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
HOVER_ALPHA = 100                    # Alpha for hover ghost


# =============================================================================
# GoBoardWidget
# =============================================================================

class GoBoardWidget(QWidget):
    """19x19 Go board widget with stone placement and removal."""

    # Signal emitted when hover position changes: (i, j, valid)
    hover_changed = Signal(int, int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(400, 400)

        # State
        self.stones: dict[tuple[int, int], str] = {}  # (i, j) -> "B" or "W"
        self.move_history: list[tuple[int, int, str]] = []  # [(i, j, color), ...]
        self.hover_pos: tuple[int, int] | None = None
        self.hover_valid: bool = False

    def _next_color(self) -> str:
        """Return next color based on move history length."""
        return "B" if len(self.move_history) % 2 == 0 else "W"

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
        return board.width() / (BOARD_SIZE - 1)

    def _mouse_to_grid(self, pos: QPointF) -> tuple[int, int, bool]:
        """Convert mouse position to grid coordinates and validity."""
        board = self._board_rect()
        spacing = self._grid_spacing()

        # Relative coordinates
        rx = pos.x() - board.left()
        ry = pos.y() - board.top()

        # Float grid indices
        fi = rx / spacing
        fj = ry / spacing

        # Nearest intersection (clamped to 0..18)
        i = max(0, min(18, round(fi)))
        j = max(0, min(18, round(fj)))

        # Distance check
        dist = math.sqrt((fi - i) ** 2 + (fj - j) ** 2) * spacing
        valid = dist <= spacing * HIT_THRESHOLD_RATIO

        return (i, j, valid)

    def _grid_to_pixel(self, i: int, j: int) -> QPointF:
        """Convert grid coordinates to pixel position."""
        board = self._board_rect()
        spacing = self._grid_spacing()
        x = board.left() + i * spacing
        y = board.top() + j * spacing
        return QPointF(x, y)

    # -------------------------------------------------------------------------
    # Painting
    # -------------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        board = self._board_rect()
        spacing = self._grid_spacing()

        # 1. Background
        painter.fillRect(self.rect(), BOARD_COLOR)

        # 2. Grid lines
        pen = QPen(LINE_COLOR, 1)
        painter.setPen(pen)
        for k in range(BOARD_SIZE):
            # Vertical lines
            x = board.left() + k * spacing
            painter.drawLine(QPointF(x, board.top()), QPointF(x, board.bottom()))
            # Horizontal lines
            y = board.top() + k * spacing
            painter.drawLine(QPointF(board.left(), y), QPointF(board.right(), y))

        # 3. Hoshi (star points)
        hoshi_radius = spacing * HOSHI_RADIUS_RATIO
        painter.setBrush(QBrush(LINE_COLOR))
        painter.setPen(Qt.NoPen)
        for hi, hj in HOSHI_POINTS:
            center = self._grid_to_pixel(hi, hj)
            painter.drawEllipse(center, hoshi_radius, hoshi_radius)

        # 4. Stones
        stone_radius = spacing * STONE_RADIUS_RATIO
        for (si, sj), color in self.stones.items():
            center = self._grid_to_pixel(si, sj)
            stone_color = BLACK_STONE if color == "B" else WHITE_STONE
            painter.setBrush(QBrush(stone_color))
            painter.setPen(QPen(LINE_COLOR, 1))
            painter.drawEllipse(center, stone_radius, stone_radius)

        # 5. Last move marker
        if self.move_history:
            li, lj, lc = self.move_history[-1]
            center = self._grid_to_pixel(li, lj)
            marker_color = MARKER_BLACK if lc == "B" else MARKER_WHITE
            marker_radius = stone_radius * 0.4
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(marker_color, 2))
            painter.drawEllipse(center, marker_radius, marker_radius)

        # 6. Hover ghost (semi-transparent next color)
        if self.hover_pos and self.hover_valid:
            hi, hj = self.hover_pos
            if (hi, hj) not in self.stones:
                center = self._grid_to_pixel(hi, hj)
                next_color = self._next_color()
                ghost_color = QColor(BLACK_STONE if next_color == "B" else WHITE_STONE)
                ghost_color.setAlpha(HOVER_ALPHA)
                painter.setBrush(QBrush(ghost_color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(center, stone_radius, stone_radius)

        painter.end()

    # -------------------------------------------------------------------------
    # Mouse Events
    # -------------------------------------------------------------------------

    def mouseMoveEvent(self, event):
        pos = event.position()
        i, j, valid = self._mouse_to_grid(pos)
        self.hover_pos = (i, j)
        self.hover_valid = valid
        self.hover_changed.emit(i, j, valid)
        self.update()

    def mousePressEvent(self, event):
        pos = event.position()
        i, j, valid = self._mouse_to_grid(pos)

        if event.button() == Qt.LeftButton:
            # Place stone if valid and not occupied
            if valid and (i, j) not in self.stones:
                color = self._next_color()
                self.stones[(i, j)] = color
                self.move_history.append((i, j, color))
                self.update()

        elif event.button() == Qt.RightButton:
            # Remove stone if valid and occupied
            if valid and (i, j) in self.stones:
                removed_color = self.stones.pop((i, j))
                # Remove from move_history (scan from end for matching entry)
                for idx in range(len(self.move_history) - 1, -1, -1):
                    hi, hj, hc = self.move_history[idx]
                    if hi == i and hj == j and hc == removed_color:
                        self.move_history.pop(idx)
                        break
                self.update()


# =============================================================================
# MainWindow
# =============================================================================

class MainWindow(QMainWindow):
    """Main window with Go board and status bar."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Go Board PoC")
        self.setMinimumSize(500, 550)

        # Board widget
        self.board = GoBoardWidget()
        self.setCentralWidget(self.board)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Hover over the board to see coordinates")

        # Connect signal
        self.board.hover_changed.connect(self.update_status)

    def update_status(self, i: int, j: int, valid: bool):
        """Update status bar with hover info."""
        next_color = self.board._next_color()
        color_name = "Black" if next_color == "B" else "White"
        validity = "valid" if valid else "invalid"
        occupied = "(occupied)" if (i, j) in self.board.stones else ""
        self.status_bar.showMessage(
            f"Position: ({i}, {j}) - Click {validity} - Next: {color_name} {occupied}"
        )


# =============================================================================
# Main
# =============================================================================

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(700, 750)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

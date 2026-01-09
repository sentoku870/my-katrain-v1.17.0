"""
StatsPanel - Qt widget for displaying game statistics.

Shows current position statistics:
- Winrate (percentage)
- Score lead (points)
- Points lost (cumulative for current player)

Layout mirrors Kivy version's StatsBox:
┌─────────────────────────────────┐
│ Winrate: 67.3%     Score: +4.5  │
│ Loss: Black 12.3 / White 8.7    │
└─────────────────────────────────┘
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QFrame,
)
from PySide6.QtGui import QFont


# Colors for stats display (Kivy-style)
WINRATE_COLOR = "#CC3333"      # Red-ish for winrate
SCORE_COLOR = "#3366CC"        # Blue-ish for score
LOSS_BLACK_COLOR = "#333333"   # Dark for black loss
LOSS_WHITE_COLOR = "#666666"   # Lighter for white loss


class StatsPanel(QWidget):
    """
    Panel displaying current position statistics.

    Shows winrate, score, and cumulative loss for both players.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.clear()

    def _setup_ui(self):
        """Setup the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # Top row: Winrate and Score
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        # Winrate label
        self._winrate_label = QLabel("Winrate: --")
        self._winrate_label.setStyleSheet(f"color: {WINRATE_COLOR}; font-weight: bold;")
        top_row.addWidget(self._winrate_label)

        top_row.addStretch()

        # Score label
        self._score_label = QLabel("Score: --")
        self._score_label.setStyleSheet(f"color: {SCORE_COLOR}; font-weight: bold;")
        top_row.addWidget(self._score_label)

        layout.addLayout(top_row)

        # Bottom row: Loss for both players
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        # Loss label
        self._loss_label = QLabel("Loss: -- / --")
        self._loss_label.setStyleSheet("color: #666666; font-size: 11px;")
        bottom_row.addWidget(self._loss_label)

        bottom_row.addStretch()

        layout.addLayout(bottom_row)

        # Frame border
        self.setFrameStyle()

    def setFrameStyle(self):
        """Apply frame styling."""
        self.setAutoFillBackground(True)
        self.setStyleSheet("""
            StatsPanel {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
            }
        """)

    def set_stats(
        self,
        winrate: Optional[float] = None,
        score: Optional[float] = None,
        black_loss: Optional[float] = None,
        white_loss: Optional[float] = None,
        current_player: str = "B",
    ):
        """
        Update the statistics display.

        Args:
            winrate: Current winrate (0.0-1.0), None if unavailable
            score: Score lead from Black's perspective, None if unavailable
            black_loss: Cumulative points lost by Black, None if unavailable
            white_loss: Cumulative points lost by White, None if unavailable
            current_player: "B" or "W" - used to highlight current player's stats
        """
        # Winrate
        if winrate is not None:
            wr_pct = winrate * 100
            # Color based on who's winning
            if winrate > 0.55:
                color = "#228B22"  # Green - Black winning
            elif winrate < 0.45:
                color = "#CC3333"  # Red - White winning
            else:
                color = "#666666"  # Gray - close game
            self._winrate_label.setText(f"Winrate: {wr_pct:.1f}%")
            self._winrate_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        else:
            self._winrate_label.setText("Winrate: --")
            self._winrate_label.setStyleSheet(f"color: {WINRATE_COLOR}; font-weight: bold;")

        # Score
        if score is not None:
            sign = "+" if score >= 0 else ""
            # Color based on score
            if score > 2:
                color = "#228B22"  # Green - Black leading
            elif score < -2:
                color = "#CC3333"  # Red - White leading
            else:
                color = "#666666"  # Gray - close
            self._score_label.setText(f"Score: {sign}{score:.1f}")
            self._score_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        else:
            self._score_label.setText("Score: --")
            self._score_label.setStyleSheet(f"color: {SCORE_COLOR}; font-weight: bold;")

        # Loss
        if black_loss is not None and white_loss is not None:
            # Highlight current player's loss with different styling
            if current_player == "B":
                black_text = f"<b>B: {black_loss:.1f}</b>"
                white_text = f"W: {white_loss:.1f}"
            else:
                black_text = f"B: {black_loss:.1f}"
                white_text = f"<b>W: {white_loss:.1f}</b>"
            self._loss_label.setText(f"Loss: {black_text} / {white_text}")
        elif black_loss is not None:
            self._loss_label.setText(f"Loss: B: {black_loss:.1f} / W: --")
        elif white_loss is not None:
            self._loss_label.setText(f"Loss: B: -- / W: {white_loss:.1f}")
        else:
            self._loss_label.setText("Loss: -- / --")

    def clear(self):
        """Clear all statistics."""
        self._winrate_label.setText("Winrate: --")
        self._winrate_label.setStyleSheet(f"color: {WINRATE_COLOR}; font-weight: bold;")
        self._score_label.setText("Score: --")
        self._score_label.setStyleSheet(f"color: {SCORE_COLOR}; font-weight: bold;")
        self._loss_label.setText("Loss: -- / --")

    def set_theme_colors(self, good: str, bad: str, neutral: str):
        """Set theme colors for stats display."""
        global WINRATE_COLOR, SCORE_COLOR
        # Store theme colors for dynamic updates
        self._theme_good = good
        self._theme_bad = bad
        self._theme_neutral = neutral
        # These will be used in set_stats for color calculations

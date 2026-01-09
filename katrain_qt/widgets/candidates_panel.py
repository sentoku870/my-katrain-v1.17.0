"""
CandidatesPanel - Qt widget for displaying KataGo analysis candidates.

Shows a table of candidate moves with:
- Rank (1-5)
- Coordinate (D4, Q16, etc.)
- Score lead
- Visits
- Loss (optional, via Dev settings)
"""

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
)

from katrain_qt.analysis.models import CandidateMove, coord_to_display

# Import shared evaluation constants (SINGLE SOURCE OF TRUTH)
from katrain_qt.common.eval_constants import (
    EVAL_ROW_COLORS as ROW_BG_COLORS,
    EVAL_THRESHOLDS_ASC as ROW_BG_THRESHOLDS,
    LOW_VISITS_THRESHOLD,
    LOW_VISITS_ROW_BG as LOW_VISITS_BG,
)
from katrain_qt.settings import get_settings


class CandidatesPanel(QWidget):
    """
    Panel displaying KataGo analysis candidates.

    Signals:
        candidate_selected(int, int): Emitted when user clicks a candidate (col, row)
        candidate_hovered(int, list, str): Emitted when hovering over candidate
            (row_index, pv_list, starting_color "B"/"W"), or (-1, [], "") when leaving
    """

    candidate_selected = Signal(int, int)
    candidate_hovered = Signal(int, list, str)  # row_index, pv, starting_color

    def __init__(self, parent=None, next_player: str = "B"):
        super().__init__(parent)
        self._board_size = 19
        self._candidates: List[CandidateMove] = []
        self._settings = get_settings()
        self._next_player = next_player  # "B" or "W" - who plays the first PV move

        self._setup_ui()

    def _setup_ui(self):
        """Setup the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        header = QLabel("Candidates")
        header.setStyleSheet("font-weight: bold;")
        layout.addWidget(header)

        # Table - columns depend on dev settings
        self._table = QTableWidget()
        self._update_table_columns()
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)

        # Connect selection signal
        self._table.cellClicked.connect(self._on_cell_clicked)

        # Enable mouse tracking for hover events
        # Both table AND viewport need mouse tracking for cellEntered to work reliably
        self._table.setMouseTracking(True)
        self._table.viewport().setMouseTracking(True)
        self._table.cellEntered.connect(self._on_cell_entered)
        self._table.viewport().installEventFilter(self)
        self._last_hover_row = -1

        layout.addWidget(self._table)

        # Status label
        self._status_label = QLabel("No analysis")
        self._status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self._status_label)

    def set_board_size(self, size: int):
        """Set board size for coordinate display."""
        self._board_size = size

    def _update_table_columns(self):
        """Update table columns based on dev settings."""
        show_loss = self._settings.dev_show_loss

        if show_loss:
            self._table.setColumnCount(5)
            self._table.setHorizontalHeaderLabels(["#", "Move", "Score", "Loss", "Visits"])
        else:
            self._table.setColumnCount(4)
            self._table.setHorizontalHeaderLabels(["#", "Move", "Score", "Visits"])

        # Column widths
        header_view = self._table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.Fixed)
        header_view.setSectionResizeMode(1, QHeaderView.Fixed)
        header_view.setSectionResizeMode(2, QHeaderView.Stretch)
        if show_loss:
            header_view.setSectionResizeMode(3, QHeaderView.Stretch)
            header_view.setSectionResizeMode(4, QHeaderView.Stretch)
        else:
            header_view.setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 30)  # Rank
        self._table.setColumnWidth(1, 50)  # Move

    def refresh_columns(self):
        """Refresh table columns (call after settings change)."""
        self._update_table_columns()
        if self._candidates:
            self.set_candidates(self._candidates)

    def set_candidates(self, candidates: List[CandidateMove]):
        """Update the candidates display with row coloring."""
        self._candidates = candidates
        self._table.setRowCount(len(candidates))

        show_loss = self._settings.dev_show_loss

        # Find best score for loss calculation (rank==1 or max score_lead)
        best_score: Optional[float] = None
        if candidates:
            # First try to find rank==1 candidate
            for c in candidates:
                if c.rank == 1:
                    best_score = c.score_lead
                    break
            # Fallback: use max score_lead
            if best_score is None:
                best_score = max(c.score_lead for c in candidates)

        for i, cand in enumerate(candidates):
            col_idx = 0

            # Calculate loss for row coloring
            loss = 0.0 if best_score is None else best_score - cand.score_lead
            loss = max(0.0, loss)

            # Determine row background color
            is_low_visits = cand.visits < LOW_VISITS_THRESHOLD
            if is_low_visits:
                row_bg = QBrush(LOW_VISITS_BG)
            else:
                # 6-stage color based on loss
                color_idx = 0
                for j, threshold in enumerate(ROW_BG_THRESHOLDS):
                    if loss > threshold:
                        color_idx = j + 1
                color_idx = min(color_idx, len(ROW_BG_COLORS) - 1)
                row_bg = QBrush(ROW_BG_COLORS[color_idx])

            # Rank
            rank_item = QTableWidgetItem(str(cand.rank))
            rank_item.setTextAlignment(Qt.AlignCenter)
            rank_item.setBackground(row_bg)
            self._table.setItem(i, col_idx, rank_item)
            col_idx += 1

            # Move coordinate
            coord = coord_to_display(cand.col, cand.row, self._board_size)
            move_item = QTableWidgetItem(coord)
            move_item.setTextAlignment(Qt.AlignCenter)
            move_item.setBackground(row_bg)
            self._table.setItem(i, col_idx, move_item)
            col_idx += 1

            # Score lead
            score_str = f"{cand.score_lead:+.1f}" if cand.score_lead != 0 else "0.0"
            score_item = QTableWidgetItem(score_str)
            score_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            score_item.setBackground(row_bg)
            self._table.setItem(i, col_idx, score_item)
            col_idx += 1

            # Loss (optional)
            if show_loss and best_score is not None:
                if loss <= 0.05:  # Essentially no loss (best move)
                    loss_str = "-"
                else:
                    loss_str = f"{loss:.1f}"
                loss_item = QTableWidgetItem(loss_str)
                loss_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                loss_item.setBackground(row_bg)
                # Color code: orange for significant loss
                if loss >= 2.0:
                    loss_item.setForeground(Qt.darkRed)
                elif loss >= 0.5:
                    loss_item.setForeground(Qt.darkYellow)
                self._table.setItem(i, col_idx, loss_item)
                col_idx += 1

            # Visits
            visits_item = QTableWidgetItem(f"{cand.visits:,}")
            visits_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            visits_item.setBackground(row_bg)
            self._table.setItem(i, col_idx, visits_item)

        # Update status
        if candidates:
            total_visits = sum(c.visits for c in candidates)
            self._status_label.setText(f"{len(candidates)} candidates, {total_visits:,} total visits")
        else:
            self._status_label.setText("No analysis")

    def clear(self):
        """Clear all candidates."""
        self._candidates = []
        self._table.setRowCount(0)
        self._status_label.setText("No analysis")

    def _on_cell_clicked(self, row: int, col: int):
        """Handle cell click - emit candidate selection."""
        if 0 <= row < len(self._candidates):
            cand = self._candidates[row]
            self.candidate_selected.emit(cand.col, cand.row)

    def _on_cell_entered(self, row: int, col: int):
        """Handle cell hover - emit candidate hover signal for PV preview."""
        if row == self._last_hover_row:
            return  # No change

        self._last_hover_row = row

        if 0 <= row < len(self._candidates):
            cand = self._candidates[row]
            self.candidate_hovered.emit(row, cand.pv, self._next_player)
        else:
            self.candidate_hovered.emit(-1, [], "")

    def set_next_player(self, player: str):
        """Set next player for PV color alternation."""
        self._next_player = player

    def leaveEvent(self, event):
        """Clear hover when mouse leaves the panel."""
        if self._last_hover_row >= 0:
            self._last_hover_row = -1
            self.candidate_hovered.emit(-1, [], "")
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        """Event filter for viewport to handle mouse leaving table area."""
        from PySide6.QtCore import QEvent
        if obj == self._table.viewport() and event.type() == QEvent.Leave:
            if self._last_hover_row >= 0:
                self._last_hover_row = -1
                self.candidate_hovered.emit(-1, [], "")
        return super().eventFilter(obj, event)

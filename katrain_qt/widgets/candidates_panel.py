"""
CandidatesPanel - Qt widget for displaying KataGo analysis candidates.

Shows a table of candidate moves with:
- Rank (1-5)
- Coordinate (D4, Q16, etc.)
- Score lead
- Visits
"""

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
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


class CandidatesPanel(QWidget):
    """
    Panel displaying KataGo analysis candidates.

    Signals:
        candidate_selected(int, int): Emitted when user clicks a candidate (col, row)
    """

    candidate_selected = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._board_size = 19
        self._candidates: List[CandidateMove] = []

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

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["#", "Move", "Score", "Visits"])
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)

        # Column widths
        header_view = self._table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.Fixed)
        header_view.setSectionResizeMode(1, QHeaderView.Fixed)
        header_view.setSectionResizeMode(2, QHeaderView.Stretch)
        header_view.setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 30)  # Rank
        self._table.setColumnWidth(1, 50)  # Move

        # Connect selection signal
        self._table.cellClicked.connect(self._on_cell_clicked)

        layout.addWidget(self._table)

        # Status label
        self._status_label = QLabel("No analysis")
        self._status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self._status_label)

    def set_board_size(self, size: int):
        """Set board size for coordinate display."""
        self._board_size = size

    def set_candidates(self, candidates: List[CandidateMove]):
        """Update the candidates display."""
        self._candidates = candidates
        self._table.setRowCount(len(candidates))

        for i, cand in enumerate(candidates):
            # Rank
            rank_item = QTableWidgetItem(str(cand.rank))
            rank_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(i, 0, rank_item)

            # Move coordinate
            coord = coord_to_display(cand.col, cand.row, self._board_size)
            move_item = QTableWidgetItem(coord)
            move_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(i, 1, move_item)

            # Score lead
            score_str = f"{cand.score_lead:+.1f}" if cand.score_lead != 0 else "0.0"
            score_item = QTableWidgetItem(score_str)
            score_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(i, 2, score_item)

            # Visits
            visits_item = QTableWidgetItem(f"{cand.visits:,}")
            visits_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(i, 3, visits_item)

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

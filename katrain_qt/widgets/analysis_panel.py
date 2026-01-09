"""
AnalysisPanel - Qt widget for displaying detailed position analysis.

Features:
- Current position summary: move number, player to move, last move
- Winrate display (Black's winning probability)
- Score lead display (Black perspective)
- Top 5 candidate moves with details
- PV (principal variation) for selected candidate
- Updates on navigation, analysis, and candidate selection
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSizePolicy,
)

from katrain_qt.analysis.models import AnalysisResult, CandidateMove, coord_to_display


# =============================================================================
# Constants
# =============================================================================

# Colors for winrate bar
WINRATE_BLACK_COLOR = "#333333"
WINRATE_WHITE_COLOR = "#CCCCCC"


# =============================================================================
# AnalysisPanel Widget
# =============================================================================

class AnalysisPanel(QWidget):
    """
    Panel displaying detailed position analysis.

    Signals:
        candidate_selected(int): Emitted when user selects a candidate (index 0-4)
    """

    candidate_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(250)

        # Data
        self._result: Optional[AnalysisResult] = None
        self._board_size: int = 19
        self._selected_idx: int = 0

        # Build UI
        self._setup_ui()

    def _setup_ui(self):
        """Create the panel layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Position Info Group
        self._position_group = QGroupBox("Position")
        position_layout = QVBoxLayout(self._position_group)
        position_layout.setSpacing(4)

        self._move_label = QLabel("Move: -")
        self._player_label = QLabel("To play: -")
        self._last_move_label = QLabel("Last: -")

        position_layout.addWidget(self._move_label)
        position_layout.addWidget(self._player_label)
        position_layout.addWidget(self._last_move_label)
        layout.addWidget(self._position_group)

        # Evaluation Group
        self._eval_group = QGroupBox("Evaluation")
        eval_layout = QVBoxLayout(self._eval_group)
        eval_layout.setSpacing(4)

        # Winrate row
        winrate_row = QHBoxLayout()
        winrate_row.addWidget(QLabel("Winrate:"))
        self._winrate_label = QLabel("-")
        self._winrate_label.setAlignment(Qt.AlignRight)
        winrate_row.addWidget(self._winrate_label)
        eval_layout.addLayout(winrate_row)

        # Score row
        score_row = QHBoxLayout()
        score_row.addWidget(QLabel("Score (B):"))
        self._score_label = QLabel("-")
        self._score_label.setAlignment(Qt.AlignRight)
        score_row.addWidget(self._score_label)
        eval_layout.addLayout(score_row)

        # Visits row
        visits_row = QHBoxLayout()
        visits_row.addWidget(QLabel("Visits:"))
        self._visits_label = QLabel("-")
        self._visits_label.setAlignment(Qt.AlignRight)
        visits_row.addWidget(self._visits_label)
        eval_layout.addLayout(visits_row)

        layout.addWidget(self._eval_group)

        # Candidates Table
        self._candidates_group = QGroupBox("Top Moves")
        candidates_layout = QVBoxLayout(self._candidates_group)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["#", "Move", "Score", "Visits"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setMaximumHeight(150)
        self._table.cellClicked.connect(self._on_cell_clicked)

        candidates_layout.addWidget(self._table)
        layout.addWidget(self._candidates_group)

        # PV Group
        self._pv_group = QGroupBox("Principal Variation")
        pv_layout = QVBoxLayout(self._pv_group)

        self._pv_label = QLabel("-")
        self._pv_label.setWordWrap(True)
        self._pv_label.setMinimumHeight(40)
        font = QFont("Consolas", 9)
        self._pv_label.setFont(font)

        pv_layout.addWidget(self._pv_label)
        layout.addWidget(self._pv_group)

        # Stretch at bottom
        layout.addStretch()

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_board_size(self, size: int):
        """Set board size for coordinate display."""
        self._board_size = size

    def set_position_info(
        self,
        move_number: int,
        next_player: str,
        last_move: Optional[tuple],
    ):
        """
        Update position info (call on every navigation).

        Args:
            move_number: Current move number
            next_player: "B" or "W"
            last_move: (col, row, player) or None
        """
        self._move_label.setText(f"Move: {move_number}")
        player_text = "Black" if next_player == "B" else "White"
        self._player_label.setText(f"To play: {player_text}")

        if last_move:
            col, row, player = last_move
            coord = coord_to_display(col, row, self._board_size)
            last_player = "B" if player == "B" else "W"
            self._last_move_label.setText(f"Last: {last_player} {coord}")
        else:
            self._last_move_label.setText("Last: -")

    def set_analysis(self, result: Optional[AnalysisResult]):
        """
        Update with new analysis result.

        Args:
            result: AnalysisResult or None to clear
        """
        self._result = result
        self._selected_idx = 0

        if result is None:
            self._clear_analysis_display()
            return

        # Update evaluation
        self._update_evaluation(result)

        # Update candidates table
        self._update_candidates_table(result.candidates)

        # Update PV for first candidate
        self._update_pv_display()

    def set_selected_candidate(self, idx: int):
        """
        Set selected candidate by index.

        Args:
            idx: Candidate index (0-based)
        """
        if self._result is None:
            return

        if 0 <= idx < len(self._result.candidates):
            self._selected_idx = idx
            self._table.selectRow(idx)
            self._update_pv_display()

    def clear(self):
        """Clear all analysis display."""
        self._result = None
        self._selected_idx = 0
        self._clear_analysis_display()

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    def _clear_analysis_display(self):
        """Clear analysis-related displays (keep position info)."""
        self._winrate_label.setText("-")
        self._score_label.setText("-")
        self._visits_label.setText("-")
        self._table.setRowCount(0)
        self._pv_label.setText("-")

    def _update_evaluation(self, result: AnalysisResult):
        """Update evaluation displays."""
        # Winrate (Black perspective)
        if result.winrate_black is not None:
            pct = result.winrate_black * 100
            self._winrate_label.setText(f"B {pct:.1f}% / W {100-pct:.1f}%")
        else:
            self._winrate_label.setText("-")

        # Score (Black perspective)
        if result.score_lead_black is not None:
            score = result.score_lead_black
            if score > 0:
                self._score_label.setText(f"B+{score:.1f}")
            elif score < 0:
                self._score_label.setText(f"W+{-score:.1f}")
            else:
                self._score_label.setText("Even")
        else:
            self._score_label.setText("-")

        # Visits
        self._visits_label.setText(f"{result.root_visits:,}")

    def _update_candidates_table(self, candidates: list):
        """Update candidates table."""
        self._table.setRowCount(len(candidates))

        for i, cand in enumerate(candidates):
            # Rank
            rank_item = QTableWidgetItem(str(cand.rank))
            rank_item.setTextAlignment(Qt.AlignCenter)
            rank_item.setFlags(rank_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(i, 0, rank_item)

            # Move
            coord = coord_to_display(cand.col, cand.row, self._board_size)
            move_item = QTableWidgetItem(coord)
            move_item.setTextAlignment(Qt.AlignCenter)
            move_item.setFlags(move_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(i, 1, move_item)

            # Score (to-play perspective for intuitive reading)
            score_item = QTableWidgetItem(f"{cand.score_lead:+.1f}")
            score_item.setTextAlignment(Qt.AlignCenter)
            score_item.setFlags(score_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(i, 2, score_item)

            # Visits
            visits_item = QTableWidgetItem(f"{cand.visits:,}")
            visits_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            visits_item.setFlags(visits_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(i, 3, visits_item)

        # Select first row
        if candidates:
            self._table.selectRow(0)

    def _update_pv_display(self):
        """Update PV display for selected candidate."""
        if self._result is None:
            self._pv_label.setText("-")
            return

        if 0 <= self._selected_idx < len(self._result.candidates):
            cand = self._result.candidates[self._selected_idx]
            pv_str = cand.pv_string(max_moves=12)
            if pv_str:
                # Add move coordinate as first move
                coord = coord_to_display(cand.col, cand.row, self._board_size)
                self._pv_label.setText(f"{coord} → {pv_str}")
            else:
                coord = coord_to_display(cand.col, cand.row, self._board_size)
                self._pv_label.setText(f"{coord} (no PV)")
        else:
            self._pv_label.setText("-")

    def _on_cell_clicked(self, row: int, col: int):
        """Handle table cell click."""
        if self._result and 0 <= row < len(self._result.candidates):
            self._selected_idx = row
            self._update_pv_display()
            self.candidate_selected.emit(row)

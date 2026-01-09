"""
AnalysisPanel - Qt widget for displaying detailed position analysis (本家 style).

Shows current position and evaluation with high information density:
- Position info (move number, player to play)
- Evaluation (winrate + score, prominent display)
- Top candidates table with row coloring
- Principal Variation display

Layout matches 本家:
┌─────────────────────────────────┐
│ Move 45, White to play          │
├─────────────────────────────────┤
│ Win Rate       ●64.2%           │  ← Large, prominent
│ Estimated Score   B+2.0         │  ← Medium
├─────────────────────────────────┤
│ Top Moves                       │
│ # Move  Score  Visits           │
│ 1 D16   +2.3   1.2k   45%       │  ← Row colored by loss
│ 2 Q4    +1.8   0.8k   30%       │
│ ...                             │
├─────────────────────────────────┤
│ PV: D16 Q4 R5 ...               │
└─────────────────────────────────┘
"""

from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
)
from PySide6.QtGui import QFont, QColor, QBrush

from katrain_qt.analysis.models import AnalysisResult, CandidateMove, coord_to_display

# Import shared evaluation constants (SINGLE SOURCE OF TRUTH)
from katrain_qt.common.eval_constants import (
    EVAL_ROW_COLORS,
    EVAL_THRESHOLDS_ASC as EVAL_THRESHOLDS,
)


class AnalysisPanel(QWidget):
    """
    Panel displaying detailed position analysis (本家 style).

    Signals:
        candidate_selected(int): Emitted when user selects a candidate (index 0-4)
        candidate_hovered(int, list, str): Emitted when hovering over candidate
            (row_index, pv_list, starting_color "B"/"W"), or (-1, [], "") when leaving
    """

    candidate_selected = Signal(int)
    candidate_hovered = Signal(int, list, str)  # row_index, pv, starting_color

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(250)

        # Data
        self._result: Optional[AnalysisResult] = None
        self._board_size: int = 19
        self._selected_idx: int = 0
        self._next_player: str = "B"  # Who plays the first PV move
        self._last_hover_row: int = -1  # Track last hovered row

        # Build UI
        self._setup_ui()

    def _setup_ui(self):
        """Create the panel layout (本家 style)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # === Position Info (compact) ===
        position_row = QHBoxLayout()
        self._move_label = QLabel("Move --")
        self._move_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        position_row.addWidget(self._move_label)

        position_row.addStretch()

        self._player_label = QLabel("-- to play")
        self._player_label.setStyleSheet("color: #666666; font-size: 11px;")
        position_row.addWidget(self._player_label)

        layout.addLayout(position_row)

        # === Separator ===
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("background-color: #CCCCCC;")
        sep1.setFixedHeight(1)
        layout.addWidget(sep1)

        # === Evaluation (prominent - 本家 style) ===
        # Win Rate (large)
        winrate_row = QHBoxLayout()
        winrate_title = QLabel("Win Rate")
        winrate_title.setStyleSheet("color: #666666; font-size: 11px;")
        winrate_row.addWidget(winrate_title)
        winrate_row.addStretch()
        self._winrate_label = QLabel("--")
        winrate_font = QFont()
        winrate_font.setPointSize(14)
        winrate_font.setBold(True)
        self._winrate_label.setFont(winrate_font)
        winrate_row.addWidget(self._winrate_label)
        layout.addLayout(winrate_row)

        # Score (medium)
        score_row = QHBoxLayout()
        score_title = QLabel("Estimated Score")
        score_title.setStyleSheet("color: #666666; font-size: 10px;")
        score_row.addWidget(score_title)
        score_row.addStretch()
        self._score_label = QLabel("--")
        score_font = QFont()
        score_font.setPointSize(12)
        score_font.setBold(True)
        self._score_label.setFont(score_font)
        score_row.addWidget(self._score_label)
        layout.addLayout(score_row)

        # Visits (small)
        visits_row = QHBoxLayout()
        visits_title = QLabel("Total Visits")
        visits_title.setStyleSheet("color: #888888; font-size: 9px;")
        visits_row.addWidget(visits_title)
        visits_row.addStretch()
        self._visits_label = QLabel("--")
        self._visits_label.setStyleSheet("color: #888888; font-size: 10px;")
        visits_row.addWidget(self._visits_label)
        layout.addLayout(visits_row)

        # === Separator ===
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background-color: #CCCCCC;")
        sep2.setFixedHeight(1)
        layout.addWidget(sep2)

        # === Candidates Table (with row coloring) ===
        candidates_title = QLabel("Top Moves")
        candidates_title.setStyleSheet("font-weight: bold; font-size: 10px; color: #333333;")
        layout.addWidget(candidates_title)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["#", "Move", "Score", "Visits", "%"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setMaximumHeight(130)
        self._table.setStyleSheet("font-size: 10px;")
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.setMouseTracking(True)
        self._table.cellEntered.connect(self._on_cell_entered)
        self._table.viewport().installEventFilter(self)
        layout.addWidget(self._table)

        # === PV Group (compact) ===
        pv_title = QLabel("Principal Variation")
        pv_title.setStyleSheet("font-weight: bold; font-size: 9px; color: #666666;")
        layout.addWidget(pv_title)

        self._pv_label = QLabel("-")
        self._pv_label.setWordWrap(True)
        self._pv_label.setMinimumHeight(30)
        self._pv_label.setStyleSheet("font-family: Consolas; font-size: 9px; color: #333333;")
        layout.addWidget(self._pv_label)

        # === Last move label (compact) ===
        self._last_move_label = QLabel("Last: -")
        self._last_move_label.setStyleSheet("color: #888888; font-size: 9px;")
        layout.addWidget(self._last_move_label)

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
        self._move_label.setText(f"Move {move_number}")
        player_text = "Black" if next_player == "B" else "White"
        self._player_label.setText(f"{player_text} to play")

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
        self._winrate_label.setText("--")
        self._winrate_label.setStyleSheet("")
        self._score_label.setText("--")
        self._score_label.setStyleSheet("")
        self._visits_label.setText("--")
        self._table.setRowCount(0)
        self._pv_label.setText("-")

    def _update_evaluation(self, result: AnalysisResult):
        """Update evaluation display (本家 style)."""
        # Winrate
        if result.winrate_black is not None:
            wr = result.winrate_black
            if wr > 0.5:
                # Black winning
                wr_pct = wr * 100
                indicator = "●"
                color = "#228B22"  # Green
            else:
                # White winning
                wr_pct = (1 - wr) * 100
                indicator = "○"
                color = "#CC3333"  # Red

            self._winrate_label.setText(f"{indicator}{wr_pct:.1f}%")
            self._winrate_label.setStyleSheet(f"color: {color};")
        else:
            self._winrate_label.setText("--")
            self._winrate_label.setStyleSheet("")

        # Score
        if result.score_lead_black is not None:
            score = result.score_lead_black
            if score > 0:
                score_text = f"B+{score:.1f}"
                color = "#228B22"
            elif score < 0:
                score_text = f"W+{-score:.1f}"
                color = "#CC3333"
            else:
                score_text = "Even"
                color = "#666666"
            self._score_label.setText(score_text)
            self._score_label.setStyleSheet(f"color: {color};")
        else:
            self._score_label.setText("--")
            self._score_label.setStyleSheet("")

        # Visits
        total_visits = sum(c.visits for c in result.candidates) if result.candidates else 0
        if total_visits >= 1000:
            visits_text = f"{total_visits / 1000:.1f}k"
        else:
            visits_text = str(total_visits)
        self._visits_label.setText(visits_text)

    def _update_candidates_table(self, candidates: List[CandidateMove]):
        """Update candidates table with row coloring (本家 style)."""
        self._table.setRowCount(len(candidates))

        # Find best score for loss calculation
        best_score = candidates[0].score_lead if candidates else 0
        for c in candidates:
            if c.rank == 1:
                best_score = c.score_lead
                break

        # Total visits for percentage
        total_visits = sum(c.visits for c in candidates) if candidates else 1

        for i, cand in enumerate(candidates):
            # Calculate loss
            loss = max(0, best_score - cand.score_lead)

            # Determine row color
            color_idx = 0
            for j, threshold in enumerate(EVAL_THRESHOLDS):
                if loss > threshold:
                    color_idx = j + 1
            color_idx = min(color_idx, len(EVAL_ROW_COLORS) - 1)
            row_color = EVAL_ROW_COLORS[color_idx]

            # Rank
            rank_item = QTableWidgetItem(str(cand.rank))
            rank_item.setTextAlignment(Qt.AlignCenter)
            rank_item.setBackground(QBrush(row_color))
            self._table.setItem(i, 0, rank_item)

            # Move coordinate
            coord = coord_to_display(cand.col, cand.row, self._board_size)
            move_item = QTableWidgetItem(coord)
            move_item.setBackground(QBrush(row_color))
            self._table.setItem(i, 1, move_item)

            # Score
            score_text = f"{cand.score_lead:+.1f}"
            score_item = QTableWidgetItem(score_text)
            score_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            score_item.setBackground(QBrush(row_color))
            self._table.setItem(i, 2, score_item)

            # Visits
            if cand.visits >= 1000:
                visits_text = f"{cand.visits / 1000:.1f}k"
            else:
                visits_text = str(cand.visits)
            visits_item = QTableWidgetItem(visits_text)
            visits_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            visits_item.setBackground(QBrush(row_color))
            self._table.setItem(i, 3, visits_item)

            # Percentage
            pct = (cand.visits / total_visits * 100) if total_visits > 0 else 0
            pct_item = QTableWidgetItem(f"{pct:.0f}%")
            pct_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            pct_item.setBackground(QBrush(row_color))
            self._table.setItem(i, 4, pct_item)

        # Select first row
        if candidates:
            self._table.selectRow(0)

    def _update_pv_display(self):
        """Update PV display for selected candidate."""
        if self._result is None or not self._result.candidates:
            self._pv_label.setText("-")
            return

        if self._selected_idx < len(self._result.candidates):
            cand = self._result.candidates[self._selected_idx]
            if cand.pv:
                # Convert PV to display format
                pv_coords = []
                for move in cand.pv[:10]:  # Limit to 10 moves
                    if move.lower() == "pass":
                        pv_coords.append("pass")
                    else:
                        pv_coords.append(move)
                pv_text = " → ".join(pv_coords)
                if len(cand.pv) > 10:
                    pv_text += " ..."
                self._pv_label.setText(pv_text)
            else:
                self._pv_label.setText("-")

    def _on_cell_clicked(self, row: int, col: int):
        """Handle cell click in candidates table."""
        if self._result is None:
            return
        if 0 <= row < len(self._result.candidates):
            self._selected_idx = row
            self._update_pv_display()
            self.candidate_selected.emit(row)

    def _on_cell_entered(self, row: int, col: int):
        """Handle cell hover - emit candidate hover signal for PV preview."""
        if row == self._last_hover_row:
            return  # No change

        self._last_hover_row = row

        if self._result is None:
            self.candidate_hovered.emit(-1, [], "")
            return

        if 0 <= row < len(self._result.candidates):
            cand = self._result.candidates[row]
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

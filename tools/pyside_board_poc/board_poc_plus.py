"""
PySide6 Go Board PoC+ - Extended proof-of-concept with SGF loading,
candidate overlays, and KataGo integration for real analysis.

Features:
- SGF load + navigation (19x19 only for PoC)
- Overlay drawing (candidate moves with labels)
- KataGo integration for real analysis (with dummy fallback)
- Right dock panel for candidates list
"""

import hashlib
import math
import os
import random
import sys
from pathlib import Path

from PySide6.QtCore import (
    Qt, Signal, Slot, QObject, QThread, QTimer, QRectF, QPointF
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QKeySequence, QShortcut, QAction
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStatusBar, QToolBar,
    QDockWidget, QVBoxLayout, QLabel, QListWidget, QFileDialog,
    QMenuBar, QMenu, QPushButton, QHBoxLayout,
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox
)

# Support both direct execution and package import
try:
    from models import BoardModel, AnalysisModel, coord_to_display, CandidateMove
    from katago_engine import KataGoEngine, load_settings, save_settings
except ImportError:
    from .models import BoardModel, AnalysisModel, coord_to_display, CandidateMove
    from .katago_engine import KataGoEngine, load_settings, save_settings


# =============================================================================
# Constants
# =============================================================================

BOARD_SIZE = 19
HOSHI_POINTS = [
    (3, 3), (3, 9), (3, 15),
    (9, 3), (9, 9), (9, 15),
    (15, 3), (15, 9), (15, 15),
]

# Board appearance
MARGIN_RATIO = 0.05
MARGIN_MIN = 20
STONE_RADIUS_RATIO = 0.45
HOSHI_RADIUS_RATIO = 0.12
HIT_THRESHOLD_RATIO = 0.45

# Colors
BOARD_COLOR = QColor("#DEB887")
LINE_COLOR = QColor("#000000")
BLACK_STONE = QColor("#000000")
WHITE_STONE = QColor("#FFFFFF")
MARKER_BLACK = QColor("#FFFFFF")
MARKER_WHITE = QColor("#000000")
HOVER_ALPHA = 100

# Overlay appearance
OVERLAY_COLOR = QColor("#0064FF")
OVERLAY_ALPHA = 120
OVERLAY_RADIUS_RATIO = 0.38
LABEL_FONT_RATIO = 0.28

# Analysis
ANALYSIS_INTERVAL_MS = 500
MAX_CANDIDATES = 5
DEBOUNCE_MS = 200  # Debounce delay for KataGo queries


# =============================================================================
# AnalysisWorker (runs in QThread)
# =============================================================================

class AnalysisWorker(QObject):
    """
    Worker that generates dummy candidate moves periodically.
    IMPORTANT: QTimer is created in start() after moveToThread().
    """
    candidates_updated = Signal(list)

    def __init__(self):
        super().__init__()
        self.timer = None
        self._stones_snapshot: list[tuple[int, int, str]] = []
        self._running = False

    @Slot()
    def start(self):
        """Start periodic candidate generation (called in worker thread)."""
        if self.timer is None:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._generate_candidates)
        self._running = True
        self.timer.start(ANALYSIS_INTERVAL_MS)

    @Slot()
    def stop(self):
        """Stop candidate generation (called in worker thread)."""
        self._running = False
        if self.timer:
            self.timer.stop()

    @Slot(list)
    def set_position(self, stones_snapshot: list):
        """Receive position snapshot (thread-safe: immutable data)."""
        self._stones_snapshot = stones_snapshot

    def _generate_candidates(self):
        """Generate dummy candidates based on current position."""
        if not self._running:
            return

        # Build occupied set from snapshot
        occupied = set((c, r) for c, r, _ in self._stones_snapshot)

        # Stable seed using hashlib (reproducible across runs)
        data = str(sorted(self._stones_snapshot)).encode('utf-8')
        seed = int(hashlib.sha1(data).hexdigest()[:8], 16)

        rng = random.Random(seed)

        # Find empty intersections
        empty = [(c, r) for c in range(BOARD_SIZE) for r in range(BOARD_SIZE)
                 if (c, r) not in occupied]

        if not empty:
            self.candidates_updated.emit([])
            return

        # Select random candidates
        count = min(MAX_CANDIDATES, len(empty))
        selected = rng.sample(empty, count)

        # Generate candidates with dummy values
        candidates = []
        for i, (c, r) in enumerate(selected):
            rank = i + 1
            value = round(rng.uniform(-0.5, 0.5), 2)
            candidates.append((c, r, rank, value))

        self.candidates_updated.emit(candidates)


# =============================================================================
# Configure KataGo Dialog
# =============================================================================

class ConfigureKataGoDialog(QDialog):
    """Dialog for configuring KataGo paths."""

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure KataGo")
        self.setMinimumWidth(500)
        self.settings = dict(settings)

        layout = QVBoxLayout(self)

        # Form layout for paths
        form = QFormLayout()

        # KataGo executable
        self.exe_edit = QLineEdit(self.settings.get("katago_exe", ""))
        exe_row = QHBoxLayout()
        exe_row.addWidget(self.exe_edit)
        exe_browse = QPushButton("Browse...")
        exe_browse.clicked.connect(self._browse_exe)
        exe_row.addWidget(exe_browse)
        form.addRow("KataGo Executable:", exe_row)

        # Config file
        self.config_edit = QLineEdit(self.settings.get("config_path", ""))
        config_row = QHBoxLayout()
        config_row.addWidget(self.config_edit)
        config_browse = QPushButton("Browse...")
        config_browse.clicked.connect(self._browse_config)
        config_row.addWidget(config_browse)
        form.addRow("Analysis Config:", config_row)

        # Model file
        self.model_edit = QLineEdit(self.settings.get("model_path", ""))
        model_row = QHBoxLayout()
        model_row.addWidget(self.model_edit)
        model_browse = QPushButton("Browse...")
        model_browse.clicked.connect(self._browse_model)
        model_row.addWidget(model_browse)
        form.addRow("Model File:", model_row)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select KataGo Executable", "",
            "Executable Files (*.exe);;All Files (*)"
        )
        if path:
            self.exe_edit.setText(path)

    def _browse_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Analysis Config", "",
            "Config Files (*.cfg);;All Files (*)"
        )
        if path:
            self.config_edit.setText(path)

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Model File", "",
            "Model Files (*.bin.gz *.gz);;All Files (*)"
        )
        if path:
            self.model_edit.setText(path)

    def get_settings(self) -> dict:
        """Return updated settings."""
        self.settings["katago_exe"] = self.exe_edit.text()
        self.settings["config_path"] = self.config_edit.text()
        self.settings["model_path"] = self.model_edit.text()
        return self.settings


# =============================================================================
# CandidatesPanel (Right Dock)
# =============================================================================

class CandidatesPanel(QWidget):
    """Panel showing current candidate moves."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.title_label = QLabel("Candidates")
        self.title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.title_label)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

    def update_candidates(self, candidates: list):
        """Update the list with new candidates.

        Supports both:
        - CandidateMove objects (from KataGo)
        - Tuples (col, row, rank, value) (from dummy analysis)
        """
        self.list_widget.clear()
        for item in candidates:
            if isinstance(item, CandidateMove):
                coord = coord_to_display(item.col, item.row)
                self.list_widget.addItem(
                    f"{item.rank}. {coord}: {item.score_lead:+.2f} ({item.visits} visits)"
                )
            else:
                # Legacy tuple format
                col, row, rank, value = item
                coord = coord_to_display(col, row)
                self.list_widget.addItem(f"{rank}. {coord}: {value:+.2f}")


# =============================================================================
# BoardWidgetPlus
# =============================================================================

class BoardWidgetPlus(QWidget):
    """
    Extended board widget with overlay support.
    """
    hover_changed = Signal(int, int, bool)

    def __init__(self, board_model: BoardModel, analysis_model: AnalysisModel, parent=None):
        super().__init__(parent)
        self.board_model = board_model
        self.analysis_model = analysis_model

        self.setMouseTracking(True)
        self.setMinimumSize(400, 400)
        self.setFocusPolicy(Qt.StrongFocus)

        # State
        self.hover_pos: tuple[int, int] | None = None
        self.hover_valid: bool = False
        self.show_overlay: bool = True
        self.edit_mode: bool = False

        # Connect model signals
        self.board_model.position_changed.connect(self.update)
        self.analysis_model.candidates_changed.connect(self.update)

    def set_show_overlay(self, show: bool):
        self.show_overlay = show
        self.update()

    def set_edit_mode(self, enabled: bool):
        self.edit_mode = enabled

    # -------------------------------------------------------------------------
    # Geometry helpers
    # -------------------------------------------------------------------------

    def _board_rect(self) -> QRectF:
        w, h = self.width(), self.height()
        margin = max(MARGIN_MIN, min(w, h) * MARGIN_RATIO)
        available = min(w, h) - 2 * margin
        x = (w - available) / 2
        y = (h - available) / 2
        return QRectF(x, y, available, available)

    def _grid_spacing(self) -> float:
        board = self._board_rect()
        return board.width() / (BOARD_SIZE - 1)

    def _mouse_to_grid(self, pos: QPointF) -> tuple[int, int, bool]:
        board = self._board_rect()
        spacing = self._grid_spacing()

        rx = pos.x() - board.left()
        ry = pos.y() - board.top()

        fi = rx / spacing
        fj = ry / spacing

        i = max(0, min(18, round(fi)))
        j = max(0, min(18, round(fj)))

        dist = math.sqrt((fi - i) ** 2 + (fj - j) ** 2) * spacing
        valid = dist <= spacing * HIT_THRESHOLD_RATIO

        return (i, j, valid)

    def _grid_to_pixel(self, col: int, row: int) -> QPointF:
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

        board = self._board_rect()
        spacing = self._grid_spacing()
        stones = self.board_model.stones_at_current()

        # 1. Background
        painter.fillRect(self.rect(), BOARD_COLOR)

        # 2. Grid lines
        pen = QPen(LINE_COLOR, 1)
        painter.setPen(pen)
        for k in range(BOARD_SIZE):
            x = board.left() + k * spacing
            painter.drawLine(QPointF(x, board.top()), QPointF(x, board.bottom()))
            y = board.top() + k * spacing
            painter.drawLine(QPointF(board.left(), y), QPointF(board.right(), y))

        # 3. Hoshi
        hoshi_radius = spacing * HOSHI_RADIUS_RATIO
        painter.setBrush(QBrush(LINE_COLOR))
        painter.setPen(Qt.NoPen)
        for hi, hj in HOSHI_POINTS:
            center = self._grid_to_pixel(hi, hj)
            painter.drawEllipse(center, hoshi_radius, hoshi_radius)

        # 4. Stones
        stone_radius = spacing * STONE_RADIUS_RATIO
        for (col, row), color in stones.items():
            center = self._grid_to_pixel(col, row)
            stone_color = BLACK_STONE if color == "B" else WHITE_STONE
            painter.setBrush(QBrush(stone_color))
            painter.setPen(QPen(LINE_COLOR, 1))
            painter.drawEllipse(center, stone_radius, stone_radius)

        # 5. Last move marker
        last_move = self.board_model.last_move()
        if last_move:
            col, row = last_move
            if (col, row) in stones:
                center = self._grid_to_pixel(col, row)
                marker_color = MARKER_BLACK if stones[(col, row)] == "B" else MARKER_WHITE
                marker_radius = stone_radius * 0.4
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(marker_color, 2))
                painter.drawEllipse(center, marker_radius, marker_radius)

        # 6. Candidate overlays
        if self.show_overlay and self.analysis_model.candidates:
            overlay_radius = spacing * OVERLAY_RADIUS_RATIO
            font = painter.font()
            font.setPointSizeF(max(8, spacing * LABEL_FONT_RATIO))
            font.setBold(True)
            painter.setFont(font)

            for item in self.analysis_model.candidates:
                # Support both CandidateMove and tuple formats
                if isinstance(item, CandidateMove):
                    col, row, rank, value = item.col, item.row, item.rank, item.score_lead
                else:
                    col, row, rank, value = item

                if (col, row) in stones:
                    continue  # Skip occupied

                center = self._grid_to_pixel(col, row)

                # Semi-transparent circle
                overlay_color = QColor(OVERLAY_COLOR)
                overlay_color.setAlpha(OVERLAY_ALPHA)
                painter.setBrush(QBrush(overlay_color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(center, overlay_radius, overlay_radius)

                # Rank label (center)
                painter.setPen(QPen(Qt.white))
                text_rect = QRectF(
                    center.x() - overlay_radius,
                    center.y() - overlay_radius * 0.6,
                    overlay_radius * 2,
                    overlay_radius * 1.2
                )
                painter.drawText(text_rect, Qt.AlignCenter, str(rank))

                # Value label (below rank)
                value_rect = QRectF(
                    center.x() - overlay_radius,
                    center.y() + overlay_radius * 0.1,
                    overlay_radius * 2,
                    overlay_radius * 0.8
                )
                small_font = painter.font()
                small_font.setPointSizeF(max(6, spacing * LABEL_FONT_RATIO * 0.7))
                painter.setFont(small_font)
                painter.drawText(value_rect, Qt.AlignCenter, f"{value:+.1f}")
                painter.setFont(font)

        # 7. Hover ghost (edit mode only)
        if self.edit_mode and self.hover_pos and self.hover_valid:
            hi, hj = self.hover_pos
            if (hi, hj) not in stones:
                center = self._grid_to_pixel(hi, hj)
                next_color = self.board_model.next_color()
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
        if not self.edit_mode:
            return

        pos = event.position()
        col, row, valid = self._mouse_to_grid(pos)
        if not valid:
            return

        stones = self.board_model.stones_at_current()

        if event.button() == Qt.LeftButton:
            if (col, row) not in stones:
                color = self.board_model.next_color()
                self.board_model.place_edit_stone(col, row, color)

        elif event.button() == Qt.RightButton:
            if (col, row) in self.board_model._edit_stones:
                self.board_model.remove_edit_stone(col, row)


# =============================================================================
# MainWindowPlus
# =============================================================================

class MainWindowPlus(QMainWindow):
    """Main window with board, dock panel, and analysis controls."""

    # Signals for thread-safe communication with dummy worker
    request_start_analysis = Signal()
    request_stop_analysis = Signal()
    position_updated = Signal(list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Go Board PoC+")
        self.setMinimumSize(800, 650)

        # Models
        self.board_model = BoardModel()
        self.analysis_model = AnalysisModel()

        # Central widget (board)
        self.board_widget = BoardWidgetPlus(self.board_model, self.analysis_model)
        self.setCentralWidget(self.board_widget)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Open an SGF or start analysis")

        # Right dock panel
        self._setup_dock()

        # Menu bar
        self._setup_menu()

        # Toolbar
        self._setup_toolbar()

        # Keyboard shortcuts (QShortcut for reliable key handling)
        self._setup_shortcuts()

        # Analysis state
        self._analysis_running = False
        self._use_katago = False  # True if using KataGo, False for dummy

        # Dummy analysis thread (fallback)
        self._setup_analysis_thread()

        # KataGo engine (lazy init)
        self._engine: KataGoEngine | None = None
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._send_katago_request)
        self._query_counter = 0
        self._pending_query_id: str | None = None

        # Load settings
        self._settings = load_settings()

        # Connect signals
        self.board_widget.hover_changed.connect(self._on_hover_changed)
        self.board_model.position_changed.connect(self._on_position_changed)

    def _setup_dock(self):
        """Setup right dock panel for candidates."""
        self.candidates_panel = CandidatesPanel()
        self.dock_widget = QDockWidget("Analysis", self)
        self.dock_widget.setWidget(self.candidates_panel)
        self.dock_widget.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)

        # Connect analysis model to panel
        self.analysis_model.candidates_changed.connect(
            self.candidates_panel.update_candidates
        )

    def _setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open SGF...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_sgf)
        file_menu.addAction(open_action)

        open_sample_action = QAction("Open &Sample SGF", self)
        open_sample_action.triggered.connect(self.open_sample_sgf)
        file_menu.addAction(open_sample_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        self.edit_mode_action = QAction("&Edit Mode", self)
        self.edit_mode_action.setCheckable(True)
        self.edit_mode_action.setChecked(False)
        self.edit_mode_action.triggered.connect(self._toggle_edit_mode)
        edit_menu.addAction(self.edit_mode_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        self.overlay_action = QAction("Show &Candidates", self)
        self.overlay_action.setCheckable(True)
        self.overlay_action.setChecked(True)
        self.overlay_action.triggered.connect(self._toggle_overlay)
        view_menu.addAction(self.overlay_action)

        # Analysis menu
        analysis_menu = menubar.addMenu("&Analysis")

        self.start_analysis_action = QAction("&Start Analysis", self)
        self.start_analysis_action.triggered.connect(self.start_analysis)
        analysis_menu.addAction(self.start_analysis_action)

        self.stop_analysis_action = QAction("S&top Analysis", self)
        self.stop_analysis_action.triggered.connect(self.stop_analysis)
        self.stop_analysis_action.setEnabled(False)
        analysis_menu.addAction(self.stop_analysis_action)

        analysis_menu.addSeparator()

        configure_action = QAction("&Configure KataGo...", self)
        configure_action.triggered.connect(self._configure_katago)
        analysis_menu.addAction(configure_action)

    def _setup_toolbar(self):
        """Setup navigation toolbar."""
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Navigation buttons
        self.btn_first = QPushButton("|<")
        self.btn_first.setToolTip("First (Home)")
        self.btn_first.clicked.connect(self.go_first)
        toolbar.addWidget(self.btn_first)

        self.btn_prev = QPushButton("<")
        self.btn_prev.setToolTip("Previous (Left)")
        self.btn_prev.clicked.connect(self.go_prev)
        toolbar.addWidget(self.btn_prev)

        self.btn_next = QPushButton(">")
        self.btn_next.setToolTip("Next (Right)")
        self.btn_next.clicked.connect(self.go_next)
        toolbar.addWidget(self.btn_next)

        self.btn_last = QPushButton(">|")
        self.btn_last.setToolTip("Last (End)")
        self.btn_last.clicked.connect(self.go_last)
        toolbar.addWidget(self.btn_last)

        toolbar.addSeparator()

        # Move indicator
        self.move_label = QLabel(" Move: 0/0 ")
        toolbar.addWidget(self.move_label)

        toolbar.addSeparator()

        # Analysis buttons
        self.btn_start_analysis = QPushButton("Start Analysis")
        self.btn_start_analysis.clicked.connect(self.start_analysis)
        toolbar.addWidget(self.btn_start_analysis)

        self.btn_stop_analysis = QPushButton("Stop Analysis")
        self.btn_stop_analysis.clicked.connect(self.stop_analysis)
        self.btn_stop_analysis.setEnabled(False)
        toolbar.addWidget(self.btn_stop_analysis)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts using QShortcut (focus-independent)."""
        QShortcut(QKeySequence(Qt.Key_Left), self, self.go_prev)
        QShortcut(QKeySequence(Qt.Key_Right), self, self.go_next)
        QShortcut(QKeySequence(Qt.Key_Home), self, self.go_first)
        QShortcut(QKeySequence(Qt.Key_End), self, self.go_last)
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_sgf)
        QShortcut(QKeySequence(Qt.Key_Space), self, self.toggle_analysis)

    def _setup_analysis_thread(self):
        """Setup analysis worker and thread."""
        self.analysis_thread = QThread()
        self.worker = AnalysisWorker()
        self.worker.moveToThread(self.analysis_thread)

        # Connect signals (QueuedConnection by default across threads)
        self.request_start_analysis.connect(self.worker.start)
        self.request_stop_analysis.connect(self.worker.stop)
        self.position_updated.connect(self.worker.set_position)
        self.worker.candidates_updated.connect(self._on_candidates_updated)

        # Start thread (worker event loop)
        self.analysis_thread.start()

    # -------------------------------------------------------------------------
    # Slots
    # -------------------------------------------------------------------------

    def _on_hover_changed(self, col: int, row: int, valid: bool):
        """Update status bar with hover info."""
        coord = coord_to_display(col, row)
        move_num = self.board_model.current_move_number()
        total = self.board_model.move_count()
        next_color = "Black" if self.board_model.next_color() == "B" else "White"

        stones = self.board_model.stones_at_current()
        occupied = "(occupied)" if (col, row) in stones else ""
        validity = "valid" if valid else ""

        status = f"Move: {move_num}/{total} | {coord} {validity} {occupied} | Next: {next_color}"
        if self._analysis_running:
            status += " | [Analysis running]"
        self.status_bar.showMessage(status)

    def _on_position_changed(self):
        """Update UI when board position changes."""
        move_num = self.board_model.current_move_number()
        total = self.board_model.move_count()
        self.move_label.setText(f" Move: {move_num}/{total} ")

        # Request analysis if running
        if self._analysis_running:
            if self._use_katago:
                self._request_katago_analysis_debounced()
            else:
                self._send_position_to_worker()

    @Slot(list)
    def _on_candidates_updated(self, candidates: list):
        """Receive candidates from worker."""
        self.analysis_model.set_candidates(candidates)

    def _send_position_to_worker(self):
        """Send current position to worker as immutable snapshot."""
        stones = self.board_model.stones_at_current()
        snapshot = [(col, row, color) for (col, row), color in stones.items()]
        self.position_updated.emit(snapshot)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def open_sgf(self):
        """Open SGF file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open SGF", "", "SGF Files (*.sgf);;All Files (*)"
        )
        if file_path:
            self._load_sgf_file(file_path)

    def open_sample_sgf(self):
        """Load bundled sample SGF."""
        script_dir = Path(__file__).parent
        sample_path = script_dir / "sample.sgf"
        if sample_path.exists():
            self._load_sgf_file(str(sample_path))
        else:
            self.status_bar.showMessage("sample.sgf not found!")

    def _load_sgf_file(self, file_path: str):
        """Load SGF from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.board_model.load_sgf(content)

            # Validate board size (PoC supports 19x19 only)
            if self.board_model.board_size != BOARD_SIZE:
                QMessageBox.warning(
                    self, "Unsupported Board Size",
                    f"This PoC only supports 19x19 boards.\n"
                    f"Loaded SGF has {self.board_model.board_size}x{self.board_model.board_size}."
                )
                self.board_model.clear()
                return

            self.analysis_model.clear()
            self.edit_mode_action.setChecked(False)
            self.board_widget.set_edit_mode(False)
            self.status_bar.showMessage(f"Loaded: {os.path.basename(file_path)}")

            # Request analysis if running
            if self._analysis_running:
                if self._use_katago:
                    self._request_katago_analysis_debounced()
                else:
                    self._send_position_to_worker()
        except Exception as e:
            self.status_bar.showMessage(f"Error loading SGF: {e}")

    def go_first(self):
        self.board_model.go_first()

    def go_prev(self):
        self.board_model.go_prev()

    def go_next(self):
        self.board_model.go_next()

    def go_last(self):
        self.board_model.go_last()

    def toggle_analysis(self):
        """Toggle analysis start/stop."""
        if self._analysis_running:
            self.stop_analysis()
        else:
            self.start_analysis()

    def start_analysis(self):
        """Start analysis (KataGo or dummy fallback)."""
        if self._analysis_running:
            return

        # Check if KataGo is configured
        katago_exe = self._settings.get("katago_exe", "")
        if katago_exe and Path(katago_exe).exists():
            # Use KataGo
            self._use_katago = True
            if not self._start_katago_engine():
                # Failed to start KataGo, use dummy instead
                self._use_katago = False
                self._start_dummy_analysis()
        else:
            # Use dummy analysis
            self._use_katago = False
            self._start_dummy_analysis()

        self._analysis_running = True

        # Update UI
        self.btn_start_analysis.setEnabled(False)
        self.btn_stop_analysis.setEnabled(True)
        self.start_analysis_action.setEnabled(False)
        self.stop_analysis_action.setEnabled(True)

        mode = "KataGo" if self._use_katago else "dummy"
        self.status_bar.showMessage(f"Analysis started ({mode})")

    def _start_dummy_analysis(self):
        """Start dummy analysis worker."""
        self._send_position_to_worker()
        self.request_start_analysis.emit()

    def _start_katago_engine(self) -> bool:
        """Start KataGo engine. Returns True on success."""
        if self._engine is None:
            self._engine = KataGoEngine(self)
            self._engine.ready.connect(self._on_katago_ready)
            self._engine.analysis_received.connect(self._on_katago_analysis)
            self._engine.error_occurred.connect(self._on_katago_error)
            self._engine.status_changed.connect(self._on_katago_status)

        if not self._engine.is_running():
            success = self._engine.start_engine(
                self._settings.get("katago_exe", ""),
                self._settings.get("config_path", ""),
                self._settings.get("model_path", ""),
                self._settings.get("max_visits", 1000),
                self._settings.get("rules", "japanese"),
            )
            if not success:
                return False

        # Send initial analysis request (will be queued until engine ready)
        self._request_katago_analysis_debounced()
        return True

    def stop_analysis(self):
        """Stop analysis (KataGo or dummy)."""
        if not self._analysis_running:
            return

        self._analysis_running = False
        self._debounce_timer.stop()
        self._pending_query_id = None  # Clear pending query to ignore late responses

        if self._use_katago:
            self._stop_katago_engine()
        else:
            self.request_stop_analysis.emit()

        self.analysis_model.clear()

        # Update UI
        self.btn_start_analysis.setEnabled(True)
        self.btn_stop_analysis.setEnabled(False)
        self.start_analysis_action.setEnabled(True)
        self.stop_analysis_action.setEnabled(False)
        self.status_bar.showMessage("Analysis stopped")

    def _stop_katago_engine(self):
        """Stop KataGo engine."""
        if self._engine is not None:
            self._engine.stop_engine()
            # Don't delete engine, just stop it for potential restart

    def _toggle_edit_mode(self, checked: bool):
        """Toggle edit mode."""
        self.board_widget.set_edit_mode(checked)
        if checked:
            self.status_bar.showMessage("Edit mode ON - Click to place stones")
        else:
            self.board_model.clear_edits()
            self.status_bar.showMessage("Edit mode OFF")

    def _toggle_overlay(self, checked: bool):
        """Toggle candidate overlay visibility."""
        self.board_widget.set_show_overlay(checked)

    # -------------------------------------------------------------------------
    # KataGo Integration
    # -------------------------------------------------------------------------

    def _request_katago_analysis_debounced(self):
        """Request KataGo analysis with debounce."""
        self._debounce_timer.start(DEBOUNCE_MS)

    def _send_katago_request(self):
        """Actually send KataGo query (called after debounce)."""
        if not self._engine or not self._analysis_running:
            return

        snapshot = self.board_model.get_position_snapshot()
        self._query_counter += 1
        self._pending_query_id = f"QUERY:{self._query_counter}"
        self._engine.request_analysis(snapshot, self._pending_query_id)

    @Slot()
    def _on_katago_ready(self):
        """Handle engine ready signal."""
        self.status_bar.showMessage("KataGo ready")

    @Slot(str, list)
    def _on_katago_analysis(self, query_id: str, candidates: list):
        """Handle analysis results from KataGo."""
        # Ignore if analysis stopped or stale response
        if not self._analysis_running:
            return
        if query_id != self._pending_query_id:
            return
        self.analysis_model.set_candidates(candidates)

    @Slot(str)
    def _on_katago_error(self, error: str):
        """Handle KataGo error."""
        self.status_bar.showMessage(f"KataGo error: {error}")
        QMessageBox.warning(self, "KataGo Error", error)

    @Slot(str)
    def _on_katago_status(self, status: str):
        """Handle KataGo status change."""
        if self._analysis_running and self._use_katago:
            self.status_bar.showMessage(f"[KataGo] {status}")

    def _configure_katago(self):
        """Show KataGo configuration dialog."""
        dialog = ConfigureKataGoDialog(self._settings, self)
        if dialog.exec() == QDialog.Accepted:
            self._settings = dialog.get_settings()
            save_settings(self._settings)
            self.status_bar.showMessage("KataGo settings saved")

            # If analysis is running with KataGo, restart engine
            if self._analysis_running and self._use_katago:
                self.stop_analysis()
                self.start_analysis()

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def closeEvent(self, event):
        """Clean shutdown of analysis thread and KataGo."""
        # Stop KataGo engine
        if self._engine is not None:
            self._engine.stop_engine()

        # Stop dummy analysis thread
        self.request_stop_analysis.emit()
        self.analysis_thread.quit()
        self.analysis_thread.wait()
        event.accept()


# =============================================================================
# Main
# =============================================================================

def main():
    app = QApplication(sys.argv)
    window = MainWindowPlus()
    window.resize(900, 750)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

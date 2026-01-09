"""
KaTrain Qt Shell - Minimal Qt frontend using KaTrain core.

Milestone M3.4: Hardening + Stop/Go gate.

Run with:
    python -m katrain_qt.app_qt

Features:
  - SGF file loading (File -> Open SGF)
  - Navigation: First/Prev/Next/Last
  - Click-to-play: Left click to place stones (captures/ko handled by core)
  - Pass: P key or toolbar button
  - KataGo analysis: Start/Stop, candidate overlay, candidates panel
  - Keyboard shortcuts: Left/Right/Home/End, Ctrl+O, P, Space

KaTrain core (source of truth) provides:
  - Move validation (occupied, ko, suicide)
  - Capture computation
  - SGF parsing and game tree

KataGo provides:
  - Position analysis
  - Candidate moves with score and visits

Logging:
  - Set KATRAIN_QT_LOGLEVEL=DEBUG for verbose logging
  - Default level is INFO
"""

import logging
import os
import sys
import uuid
import webbrowser
from pathlib import Path
from typing import List, Optional


# =============================================================================
# Logging Configuration
# =============================================================================

def setup_logging():
    """Configure logging for katrain_qt package."""
    # Get log level from environment (default: INFO)
    level_name = os.environ.get("KATRAIN_QT_LOGLEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Configure root logger for katrain_qt
    logger = logging.getLogger("katrain_qt")
    logger.setLevel(level)

    # Only add handler if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Setup logging early
_logger = setup_logging()

# Now safe to import Qt and adapter
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStatusBar,
    QToolBar,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QMenuBar,
    QMenu,
    QDockWidget,
    QDialog,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QSpinBox,
    QTextEdit,
)

from katrain_qt.core_adapter import GameAdapter
from katrain_qt.widgets.board_widget import GoBoardWidget
from katrain_qt.widgets.candidates_panel import CandidatesPanel
from katrain_qt.widgets.score_graph import ScoreGraphWidget
from katrain_qt.widgets.analysis_panel import AnalysisPanel
from katrain_qt.analysis.katago_engine import KataGoEngine
from katrain_qt.analysis.models import CandidateMove, AnalysisResult, coord_to_display
from katrain_qt.settings import get_settings, Settings
from katrain_qt.dialogs.settings_dialog import SettingsDialog
from katrain_qt.i18n import set_language, tr
from katrain_qt.sound import init_sound_manager, get_sound_manager
from katrain_qt.theme import init_theme_manager, get_theme_manager


# =============================================================================
# Constants
# =============================================================================

DEBOUNCE_MS = 200  # Debounce delay for analysis requests


# =============================================================================
# MainWindow
# =============================================================================

class MainWindow(QMainWindow):
    """Main window with Go board, navigation, and analysis controls."""

    # Base window title (without file/dirty indicators)
    BASE_TITLE = "KaTrain Qt Shell (M4.5)"

    def __init__(self):
        super().__init__()
        self.setMinimumSize(900, 750)

        # Settings manager
        self._settings = get_settings()

        # Initialize language from settings
        set_language(self._settings.language)

        # Initialize sound manager from settings
        init_sound_manager(
            enabled=self._settings.sound_enabled,
            volume=self._settings.sound_volume,
        )

        # Initialize theme manager from settings
        init_theme_manager(self._settings.theme)

        # Game adapter (KaTrain core wrapper)
        self.adapter = GameAdapter(self)

        # KataGo engine
        self.engine = KataGoEngine(self)

        # File state tracking
        self._current_sgf_path: Optional[str] = None  # Path to current SGF file
        self._dirty = False  # True if unsaved changes exist

        # Analysis state
        self._analysis_active = False
        self._current_query_id: Optional[str] = None
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._send_analysis_request)

        # Score series model: move_number -> score_lead (Black perspective)
        self._score_by_move: dict[int, float] = {}

        # Analysis cache: node_id -> AnalysisResult
        # Uses node identity (id()) instead of move_number to handle variations correctly
        self._analysis_cache: dict[int, AnalysisResult] = {}

        # Currently selected candidate index (for PV display)
        self._selected_candidate_idx: int = 0

        # KataGo onboarding: show prompt at most once per session
        self._katago_prompt_shown = False

        # Central widget with horizontal layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Board widget (left side, takes most space)
        self.board_widget = GoBoardWidget()
        main_layout.addWidget(self.board_widget, stretch=3)

        # Connect board to adapter
        self.board_widget.set_stone_provider(self.adapter.get_stones)
        self.board_widget.set_last_move_provider(self.adapter.get_last_move)
        self.board_widget.set_board_size_provider(lambda: self.adapter.board_size)
        self.board_widget.set_next_player_provider(lambda: self.adapter.next_player)

        # Connect click-to-play
        self.board_widget.intersection_clicked.connect(self._on_intersection_clicked)

        # Initial overlay visibility
        self.board_widget.set_show_candidates(True)   # Candidates on by default
        self.board_widget.set_show_ownership(False)   # Ownership off by default

        # Candidates panel (right dock)
        self.candidates_panel = CandidatesPanel()
        candidates_dock = QDockWidget("Candidates", self)
        candidates_dock.setObjectName("CandidatesDock")  # Required for saveState/restoreState
        candidates_dock.setWidget(self.candidates_panel)
        candidates_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, candidates_dock)

        # Analysis panel (right dock, below candidates)
        self.analysis_panel = AnalysisPanel()
        analysis_dock = QDockWidget("Analysis Details", self)
        analysis_dock.setObjectName("AnalysisDetailsDock")  # Required for saveState/restoreState
        analysis_dock.setWidget(self.analysis_panel)
        analysis_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, analysis_dock)

        # Stack candidates and analysis panels vertically
        self.splitDockWidget(candidates_dock, analysis_dock, Qt.Vertical)

        # Connect analysis panel candidate selection
        self.analysis_panel.candidate_selected.connect(self._on_analysis_candidate_selected)

        # Connect candidates panel hover for PV preview
        self.candidates_panel.candidate_hovered.connect(self._on_candidate_hovered)

        # Comment panel (right dock, below analysis) - M5.1b
        self.comment_edit = QTextEdit()
        self.comment_edit.setPlaceholderText("Move comment...")
        self.comment_edit.setMaximumHeight(100)
        self.comment_edit.textChanged.connect(self._on_comment_changed)
        comment_dock = QDockWidget("Comment", self)
        comment_dock.setObjectName("CommentDock")  # Required for saveState/restoreState
        comment_dock.setWidget(self.comment_edit)
        comment_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, comment_dock)
        self.splitDockWidget(analysis_dock, comment_dock, Qt.Vertical)

        # Score graph (bottom dock)
        self.score_graph = ScoreGraphWidget()
        score_dock = QDockWidget("Score Graph", self)
        score_dock.setObjectName("ScoreGraphDock")  # Required for saveState/restoreState
        score_dock.setWidget(self.score_graph)
        score_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, score_dock)

        # Connect score graph click to navigation
        self.score_graph.move_selected.connect(self._on_graph_move_selected)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Move counter label (in status bar)
        self.move_label = QLabel(" Move: 0/0 ")
        self.status_bar.addPermanentWidget(self.move_label)

        # Analysis status label
        self.analysis_label = QLabel(" Analysis: Off ")
        self.status_bar.addPermanentWidget(self.analysis_label)

        # Setup UI
        self._setup_menu()
        self._setup_toolbar()
        self._setup_shortcuts()

        # Connect adapter signals
        self.adapter.position_changed.connect(self._on_position_changed)
        self.adapter.status_changed.connect(self._on_status_changed)
        self.adapter.error_occurred.connect(self._on_error)
        self.board_widget.hover_changed.connect(self._on_hover_changed)
        self.board_widget.context_menu_requested.connect(self._on_board_context_menu)

        # Connect engine signals
        self.engine.ready.connect(self._on_engine_ready)
        self.engine.analysis_received.connect(self._on_analysis_received)
        self.engine.error_occurred.connect(self._on_engine_error)
        self.engine.status_changed.connect(self._on_engine_status)

        # Initial state
        self._update_window_title()
        self.status_bar.showMessage("Ready - Open an SGF file or start a new game")

        # Apply theme
        self._apply_theme()

    # -------------------------------------------------------------------------
    # Theme
    # -------------------------------------------------------------------------

    def _apply_theme(self):
        """Apply the current theme to the application."""
        theme_mgr = get_theme_manager()
        stylesheet = theme_mgr.get_stylesheet()
        self.setStyleSheet(stylesheet)

        # Update board widget colors if theme supports it
        colors = theme_mgr.colors
        if hasattr(self, 'board_widget'):
            self.board_widget.set_board_color(colors.board)
            self.board_widget.set_line_color(colors.board_line)

        # Update stats panel colors (if exists)
        if hasattr(self, 'stats_panel'):
            self.stats_panel.set_theme_colors(
                colors.winrate_good,
                colors.winrate_bad,
                colors.winrate_neutral,
            )

        # Update score graph colors (if exists)
        if hasattr(self, 'score_graph'):
            self.score_graph.set_theme_colors(
                colors.graph_background,
                colors.graph_line,
                colors.graph_zero_line,
            )

    # -------------------------------------------------------------------------
    # Window Title and Dirty State
    # -------------------------------------------------------------------------

    def _update_window_title(self):
        """Update window title with filename and dirty indicator."""
        title = self.BASE_TITLE

        if self._current_sgf_path:
            filename = Path(self._current_sgf_path).name
            title = f"{filename} - {title}"
        elif self.adapter.is_loaded():
            title = f"Untitled - {title}"

        if self._dirty:
            title = f"*{title}"

        self.setWindowTitle(title)

    def _set_dirty(self, dirty: bool = True):
        """Set the dirty state and update window title."""
        if self._dirty != dirty:
            self._dirty = dirty
            self._update_window_title()

    def _check_unsaved_changes(self) -> bool:
        """
        Check for unsaved changes and prompt user if needed.

        Returns:
            True if it's safe to proceed (no changes or user chose to discard).
            False if user cancelled the operation.
        """
        if not self._dirty:
            return True

        filename = Path(self._current_sgf_path).name if self._current_sgf_path else "Untitled"

        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            f"Save changes to '{filename}'?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )

        if result == QMessageBox.Save:
            # Try to save
            if self._current_sgf_path:
                success = self._do_save(self._current_sgf_path)
            else:
                success = self._do_save_as()
            return success
        elif result == QMessageBox.Discard:
            return True
        else:  # Cancel
            return False

    def _do_save(self, path: str) -> bool:
        """
        Save to the given path without showing a dialog.

        Returns True on success, False on failure.
        """
        if not self.adapter.is_loaded():
            return False

        success = self.adapter.save_sgf(path)
        if success:
            self._current_sgf_path = path
            self._set_dirty(False)
            self.status_bar.showMessage(f"Saved: {Path(path).name}", 5000)

            # Update last_sgf_dir
            self._settings.last_sgf_dir = str(Path(path).parent)
            self._settings.save()
        else:
            QMessageBox.warning(
                self,
                "Save Failed",
                f"Failed to save SGF file:\n{path}\n\n"
                "Check that the directory exists and you have write permission."
            )
        return success

    def _do_save_as(self) -> bool:
        """
        Show Save As dialog and save.

        Returns True if saved successfully, False if cancelled or failed.
        """
        if not self.adapter.is_loaded():
            self.status_bar.showMessage("No game to save", 3000)
            return False

        # Use last directory or current file's directory
        start_dir = ""
        if self._current_sgf_path:
            start_dir = str(Path(self._current_sgf_path).parent)
        elif self._settings.last_sgf_dir:
            start_dir = self._settings.last_sgf_dir

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save SGF File",
            start_dir,
            "SGF Files (*.sgf);;All Files (*)"
        )
        if not file_path:
            return False

        # Ensure .sgf extension
        if not file_path.lower().endswith(".sgf"):
            file_path += ".sgf"

        return self._do_save(file_path)

    def closeEvent(self, event):
        """Handle window close - check for unsaved changes and save state."""
        # Check for unsaved changes
        if not self._check_unsaved_changes():
            event.ignore()
            return

        # Stop analysis if running
        if self._analysis_active:
            self._stop_analysis()

        # Stop engine
        if self.engine.is_running():
            self.engine.stop_engine()

        # Save window geometry and state
        self._settings.save_window_geometry(self.saveGeometry())
        self._settings.save_window_state(self.saveState())
        self._settings.sync()

        event.accept()

    def _setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New Game", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._new_game)
        file_menu.addAction(new_action)

        open_action = QAction("&Open SGF...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_sgf)
        file_menu.addAction(open_action)

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._save_sgf)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self._save_sgf_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Navigate menu
        nav_menu = menubar.addMenu("&Navigate")

        first_action = QAction("&First", self)
        first_action.setShortcut(QKeySequence.MoveToStartOfDocument)
        first_action.triggered.connect(self._nav_first)
        nav_menu.addAction(first_action)

        prev_action = QAction("&Previous", self)
        prev_action.setShortcut(QKeySequence.MoveToPreviousChar)
        prev_action.triggered.connect(self._nav_prev)
        nav_menu.addAction(prev_action)

        next_action = QAction("&Next", self)
        next_action.setShortcut(QKeySequence.MoveToNextChar)
        next_action.triggered.connect(self._nav_next)
        nav_menu.addAction(next_action)

        last_action = QAction("&Last", self)
        last_action.setShortcut(QKeySequence.MoveToEndOfDocument)
        last_action.triggered.connect(self._nav_last)
        nav_menu.addAction(last_action)

        # Analysis menu
        analysis_menu = menubar.addMenu("&Analysis")

        self.start_analysis_action = QAction("&Start Analysis", self)
        self.start_analysis_action.setShortcut(Qt.Key_Space)
        self.start_analysis_action.triggered.connect(self._toggle_analysis)
        analysis_menu.addAction(self.start_analysis_action)

        analysis_menu.addSeparator()

        configure_action = QAction("&Configure KataGo...", self)
        configure_action.triggered.connect(self._configure_katago)
        analysis_menu.addAction(configure_action)

        # View menu (display options)
        view_menu = menubar.addMenu("&View")

        self.show_candidates_action = QAction("Show &Candidates", self)
        self.show_candidates_action.setCheckable(True)
        self.show_candidates_action.setChecked(True)  # Default on
        self.show_candidates_action.setShortcut("C")
        self.show_candidates_action.triggered.connect(self._toggle_candidates)
        view_menu.addAction(self.show_candidates_action)

        self.show_ownership_action = QAction("Show &Territory", self)
        self.show_ownership_action.setCheckable(True)
        self.show_ownership_action.setChecked(False)  # Default off
        self.show_ownership_action.setShortcut("T")
        self.show_ownership_action.triggered.connect(self._toggle_ownership)
        view_menu.addAction(self.show_ownership_action)

        # Edit menu (Settings)
        edit_menu = menubar.addMenu("&Edit")

        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut(QKeySequence.Preferences)
        settings_action.triggered.connect(self._show_settings)
        edit_menu.addAction(settings_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        """Setup navigation toolbar."""
        toolbar = QToolBar("Navigation")
        toolbar.setObjectName("NavigationToolbar")  # Required for saveState/restoreState
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Navigation buttons
        self.btn_first = QPushButton("|<")
        self.btn_first.setToolTip("First move (Home)")
        self.btn_first.clicked.connect(self._nav_first)
        toolbar.addWidget(self.btn_first)

        self.btn_prev = QPushButton("<")
        self.btn_prev.setToolTip("Previous move (Left)")
        self.btn_prev.clicked.connect(self._nav_prev)
        toolbar.addWidget(self.btn_prev)

        self.btn_next = QPushButton(">")
        self.btn_next.setToolTip("Next move (Right)")
        self.btn_next.clicked.connect(self._nav_next)
        toolbar.addWidget(self.btn_next)

        self.btn_last = QPushButton(">|")
        self.btn_last.setToolTip("Last move (End)")
        self.btn_last.clicked.connect(self._nav_last)
        toolbar.addWidget(self.btn_last)

        toolbar.addSeparator()

        # Variation navigation (M5.1a)
        self.btn_prev_var = QPushButton("^")
        self.btn_prev_var.setToolTip("Previous variation (Ctrl+Up)")
        self.btn_prev_var.clicked.connect(self._nav_prev_variation)
        self.btn_prev_var.setFixedWidth(30)
        toolbar.addWidget(self.btn_prev_var)

        self.lbl_variation = QLabel("Var 1/1")
        self.lbl_variation.setFixedWidth(60)
        self.lbl_variation.setToolTip("Current variation / total siblings")
        toolbar.addWidget(self.lbl_variation)

        self.btn_next_var = QPushButton("v")
        self.btn_next_var.setToolTip("Next variation (Ctrl+Down)")
        self.btn_next_var.clicked.connect(self._nav_next_variation)
        self.btn_next_var.setFixedWidth(30)
        toolbar.addWidget(self.btn_next_var)

        toolbar.addSeparator()

        # Pass button
        self.btn_pass = QPushButton("Pass")
        self.btn_pass.setToolTip("Pass (P)")
        self.btn_pass.clicked.connect(self._play_pass)
        toolbar.addWidget(self.btn_pass)

        toolbar.addSeparator()

        # Analysis buttons
        self.btn_analysis = QPushButton("Start Analysis")
        self.btn_analysis.setToolTip("Toggle analysis (Space)")
        self.btn_analysis.clicked.connect(self._toggle_analysis)
        toolbar.addWidget(self.btn_analysis)

        toolbar.addSeparator()

        # Open button
        self.btn_open = QPushButton("Open SGF")
        self.btn_open.setToolTip("Open SGF file (Ctrl+O)")
        self.btn_open.clicked.connect(self._open_sgf)
        toolbar.addWidget(self.btn_open)

        # New Game button
        self.btn_new = QPushButton("New Game")
        self.btn_new.setToolTip("Start new game (Ctrl+N)")
        self.btn_new.clicked.connect(self._new_game)
        toolbar.addWidget(self.btn_new)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Additional shortcuts that may not be covered by menu actions
        QShortcut(Qt.Key_Left, self, self._nav_prev)
        QShortcut(Qt.Key_Right, self, self._nav_next)
        QShortcut(Qt.Key_Home, self, self._nav_first)
        QShortcut(Qt.Key_End, self, self._nav_last)
        QShortcut(Qt.Key_P, self, self._play_pass)
        QShortcut(Qt.Key_Space, self, self._toggle_analysis)
        # Variation navigation (M5.1a)
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Up), self, self._nav_prev_variation)
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Down), self, self._nav_next_variation)
        # Number keys 1-9 to select candidate moves (Kivy parity)
        for i in range(1, 10):
            QShortcut(
                getattr(Qt, f"Key_{i}"),
                self,
                lambda idx=i: self._select_candidate_by_rank(idx),
            )

    # -------------------------------------------------------------------------
    # Adapter Slots
    # -------------------------------------------------------------------------

    @Slot()
    def _on_position_changed(self):
        """Update UI when board position changes."""
        self.board_widget.update()
        self._update_move_label()
        self._update_variation_label()
        self._update_comment_panel()

        # Update score graph current move marker
        self.score_graph.set_current_move(self.adapter.current_move_number)

        # Update analysis panel (uses cache if available)
        self._update_analysis_panel()

        # Trigger analysis if active
        if self._analysis_active:
            self._request_analysis_debounced()

    @Slot(str)
    def _on_status_changed(self, message: str):
        """Show status message."""
        self.status_bar.showMessage(message, 5000)

    @Slot(str)
    def _on_error(self, message: str):
        """Show error message."""
        self.status_bar.showMessage(f"Error: {message}")
        QMessageBox.warning(self, "Error", message)

    @Slot(int, int, bool)
    def _on_hover_changed(self, col: int, row: int, valid: bool):
        """Update status bar with hover info."""
        if not self.adapter.is_loaded():
            return

        if valid and col >= 0 and row >= 0:
            coord = coord_to_display(col, row, self.adapter.board_size)
            next_player = "Black" if self.adapter.next_player == "B" else "White"
            stones = self.adapter.get_stones()
            occupied = " (occupied)" if (col, row) in stones else ""
            self.status_bar.showMessage(f"Position: {coord} - Next: {next_player}{occupied}")
        else:
            self._update_move_label()

    @Slot(int, int)
    def _on_intersection_clicked(self, col: int, row: int):
        """Handle click on board intersection - attempt to play move."""
        if not self.adapter.is_loaded():
            return

        success, message = self.adapter.play_move_qt(col, row)
        if success:
            self._set_dirty(True)  # Mark dirty on successful move
            self.status_bar.showMessage(message, 3000)
            # Play stone sound
            get_sound_manager().play_stone()
        else:
            # Show illegal move reason
            self.status_bar.showMessage(message, 5000)
            # Play error sound for illegal move
            get_sound_manager().play_boing()

    @Slot(int, int, object)
    def _on_board_context_menu(self, col: int, row: int, global_pos):
        """Show context menu on right-click."""
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)

        # Analysis actions
        if self._analysis_active:
            stop_action = menu.addAction("Stop Analysis")
            stop_action.triggered.connect(self._stop_analysis)
        else:
            start_action = menu.addAction("Start Analysis")
            start_action.triggered.connect(self._start_analysis)

        menu.addSeparator()

        # Navigation actions
        nav_menu = menu.addMenu("Navigate")
        nav_menu.addAction("First Move", self._nav_first)
        nav_menu.addAction("Previous Move", self._nav_prev)
        nav_menu.addAction("Next Move", self._nav_next)
        nav_menu.addAction("Last Move", self._nav_last)

        menu.addSeparator()

        # Game actions
        pass_action = menu.addAction("Pass")
        pass_action.triggered.connect(self._play_pass)

        menu.addSeparator()

        # View toggles
        view_menu = menu.addMenu("View")
        show_coords = view_menu.addAction("Show Coordinates")
        show_coords.setCheckable(True)
        show_coords.setChecked(self.show_coords_action.isChecked())
        show_coords.triggered.connect(self._toggle_coordinates)

        show_cands = view_menu.addAction("Show Candidates")
        show_cands.setCheckable(True)
        show_cands.setChecked(self.show_candidates_action.isChecked())
        show_cands.triggered.connect(self._toggle_candidates)

        show_ownership = view_menu.addAction("Show Ownership")
        show_ownership.setCheckable(True)
        show_ownership.setChecked(self.show_ownership_action.isChecked())
        show_ownership.triggered.connect(self._toggle_ownership)

        menu.exec(global_pos)

    def _update_move_label(self):
        """Update the move counter label."""
        if self.adapter.is_loaded():
            current = self.adapter.current_move_number
            total = self.adapter.total_moves
            self.move_label.setText(f" Move: {current}/{total} ")

            # Show player info
            next_player = "Black" if self.adapter.next_player == "B" else "White"
            last_move = self.adapter.get_last_move()
            if last_move:
                lc, lr, lp = last_move
                coord = coord_to_display(lc, lr, self.adapter.board_size)
                player = "Black" if lp == "B" else "White"
                self.status_bar.showMessage(f"Last: {player} {coord} - Next: {next_player}")
            else:
                self.status_bar.showMessage(f"Next: {next_player}")
        else:
            self.move_label.setText(" Move: 0/0 ")

    def _update_score_graph(self):
        """Rebuild and update score graph series from stored scores."""
        if not self.adapter.is_loaded():
            self.score_graph.clear()
            return

        # Build series: list of scores indexed by move number
        total = self.adapter.total_moves
        series: List[Optional[float]] = []
        for i in range(total + 1):  # Include move 0
            series.append(self._score_by_move.get(i))

        self.score_graph.set_series(series)
        self.score_graph.set_current_move(self.adapter.current_move_number)

        # Find blunders (large score swings >= 5.0 points)
        blunder_threshold = 5.0
        blunder_moves: List[int] = []
        for i in range(1, len(series)):
            prev_score = series[i - 1]
            curr_score = series[i]
            if prev_score is not None and curr_score is not None:
                # Score difference (absolute value of swing)
                diff = abs(curr_score - prev_score)
                if diff >= blunder_threshold:
                    blunder_moves.append(i)
        self.score_graph.set_blunder_moves(blunder_moves)

    def _clear_score_data(self):
        """Clear score series data, analysis cache, and update graph."""
        self._score_by_move.clear()
        self._analysis_cache.clear()
        self._selected_candidate_idx = 0
        self.score_graph.clear()
        self.analysis_panel.clear()

    def _update_analysis_panel(self, result: Optional[AnalysisResult] = None):
        """
        Update analysis panel with current position and analysis.

        If result is None, tries to use cached analysis for current move.
        """
        if not self.adapter.is_loaded():
            self.analysis_panel.clear()
            return

        # Update position info
        self.analysis_panel.set_board_size(self.adapter.board_size)
        self.analysis_panel.set_position_info(
            move_number=self.adapter.current_move_number,
            next_player=self.adapter.next_player,
            last_move=self.adapter.get_last_move(),
        )

        # Use provided result or try cache (by node_id for variation safety)
        if result is None:
            node_id = self.adapter.current_node_id
            result = self._analysis_cache.get(node_id)
            if result is None:
                # Clear stale ownership overlay when navigating to unanalyzed node
                self.board_widget.clear_ownership()

        self.analysis_panel.set_analysis(result)

    @Slot(int)
    def _on_graph_move_selected(self, move_no: int):
        """Handle click on score graph to navigate to move."""
        if self.adapter.is_loaded():
            self.adapter.nav_to_move(move_no)

    @Slot(int)
    def _on_analysis_candidate_selected(self, idx: int):
        """Handle candidate selection from analysis panel."""
        self._selected_candidate_idx = idx
        # Optionally update board overlay to highlight selected candidate
        # (not implemented in this milestone)

    @Slot(int, list, str)
    def _on_candidate_hovered(self, row_index: int, pv: list, starting_color: str):
        """Handle candidate hover - show PV preview on board."""
        if row_index < 0 or not pv:
            # Clear PV preview
            self.board_widget.clear_pv_preview()
        else:
            # Show PV preview
            self.board_widget.set_pv_preview(pv, starting_color)

    # -------------------------------------------------------------------------
    # Engine Slots
    # -------------------------------------------------------------------------

    @Slot()
    def _on_engine_ready(self):
        """Handle engine ready."""
        self.analysis_label.setText(" Analysis: Ready ")
        # Send initial analysis if we have a position
        if self._analysis_active and self.adapter.is_loaded():
            self._request_analysis_debounced()

    @Slot(object)
    def _on_analysis_received(self, result: AnalysisResult):
        """Handle analysis result from KataGo."""
        # Filter stale responses
        if result.query_id != self._current_query_id:
            return

        # Cache result by node_id (handles variations correctly)
        node_id = self.adapter.current_node_id
        self._analysis_cache[node_id] = result

        # Update candidates panel
        self.candidates_panel.set_board_size(self.adapter.board_size)
        self.candidates_panel.set_next_player(result.next_player)
        self.candidates_panel.set_candidates(result.candidates)

        # Update board overlay
        self.board_widget.set_candidates(result.candidates)

        # Update ownership overlay
        if result.ownership:
            self.board_widget.set_ownership(result.ownership)

        # Store score by move number for graph (still uses move_no for visualization)
        move_no = self.adapter.current_move_number
        if result.score_lead_black is not None:
            self._score_by_move[move_no] = result.score_lead_black
            self._update_score_graph()

        # Update analysis panel
        self._update_analysis_panel(result)

        # Update status
        best = result.best_move()
        if best:
            coord = coord_to_display(best.col, best.row, self.adapter.board_size)
            # Show score from to-play perspective in status
            score_to_play = result.score_lead_to_play()
            score_str = f"{score_to_play:+.1f}" if score_to_play is not None else "?"
            self.analysis_label.setText(f" Best: {coord} ({score_str}) ")

    @Slot(str)
    def _on_engine_error(self, message: str):
        """Handle engine error with actionable dialog for critical errors."""
        self.status_bar.showMessage(f"KataGo: {message}", 5000)

        # Show detailed dialog for startup failures
        if "not found" in message.lower() or "failed to start" in message.lower():
            QMessageBox.critical(
                self,
                "KataGo Error",
                f"{message}\n\n"
                "To fix this:\n"
                "1. Go to Edit → Settings\n"
                "2. Set the correct paths for:\n"
                "   - KataGo executable\n"
                "   - Config file (analysis.cfg)\n"
                "   - Model file (.bin.gz)\n\n"
                "Or set environment variables:\n"
                "   KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL"
            )
            # Stop analysis state
            if self._analysis_active:
                self._stop_analysis()
        elif "crashed" in message.lower() or "exited" in message.lower():
            QMessageBox.warning(
                self,
                "KataGo Stopped",
                f"{message}\n\n"
                "KataGo stopped unexpectedly. Check that:\n"
                "- The config file is compatible with your KataGo version\n"
                "- The model file is valid and not corrupted\n"
                "- Your system has enough memory"
            )
            if self._analysis_active:
                self._stop_analysis()

    @Slot(str)
    def _on_engine_status(self, message: str):
        """Handle engine status change."""
        self.analysis_label.setText(f" {message} ")

    # -------------------------------------------------------------------------
    # View Toggles
    # -------------------------------------------------------------------------

    def _toggle_candidates(self):
        """Toggle candidate move overlay display."""
        show = self.show_candidates_action.isChecked()
        self.board_widget.set_show_candidates(show)

    def _toggle_ownership(self):
        """Toggle territory (ownership) overlay display."""
        show = self.show_ownership_action.isChecked()
        self.board_widget.set_show_ownership(show)

    # -------------------------------------------------------------------------
    # Analysis Control
    # -------------------------------------------------------------------------

    def _toggle_analysis(self):
        """Toggle analysis on/off."""
        if self._analysis_active:
            self._stop_analysis()
        else:
            self._start_analysis()

    def _start_analysis(self):
        """Start KataGo analysis."""
        if not self.adapter.is_loaded():
            self.status_bar.showMessage("Load a game or start new game first", 3000)
            return

        # Check board size (19x19 only for now)
        if self.adapter.board_size != 19:
            QMessageBox.warning(
                self,
                "Unsupported Board Size",
                f"Analysis only supports 19x19 boards.\n"
                f"Current board is {self.adapter.board_size}x{self.adapter.board_size}."
            )
            return

        # Check if paths are configured (uses Settings with env var support)
        if not self._settings.katago_exe or not self._settings.config_path or not self._settings.model_path:
            result = QMessageBox.question(
                self,
                "Configure KataGo",
                "KataGo is not configured. Would you like to configure it now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if result == QMessageBox.Yes:
                self._show_settings()
            else:
                return

            # Re-check after settings dialog
            if not self._settings.katago_exe or not self._settings.config_path or not self._settings.model_path:
                return

        # Start engine if not running
        if not self.engine.is_running():
            success = self.engine.start_engine(
                exe_path=self._settings.katago_exe,
                config_path=self._settings.config_path,
                model_path=self._settings.model_path,
                max_visits=self._settings.max_visits,
                rules=self.adapter.rules,
            )
            if not success:
                return

        self._analysis_active = True
        self.board_widget.set_show_candidates(True)
        self.show_candidates_action.setChecked(True)  # Sync menu checkbox
        self.btn_analysis.setText("Stop Analysis")
        self.start_analysis_action.setText("&Stop Analysis")
        self.analysis_label.setText(" Analysis: Running ")

        # Request analysis for current position
        self._request_analysis_debounced()

    def _stop_analysis(self):
        """Stop KataGo analysis."""
        self._analysis_active = False
        self._debounce_timer.stop()
        self._current_query_id = None

        # Clear display
        self.board_widget.set_show_candidates(False)
        self.board_widget.clear_candidates()
        self.board_widget.clear_ownership()
        self.candidates_panel.clear()
        self.analysis_panel.clear()

        # Update UI
        self.btn_analysis.setText("Start Analysis")
        self.start_analysis_action.setText("&Start Analysis")

        if self.engine.is_running():
            self.engine.stop_engine()
            self.analysis_label.setText(" Analysis: Off ")
        else:
            self.analysis_label.setText(" Analysis: Off ")

    def _request_analysis_debounced(self):
        """Request analysis with debounce."""
        self._debounce_timer.start(DEBOUNCE_MS)

    def _send_analysis_request(self):
        """Actually send analysis request to KataGo."""
        if not self._analysis_active:
            return

        if not self.adapter.is_loaded():
            return

        snapshot = self.adapter.get_position_snapshot()
        if snapshot is None:
            return

        # Generate new query ID
        self._current_query_id = str(uuid.uuid4())[:8]

        # Send request
        self.engine.request_analysis(snapshot, self._current_query_id)

    def _configure_katago(self):
        """Show KataGo configuration dialog (redirects to Settings)."""
        self._show_settings()

    def _show_settings(self):
        """Show the settings dialog."""
        dialog = SettingsDialog(self, self._settings)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()

    def _on_settings_changed(self):
        """Handle settings changes."""
        self.status_bar.showMessage("Settings saved", 3000)
        # Update language
        set_language(self._settings.language)
        # Update sound settings
        sound_mgr = get_sound_manager()
        sound_mgr.enabled = self._settings.sound_enabled
        sound_mgr.volume = self._settings.sound_volume
        # Update theme
        theme_mgr = get_theme_manager()
        theme_mgr.set_theme(self._settings.theme)
        self._apply_theme()
        # Refresh candidates panel columns (for dev features like Loss column)
        self.candidates_panel.refresh_columns()
        # If analysis is running, restart engine with new settings
        if self._analysis_active:
            self.status_bar.showMessage("Settings saved - restart analysis to apply changes", 5000)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def _open_sgf(self):
        """Open SGF file dialog."""
        # Check for unsaved changes first
        if not self._check_unsaved_changes():
            return

        # Use last directory or empty
        start_dir = self._settings.last_sgf_dir or ""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open SGF File",
            start_dir,
            "SGF Files (*.sgf);;All Files (*)"
        )
        if file_path:
            # Remember directory
            self._settings.last_sgf_dir = str(Path(file_path).parent)
            self._settings.save()

            # Stop analysis before loading
            if self._analysis_active:
                self._stop_analysis()

            # Clear old score data
            self._clear_score_data()

            success = self.adapter.load_sgf_file(file_path)
            if success:
                # Update file state
                self._current_sgf_path = file_path
                self._set_dirty(False)
                self._update_window_title()

                # Check board size (Qt shell supports 9x9, 13x13, 19x19)
                size = self.adapter.board_size
                if size not in (9, 13, 19):
                    QMessageBox.warning(
                        self,
                        "Unsupported Board Size",
                        f"Board size {size}x{size} may not display correctly.\n"
                        "Supported sizes: 9x9, 13x13, 19x19"
                    )

    def _save_sgf(self):
        """Save current game to SGF file (Save command)."""
        if not self.adapter.is_loaded():
            self.status_bar.showMessage("No game to save", 3000)
            return

        # If we have a current path, save directly; otherwise show Save As dialog
        if self._current_sgf_path:
            self._do_save(self._current_sgf_path)
        else:
            self._do_save_as()

    def _save_sgf_as(self):
        """Save current game to a new SGF file (Save As command)."""
        self._do_save_as()

    def _nav_first(self):
        """Navigate to first move."""
        self.adapter.nav_first()

    def _nav_prev(self):
        """Navigate to previous move."""
        self.adapter.nav_prev()

    def _nav_next(self):
        """Navigate to next move."""
        self.adapter.nav_next()

    def _nav_last(self):
        """Navigate to last move."""
        self.adapter.nav_last()

    def _nav_prev_variation(self):
        """Navigate to previous variation (M5.1a)."""
        if self.adapter.nav_prev_variation():
            self.status_bar.showMessage("Switched to previous variation", 2000)

    def _nav_next_variation(self):
        """Navigate to next variation (M5.1a)."""
        if self.adapter.nav_next_variation():
            self.status_bar.showMessage("Switched to next variation", 2000)

    def _update_variation_label(self):
        """Update variation display label (M5.1a)."""
        if not self.adapter.is_loaded():
            self.lbl_variation.setText("Var -/-")
            self.btn_prev_var.setEnabled(False)
            self.btn_next_var.setEnabled(False)
            return

        sibling_count = self.adapter.get_sibling_count()
        current_idx = self.adapter.get_current_variation_index()

        if sibling_count <= 1:
            self.lbl_variation.setText("Var 1/1")
            self.btn_prev_var.setEnabled(False)
            self.btn_next_var.setEnabled(False)
        else:
            self.lbl_variation.setText(f"Var {current_idx + 1}/{sibling_count}")
            self.btn_prev_var.setEnabled(True)
            self.btn_next_var.setEnabled(True)

    def _update_comment_panel(self):
        """Update comment panel with current node's comment (M5.1b)."""
        # Block signals to prevent feedback loop
        self.comment_edit.blockSignals(True)
        try:
            if self.adapter.is_loaded():
                self.comment_edit.setText(self.adapter.get_comment())
                self.comment_edit.setEnabled(True)
            else:
                self.comment_edit.clear()
                self.comment_edit.setEnabled(False)
        finally:
            self.comment_edit.blockSignals(False)

    def _on_comment_changed(self):
        """Handle comment text changes (M5.1b)."""
        if not self.adapter.is_loaded():
            return

        new_text = self.comment_edit.toPlainText()
        if self.adapter.set_comment(new_text):
            self._set_dirty(True)

    def _play_pass(self):
        """Play a pass move."""
        if not self.adapter.is_loaded():
            self.status_bar.showMessage("No game loaded", 3000)
            return

        success, message = self.adapter.play_pass()
        if success:
            self._set_dirty(True)  # Mark dirty on successful pass
            self.status_bar.showMessage(message, 3000)
        else:
            self.status_bar.showMessage(message, 5000)

    def _select_candidate_by_rank(self, rank: int):
        """Select and play a candidate move by its rank (1-9)."""
        if not self.adapter.is_loaded():
            return

        # Get candidates from the panel
        candidates = self.candidates_panel._candidates
        if not candidates:
            self.status_bar.showMessage("No candidates available", 3000)
            return

        # Find candidate with matching rank
        for cand in candidates:
            if cand.rank == rank:
                # Play the move
                success, message = self.adapter.play_move_qt(cand.col, cand.row)
                if success:
                    self._set_dirty(True)
                    self.status_bar.showMessage(f"Played candidate #{rank}", 3000)
                    # Play stone sound
                    if hasattr(self, '_sound_manager'):
                        self._sound_manager.play_stone()
                else:
                    self.status_bar.showMessage(message, 5000)
                return

        self.status_bar.showMessage(f"No candidate with rank {rank}", 3000)

    def _new_game(self):
        """Start a new empty game."""
        # Check for unsaved changes first
        if not self._check_unsaved_changes():
            return

        # Stop analysis before new game
        if self._analysis_active:
            self._stop_analysis()

        # Clear old score data
        self._clear_score_data()

        self.adapter.new_game(size=19)

        # Reset file state
        self._current_sgf_path = None
        self._set_dirty(False)
        self._update_window_title()

        self.status_bar.showMessage("New 19x19 game started", 3000)

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About KaTrain Qt Shell",
            "KaTrain Qt Shell (M4.5 - MVR)\n\n"
            "A Qt frontend for KaTrain core.\n\n"
            "Features:\n"
            "- SGF file loading and saving (Save/Save As)\n"
            "- Unsaved changes prompt\n"
            "- Navigation (First/Prev/Next/Last)\n"
            "- Click-to-play (captures/ko handled by core)\n"
            "- Pass (P key or toolbar button)\n"
            "- KataGo analysis (Space to toggle)\n"
            "- Score graph with navigation\n"
            "- Analysis panel with PV display\n"
            "- Settings persistence\n\n"
            "KaTrain core provides:\n"
            "- SGF parsing\n"
            "- Move validation\n"
            "- Capture computation\n"
            "- Ko rule enforcement\n\n"
            "KataGo provides:\n"
            "- Position analysis\n"
            "- Candidate move evaluation\n\n"
            "This is a development milestone, not a full application."
        )

    # -------------------------------------------------------------------------
    # Window State Persistence
    # -------------------------------------------------------------------------

    def showEvent(self, event):
        """Restore window geometry on show."""
        super().showEvent(event)

        # Only restore on first show (avoid repeated restores on minimize/restore)
        if not hasattr(self, '_geometry_restored'):
            self._geometry_restored = True

            # Restore window geometry
            geometry = self._settings.load_window_geometry()
            if geometry:
                self.restoreGeometry(geometry)

            # Restore dock/window state
            state = self._settings.load_window_state()
            if state:
                self.restoreState(state)

            # Check KataGo configuration on first show
            self._check_katago_on_startup()

    def _check_katago_on_startup(self):
        """
        Check if KataGo is configured on first startup.

        If not configured, show a friendly dialog with options:
        - Open Settings: opens settings dialog
        - Download KataGo: opens browser to GitHub releases
        - Later: dismiss and continue without analysis
        """
        # Only show once per session
        if self._katago_prompt_shown:
            return

        # Check if all paths are configured
        katago_exe = self._settings.katago_exe
        config_path = self._settings.config_path
        model_path = self._settings.model_path

        # If all are configured, no prompt needed
        if katago_exe and config_path and model_path:
            return

        # Mark as shown (regardless of user choice)
        self._katago_prompt_shown = True

        # Build the message
        missing = []
        if not katago_exe:
            missing.append("- KataGo executable")
        if not config_path:
            missing.append("- Analysis config file")
        if not model_path:
            missing.append("- Neural network model")

        msg = QMessageBox(self)
        msg.setWindowTitle("KataGo Not Configured")
        msg.setIcon(QMessageBox.Information)
        msg.setText("KataGo is required for game analysis.")
        msg.setInformativeText(
            "The following paths are not configured:\n" +
            "\n".join(missing) +
            "\n\nYou can still view and edit SGF files without analysis."
        )

        # Custom buttons
        settings_btn = msg.addButton("Open Settings", QMessageBox.AcceptRole)
        download_btn = msg.addButton("Download KataGo...", QMessageBox.ActionRole)
        later_btn = msg.addButton("Later", QMessageBox.RejectRole)

        msg.setDefaultButton(settings_btn)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == settings_btn:
            # Open settings dialog
            self._show_settings()
        elif clicked == download_btn:
            # Open browser to KataGo releases
            webbrowser.open("https://github.com/lightvector/KataGo/releases")



# =============================================================================
# Main
# =============================================================================

def main():
    """Entry point for the Qt shell."""
    app = QApplication(sys.argv)
    app.setApplicationName("KaTrain Qt Shell")
    app.setOrganizationName("KaTrain")

    window = MainWindow()

    # Only resize if no saved geometry
    if not window._settings.load_window_geometry():
        window.resize(1000, 800)

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

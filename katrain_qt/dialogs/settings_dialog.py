"""
Settings Dialog for KaTrain Qt.

Provides a tabbed dialog for configuring:
- KataGo paths (executable, config, model)
- Analysis parameters (max visits, max candidates)
- Game defaults (komi, rules)

Environment variable overrides are displayed but not editable.
"""

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QGroupBox,
    QFormLayout,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
)

from katrain_qt.settings import Settings, get_settings


# =============================================================================
# Settings Dialog
# =============================================================================

class SettingsDialog(QDialog):
    """
    Settings dialog with tabs for KataGo, Analysis, and Game settings.

    Signals:
        settings_changed: Emitted when settings are saved
    """

    settings_changed = Signal()

    def __init__(self, parent=None, settings: Settings = None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._settings = settings or get_settings()
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        """Create the dialog layout."""
        layout = QVBoxLayout(self)

        # Tab widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Create tabs
        self._create_katago_tab()
        self._create_analysis_tab()
        self._create_game_tab()

        # Button box
        button_box = QDialogButtonBox()
        self._save_btn = button_box.addButton("Save", QDialogButtonBox.AcceptRole)
        self._cancel_btn = button_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        self._reset_btn = button_box.addButton("Reset to Defaults", QDialogButtonBox.ResetRole)
        self._open_folder_btn = button_box.addButton("Open Settings Folder", QDialogButtonBox.ActionRole)

        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn.clicked.connect(self.reject)
        self._reset_btn.clicked.connect(self._on_reset)
        self._open_folder_btn.clicked.connect(self._on_open_folder)

        layout.addWidget(button_box)

    def _create_katago_tab(self):
        """Create KataGo paths tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Paths group
        paths_group = QGroupBox("KataGo Paths")
        paths_layout = QFormLayout(paths_group)

        # Executable
        exe_layout = QHBoxLayout()
        self._exe_edit = QLineEdit()
        self._exe_edit.setPlaceholderText("Path to KataGo executable")
        self._exe_browse = QPushButton("Browse...")
        self._exe_browse.clicked.connect(lambda: self._browse_file(self._exe_edit, "KataGo Executable", ""))
        exe_layout.addWidget(self._exe_edit)
        exe_layout.addWidget(self._exe_browse)

        exe_row = QWidget()
        exe_row.setLayout(exe_layout)
        paths_layout.addRow("Executable:", exe_row)

        # Env override indicator for exe
        self._exe_env_label = QLabel()
        self._exe_env_label.setStyleSheet("color: gray; font-style: italic;")
        paths_layout.addRow("", self._exe_env_label)

        # Config
        config_layout = QHBoxLayout()
        self._config_edit = QLineEdit()
        self._config_edit.setPlaceholderText("Path to analysis config file")
        self._config_browse = QPushButton("Browse...")
        self._config_browse.clicked.connect(lambda: self._browse_file(self._config_edit, "Config File", "Config Files (*.cfg);;All Files (*)"))
        config_layout.addWidget(self._config_edit)
        config_layout.addWidget(self._config_browse)

        config_row = QWidget()
        config_row.setLayout(config_layout)
        paths_layout.addRow("Config:", config_row)

        # Env override indicator for config
        self._config_env_label = QLabel()
        self._config_env_label.setStyleSheet("color: gray; font-style: italic;")
        paths_layout.addRow("", self._config_env_label)

        # Model
        model_layout = QHBoxLayout()
        self._model_edit = QLineEdit()
        self._model_edit.setPlaceholderText("Path to neural network model")
        self._model_browse = QPushButton("Browse...")
        self._model_browse.clicked.connect(lambda: self._browse_file(self._model_edit, "Model File", "Model Files (*.bin.gz *.gz);;All Files (*)"))
        model_layout.addWidget(self._model_edit)
        model_layout.addWidget(self._model_browse)

        model_row = QWidget()
        model_row.setLayout(model_layout)
        paths_layout.addRow("Model:", model_row)

        # Env override indicator for model
        self._model_env_label = QLabel()
        self._model_env_label.setStyleSheet("color: gray; font-style: italic;")
        paths_layout.addRow("", self._model_env_label)

        layout.addWidget(paths_group)

        # Info label
        info_label = QLabel(
            "Note: Environment variables (KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL) "
            "override these settings when set."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray;")
        layout.addWidget(info_label)

        layout.addStretch()
        self._tabs.addTab(tab, "KataGo")

    def _create_analysis_tab(self):
        """Create analysis parameters tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Analysis group
        analysis_group = QGroupBox("Analysis Parameters")
        analysis_layout = QFormLayout(analysis_group)

        # Max visits
        self._visits_spin = QSpinBox()
        self._visits_spin.setRange(1, 100000)
        self._visits_spin.setSingleStep(100)
        self._visits_spin.setSuffix(" visits")
        analysis_layout.addRow("Max Visits:", self._visits_spin)

        visits_help = QLabel("Higher values give more accurate analysis but take longer.")
        visits_help.setStyleSheet("color: gray; font-size: 10px;")
        analysis_layout.addRow("", visits_help)

        # Max candidates
        self._candidates_spin = QSpinBox()
        self._candidates_spin.setRange(1, 20)
        self._candidates_spin.setSuffix(" moves")
        analysis_layout.addRow("Max Candidates:", self._candidates_spin)

        candidates_help = QLabel("Number of candidate moves to display in analysis.")
        candidates_help.setStyleSheet("color: gray; font-size: 10px;")
        analysis_layout.addRow("", candidates_help)

        layout.addWidget(analysis_group)
        layout.addStretch()
        self._tabs.addTab(tab, "Analysis")

    def _create_game_tab(self):
        """Create game defaults tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Game defaults group
        game_group = QGroupBox("Game Defaults")
        game_layout = QFormLayout(game_group)

        # Komi
        self._komi_spin = QDoubleSpinBox()
        self._komi_spin.setRange(-100.0, 100.0)
        self._komi_spin.setSingleStep(0.5)
        self._komi_spin.setDecimals(1)
        game_layout.addRow("Komi:", self._komi_spin)

        # Rules
        self._rules_combo = QComboBox()
        self._rules_combo.addItems([
            "japanese",
            "chinese",
            "korean",
            "aga",
            "new-zealand",
            "tromp-taylor",
        ])
        game_layout.addRow("Rules:", self._rules_combo)

        layout.addWidget(game_group)
        layout.addStretch()
        self._tabs.addTab(tab, "Game")

    def _browse_file(self, edit: QLineEdit, title: str, filter: str):
        """Open file browser and set result to edit field."""
        current = edit.text()
        start_dir = str(Path(current).parent) if current and Path(current).exists() else ""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {title}",
            start_dir,
            filter if filter else "All Files (*)",
        )

        if file_path:
            edit.setText(file_path)

    def _load_values(self):
        """Load current settings into UI fields."""
        # KataGo paths - show saved values (not env-overridden)
        self._exe_edit.setText(self._settings._settings.katago_exe)
        self._config_edit.setText(self._settings._settings.config_path)
        self._model_edit.setText(self._settings._settings.model_path)

        # Update env override indicators
        self._update_env_indicators()

        # Analysis
        self._visits_spin.setValue(self._settings.max_visits)
        self._candidates_spin.setValue(self._settings.max_candidates)

        # Game
        self._komi_spin.setValue(self._settings.komi)
        rules_idx = self._rules_combo.findText(self._settings.rules)
        if rules_idx >= 0:
            self._rules_combo.setCurrentIndex(rules_idx)

    def _update_env_indicators(self):
        """Update environment variable override indicators."""
        if self._settings.is_katago_exe_from_env():
            self._exe_env_label.setText(f"(Overridden by KATAGO_EXE: {os.environ.get('KATAGO_EXE', '')})")
            self._exe_edit.setEnabled(False)
            self._exe_browse.setEnabled(False)
        else:
            self._exe_env_label.setText("")
            self._exe_edit.setEnabled(True)
            self._exe_browse.setEnabled(True)

        if self._settings.is_config_path_from_env():
            self._config_env_label.setText(f"(Overridden by KATAGO_CONFIG: {os.environ.get('KATAGO_CONFIG', '')})")
            self._config_edit.setEnabled(False)
            self._config_browse.setEnabled(False)
        else:
            self._config_env_label.setText("")
            self._config_edit.setEnabled(True)
            self._config_browse.setEnabled(True)

        if self._settings.is_model_path_from_env():
            self._model_env_label.setText(f"(Overridden by KATAGO_MODEL: {os.environ.get('KATAGO_MODEL', '')})")
            self._model_edit.setEnabled(False)
            self._model_browse.setEnabled(False)
        else:
            self._model_env_label.setText("")
            self._model_edit.setEnabled(True)
            self._model_browse.setEnabled(True)

    def _on_save(self):
        """Save settings and close dialog."""
        # KataGo paths (only save if not env-overridden)
        if not self._settings.is_katago_exe_from_env():
            self._settings.katago_exe = self._exe_edit.text().strip()
        if not self._settings.is_config_path_from_env():
            self._settings.config_path = self._config_edit.text().strip()
        if not self._settings.is_model_path_from_env():
            self._settings.model_path = self._model_edit.text().strip()

        # Analysis
        self._settings.max_visits = self._visits_spin.value()
        self._settings.max_candidates = self._candidates_spin.value()

        # Game
        self._settings.komi = self._komi_spin.value()
        self._settings.rules = self._rules_combo.currentText()

        # Persist
        self._settings.save()

        self.settings_changed.emit()
        self.accept()

    def _on_reset(self):
        """Reset settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to defaults?\n\n"
            "This will clear saved KataGo paths and analysis parameters.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self._settings.reset_to_defaults()
            self._load_values()
            QMessageBox.information(
                self,
                "Settings Reset",
                "Settings have been reset to defaults.",
            )

    def _on_open_folder(self):
        """Open the settings folder in file explorer."""
        folder = self._settings.settings_dir
        if folder.exists():
            import subprocess
            import sys

            if sys.platform == "win32":
                subprocess.run(["explorer", str(folder)])
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)])
            else:
                subprocess.run(["xdg-open", str(folder)])
        else:
            QMessageBox.warning(
                self,
                "Folder Not Found",
                f"Settings folder does not exist:\n{folder}",
            )

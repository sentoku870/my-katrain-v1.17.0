"""
New Game Dialog for KaTrain Qt.

Provides a dialog for creating a new game with configurable:
- Board size (9x9, 13x13, 19x19)
- Komi
- Rules (Japanese, Chinese, Korean, AGA, Tromp-Taylor)
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QDialogButtonBox,
    QGroupBox,
)

from katrain_qt.settings import get_settings


# Available board sizes
BOARD_SIZES = [
    (9, "9x9"),
    (13, "13x13"),
    (19, "19x19"),
]

# Available rules
RULES = [
    ("japanese", "Japanese"),
    ("chinese", "Chinese"),
    ("korean", "Korean"),
    ("aga", "AGA"),
    ("new-zealand", "New Zealand"),
    ("tromp-taylor", "Tromp-Taylor"),
]


class NewGameDialog(QDialog):
    """
    Dialog for creating a new game with board size, komi, and rules selection.

    Signals:
        game_created(int, float, str): Emitted when OK is clicked (size, komi, rules)
    """

    game_created = Signal(int, float, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Game")
        self.setMinimumWidth(300)

        self._settings = get_settings()
        self._setup_ui()
        self._load_defaults()

    def _setup_ui(self):
        """Create the dialog layout."""
        layout = QVBoxLayout(self)

        # Game settings group
        settings_group = QGroupBox("Game Settings")
        form_layout = QFormLayout(settings_group)

        # Board size
        self._size_combo = QComboBox()
        for size, label in BOARD_SIZES:
            self._size_combo.addItem(label, size)
        form_layout.addRow("Board Size:", self._size_combo)

        # Komi
        self._komi_spin = QDoubleSpinBox()
        self._komi_spin.setRange(-100.0, 100.0)
        self._komi_spin.setSingleStep(0.5)
        self._komi_spin.setDecimals(1)
        form_layout.addRow("Komi:", self._komi_spin)

        # Rules
        self._rules_combo = QComboBox()
        for value, label in RULES:
            self._rules_combo.addItem(label, value)
        form_layout.addRow("Rules:", self._rules_combo)

        layout.addWidget(settings_group)

        # Help text
        help_label = QLabel(
            "Tip: Default values are loaded from Settings.\n"
            "Changes here only affect this game."
        )
        help_label.setStyleSheet("color: gray; font-size: 10px;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # Stretch to push buttons to bottom
        layout.addStretch()

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_defaults(self):
        """Load default values from settings."""
        # Board size - default to 19x19
        size_idx = self._size_combo.findData(19)
        if size_idx >= 0:
            self._size_combo.setCurrentIndex(size_idx)

        # Komi from settings
        self._komi_spin.setValue(self._settings.komi)

        # Rules from settings
        rules_idx = self._rules_combo.findData(self._settings.rules)
        if rules_idx >= 0:
            self._rules_combo.setCurrentIndex(rules_idx)

    def _on_accept(self):
        """Handle OK button click."""
        size = self._size_combo.currentData()
        komi = self._komi_spin.value()
        rules = self._rules_combo.currentData()

        self.game_created.emit(size, komi, rules)
        self.accept()

    def get_values(self) -> tuple:
        """
        Get the selected values.

        Returns:
            Tuple of (board_size: int, komi: float, rules: str)
        """
        return (
            self._size_combo.currentData(),
            self._komi_spin.value(),
            self._rules_combo.currentData(),
        )

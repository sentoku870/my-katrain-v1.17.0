"""
Theme management for KaTrain Qt.

Provides light and dark themes with consistent color schemes.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


@dataclass
class ThemeColors:
    """Color scheme for a theme."""

    # Main window
    background: str
    text: str
    text_secondary: str

    # Board
    board: str
    board_line: str
    board_star: str

    # Stones
    stone_black: str
    stone_white: str
    stone_black_text: str
    stone_white_text: str

    # UI elements
    panel_background: str
    panel_border: str
    button_background: str
    button_text: str
    button_hover: str

    # Stats colors
    winrate_good: str  # Green - winning
    winrate_bad: str  # Red - losing
    winrate_neutral: str  # Gray - close
    score_good: str
    score_bad: str
    score_neutral: str

    # Graph
    graph_background: str
    graph_line: str
    graph_zero_line: str
    graph_marker: str


# Light theme (default)
LIGHT_THEME = ThemeColors(
    # Main window
    background="#F5F5F5",
    text="#000000",
    text_secondary="#666666",
    # Board
    board="#DEB887",
    board_line="#000000",
    board_star="#000000",
    # Stones
    stone_black="#1A1A1A",
    stone_white="#F0F0F0",
    stone_black_text="#FFFFFF",
    stone_white_text="#000000",
    # UI elements
    panel_background="#F5F5F5",
    panel_border="#CCCCCC",
    button_background="#E0E0E0",
    button_text="#000000",
    button_hover="#D0D0D0",
    # Stats colors
    winrate_good="#228B22",
    winrate_bad="#CC3333",
    winrate_neutral="#666666",
    score_good="#228B22",
    score_bad="#CC3333",
    score_neutral="#666666",
    # Graph
    graph_background="#FFFFFF",
    graph_line="#3366CC",
    graph_zero_line="#AAAAAA",
    graph_marker="#FF6600",
)

# Dark theme
DARK_THEME = ThemeColors(
    # Main window
    background="#2D2D2D",
    text="#E0E0E0",
    text_secondary="#999999",
    # Board
    board="#8B7355",
    board_line="#1A1A1A",
    board_star="#1A1A1A",
    # Stones
    stone_black="#0A0A0A",
    stone_white="#E8E8E8",
    stone_black_text="#FFFFFF",
    stone_white_text="#000000",
    # UI elements
    panel_background="#3D3D3D",
    panel_border="#555555",
    button_background="#4D4D4D",
    button_text="#E0E0E0",
    button_hover="#5D5D5D",
    # Stats colors
    winrate_good="#4CAF50",
    winrate_bad="#EF5350",
    winrate_neutral="#9E9E9E",
    score_good="#4CAF50",
    score_bad="#EF5350",
    score_neutral="#9E9E9E",
    # Graph
    graph_background="#3D3D3D",
    graph_line="#64B5F6",
    graph_zero_line="#666666",
    graph_marker="#FFB74D",
)

# Theme registry
THEMES: Dict[str, ThemeColors] = {
    "light": LIGHT_THEME,
    "dark": DARK_THEME,
}


class ThemeManager:
    """
    Manages application theme.

    Usage:
        theme_mgr = get_theme_manager()
        theme_mgr.set_theme("dark")
        colors = theme_mgr.colors
    """

    def __init__(self, theme_name: str = "light"):
        self._theme_name = theme_name if theme_name in THEMES else "light"
        self._colors = THEMES[self._theme_name]

    @property
    def theme_name(self) -> str:
        """Current theme name."""
        return self._theme_name

    @property
    def colors(self) -> ThemeColors:
        """Current theme colors."""
        return self._colors

    @property
    def is_dark(self) -> bool:
        """Check if current theme is dark."""
        return self._theme_name == "dark"

    def set_theme(self, theme_name: str) -> bool:
        """
        Set the current theme.

        Args:
            theme_name: "light" or "dark"

        Returns:
            True if theme was changed, False if invalid name
        """
        if theme_name not in THEMES:
            return False

        self._theme_name = theme_name
        self._colors = THEMES[theme_name]
        return True

    def get_stylesheet(self) -> str:
        """
        Generate Qt stylesheet for the current theme.

        Returns:
            CSS-like stylesheet string
        """
        c = self._colors
        return f"""
            QMainWindow, QDialog {{
                background-color: {c.background};
                color: {c.text};
            }}

            QWidget {{
                background-color: {c.background};
                color: {c.text};
            }}

            QLabel {{
                color: {c.text};
            }}

            QGroupBox {{
                background-color: {c.panel_background};
                border: 1px solid {c.panel_border};
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }}

            QGroupBox::title {{
                color: {c.text};
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }}

            QPushButton {{
                background-color: {c.button_background};
                color: {c.button_text};
                border: 1px solid {c.panel_border};
                border-radius: 4px;
                padding: 6px 12px;
            }}

            QPushButton:hover {{
                background-color: {c.button_hover};
            }}

            QPushButton:pressed {{
                background-color: {c.panel_border};
            }}

            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: {c.panel_background};
                color: {c.text};
                border: 1px solid {c.panel_border};
                border-radius: 4px;
                padding: 4px;
            }}

            QComboBox::drop-down {{
                border: none;
            }}

            QTableWidget {{
                background-color: {c.panel_background};
                color: {c.text};
                gridline-color: {c.panel_border};
                border: 1px solid {c.panel_border};
            }}

            QTableWidget::item {{
                padding: 4px;
            }}

            QHeaderView::section {{
                background-color: {c.button_background};
                color: {c.text};
                border: 1px solid {c.panel_border};
                padding: 4px;
            }}

            QTabWidget::pane {{
                background-color: {c.panel_background};
                border: 1px solid {c.panel_border};
            }}

            QTabBar::tab {{
                background-color: {c.button_background};
                color: {c.text};
                border: 1px solid {c.panel_border};
                padding: 8px 16px;
            }}

            QTabBar::tab:selected {{
                background-color: {c.panel_background};
            }}

            QScrollBar:vertical {{
                background-color: {c.background};
                width: 12px;
            }}

            QScrollBar::handle:vertical {{
                background-color: {c.panel_border};
                border-radius: 6px;
                min-height: 20px;
            }}

            QScrollBar:horizontal {{
                background-color: {c.background};
                height: 12px;
            }}

            QScrollBar::handle:horizontal {{
                background-color: {c.panel_border};
                border-radius: 6px;
                min-width: 20px;
            }}

            QCheckBox {{
                color: {c.text};
            }}

            QSlider::groove:horizontal {{
                background-color: {c.panel_border};
                height: 4px;
                border-radius: 2px;
            }}

            QSlider::handle:horizontal {{
                background-color: {c.button_background};
                border: 1px solid {c.panel_border};
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}

            QMenuBar {{
                background-color: {c.panel_background};
                color: {c.text};
            }}

            QMenuBar::item:selected {{
                background-color: {c.button_hover};
            }}

            QMenu {{
                background-color: {c.panel_background};
                color: {c.text};
                border: 1px solid {c.panel_border};
            }}

            QMenu::item:selected {{
                background-color: {c.button_hover};
            }}

            QToolBar {{
                background-color: {c.panel_background};
                border: none;
                spacing: 4px;
            }}

            QStatusBar {{
                background-color: {c.panel_background};
                color: {c.text_secondary};
            }}

            QDockWidget {{
                color: {c.text};
            }}

            QDockWidget::title {{
                background-color: {c.button_background};
                padding: 4px;
            }}
        """


# =============================================================================
# Module-level singleton
# =============================================================================

_theme_manager: Optional[ThemeManager] = None


def init_theme_manager(theme_name: str = "light") -> ThemeManager:
    """Initialize the global theme manager."""
    global _theme_manager
    _theme_manager = ThemeManager(theme_name)
    return _theme_manager


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance."""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager

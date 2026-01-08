"""
Tests for Qt window state persistence (objectName requirements).

QMainWindow.saveState()/restoreState() requires all QDockWidget and QToolBar
to have objectName set, otherwise Qt emits warnings and state restoration
may not work correctly.
"""

import pytest
from PySide6.QtWidgets import QApplication, QDockWidget, QToolBar


@pytest.fixture(scope="module")
def app():
    """Create QApplication for the test module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def main_window(app):
    """Create MainWindow instance."""
    from katrain_qt.app_qt import MainWindow
    window = MainWindow()
    yield window
    window.close()


class TestObjectNames:
    """Tests for QDockWidget and QToolBar objectName requirements."""

    def test_all_docks_have_object_name(self, main_window):
        """All QDockWidget instances must have objectName set."""
        docks = main_window.findChildren(QDockWidget)

        # Should have at least 4 docks (Candidates, Analysis Details, Comment, Score Graph)
        assert len(docks) >= 4, f"Expected at least 4 docks, found {len(docks)}"

        for dock in docks:
            assert dock.objectName(), f"QDockWidget '{dock.windowTitle()}' is missing objectName"

    def test_all_toolbars_have_object_name(self, main_window):
        """All QToolBar instances must have objectName set."""
        toolbars = main_window.findChildren(QToolBar)

        # Should have at least 1 toolbar (Navigation)
        assert len(toolbars) >= 1, f"Expected at least 1 toolbar, found {len(toolbars)}"

        for toolbar in toolbars:
            assert toolbar.objectName(), f"QToolBar '{toolbar.windowTitle()}' is missing objectName"

    def test_specific_dock_object_names(self, main_window):
        """Verify specific dock objectNames for documentation."""
        expected_docks = {
            "CandidatesDock": "Candidates",
            "AnalysisDetailsDock": "Analysis Details",
            "CommentDock": "Comment",
            "ScoreGraphDock": "Score Graph",
        }

        for obj_name, title in expected_docks.items():
            dock = main_window.findChild(QDockWidget, obj_name)
            assert dock is not None, f"Dock with objectName '{obj_name}' not found"
            assert dock.windowTitle() == title, f"Dock '{obj_name}' has wrong title"

    def test_navigation_toolbar_object_name(self, main_window):
        """Verify Navigation toolbar has correct objectName."""
        toolbar = main_window.findChild(QToolBar, "NavigationToolbar")
        assert toolbar is not None, "Navigation toolbar with objectName 'NavigationToolbar' not found"
        assert toolbar.windowTitle() == "Navigation", "Navigation toolbar has wrong title"

    def test_object_names_are_unique(self, main_window):
        """All objectNames should be unique to avoid state restoration issues."""
        docks = main_window.findChildren(QDockWidget)
        toolbars = main_window.findChildren(QToolBar)

        all_names = []
        for dock in docks:
            if dock.objectName():
                all_names.append(dock.objectName())
        for toolbar in toolbars:
            if toolbar.objectName():
                all_names.append(toolbar.objectName())

        # Check for duplicates
        seen = set()
        for name in all_names:
            assert name not in seen, f"Duplicate objectName found: '{name}'"
            seen.add(name)

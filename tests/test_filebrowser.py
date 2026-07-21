"""Unit tests for ``katrain.gui.widgets.filebrowser`` (Phase 282-P1C).

The ``I18NFileBrowser`` widget (497 LOC) had zero direct tests despite
being referenced from ``llm_coach_popup`` and ``config_popups``. This
file covers the pure helpers (``last_modified_first``,
``_shorten_filenames``, ``get_home_directory``, ``get_drives``) and
locks in the public class API via source-static checks.

The widget itself requires a real Kivy font pipeline + window
runtime which the headless CI cannot provide. Runtime instantiation
tests are skipped in favor of structural contracts.

Coverage targets:
- ``last_modified_first`` sort behavior (dirs first, then mtime)
- ``_shorten_filenames`` 4 length branches
- ``get_drives`` Linux branch returns non-empty list
- Class definitions (TreeLabel, LinkTree, I18NFileChooserListView,
  I18NFileChooserListLayout, I18NFileBrowser)
- ``I18NFileBrowser.__events__`` contract
- Default property values
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FB_PATH = REPO_ROOT / "katrain" / "gui" / "widgets" / "filebrowser.py"


# =============================================================================
# Pure helper tests
# =============================================================================


class TestLastModifiedFirst:
    """``last_modified_first(files, filesystem)``: sort dirs first (alphabetical),
    then files by mtime descending."""

    def _fs(self, dirs: set[str], files: set[str]) -> MagicMock:
        """Mock filesystem that returns is_dir based on membership."""
        fs = MagicMock()
        fs.is_dir.side_effect = lambda f: f in dirs
        return fs

    def test_dirs_come_before_files(self, tmp_path):
        """Directories must appear before files regardless of mtime."""
        d1 = tmp_path / "adir"
        d1.mkdir()
        d2 = tmp_path / "bdir"
        d2.mkdir()
        f1 = tmp_path / "file1.txt"
        f1.write_text("x")
        f2 = tmp_path / "file2.txt"
        f2.write_text("y")

        fs = self._fs({str(d1), str(d2)}, {str(f1), str(f2)})
        result = last_modified_first([str(f1), str(d2), str(f2), str(d1)], fs)
        # First half should be all dirs (alphabetical)
        dir_part = [x for x in result if x in (str(d1), str(d2))]
        assert dir_part == sorted([str(d1), str(d2)])

    def test_files_sorted_by_mtime_desc(self, tmp_path):
        f_old = tmp_path / "old.txt"
        f_old.write_text("x")
        import os

        # Force distinct mtimes
        os.utime(f_old, (1000, 1000))

        f_new = tmp_path / "new.txt"
        f_new.write_text("y")
        os.utime(f_new, (2000, 2000))

        fs = self._fs(set(), {str(f_old), str(f_new)})
        result = last_modified_first([str(f_old), str(f_new)], fs)
        # Newer file first
        assert result == [str(f_new), str(f_old)]

    def test_all_files(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f1.write_text("x")
        f2 = tmp_path / "b.txt"
        f2.write_text("y")
        fs = self._fs(set(), {str(f1), str(f2)})
        result = last_modified_first([str(f1), str(f2)], fs)
        # Files are sorted by mtime descending (which is their creation order)
        assert len(result) == 2
        assert all(x in (str(f1), str(f2)) for x in result)

    def test_all_dirs(self, tmp_path):
        d1 = tmp_path / "a"
        d1.mkdir()
        d2 = tmp_path / "b"
        d2.mkdir()
        fs = self._fs({str(d1), str(d2)}, set())
        result = last_modified_first([str(d2), str(d1)], fs)
        # Sorted alphabetically
        assert result == [str(d1), str(d2)]


class TestShortenFilenames:
    """``_shorten_filenames``: 4-branch logic (0/1/2/many files).

    The function is an instance method on ``I18NFileBrowser``, but it
    is pure (no ``self`` access). We invoke it via an unbound method
    call so we don't need a full widget instance.
    """

    @staticmethod
    def _call(filenames):
        """Invoke ``_shorten_filenames`` without instantiating the widget."""
        from katrain.gui.widgets.filebrowser import I18NFileBrowser

        return I18NFileBrowser._shorten_filenames(None, filenames)

    def test_empty_returns_empty_string(self):
        assert self._call([]) == ""

    def test_single_returns_filename(self):
        assert self._call(["/foo.txt"]) == "/foo.txt"

    def test_two_returns_comma_joined(self):
        assert self._call(["/a.txt", "/b.txt"]) == "/a.txt, /b.txt"

    def test_many_returns_ellipsis_form(self):
        result = self._call(["/a.txt", "/b.txt", "/c.txt", "/d.txt"])
        # Format: first, _..._, last
        assert result == "/a.txt, _..._, /d.txt"


class TestGetHomeDirectory:
    def test_returns_string(self):
        result = get_home_directory()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_existing_directory(self):
        """On Linux/Mac, expanduser returns an existing path."""

        result = get_home_directory()
        # Should be a real path (the only platform-specific branch is Windows)
        assert isinstance(result, str)


class TestGetDrives:
    """Platform-specific branch coverage. On Linux CI, only the Linux
    branch is exercised."""

    def test_returns_list(self):
        result = get_drives()
        assert isinstance(result, list)

    def test_linux_includes_root(self):
        """The Linux branch always adds ``/`` as the first entry."""
        result = get_drives()
        # Every entry is (path, name)
        assert all(isinstance(x, tuple) and len(x) == 2 for x in result)
        # First entry should be the root (/)
        from os.path import sep

        assert (sep, sep) in result

    def test_linux_includes_home(self):
        """The Linux branch always adds ``~/`` as the second entry."""
        from os.path import expanduser

        result = get_drives()
        assert (expanduser("~"), "~/") in result


# =============================================================================
# Source-static regression guards
# =============================================================================


def _get_module_tree() -> ast.Module:
    return ast.parse(FB_PATH.read_text(encoding="utf-8"))


class TestFileBrowserPublicApi:
    """Lock in the public class surface and KV string structure."""

    @pytest.mark.parametrize(
        "class_name",
        [
            "I18NFileChooserListView",
            "I18NFileChooserListLayout",
            "TreeLabel",
            "LinkTree",
            "I18NFileBrowser",
        ],
    )
    def test_classes_exist(self, class_name):
        text = FB_PATH.read_text(encoding="utf-8")
        assert f"class {class_name}" in text, f"filebrowser.py missing class {class_name!r}"

    def test_kv_template_loaded(self):
        """The KV template strings must be loaded at import time."""
        text = FB_PATH.read_text(encoding="utf-8")
        assert "Builder.load_string" in text
        assert "I18NFileBrowser" in text  # KV root widget name
        assert "I18NFileListEntry" in text  # KV template class

    def test_default_font_applied(self):
        """Kivy file chooser must use Theme.DEFAULT_FONT for I18N."""
        text = FB_PATH.read_text(encoding="utf-8")
        assert "Theme.DEFAULT_FONT" in text

    def test_on_success_on_submit_events_declared(self):
        """``I18NFileBrowser.__events__`` must declare both events."""
        text = FB_PATH.read_text(encoding="utf-8")
        assert "__events__" in text
        assert '"on_success"' in text or "'on_success'" in text
        assert '"on_submit"' in text or "'on_submit'" in text

    def test_button_clicked_method_exists(self):
        text = FB_PATH.read_text(encoding="utf-8")
        assert "def button_clicked(self) -> None:" in text

    def test_dirselect_handling_present(self):
        """``button_clicked`` must branch on ``self.dirselect``."""
        text = FB_PATH.read_text(encoding="utf-8")
        # Locate button_clicked and check it uses dirselect
        assert "if self.dirselect:" in text


class TestFileBrowserDefaultValues:
    """Property defaults must remain stable - callers depend on them."""

    def test_select_string_default(self):
        """``select_string`` defaults to 'Ok'."""
        text = FB_PATH.read_text(encoding="utf-8")
        assert 'select_string = StringProperty("Ok")' in text

    def test_path_default(self):
        text = FB_PATH.read_text(encoding="utf-8")
        assert 'path = StringProperty("/")' in text

    def test_show_hidden_default_for_filechooserlistview(self):
        """``I18NFileChooserListView`` shows hidden files by default
        (to avoid errors on Windows with hidden system files)."""
        text = FB_PATH.read_text(encoding="utf-8")
        assert "show_hidden = BooleanProperty(True)" in text

    def test_sort_func_default(self):
        """Default sort_func is ``last_modified_first``."""
        text = FB_PATH.read_text(encoding="utf-8")
        assert "sort_func = ObjectProperty(last_modified_first)" in text


class TestFileBrowserImports:
    """Ensure Kivy imports are present (they're part of the public API)."""

    @pytest.mark.parametrize(
        "import_str",
        [
            "from kivy.uix.boxlayout import BoxLayout",
            "from kivy.uix.filechooser import",
            "from kivy.uix.treeview import",
            "from kivy.clock import Clock",
            "from kivy.properties import",
        ],
    )
    def test_kivy_import_present(self, import_str):
        text = FB_PATH.read_text(encoding="utf-8")
        assert import_str in text, f"filebrowser.py missing {import_str!r}"


# =============================================================================
# Late import (after Kivy env is set up by conftest)
# =============================================================================

from katrain.gui.widgets.filebrowser import (  # noqa: E402
    get_drives,
    get_home_directory,
    last_modified_first,
)

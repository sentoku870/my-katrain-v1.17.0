"""Tests for katrain.common.file_opener.

Cross-platform file/folder opener tests.
Uses mock to avoid actually opening files/folders during tests.
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from katrain.common import file_opener
from katrain.common.file_opener import (
    OpenResult,
    open_file,
    open_file_in_folder,
    open_folder,
)


class TestOpenResult:
    """Tests for OpenResult dataclass."""

    def test_success_result(self):
        result = OpenResult(True)
        assert result.success is True
        assert result.error_message is None
        assert result.error_detail is None

    def test_error_result(self):
        result = OpenResult(False, "path-not-exist", "Path does not exist: /foo")
        assert result.success is False
        assert result.error_message == "path-not-exist"
        assert result.error_detail == "Path does not exist: /foo"


class TestOpenFolder:
    """Tests for open_folder function."""

    def test_returns_error_when_path_not_exists(self, tmp_path):
        result = open_folder(tmp_path / "nonexistent")
        assert not result.success
        assert result.error_message == "path-not-exist"
        assert "does not exist" in result.error_detail

    def test_returns_error_when_path_is_file(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("test")
        result = open_folder(f)
        assert not result.success
        assert result.error_message == "not-a-folder"
        assert "Not a folder" in result.error_detail

    def test_windows_uses_startfile(self, tmp_path):
        """Windows: os.startfile is used."""
        with patch.object(file_opener, "get_platform", return_value="win"):
            # create=True allows mocking os.startfile on non-Windows
            with patch.object(os, "startfile", create=True) as mock_startfile:
                result = open_folder(tmp_path)
                assert result.success
                mock_startfile.assert_called_once_with(str(tmp_path))

    @patch("subprocess.run")
    def test_macos_uses_open(self, mock_run, tmp_path):
        """macOS: open command is used."""
        with patch.object(file_opener, "get_platform", return_value="macosx"):
            mock_run.return_value = MagicMock(returncode=0)
            result = open_folder(tmp_path)
            assert result.success
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == ["open", str(tmp_path)]

    @patch("subprocess.run")
    def test_linux_uses_xdg_open(self, mock_run, tmp_path):
        """Linux: xdg-open command is used."""
        with patch.object(file_opener, "get_platform", return_value="linux"):
            mock_run.return_value = MagicMock(returncode=0)
            result = open_folder(tmp_path)
            assert result.success
            assert mock_run.call_args[0][0] == ["xdg-open", str(tmp_path)]

    def test_handles_command_not_found(self, tmp_path):
        """Returns error when command is not found."""
        with patch.object(file_opener, "get_platform", return_value="linux"):
            with patch("subprocess.run", side_effect=FileNotFoundError("xdg-open")):
                result = open_folder(tmp_path)
                assert not result.success
                assert result.error_message == "command-not-found"


class TestOpenFile:
    """Tests for open_file function."""

    def test_returns_error_when_file_not_exists(self, tmp_path):
        result = open_file(tmp_path / "nonexistent.txt")
        assert not result.success
        assert result.error_message == "path-not-exist"

    def test_returns_error_when_path_is_dir(self, tmp_path):
        result = open_file(tmp_path)
        assert not result.success
        assert result.error_message == "not-a-file"
        assert "Not a file" in result.error_detail

    def test_windows_uses_startfile(self, tmp_path):
        """Windows: os.startfile is used for files."""
        f = tmp_path / "test.md"
        f.write_text("test")
        with patch.object(file_opener, "get_platform", return_value="win"):
            with patch.object(os, "startfile", create=True) as mock_startfile:
                result = open_file(f)
                assert result.success
                mock_startfile.assert_called_once_with(str(f))

    @patch("subprocess.run")
    def test_macos_uses_open(self, mock_run, tmp_path):
        """macOS: open command is used for files."""
        f = tmp_path / "test.md"
        f.write_text("test")
        with patch.object(file_opener, "get_platform", return_value="macosx"):
            mock_run.return_value = MagicMock(returncode=0)
            result = open_file(f)
            assert result.success
            assert mock_run.call_args[0][0] == ["open", str(f)]

    @patch("subprocess.run")
    def test_linux_uses_xdg_open(self, mock_run, tmp_path):
        """Linux: xdg-open command is used for files."""
        f = tmp_path / "test.md"
        f.write_text("test")
        with patch.object(file_opener, "get_platform", return_value="linux"):
            mock_run.return_value = MagicMock(returncode=0)
            result = open_file(f)
            assert result.success
            assert mock_run.call_args[0][0] == ["xdg-open", str(f)]


class TestOpenFileInFolder:
    """Tests for open_file_in_folder function."""

    def test_returns_error_when_file_not_exists(self, tmp_path):
        result = open_file_in_folder(tmp_path / "nonexistent.txt")
        assert not result.success
        assert result.error_message == "path-not-exist"

    @patch("subprocess.run")
    def test_windows_uses_explorer_select(self, mock_run, tmp_path):
        """Windows: explorer /select, <path> with separate args."""
        f = tmp_path / "test file.txt"  # space in filename
        f.write_text("test")
        with patch.object(file_opener, "get_platform", return_value="win"):
            result = open_file_in_folder(f)
            assert result.success
            # shell=False with separate args
            call_args = mock_run.call_args
            assert call_args[0][0] == ["explorer", "/select,", str(f)]
            # Ensure shell=False (not True)
            assert call_args[1].get("shell") is not True

    @patch("subprocess.run")
    def test_handles_japanese_path(self, mock_run, tmp_path):
        """Japanese path is passed correctly."""
        f = tmp_path / "レポート" / "カルテ.md"
        f.parent.mkdir(parents=True)
        f.write_text("test")
        with patch.object(file_opener, "get_platform", return_value="win"):
            result = open_file_in_folder(f)
            assert result.success
            # Japanese path is passed as-is
            assert mock_run.call_args[0][0][2] == str(f)

    @patch("subprocess.run")
    def test_macos_uses_open_R(self, mock_run, tmp_path):
        """macOS: open -R command is used."""
        f = tmp_path / "test.md"
        f.write_text("test")
        with patch.object(file_opener, "get_platform", return_value="macosx"):
            mock_run.return_value = MagicMock(returncode=0)
            result = open_file_in_folder(f)
            assert result.success
            assert mock_run.call_args[0][0] == ["open", "-R", str(f)]

    @patch("subprocess.run")
    def test_linux_opens_parent_folder(self, mock_run, tmp_path):
        """Linux: xdg-open opens parent folder (selection not supported)."""
        f = tmp_path / "subdir" / "test.md"
        f.parent.mkdir(parents=True)
        f.write_text("test")
        with patch.object(file_opener, "get_platform", return_value="linux"):
            mock_run.return_value = MagicMock(returncode=0)
            result = open_file_in_folder(f)
            assert result.success
            # Opens parent directory, not the file
            assert mock_run.call_args[0][0] == ["xdg-open", str(f.parent)]


class TestErrorHandling:
    """Tests for error handling."""

    @patch("subprocess.run")
    def test_handles_subprocess_error(self, mock_run, tmp_path):
        """Generic exception is caught and returned as error."""
        f = tmp_path / "test.md"
        f.write_text("test")
        with patch.object(file_opener, "get_platform", return_value="linux"):
            mock_run.side_effect = RuntimeError("Something went wrong")
            result = open_file(f)
            assert not result.success
            assert result.error_message == "open-failed"
            assert "Something went wrong" in result.error_detail

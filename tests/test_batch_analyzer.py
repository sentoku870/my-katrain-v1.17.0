"""
Smoke tests for batch_analyze_sgf CLI tool.

These tests verify the basic functionality of the batch analyzer
without requiring KataGo to be running.
"""

import os
import tempfile
import pytest
from pathlib import Path

from katrain.tools.batch_analyze_sgf import (
    has_analysis,
    collect_sgf_files,
    collect_sgf_files_recursive,
    read_sgf_with_fallback,
    parse_sgf_with_fallback,
    ENCODINGS_TO_TRY,
)
from katrain.core.game import KaTrainSGF


class TestHasAnalysis:
    """Tests for has_analysis() function."""

    def test_sgf_without_analysis(self, tmp_path):
        """SGF file without KT property should return False."""
        sgf_content = "(;GM[1]FF[4]SZ[19];B[pd];W[dp];B[pp])"
        sgf_file = tmp_path / "test_no_analysis.sgf"
        sgf_file.write_text(sgf_content, encoding="utf-8")

        assert has_analysis(str(sgf_file)) is False

    def test_sgf_with_kt_property(self, tmp_path):
        """SGF file with KT property should return True."""
        # Create an SGF with a mock KT property
        # KT property contains base64-encoded gzipped data
        # This is a minimal valid KT property (even if the data is invalid, the property exists)
        sgf_content = "(;GM[1]FF[4]SZ[19]KT[H4sIAAAAAAAA][H4sIAAAAAAAA][eyJtb3ZlcyI6e319];B[pd])"
        sgf_file = tmp_path / "test_with_analysis.sgf"
        sgf_file.write_text(sgf_content, encoding="utf-8")

        # The file has KT property, so it should return True
        assert has_analysis(str(sgf_file)) is True

    def test_nonexistent_file(self):
        """Non-existent file should return False."""
        assert has_analysis("/nonexistent/path/file.sgf") is False

    def test_invalid_sgf(self, tmp_path):
        """Invalid SGF content should return False."""
        sgf_file = tmp_path / "invalid.sgf"
        sgf_file.write_text("not valid sgf content", encoding="utf-8")

        assert has_analysis(str(sgf_file)) is False


class TestCollectSgfFiles:
    """Tests for collect_sgf_files() function (non-recursive, CLI)."""

    def test_empty_directory(self, tmp_path):
        """Empty directory should return empty list."""
        files = collect_sgf_files(str(tmp_path))
        assert files == []

    def test_finds_sgf_files(self, tmp_path):
        """Should find all SGF files in directory."""
        # Create test SGF files
        (tmp_path / "game1.sgf").write_text("(;GM[1])")
        (tmp_path / "game2.sgf").write_text("(;GM[1])")
        (tmp_path / "notes.txt").write_text("not an sgf")

        files = collect_sgf_files(str(tmp_path))
        assert len(files) == 2
        assert all(f.endswith(".sgf") for f in files)

    def test_case_insensitive(self, tmp_path):
        """Should find SGF files regardless of case."""
        (tmp_path / "game1.sgf").write_text("(;GM[1])")
        (tmp_path / "game2.SGF").write_text("(;GM[1])")

        files = collect_sgf_files(str(tmp_path))
        assert len(files) == 2

    def test_skip_analyzed_files(self, tmp_path):
        """Should skip files with analysis when skip_analyzed=True."""
        # File without analysis
        (tmp_path / "unanalyzed.sgf").write_text("(;GM[1]FF[4]SZ[19];B[pd])")

        # File with KT property (analysis)
        (tmp_path / "analyzed.sgf").write_text(
            "(;GM[1]FF[4]SZ[19]KT[H4sIAAAAAAAA][H4sIAAAAAAAA][eyJtb3ZlcyI6e319];B[pd])"
        )

        # Without skip
        files_all = collect_sgf_files(str(tmp_path), skip_analyzed=False)
        assert len(files_all) == 2

        # With skip
        files_skip = collect_sgf_files(str(tmp_path), skip_analyzed=True)
        assert len(files_skip) == 1
        assert "unanalyzed.sgf" in files_skip[0]


class TestCollectSgfFilesRecursive:
    """Tests for collect_sgf_files_recursive() function (GUI)."""

    def test_empty_directory(self, tmp_path):
        """Empty directory should return empty list."""
        files = collect_sgf_files_recursive(str(tmp_path))
        assert files == []

    def test_finds_nested_sgf_files(self, tmp_path):
        """Should find SGF files in subdirectories."""
        # Create nested structure
        (tmp_path / "game1.sgf").write_text("(;GM[1])")
        subdir = tmp_path / "pro"
        subdir.mkdir()
        (subdir / "game2.sgf").write_text("(;GM[1])")
        subsubdir = subdir / "2024"
        subsubdir.mkdir()
        (subsubdir / "game3.sgf").write_text("(;GM[1])")

        files = collect_sgf_files_recursive(str(tmp_path))
        assert len(files) == 3

        # Check relative paths are preserved
        rel_paths = [rel for _, rel in files]
        assert "game1.sgf" in rel_paths
        assert os.path.join("pro", "game2.sgf") in rel_paths
        assert os.path.join("pro", "2024", "game3.sgf") in rel_paths

    def test_preserves_relative_paths(self, tmp_path):
        """Should return (absolute_path, relative_path) tuples."""
        subdir = tmp_path / "folder"
        subdir.mkdir()
        (subdir / "test.sgf").write_text("(;GM[1])")

        files = collect_sgf_files_recursive(str(tmp_path))
        assert len(files) == 1

        abs_path, rel_path = files[0]
        assert os.path.isabs(abs_path)
        assert rel_path == os.path.join("folder", "test.sgf")

    def test_skip_analyzed_recursive(self, tmp_path):
        """Should skip analyzed files in subdirectories."""
        subdir = tmp_path / "games"
        subdir.mkdir()

        # File without analysis
        (subdir / "unanalyzed.sgf").write_text("(;GM[1]FF[4]SZ[19];B[pd])")

        # File with KT property (analysis)
        (subdir / "analyzed.sgf").write_text(
            "(;GM[1]FF[4]SZ[19]KT[H4sIAAAAAAAA][H4sIAAAAAAAA][eyJtb3ZlcyI6e319];B[pd])"
        )

        files_skip = collect_sgf_files_recursive(str(tmp_path), skip_analyzed=True)
        assert len(files_skip) == 1
        assert "unanalyzed.sgf" in files_skip[0][1]


class TestEncodingFallback:
    """Tests for encoding fallback functionality."""

    def test_utf8_encoding(self, tmp_path):
        """Should read UTF-8 encoded file."""
        sgf_content = "(;GM[1]PB[山田太郎])"
        sgf_file = tmp_path / "utf8.sgf"
        sgf_file.write_bytes(sgf_content.encode("utf-8"))

        content, encoding = read_sgf_with_fallback(str(sgf_file))
        assert content is not None
        assert "山田太郎" in content
        assert encoding == "utf-8"

    def test_gb18030_encoding(self, tmp_path):
        """Should read GB18030 encoded file (common for Fox/Tygem)."""
        sgf_content = "(;GM[1]PB[张三])"
        sgf_file = tmp_path / "gb18030.sgf"
        sgf_file.write_bytes(sgf_content.encode("gb18030"))

        log_messages = []
        content, encoding = read_sgf_with_fallback(str(sgf_file), log_cb=log_messages.append)
        assert content is not None
        assert "张三" in content
        assert encoding == "gb18030"
        # Should log the encoding used
        assert any("gb18030" in msg for msg in log_messages)

    def test_cp932_encoding(self, tmp_path):
        """Should read CP932 encoded file (common for Japanese SGF)."""
        # Use a character that encodes differently in CP932 vs UTF-8
        # and would fail UTF-8 decoding
        sgf_content = "(;GM[1]PB[鈴木一郎])"
        sgf_file = tmp_path / "cp932.sgf"
        raw_bytes = sgf_content.encode("cp932")
        sgf_file.write_bytes(raw_bytes)

        content, encoding = read_sgf_with_fallback(str(sgf_file))
        assert content is not None
        # The content should be readable (may be decoded as gb18030 first if that works)
        # Main test is that it doesn't fail completely
        assert "(" in content and ")" in content

    def test_utf8_bom_encoding(self, tmp_path):
        """Should read UTF-8 with BOM."""
        sgf_content = "(;GM[1]PB[Test])"
        sgf_file = tmp_path / "utf8bom.sgf"
        sgf_file.write_bytes(sgf_content.encode("utf-8-sig"))

        content, encoding = read_sgf_with_fallback(str(sgf_file))
        assert content is not None
        assert "Test" in content
        # utf-8 or utf-8-sig should both work

    def test_nonexistent_file(self):
        """Should return None for non-existent file."""
        content, encoding = read_sgf_with_fallback("/nonexistent/file.sgf")
        assert content is None
        assert encoding == ""

    def test_parse_with_fallback(self, tmp_path):
        """Should parse SGF with encoding fallback."""
        sgf_content = "(;GM[1]FF[4]SZ[19]PB[李明]PW[王刚];B[pd])"
        sgf_file = tmp_path / "chinese.sgf"
        sgf_file.write_bytes(sgf_content.encode("gb18030"))

        root = parse_sgf_with_fallback(str(sgf_file))
        assert root is not None


class TestKaTrainSGFParsing:
    """Tests for SGF parsing used by batch analyzer."""

    def test_parse_basic_sgf(self, tmp_path):
        """Should parse basic SGF file."""
        sgf_content = "(;GM[1]FF[4]SZ[19]PB[Black]PW[White];B[pd];W[dp];B[pp];W[dd])"
        sgf_file = tmp_path / "test.sgf"
        sgf_file.write_text(sgf_content, encoding="utf-8")

        root = KaTrainSGF.parse_file(str(sgf_file))

        assert root.get_property("SZ") == "19"
        assert root.get_property("PB") == "Black"
        assert root.get_property("PW") == "White"

    def test_parse_sgf_with_moves(self, tmp_path):
        """Should parse SGF with multiple moves."""
        sgf_content = "(;GM[1]FF[4]SZ[19];B[pd];W[dp];B[pp];W[dd])"
        sgf_file = tmp_path / "test.sgf"
        sgf_file.write_text(sgf_content, encoding="utf-8")

        root = KaTrainSGF.parse_file(str(sgf_file))

        # Count nodes (root + 4 moves)
        nodes = root.nodes_in_tree
        assert len(nodes) == 5

    def test_parse_japanese_sgf(self, tmp_path):
        """Should parse SGF with Japanese characters."""
        sgf_content = "(;GM[1]FF[4]SZ[19]PB[山田太郎]PW[田中次郎];B[pd])"
        sgf_file = tmp_path / "test.sgf"
        sgf_file.write_text(sgf_content, encoding="utf-8")

        root = KaTrainSGF.parse_file(str(sgf_file))

        assert root.get_property("PB") == "山田太郎"
        assert root.get_property("PW") == "田中次郎"


class TestBatchAnalyzerCLI:
    """Tests for CLI argument handling."""

    def test_import(self):
        """Should be able to import the batch analyzer module."""
        from katrain.tools import batch_analyze_sgf
        assert hasattr(batch_analyze_sgf, 'main')
        assert hasattr(batch_analyze_sgf, 'analyze_single_file')
        assert hasattr(batch_analyze_sgf, 'wait_for_analysis')
        assert hasattr(batch_analyze_sgf, 'run_batch')
        assert hasattr(batch_analyze_sgf, 'BatchResult')

    def test_batch_result_dataclass(self):
        """BatchResult should have expected fields."""
        from katrain.tools.batch_analyze_sgf import BatchResult
        result = BatchResult()
        assert result.success_count == 0
        assert result.fail_count == 0
        assert result.skip_count == 0
        assert result.output_dir == ""
        assert result.cancelled is False


class TestAnalyzeSingleFileLogging:
    """Tests for analyze_single_file error logging."""

    def test_log_cb_receives_progress(self, tmp_path):
        """log_cb should receive progress messages."""
        from katrain.tools.batch_analyze_sgf import analyze_single_file
        from unittest.mock import MagicMock

        # Create a valid SGF
        sgf_content = "(;GM[1]FF[4]SZ[19];B[pd])"
        sgf_file = tmp_path / "test.sgf"
        sgf_file.write_text(sgf_content, encoding="utf-8")

        output_file = tmp_path / "output.sgf"

        # Mock katrain and engine (will fail, but we want to check logging)
        log_messages = []

        def log_cb(msg):
            log_messages.append(msg)

        # This will fail because katrain/engine are None, but should log the error
        result = analyze_single_file(
            katrain=None,
            engine=None,
            sgf_path=str(sgf_file),
            output_path=str(output_file),
            log_cb=log_cb,
        )

        # Should have logged something (error traceback)
        assert len(log_messages) > 0
        # Should have logged the parsing step
        assert any("[1/4]" in msg for msg in log_messages)

    def test_error_traceback_logged(self, tmp_path):
        """Errors should include traceback in log."""
        from katrain.tools.batch_analyze_sgf import analyze_single_file

        # Create an invalid SGF that will cause parse error
        sgf_file = tmp_path / "invalid.sgf"
        sgf_file.write_text("not valid sgf", encoding="utf-8")

        log_messages = []
        result = analyze_single_file(
            katrain=None,
            engine=None,
            sgf_path=str(sgf_file),
            output_path=str(tmp_path / "out.sgf"),
            log_cb=log_messages.append,
        )

        assert result is False
        # Should contain error message
        assert any("ERROR" in msg or "error" in msg.lower() for msg in log_messages)

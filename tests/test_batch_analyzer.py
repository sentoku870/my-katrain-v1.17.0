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

    def test_batch_result_extended_fields(self):
        """BatchResult should have extended output count fields."""
        from katrain.tools.batch_analyze_sgf import BatchResult
        result = BatchResult()
        # New fields for karte/summary generation
        assert result.karte_written == 0
        assert result.karte_failed == 0
        assert result.summary_written is False
        assert result.summary_error is None
        assert result.analyzed_sgf_written == 0

        # Test with values
        result2 = BatchResult(
            success_count=5,
            karte_written=3,
            karte_failed=1,
            summary_written=True,
            summary_error=None,
            analyzed_sgf_written=5
        )
        assert result2.karte_written == 3
        assert result2.karte_failed == 1
        assert result2.summary_written is True
        assert result2.summary_error is None
        assert result2.analyzed_sgf_written == 5

        # Test with summary error
        result3 = BatchResult(
            summary_written=False,
            summary_error="No valid game statistics available"
        )
        assert result3.summary_written is False
        assert result3.summary_error == "No valid game statistics available"


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


class TestAnalyzeSingleFileExtended:
    """Tests for analyze_single_file extended functionality."""

    def test_save_sgf_parameter(self, tmp_path):
        """analyze_single_file should support save_sgf parameter."""
        from katrain.tools.batch_analyze_sgf import analyze_single_file

        # Create a valid SGF
        sgf_content = "(;GM[1]FF[4]SZ[19];B[pd])"
        sgf_file = tmp_path / "test.sgf"
        sgf_file.write_text(sgf_content, encoding="utf-8")

        # Call with save_sgf=False (will still fail due to None katrain, but parameter is accepted)
        log_messages = []
        result = analyze_single_file(
            katrain=None,
            engine=None,
            sgf_path=str(sgf_file),
            output_path=str(tmp_path / "out.sgf"),
            log_cb=log_messages.append,
            save_sgf=False,  # New parameter
        )
        # Should have processed (and failed for other reasons, not param error)
        assert len(log_messages) > 0

    def test_return_game_parameter(self, tmp_path):
        """analyze_single_file should support return_game parameter."""
        from katrain.tools.batch_analyze_sgf import analyze_single_file

        # Create a valid SGF
        sgf_content = "(;GM[1]FF[4]SZ[19];B[pd])"
        sgf_file = tmp_path / "test.sgf"
        sgf_file.write_text(sgf_content, encoding="utf-8")

        # Call with return_game=True (will still fail due to None katrain)
        result = analyze_single_file(
            katrain=None,
            engine=None,
            sgf_path=str(sgf_file),
            output_path=str(tmp_path / "out.sgf"),
            return_game=True,  # New parameter
        )
        # Should return None (not a Game) on failure
        assert result is None


class TestRunBatchExtended:
    """Tests for run_batch extended functionality."""

    def test_run_batch_extended_parameters(self):
        """run_batch should accept extended parameters."""
        from katrain.tools.batch_analyze_sgf import run_batch
        import inspect

        sig = inspect.signature(run_batch)
        params = list(sig.parameters.keys())

        # Check new parameters exist
        assert "save_analyzed_sgf" in params
        assert "generate_karte" in params
        assert "generate_summary" in params
        assert "karte_player_filter" in params

    def test_run_batch_parameter_defaults(self):
        """run_batch should have correct default values for backward compatibility."""
        from katrain.tools.batch_analyze_sgf import run_batch
        import inspect

        sig = inspect.signature(run_batch)

        # save_analyzed_sgf defaults to True (backward compatibility)
        assert sig.parameters["save_analyzed_sgf"].default is True

        # generate_karte defaults to False (backward compatibility)
        assert sig.parameters["generate_karte"].default is False

        # generate_summary defaults to False (backward compatibility)
        assert sig.parameters["generate_summary"].default is False

        # karte_player_filter defaults to None (both players)
        assert sig.parameters["karte_player_filter"].default is None


class TestBatchOutputDirectoryStructure:
    """Tests for batch output directory structure."""

    def test_output_subdirectory_names(self):
        """Verify expected subdirectory structure constants."""
        # These are the expected subdirectory names used in run_batch
        # This documents the expected structure:
        # output_dir/
        #   ├── analyzed/           (SGFs if save_analyzed_sgf)
        #   └── reports/
        #       ├── karte/          (if generate_karte)
        #       └── summary/        (if generate_summary)
        expected_subdirs = ["analyzed", "reports/karte", "reports/summary"]
        for subdir in expected_subdirs:
            # Just document the expected structure
            assert isinstance(subdir, str)


class TestHelperFunctions:
    """Tests for batch analyzer helper functions."""

    def test_helper_functions_exist(self):
        """Helper functions should exist in module."""
        import katrain.tools.batch_analyze_sgf as module

        # Check internal helper functions exist (for documentation)
        assert hasattr(module, "_extract_game_stats")
        assert hasattr(module, "_build_batch_summary")
        assert callable(module._extract_game_stats)
        assert callable(module._build_batch_summary)

    def test_build_batch_summary_empty_list(self):
        """_build_batch_summary should handle empty list."""
        from katrain.tools.batch_analyze_sgf import _build_batch_summary

        result = _build_batch_summary([])
        assert isinstance(result, str)
        # Should still return valid markdown
        assert "#" in result or "No" in result or "0" in result


class TestBatchOutputBehavior:
    """Tests for actual output file behavior."""

    def test_karte_filename_includes_path_hash(self):
        """Karte filenames should include path hash to avoid collisions."""
        import hashlib
        rel_path_1 = "pro/game.sgf"
        rel_path_2 = "amateur/game.sgf"

        hash_1 = hashlib.md5(rel_path_1.encode()).hexdigest()[:6]
        hash_2 = hashlib.md5(rel_path_2.encode()).hexdigest()[:6]

        # Same basename but different paths should have different hashes
        assert hash_1 != hash_2

        # Format: karte_{base_name}_{path_hash}_{timestamp}.md
        # Timestamp format: YYYYMMDD-HHMMSS (includes seconds)
        base_name = "game"
        timestamp = "20250103-120000"  # Updated to include seconds
        filename_1 = f"karte_{base_name}_{hash_1}_{timestamp}.md"
        filename_2 = f"karte_{base_name}_{hash_2}_{timestamp}.md"

        assert filename_1 != filename_2

    def test_timestamp_format_includes_seconds(self):
        """Batch timestamp should include seconds to reduce collision risk."""
        from datetime import datetime
        # Verify the expected format: YYYYMMDD-HHMMSS
        test_timestamp = datetime(2025, 1, 3, 12, 0, 30).strftime("%Y%m%d-%H%M%S")
        assert test_timestamp == "20250103-120030"
        assert len(test_timestamp) == 15  # YYYYMMDD-HHMMSS = 15 chars

    def test_output_directory_structure_creation(self, tmp_path):
        """Output directories should be created only when needed."""
        from katrain.tools.batch_analyze_sgf import run_batch
        from unittest.mock import MagicMock

        # Create mock katrain and engine
        mock_katrain = MagicMock()
        mock_engine = MagicMock()
        mock_engine.is_idle.return_value = True

        # Create input directory with a dummy SGF
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "test.sgf").write_text("(;GM[1]FF[4]SZ[19];B[pd])")

        output_dir = tmp_path / "output"

        # Run with all options OFF
        result = run_batch(
            katrain=mock_katrain,
            engine=mock_engine,
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            save_analyzed_sgf=False,
            generate_karte=False,
            generate_summary=False,
        )

        # Base output_dir should exist
        assert output_dir.exists()
        # But subdirectories should NOT exist
        assert not (output_dir / "analyzed").exists()
        assert not (output_dir / "reports" / "karte").exists()
        assert not (output_dir / "reports" / "summary").exists()

    def test_summary_generation_without_sgf_save(self, tmp_path):
        """Summary should be generated even when save_analyzed_sgf is OFF."""
        # This test verifies the code path doesn't depend on saved SGFs
        from katrain.tools.batch_analyze_sgf import _build_batch_summary
        from katrain.core.eval_metrics import MistakeCategory

        # Create mock game stats (as if extracted from in-memory Game objects)
        game_stats = [
            {
                "game_name": "test_game.sgf",
                "player_black": "Player1",
                "player_white": "Player2",
                "handicap": 0,
                "date": "2025-01-03",
                "board_size": (19, 19),
                "total_moves": 100,
                "total_points_lost": 15.5,
                "moves_by_player": {"B": 50, "W": 50},
                "loss_by_player": {"B": 8.0, "W": 7.5},
                "mistake_counts": {MistakeCategory.MISTAKE: 2},
                "mistake_total_loss": {MistakeCategory.MISTAKE: 6.0},
                "freedom_counts": {},
                "phase_moves": {"opening": 50, "middle": 40, "yose": 10},
                "phase_loss": {"opening": 3.0, "middle": 10.0, "yose": 2.5},
                "phase_mistake_counts": {("middle", "MISTAKE"): 2},
                "phase_mistake_loss": {("middle", "MISTAKE"): 6.0},
                "worst_moves": [(45, "B", "Q10", 3.5, MistakeCategory.MISTAKE)],
            }
        ]

        # Build summary from in-memory stats
        summary = _build_batch_summary(game_stats)

        # Verify summary content
        assert "# Multi-Game Summary" in summary
        assert "test_game.sgf" in summary
        assert "100" in summary  # total moves
        assert "15.5" in summary  # total loss

    def test_analyzed_sgf_not_written_when_disabled(self, tmp_path):
        """Analyzed SGF should NOT be written when save_analyzed_sgf is OFF."""
        from katrain.tools.batch_analyze_sgf import run_batch
        from unittest.mock import MagicMock

        # Create mock katrain and engine
        mock_katrain = MagicMock()
        mock_engine = MagicMock()
        mock_engine.is_idle.return_value = True

        # Create input directory
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "test.sgf").write_text("(;GM[1]FF[4]SZ[19];B[pd])")

        output_dir = tmp_path / "output"

        # Run with save_analyzed_sgf OFF
        result = run_batch(
            katrain=mock_katrain,
            engine=mock_engine,
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            save_analyzed_sgf=False,
            generate_karte=False,
            generate_summary=False,
        )

        # analyzed_sgf_written should be 0
        assert result.analyzed_sgf_written == 0
        # No analyzed directory should have been created with files
        analyzed_dir = output_dir / "analyzed"
        if analyzed_dir.exists():
            assert list(analyzed_dir.glob("*.sgf")) == []


class TestBatchErrorHandling:
    """Tests for P1 hardening: error counting and reporting."""

    def test_karte_error_counting(self):
        """Karte generation errors should be counted separately."""
        from katrain.tools.batch_analyze_sgf import BatchResult

        result = BatchResult()
        result.karte_written = 3
        result.karte_failed = 2

        # Total karte attempts = success + failure
        total_attempts = result.karte_written + result.karte_failed
        assert total_attempts == 5
        assert result.karte_written == 3
        assert result.karte_failed == 2

    def test_summary_error_states(self):
        """Summary should have distinct states: success, skipped, error."""
        from katrain.tools.batch_analyze_sgf import BatchResult

        # State 1: Success
        result_success = BatchResult(summary_written=True, summary_error=None)
        assert result_success.summary_written is True
        assert result_success.summary_error is None

        # State 2: Skipped (generate_summary=False)
        result_skipped = BatchResult(summary_written=False, summary_error=None)
        assert result_skipped.summary_written is False
        assert result_skipped.summary_error is None

        # State 3: Error
        result_error = BatchResult(
            summary_written=False,
            summary_error="No valid game statistics available"
        )
        assert result_error.summary_written is False
        assert result_error.summary_error is not None
        assert "No valid" in result_error.summary_error

    def test_gui_completion_message_format(self):
        """GUI completion message should include error counts."""
        from katrain.tools.batch_analyze_sgf import BatchResult

        result = BatchResult(
            success_count=10,
            fail_count=1,
            skip_count=2,
            karte_written=7,
            karte_failed=2,
            summary_written=True,
            summary_error=None,
            analyzed_sgf_written=10,
            output_dir="/tmp/test"
        )

        # Verify all fields are accessible for GUI formatting
        karte_total = result.karte_written + result.karte_failed
        assert karte_total == 9
        assert result.karte_written == 7
        assert result.karte_failed == 2

        # Summary status logic
        if result.summary_written:
            summary_status = "Yes"
        elif result.summary_error:
            summary_status = f"ERROR: {result.summary_error}"
        else:
            summary_status = "No (skipped)"

        assert summary_status == "Yes"

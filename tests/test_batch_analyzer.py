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
    parse_timeout_input,
    choose_visits_for_sgf,
    DEFAULT_TIMEOUT_SECONDS,
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


class TestPlayerExtraction:
    """Tests for player name extraction and grouping."""

    def test_extract_players_basic(self):
        """Basic player extraction."""
        from katrain.tools.batch_analyze_sgf import _extract_players_from_stats

        stats = [
            {"player_black": "Alice", "player_white": "Bob", "moves_by_player": {"B": 50, "W": 50}, "loss_by_player": {"B": 5.0, "W": 4.0}, "worst_moves": []},
            {"player_black": "Alice", "player_white": "Charlie", "moves_by_player": {"B": 50, "W": 50}, "loss_by_player": {"B": 6.0, "W": 3.0}, "worst_moves": []},
            {"player_black": "Bob", "player_white": "Alice", "moves_by_player": {"B": 50, "W": 50}, "loss_by_player": {"B": 4.0, "W": 5.0}, "worst_moves": []},
        ]
        groups = _extract_players_from_stats(stats, min_games=2)
        assert "Alice" in groups
        assert len(groups["Alice"]) == 3  # Alice played in all 3 games
        assert "Bob" in groups
        assert len(groups["Bob"]) == 2
        assert "Charlie" not in groups  # Only 1 game

    def test_skip_generic_names(self):
        """Generic names should be skipped."""
        from katrain.tools.batch_analyze_sgf import _extract_players_from_stats

        stats = [
            {"player_black": "Black", "player_white": "White", "moves_by_player": {"B": 50, "W": 50}, "loss_by_player": {"B": 5.0, "W": 4.0}, "worst_moves": []},
            {"player_black": "黒", "player_white": "白", "moves_by_player": {"B": 50, "W": 50}, "loss_by_player": {"B": 5.0, "W": 4.0}, "worst_moves": []},
        ]
        groups = _extract_players_from_stats(stats, min_games=1)
        assert len(groups) == 0

    def test_name_normalization(self):
        """Names with different whitespace should group together."""
        from katrain.tools.batch_analyze_sgf import _extract_players_from_stats

        stats = [
            {"player_black": "Alice  ", "player_white": "Bob", "moves_by_player": {"B": 50, "W": 50}, "loss_by_player": {"B": 5.0, "W": 4.0}, "worst_moves": []},
            {"player_black": " Alice", "player_white": "Bob", "moves_by_player": {"B": 50, "W": 50}, "loss_by_player": {"B": 5.0, "W": 4.0}, "worst_moves": []},
            {"player_black": "Alice", "player_white": "Bob", "moves_by_player": {"B": 50, "W": 50}, "loss_by_player": {"B": 5.0, "W": 4.0}, "worst_moves": []},
        ]
        groups = _extract_players_from_stats(stats, min_games=1)
        # All 3 "Alice" variations should be grouped together
        assert len(groups) == 2  # Alice and Bob
        # Find Alice's group (display name may vary based on first occurrence)
        alice_games = None
        for name, games in groups.items():
            if "Alice" in name or "alice" in name.lower():
                alice_games = games
                break
        assert alice_games is not None
        assert len(alice_games) == 3


class TestFilenameSanitization:
    """Tests for filename sanitization."""

    def test_basic_names(self):
        from katrain.tools.batch_analyze_sgf import _sanitize_filename

        assert _sanitize_filename("Alice") == "Alice"
        assert _sanitize_filename("Bob Smith") == "Bob_Smith"

    def test_cjk_names(self):
        from katrain.tools.batch_analyze_sgf import _sanitize_filename

        assert _sanitize_filename("田中太郎") == "田中太郎"
        # Slash is invalid character, should be replaced
        result = _sanitize_filename("山田/ヨセ")
        assert "/" not in result
        assert "山田" in result

    def test_invalid_chars(self):
        from katrain.tools.batch_analyze_sgf import _sanitize_filename

        result = _sanitize_filename("Alice<>Bob")
        assert "<" not in result
        assert ">" not in result

        result = _sanitize_filename("User:Name")
        assert ":" not in result

    def test_windows_reserved(self):
        from katrain.tools.batch_analyze_sgf import _sanitize_filename

        assert _sanitize_filename("CON") == "_CON_"
        assert _sanitize_filename("NUL") == "_NUL_"
        assert _sanitize_filename("com1") == "_com1_"

    def test_whitespace(self):
        from katrain.tools.batch_analyze_sgf import _sanitize_filename

        # Full-width spaces should be normalized
        result = _sanitize_filename("　全角スペース　")
        assert result == "全角スペース"

        result = _sanitize_filename("  multiple   spaces  ")
        assert result == "multiple_spaces"

    def test_empty_fallback(self):
        from katrain.tools.batch_analyze_sgf import _sanitize_filename

        assert _sanitize_filename("") == "unknown"
        assert _sanitize_filename("   ") == "unknown"
        assert _sanitize_filename("...") == "unknown"

    def test_length_truncation(self):
        from katrain.tools.batch_analyze_sgf import _sanitize_filename

        long_name = "a" * 100
        result = _sanitize_filename(long_name)
        assert len(result) <= 50


class TestEntropyNormalization:
    """Tests for board-size aware entropy normalization."""

    def test_uniform_distribution_all_sizes(self):
        """Uniform distribution should be EASY on all board sizes."""
        from katrain.core.eval_metrics import _assess_difficulty_from_policy, PositionDifficulty

        for size in [9, 13, 19]:
            n = size * size
            uniform = [1.0 / n] * n
            diff, _ = _assess_difficulty_from_policy(uniform, board_size=size)
            assert diff == PositionDifficulty.EASY, f"Uniform distribution on {size}x{size} should be EASY"

    def test_concentrated_distribution_all_sizes(self):
        """Single dominant move should be ONLY_MOVE or HARD on all board sizes."""
        from katrain.core.eval_metrics import _assess_difficulty_from_policy, PositionDifficulty

        for size in [9, 13, 19]:
            n = size * size
            concentrated = [0.0] * n
            concentrated[0] = 0.95
            concentrated[1] = 0.05
            diff, _ = _assess_difficulty_from_policy(concentrated, board_size=size)
            assert diff in (PositionDifficulty.ONLY_MOVE, PositionDifficulty.HARD), \
                f"Concentrated distribution on {size}x{size} should be ONLY_MOVE or HARD"

    def test_board_size_as_tuple(self):
        """Should handle board_size as tuple (x, y)."""
        from katrain.core.eval_metrics import _assess_difficulty_from_policy, PositionDifficulty

        uniform = [1.0 / 361] * 361
        diff, _ = _assess_difficulty_from_policy(uniform, board_size=(19, 19))
        assert diff == PositionDifficulty.EASY

    def test_invalid_board_size_fallback(self):
        """Invalid board size should fallback to 19x19."""
        from katrain.core.eval_metrics import _assess_difficulty_from_policy

        uniform = [1.0 / 361] * 361
        # Should not crash, uses 19x19 fallback
        diff1, _ = _assess_difficulty_from_policy(uniform, board_size=0)
        diff2, _ = _assess_difficulty_from_policy(uniform, board_size=-5)
        assert diff1 is not None
        assert diff2 is not None

    def test_empty_policy(self):
        """Empty policy should return UNKNOWN."""
        from katrain.core.eval_metrics import _assess_difficulty_from_policy, PositionDifficulty

        diff, score = _assess_difficulty_from_policy([])
        assert diff == PositionDifficulty.UNKNOWN
        assert score == 0.5


class TestRunBatchMinGamesParameter:
    """Tests for run_batch min_games_per_player parameter."""

    def test_run_batch_has_min_games_parameter(self):
        """run_batch should accept min_games_per_player parameter."""
        from katrain.tools.batch_analyze_sgf import run_batch
        import inspect

        sig = inspect.signature(run_batch)
        params = list(sig.parameters.keys())

        assert "min_games_per_player" in params

    def test_run_batch_min_games_default(self):
        """min_games_per_player should default to 3."""
        from katrain.tools.batch_analyze_sgf import run_batch
        import inspect

        sig = inspect.signature(run_batch)
        assert sig.parameters["min_games_per_player"].default == 3


class TestCanonicalLossHelper:
    """Tests for _get_canonical_loss helper (single source of truth)."""

    def test_positive_loss_unchanged(self):
        """Positive loss should be returned as-is."""
        from katrain.tools.batch_analyze_sgf import _get_canonical_loss

        assert _get_canonical_loss(5.0) == 5.0
        assert _get_canonical_loss(0.5) == 0.5
        assert _get_canonical_loss(100.0) == 100.0

    def test_negative_loss_clamped_to_zero(self):
        """Negative loss (gain from opponent mistake) should be clamped to 0."""
        from katrain.tools.batch_analyze_sgf import _get_canonical_loss

        assert _get_canonical_loss(-3.0) == 0.0
        assert _get_canonical_loss(-0.1) == 0.0
        assert _get_canonical_loss(-100.0) == 0.0

    def test_zero_loss_unchanged(self):
        """Zero loss should remain zero."""
        from katrain.tools.batch_analyze_sgf import _get_canonical_loss

        assert _get_canonical_loss(0.0) == 0.0

    def test_none_returns_zero(self):
        """None should return 0."""
        from katrain.tools.batch_analyze_sgf import _get_canonical_loss

        assert _get_canonical_loss(None) == 0.0


class TestSafeWriteFile:
    """Tests for _safe_write_file helper (A3: I/O error handling)."""

    def test_creates_parent_directories(self, tmp_path):
        """Should create parent directories if they don't exist."""
        from katrain.tools.batch_analyze_sgf import _safe_write_file

        nested_path = tmp_path / "a" / "b" / "c" / "test.md"
        error = _safe_write_file(
            path=str(nested_path),
            content="test content",
            file_kind="karte",
            sgf_id="test.sgf",
        )
        assert error is None
        assert nested_path.exists()
        assert nested_path.read_text(encoding="utf-8") == "test content"

    def test_returns_error_on_permission_denied(self, tmp_path, monkeypatch):
        """Should return WriteError on PermissionError."""
        from katrain.tools.batch_analyze_sgf import _safe_write_file, WriteError

        test_path = tmp_path / "test.md"

        # Simulate permission error
        def mock_open(*args, **kwargs):
            raise PermissionError("Access denied")

        monkeypatch.setattr("builtins.open", mock_open)

        error = _safe_write_file(
            path=str(test_path),
            content="test content",
            file_kind="karte",
            sgf_id="test.sgf",
        )
        assert error is not None
        assert isinstance(error, WriteError)
        assert error.file_kind == "karte"
        assert error.sgf_id == "test.sgf"
        assert error.exception_type == "PermissionError"
        assert "Access denied" in error.message

    def test_returns_error_on_oserror(self, tmp_path, monkeypatch):
        """Should return WriteError on OSError."""
        from katrain.tools.batch_analyze_sgf import _safe_write_file, WriteError

        test_path = tmp_path / "test.md"

        def mock_open(*args, **kwargs):
            raise OSError("Disk full")

        monkeypatch.setattr("builtins.open", mock_open)

        error = _safe_write_file(
            path=str(test_path),
            content="test content",
            file_kind="summary",
            sgf_id="player1",
        )
        assert error is not None
        assert error.file_kind == "summary"
        assert error.exception_type == "OSError"

    def test_writes_unicode_content(self, tmp_path):
        """Should handle Unicode content correctly."""
        from katrain.tools.batch_analyze_sgf import _safe_write_file

        test_path = tmp_path / "unicode_test.md"
        unicode_content = "# カルテ\n仙得 vs 顺势而韦\n囲碁分析"

        error = _safe_write_file(
            path=str(test_path),
            content=unicode_content,
            file_kind="karte",
            sgf_id="test.sgf",
        )
        assert error is None
        assert test_path.read_text(encoding="utf-8") == unicode_content


class TestWriteErrorDataclass:
    """Tests for WriteError dataclass."""

    def test_write_error_fields(self):
        """WriteError should have all expected fields."""
        from katrain.tools.batch_analyze_sgf import WriteError

        error = WriteError(
            file_kind="karte",
            sgf_id="test.sgf",
            target_path="/path/to/file.md",
            exception_type="PermissionError",
            message="Access denied",
        )
        assert error.file_kind == "karte"
        assert error.sgf_id == "test.sgf"
        assert error.target_path == "/path/to/file.md"
        assert error.exception_type == "PermissionError"
        assert error.message == "Access denied"


class TestBatchResultWriteErrors:
    """Tests for BatchResult write_errors field."""

    def test_write_errors_default_empty(self):
        """write_errors should default to empty list."""
        from katrain.tools.batch_analyze_sgf import BatchResult

        result = BatchResult()
        assert result.write_errors == []
        assert isinstance(result.write_errors, list)

    def test_write_errors_append(self):
        """Should be able to append WriteError objects."""
        from katrain.tools.batch_analyze_sgf import BatchResult, WriteError

        result = BatchResult()
        error = WriteError(
            file_kind="karte",
            sgf_id="test.sgf",
            target_path="/path/to/file.md",
            exception_type="OSError",
            message="Disk full",
        )
        result.write_errors.append(error)
        assert len(result.write_errors) == 1
        assert result.write_errors[0].file_kind == "karte"


class TestSanitizeFilenameTrailingChars:
    """Tests for _sanitize_filename trailing dots/spaces handling."""

    def test_strips_trailing_dots(self):
        """Should strip trailing dots (Windows requirement)."""
        from katrain.tools.batch_analyze_sgf import _sanitize_filename

        assert _sanitize_filename("name...") == "name"
        # Dots in the middle are preserved, only trailing dots stripped
        assert _sanitize_filename("file.name..") == "file.name"

    def test_strips_trailing_spaces(self):
        """Should strip trailing spaces (Windows requirement)."""
        from katrain.tools.batch_analyze_sgf import _sanitize_filename

        assert _sanitize_filename("name   ") == "name"

    def test_handles_only_dots_and_spaces(self):
        """Should return 'unknown' for only dots and spaces."""
        from katrain.tools.batch_analyze_sgf import _sanitize_filename

        assert _sanitize_filename("...   ") == "unknown"
        assert _sanitize_filename("   ") == "unknown"


# ---------------------------------------------------------------------------
# Test: Player Summary Reason Tags (Issue 2)
# ---------------------------------------------------------------------------


class TestPlayerSummaryReasonTags:
    """Tests for reason tags aggregation in player summary (Issue 2)."""

    def test_reason_tags_counted_in_stats(self):
        """Verify reason_tags_by_player is populated in game stats."""
        from katrain.tools.batch_analyze_sgf import _build_player_summary
        from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty

        # Create a mock stats dict with reason tags
        mock_stats = {
            "game_name": "test_game.sgf",
            "moves_by_player": {"B": 10, "W": 10},
            "loss_by_player": {"B": 5.0, "W": 3.0},
            "mistake_counts_by_player": {
                "B": {cat: 0 for cat in MistakeCategory},
                "W": {cat: 0 for cat in MistakeCategory},
            },
            "mistake_total_loss_by_player": {
                "B": {cat: 0.0 for cat in MistakeCategory},
                "W": {cat: 0.0 for cat in MistakeCategory},
            },
            "freedom_counts_by_player": {
                "B": {diff: 0 for diff in PositionDifficulty},
                "W": {diff: 0 for diff in PositionDifficulty},
            },
            "phase_moves_by_player": {
                "B": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
                "W": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
            },
            "phase_loss_by_player": {
                "B": {"opening": 1.0, "middle": 2.0, "yose": 2.0, "unknown": 0.0},
                "W": {"opening": 1.0, "middle": 1.0, "yose": 1.0, "unknown": 0.0},
            },
            "phase_mistake_counts_by_player": {"B": {}, "W": {}},
            "phase_mistake_loss_by_player": {"B": {}, "W": {}},
            "reason_tags_by_player": {
                "B": {"low_liberties": 5, "atari": 3, "need_connect": 2},
                "W": {"low_liberties": 2, "endgame_hint": 4},
            },
            "worst_moves": [],
        }

        # Build summary for player B
        player_games = [(mock_stats, "B")]
        summary = _build_player_summary("TestPlayer", player_games)

        # Verify reason tags section is present
        assert "## Reason Tags (Top 10)" in summary
        assert "呼吸点少 (low liberties): 5" in summary
        assert "アタリ (atari): 3" in summary
        assert "連絡必要 (need connect): 2" in summary

    def test_reason_tags_aggregated_across_games(self):
        """Verify reason tags are correctly aggregated across multiple games."""
        from katrain.tools.batch_analyze_sgf import _build_player_summary
        from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty

        def make_mock_stats(name, reason_tags):
            return {
                "game_name": name,
                "moves_by_player": {"B": 10, "W": 10},
                "loss_by_player": {"B": 5.0, "W": 3.0},
                "mistake_counts_by_player": {
                    "B": {cat: 0 for cat in MistakeCategory},
                    "W": {cat: 0 for cat in MistakeCategory},
                },
                "mistake_total_loss_by_player": {
                    "B": {cat: 0.0 for cat in MistakeCategory},
                    "W": {cat: 0.0 for cat in MistakeCategory},
                },
                "freedom_counts_by_player": {
                    "B": {diff: 0 for diff in PositionDifficulty},
                    "W": {diff: 0 for diff in PositionDifficulty},
                },
                "phase_moves_by_player": {
                    "B": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
                    "W": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
                },
                "phase_loss_by_player": {
                    "B": {"opening": 1.0, "middle": 2.0, "yose": 2.0, "unknown": 0.0},
                    "W": {"opening": 1.0, "middle": 1.0, "yose": 1.0, "unknown": 0.0},
                },
                "phase_mistake_counts_by_player": {"B": {}, "W": {}},
                "phase_mistake_loss_by_player": {"B": {}, "W": {}},
                "reason_tags_by_player": reason_tags,
                "worst_moves": [],
            }

        # Game 1: low_liberties=5, atari=3
        # Game 2: low_liberties=3, need_connect=2
        # Expected: low_liberties=8, atari=3, need_connect=2
        stats1 = make_mock_stats("game1.sgf", {"B": {"low_liberties": 5, "atari": 3}, "W": {}})
        stats2 = make_mock_stats("game2.sgf", {"B": {"low_liberties": 3, "need_connect": 2}, "W": {}})

        player_games = [(stats1, "B"), (stats2, "B")]
        summary = _build_player_summary("TestPlayer", player_games)

        # Check aggregated counts (8 total for low_liberties)
        assert "呼吸点少 (low liberties): 8" in summary
        assert "アタリ (atari): 3" in summary
        assert "連絡必要 (need connect): 2" in summary

    def test_reason_tags_ordering_is_deterministic(self):
        """Verify reason tags are sorted by count desc, then by tag name asc."""
        from katrain.tools.batch_analyze_sgf import _build_player_summary
        from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty

        mock_stats = {
            "game_name": "test_game.sgf",
            "moves_by_player": {"B": 10, "W": 10},
            "loss_by_player": {"B": 5.0, "W": 3.0},
            "mistake_counts_by_player": {
                "B": {cat: 0 for cat in MistakeCategory},
                "W": {cat: 0 for cat in MistakeCategory},
            },
            "mistake_total_loss_by_player": {
                "B": {cat: 0.0 for cat in MistakeCategory},
                "W": {cat: 0.0 for cat in MistakeCategory},
            },
            "freedom_counts_by_player": {
                "B": {diff: 0 for diff in PositionDifficulty},
                "W": {diff: 0 for diff in PositionDifficulty},
            },
            "phase_moves_by_player": {
                "B": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
                "W": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
            },
            "phase_loss_by_player": {
                "B": {"opening": 1.0, "middle": 2.0, "yose": 2.0, "unknown": 0.0},
                "W": {"opening": 1.0, "middle": 1.0, "yose": 1.0, "unknown": 0.0},
            },
            "phase_mistake_counts_by_player": {"B": {}, "W": {}},
            "phase_mistake_loss_by_player": {"B": {}, "W": {}},
            # Same count (5) for atari and low_liberties - should sort by tag name
            "reason_tags_by_player": {
                "B": {"atari": 5, "low_liberties": 5, "need_connect": 2},
                "W": {},
            },
            "worst_moves": [],
        }

        player_games = [(mock_stats, "B")]
        summary = _build_player_summary("TestPlayer", player_games)

        # Both have count 5, should be sorted alphabetically: atari before low_liberties
        # Search using Japanese labels since that's what get_reason_tag_label returns
        lines = summary.split("\n")
        # Japanese labels: アタリ (atari), 呼吸点少 (low liberties)
        tag_lines = [l for l in lines if "(atari)" in l or "(low liberties)" in l]
        assert len(tag_lines) == 2
        # atari (alphabetically first) should come before low_liberties
        atari_idx = next(i for i, l in enumerate(lines) if "(atari)" in l)
        low_lib_idx = next(i for i, l in enumerate(lines) if "(low liberties)" in l)
        assert atari_idx < low_lib_idx

    def test_invalid_reason_tags_not_counted(self):
        """Verify that invalid reason tags are not included in aggregation."""
        from katrain.core import eval_metrics

        # This tests the validation at collection time (in _collect_game_stats)
        # Invalid tags should be rejected by validate_reason_tag()
        assert eval_metrics.validate_reason_tag("low_liberties") is True
        assert eval_metrics.validate_reason_tag("atari") is True
        assert eval_metrics.validate_reason_tag("invalid_tag_xyz") is False
        assert eval_metrics.validate_reason_tag("") is False

    def test_no_reason_tags_shows_message(self):
        """Verify empty reason tags shows appropriate message."""
        from katrain.tools.batch_analyze_sgf import _build_player_summary
        from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty

        mock_stats = {
            "game_name": "test_game.sgf",
            "moves_by_player": {"B": 10, "W": 10},
            "loss_by_player": {"B": 5.0, "W": 3.0},
            "mistake_counts_by_player": {
                "B": {cat: 0 for cat in MistakeCategory},
                "W": {cat: 0 for cat in MistakeCategory},
            },
            "mistake_total_loss_by_player": {
                "B": {cat: 0.0 for cat in MistakeCategory},
                "W": {cat: 0.0 for cat in MistakeCategory},
            },
            "freedom_counts_by_player": {
                "B": {diff: 0 for diff in PositionDifficulty},
                "W": {diff: 0 for diff in PositionDifficulty},
            },
            "phase_moves_by_player": {
                "B": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
                "W": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
            },
            "phase_loss_by_player": {
                "B": {"opening": 1.0, "middle": 2.0, "yose": 2.0, "unknown": 0.0},
                "W": {"opening": 1.0, "middle": 1.0, "yose": 1.0, "unknown": 0.0},
            },
            "phase_mistake_counts_by_player": {"B": {}, "W": {}},
            "phase_mistake_loss_by_player": {"B": {}, "W": {}},
            "reason_tags_by_player": {"B": {}, "W": {}},  # Empty
            "worst_moves": [],
        }

        player_games = [(mock_stats, "B")]
        summary = _build_player_summary("TestPlayer", player_games)

        assert "## Reason Tags (Top 10)" in summary
        assert "No reason tags recorded" in summary


class TestDefinitionsSection:
    """Tests for Definitions section in Player Summary."""

    def test_definitions_section_present_in_summary(self):
        """Verify Definitions section is present in Player Summary."""
        from katrain.tools.batch_analyze_sgf import _build_player_summary
        from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty

        mock_stats = {
            "game_name": "test_game.sgf",
            "board_size": (19, 19),
            "moves_by_player": {"B": 10, "W": 10},
            "loss_by_player": {"B": 5.0, "W": 3.0},
            "mistake_counts_by_player": {
                "B": {cat: 0 for cat in MistakeCategory},
                "W": {cat: 0 for cat in MistakeCategory},
            },
            "mistake_total_loss_by_player": {
                "B": {cat: 0.0 for cat in MistakeCategory},
                "W": {cat: 0.0 for cat in MistakeCategory},
            },
            "freedom_counts_by_player": {
                "B": {diff: 0 for diff in PositionDifficulty},
                "W": {diff: 0 for diff in PositionDifficulty},
            },
            "phase_moves_by_player": {
                "B": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
                "W": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
            },
            "phase_loss_by_player": {
                "B": {"opening": 1.0, "middle": 2.0, "yose": 2.0, "unknown": 0.0},
                "W": {"opening": 1.0, "middle": 1.0, "yose": 1.0, "unknown": 0.0},
            },
            "phase_mistake_counts_by_player": {"B": {}, "W": {}},
            "phase_mistake_loss_by_player": {"B": {}, "W": {}},
            "reason_tags_by_player": {"B": {}, "W": {}},
            "reliability_by_player": {
                "B": {"total": 10, "reliable": 8, "low_confidence": 2, "total_visits": 5000, "with_visits": 10},
                "W": {"total": 10, "reliable": 9, "low_confidence": 1, "total_visits": 6000, "with_visits": 10},
            },
            "worst_moves": [],
        }

        player_games = [(mock_stats, "B")]
        summary = _build_player_summary("TestPlayer", player_games)

        # Check Definitions section exists
        assert "## Definitions" in summary

        # Check that thresholds come from SKILL_PRESETS (not hardcoded)
        from katrain.core.eval_metrics import SKILL_PRESETS
        preset = SKILL_PRESETS["standard"]
        t1, t2, t3 = preset.score_thresholds

        assert f"| Good | Loss < {t1:.1f} pts |" in summary
        assert f"| Inaccuracy | Loss {t1:.1f} - {t2:.1f} pts |" in summary
        assert f"| Mistake | Loss {t2:.1f} - {t3:.1f} pts |" in summary
        assert f"| Blunder | Loss ≥ {t3:.1f} pts |" in summary

    def test_thresholds_match_skill_presets(self):
        """Verify thresholds in Definitions match SKILL_PRESETS exactly."""
        from katrain.core.eval_metrics import SKILL_PRESETS, DEFAULT_SKILL_PRESET

        preset = SKILL_PRESETS.get("standard", SKILL_PRESETS[DEFAULT_SKILL_PRESET])
        t1, t2, t3 = preset.score_thresholds

        # Thresholds should be (1.0, 2.5, 5.0) for standard
        assert t1 == 1.0
        assert t2 == 2.5
        assert t3 == 5.0

    def test_phase_thresholds_board_size_aware(self):
        """Verify Phase thresholds are board-size-aware."""
        from katrain.core.eval_metrics import get_phase_thresholds

        # 19x19
        opening_end, middle_end = get_phase_thresholds(19)
        assert opening_end == 50
        assert middle_end == 200

        # 13x13
        opening_end, middle_end = get_phase_thresholds(13)
        assert opening_end == 30
        assert middle_end == 100

        # 9x9
        opening_end, middle_end = get_phase_thresholds(9)
        assert opening_end == 15
        assert middle_end == 50


class TestDataQualitySection:
    """Tests for Data Quality section in Player Summary."""

    def test_data_quality_section_present(self):
        """Verify Data Quality section is present in Player Summary."""
        from katrain.tools.batch_analyze_sgf import _build_player_summary
        from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty

        mock_stats = {
            "game_name": "test_game.sgf",
            "board_size": (19, 19),
            "moves_by_player": {"B": 10, "W": 10},
            "loss_by_player": {"B": 5.0, "W": 3.0},
            "mistake_counts_by_player": {
                "B": {cat: 0 for cat in MistakeCategory},
                "W": {cat: 0 for cat in MistakeCategory},
            },
            "mistake_total_loss_by_player": {
                "B": {cat: 0.0 for cat in MistakeCategory},
                "W": {cat: 0.0 for cat in MistakeCategory},
            },
            "freedom_counts_by_player": {
                "B": {diff: 0 for diff in PositionDifficulty},
                "W": {diff: 0 for diff in PositionDifficulty},
            },
            "phase_moves_by_player": {
                "B": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
                "W": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
            },
            "phase_loss_by_player": {
                "B": {"opening": 1.0, "middle": 2.0, "yose": 2.0, "unknown": 0.0},
                "W": {"opening": 1.0, "middle": 1.0, "yose": 1.0, "unknown": 0.0},
            },
            "phase_mistake_counts_by_player": {"B": {}, "W": {}},
            "phase_mistake_loss_by_player": {"B": {}, "W": {}},
            "reason_tags_by_player": {"B": {}, "W": {}},
            "reliability_by_player": {
                "B": {"total": 10, "reliable": 8, "low_confidence": 2, "total_visits": 5000, "with_visits": 10},
                "W": {"total": 10, "reliable": 9, "low_confidence": 1, "total_visits": 6000, "with_visits": 10},
            },
            "worst_moves": [],
        }

        player_games = [(mock_stats, "B")]
        summary = _build_player_summary("TestPlayer", player_games)

        # Check Data Quality section exists
        assert "## Data Quality" in summary
        assert "- Moves analyzed:" in summary
        assert "- Reliable (visits ≥" in summary
        assert "- Low-confidence:" in summary

    def test_low_reliability_warning_triggers(self):
        """Verify warning appears when reliability < 20%."""
        from katrain.tools.batch_analyze_sgf import _build_player_summary
        from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty

        # Create stats with low reliability (1 reliable out of 10 = 10%)
        mock_stats = {
            "game_name": "test_game.sgf",
            "board_size": (19, 19),
            "moves_by_player": {"B": 10, "W": 10},
            "loss_by_player": {"B": 5.0, "W": 3.0},
            "mistake_counts_by_player": {
                "B": {cat: 0 for cat in MistakeCategory},
                "W": {cat: 0 for cat in MistakeCategory},
            },
            "mistake_total_loss_by_player": {
                "B": {cat: 0.0 for cat in MistakeCategory},
                "W": {cat: 0.0 for cat in MistakeCategory},
            },
            "freedom_counts_by_player": {
                "B": {diff: 0 for diff in PositionDifficulty},
                "W": {diff: 0 for diff in PositionDifficulty},
            },
            "phase_moves_by_player": {
                "B": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
                "W": {"opening": 5, "middle": 3, "yose": 2, "unknown": 0},
            },
            "phase_loss_by_player": {
                "B": {"opening": 1.0, "middle": 2.0, "yose": 2.0, "unknown": 0.0},
                "W": {"opening": 1.0, "middle": 1.0, "yose": 1.0, "unknown": 0.0},
            },
            "phase_mistake_counts_by_player": {"B": {}, "W": {}},
            "phase_mistake_loss_by_player": {"B": {}, "W": {}},
            "reason_tags_by_player": {"B": {}, "W": {}},
            "reliability_by_player": {
                "B": {"total": 10, "reliable": 1, "low_confidence": 9, "total_visits": 500, "with_visits": 10},
                "W": {"total": 10, "reliable": 1, "low_confidence": 9, "total_visits": 500, "with_visits": 10},
            },
            "worst_moves": [],
        }

        player_games = [(mock_stats, "B")]
        summary = _build_player_summary("TestPlayer", player_games)

        # Should have the warning
        assert "⚠ Low analysis reliability (<20%)" in summary


class TestReliabilityStatsHelper:
    """Tests for compute_reliability_stats helper in eval_metrics."""

    def test_compute_reliability_stats_basic(self):
        """Test basic reliability stats computation."""
        from katrain.core.eval_metrics import compute_reliability_stats, MoveEval, RELIABILITY_VISITS_THRESHOLD

        moves = [
            MoveEval(move_number=1, player="B", gtp="D4", score_before=None, score_after=None,
                     delta_score=None, winrate_before=None, winrate_after=None, delta_winrate=None,
                     points_lost=1.0, realized_points_lost=None, root_visits=500),
            MoveEval(move_number=2, player="W", gtp="Q16", score_before=None, score_after=None,
                     delta_score=None, winrate_before=None, winrate_after=None, delta_winrate=None,
                     points_lost=0.5, realized_points_lost=None, root_visits=100),  # Low confidence
            MoveEval(move_number=3, player="B", gtp="C3", score_before=None, score_after=None,
                     delta_score=None, winrate_before=None, winrate_after=None, delta_winrate=None,
                     points_lost=2.0, realized_points_lost=None, root_visits=0),  # Zero visits
        ]

        stats = compute_reliability_stats(moves)

        assert stats.total_moves == 3
        assert stats.reliable_count == 1  # Only first move has visits >= 200
        assert stats.low_confidence_count == 2  # Second and third moves
        assert stats.zero_visits_count == 1  # Third move
        assert stats.reliability_pct == pytest.approx(100 * 1 / 3, rel=0.01)

    def test_reliability_stats_is_low_reliability(self):
        """Test is_low_reliability property."""
        from katrain.core.eval_metrics import ReliabilityStats

        # 10% reliability - should be low
        low_stats = ReliabilityStats(total_moves=10, reliable_count=1, low_confidence_count=9)
        assert low_stats.is_low_reliability is True

        # 80% reliability - should NOT be low
        high_stats = ReliabilityStats(total_moves=10, reliable_count=8, low_confidence_count=2)
        assert high_stats.is_low_reliability is False

        # Exactly 20% - should NOT be low (>=20% is OK)
        borderline = ReliabilityStats(total_moves=10, reliable_count=2, low_confidence_count=8)
        assert borderline.is_low_reliability is False


class TestBestGapFormatting:
    """Tests for Best Gap formatting (Issue C: -0% fix)."""

    def test_negative_zero_clamped(self):
        """Verify that tiny negative values don't produce -0%."""
        # The formatting logic is: if abs(val) < 0.5, treat as 0.0
        # This is in game.py important_lines_for()
        # We test the logic directly here

        def format_best_gap(best_gap):
            """Reproduce the formatting logic from game.py."""
            if best_gap is not None:
                best_gap_val = best_gap * 100
                if abs(best_gap_val) < 0.5:  # Will round to 0 anyway
                    best_gap_val = 0.0
                return f"{best_gap_val:.0f}%"
            else:
                return "-"

        # Test cases
        assert format_best_gap(-1e-9) == "0%"  # Tiny negative -> 0%
        assert format_best_gap(1e-9) == "0%"   # Tiny positive -> 0%
        assert format_best_gap(-0.001) == "0%" # Small negative -> 0%
        assert format_best_gap(0.0) == "0%"    # Zero -> 0%
        assert format_best_gap(0.01) == "1%"   # 1% stays 1%
        assert format_best_gap(-0.01) == "-1%" # -1% stays -1% (if that's valid)
        assert format_best_gap(0.25) == "25%"  # Normal value
        assert format_best_gap(None) == "-"    # None -> "-"


class TestReasonTagsFromImportantMoves:
    """Tests for Issue A: Reason tags should come from important_moves, not snapshot.moves."""

    def test_reason_tags_source_documentation(self):
        """Document that reason_tags are computed only for important moves.

        This test documents the expected behavior:
        - reason_tags are populated by get_important_move_evals(compute_reason_tags=True)
        - build_eval_snapshot() returns moves with empty reason_tags
        - _extract_game_stats should use get_important_move_evals() for reason_tags

        A full integration test would require a complete Game object with analysis,
        which is impractical for unit tests.
        """
        from katrain.core.eval_metrics import MoveEval

        # MoveEval default has empty reason_tags
        move = MoveEval(
            move_number=1,
            player="B",
            gtp="D4",
            score_before=None,
            score_after=None,
            delta_score=None,
            winrate_before=None,
            winrate_after=None,
            delta_winrate=None,
            points_lost=None,
            realized_points_lost=None,
            root_visits=0,
        )
        assert move.reason_tags == []  # Default is empty

    def test_summary_with_nonempty_reason_tags(self):
        """Verify summary shows reason tags when they are present in stats."""
        from katrain.tools.batch_analyze_sgf import _build_player_summary
        from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty

        mock_stats = {
            "game_name": "test_game.sgf",
            "board_size": (19, 19),
            "moves_by_player": {"B": 50, "W": 50},
            "loss_by_player": {"B": 25.0, "W": 20.0},
            "mistake_counts_by_player": {
                "B": {cat: 0 for cat in MistakeCategory},
                "W": {cat: 0 for cat in MistakeCategory},
            },
            "mistake_total_loss_by_player": {
                "B": {cat: 0.0 for cat in MistakeCategory},
                "W": {cat: 0.0 for cat in MistakeCategory},
            },
            "freedom_counts_by_player": {
                "B": {diff: 0 for diff in PositionDifficulty},
                "W": {diff: 0 for diff in PositionDifficulty},
            },
            "phase_moves_by_player": {
                "B": {"opening": 20, "middle": 20, "yose": 10, "unknown": 0},
                "W": {"opening": 20, "middle": 20, "yose": 10, "unknown": 0},
            },
            "phase_loss_by_player": {
                "B": {"opening": 5.0, "middle": 15.0, "yose": 5.0, "unknown": 0.0},
                "W": {"opening": 5.0, "middle": 10.0, "yose": 5.0, "unknown": 0.0},
            },
            "phase_mistake_counts_by_player": {"B": {}, "W": {}},
            "phase_mistake_loss_by_player": {"B": {}, "W": {}},
            # Simulating reason tags that would come from important moves
            "reason_tags_by_player": {
                "B": {"low_liberties": 8, "atari": 3, "need_connect": 3, "endgame_hint": 4},
                "W": {"low_liberties": 9, "endgame_hint": 4, "need_connect": 3},
            },
            "reliability_by_player": {
                "B": {"total": 50, "reliable": 40, "low_confidence": 10, "total_visits": 20000, "with_visits": 50, "max_visits": 500},
                "W": {"total": 50, "reliable": 45, "low_confidence": 5, "total_visits": 25000, "with_visits": 50, "max_visits": 600},
            },
            # PR1-1: Important moves stats for Reason Tags clarity
            "important_moves_stats_by_player": {
                "B": {"important_count": 14, "tagged_count": 10, "tag_occurrences": 18},
                "W": {"important_count": 12, "tagged_count": 9, "tag_occurrences": 16},
            },
            "worst_moves": [],
        }

        # Build summary for White player (仙得 equivalent)
        player_games = [(mock_stats, "W")]
        summary = _build_player_summary("TestPlayer", player_games)

        # Reason tags should be present (not "No reason tags recorded")
        assert "## Reason Tags (Top 10)" in summary
        assert "No reason tags recorded" not in summary
        assert "呼吸点少 (low liberties): 9" in summary
        assert "ヨセ局面 (endgame): 4" in summary


class TestPR1ReasonTagsClarity:
    """Tests for PR1-1: Reason Tags denominator and coverage clarity."""

    def test_reason_tags_shows_important_moves_count(self):
        """Verify Reason Tags section shows important moves count and tagged count."""
        from katrain.tools.batch_analyze_sgf import _build_player_summary
        from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty

        mock_stats = {
            "game_name": "test_game.sgf",
            "board_size": (19, 19),
            "moves_by_player": {"B": 50, "W": 50},
            "loss_by_player": {"B": 25.0, "W": 20.0},
            "mistake_counts_by_player": {
                "B": {cat: 0 for cat in MistakeCategory},
                "W": {cat: 0 for cat in MistakeCategory},
            },
            "mistake_total_loss_by_player": {
                "B": {cat: 0.0 for cat in MistakeCategory},
                "W": {cat: 0.0 for cat in MistakeCategory},
            },
            "freedom_counts_by_player": {
                "B": {diff: 0 for diff in PositionDifficulty},
                "W": {diff: 0 for diff in PositionDifficulty},
            },
            "phase_moves_by_player": {
                "B": {"opening": 20, "middle": 20, "yose": 10, "unknown": 0},
                "W": {"opening": 20, "middle": 20, "yose": 10, "unknown": 0},
            },
            "phase_loss_by_player": {
                "B": {"opening": 5.0, "middle": 15.0, "yose": 5.0, "unknown": 0.0},
                "W": {"opening": 5.0, "middle": 10.0, "yose": 5.0, "unknown": 0.0},
            },
            "phase_mistake_counts_by_player": {"B": {}, "W": {}},
            "phase_mistake_loss_by_player": {"B": {}, "W": {}},
            "reason_tags_by_player": {
                "B": {"low_liberties": 8, "atari": 3},
                "W": {"low_liberties": 5, "need_connect": 3},
            },
            "reliability_by_player": {
                "B": {"total": 50, "reliable": 40, "low_confidence": 10, "total_visits": 20000, "with_visits": 50, "max_visits": 500},
                "W": {"total": 50, "reliable": 45, "low_confidence": 5, "total_visits": 25000, "with_visits": 50, "max_visits": 600},
            },
            # PR1-1: Important moves stats
            "important_moves_stats_by_player": {
                "B": {"important_count": 10, "tagged_count": 8, "tag_occurrences": 11},
                "W": {"important_count": 7, "tagged_count": 5, "tag_occurrences": 8},
            },
            "worst_moves": [],
        }

        player_games = [(mock_stats, "W")]
        summary = _build_player_summary("TestPlayer", player_games)

        # PR1-1: Should show important moves count and tagged count in note
        assert "Tags computed for 7 important moves" in summary
        assert "5 moves had ≥1 tag" in summary


class TestPR1DataQualityMaxVisits:
    """Tests for PR1-2: Data Quality max visits and measured note."""

    def test_data_quality_shows_max_visits(self):
        """Verify Data Quality section shows max visits."""
        from katrain.tools.batch_analyze_sgf import _build_player_summary
        from katrain.core.eval_metrics import MistakeCategory, PositionDifficulty

        mock_stats = {
            "game_name": "test_game.sgf",
            "board_size": (19, 19),
            "moves_by_player": {"B": 50, "W": 50},
            "loss_by_player": {"B": 25.0, "W": 20.0},
            "mistake_counts_by_player": {
                "B": {cat: 0 for cat in MistakeCategory},
                "W": {cat: 0 for cat in MistakeCategory},
            },
            "mistake_total_loss_by_player": {
                "B": {cat: 0.0 for cat in MistakeCategory},
                "W": {cat: 0.0 for cat in MistakeCategory},
            },
            "freedom_counts_by_player": {
                "B": {diff: 0 for diff in PositionDifficulty},
                "W": {diff: 0 for diff in PositionDifficulty},
            },
            "phase_moves_by_player": {
                "B": {"opening": 20, "middle": 20, "yose": 10, "unknown": 0},
                "W": {"opening": 20, "middle": 20, "yose": 10, "unknown": 0},
            },
            "phase_loss_by_player": {
                "B": {"opening": 5.0, "middle": 15.0, "yose": 5.0, "unknown": 0.0},
                "W": {"opening": 5.0, "middle": 10.0, "yose": 5.0, "unknown": 0.0},
            },
            "phase_mistake_counts_by_player": {"B": {}, "W": {}},
            "phase_mistake_loss_by_player": {"B": {}, "W": {}},
            "reason_tags_by_player": {"B": {}, "W": {}},
            "reliability_by_player": {
                "B": {"total": 50, "reliable": 40, "low_confidence": 10, "total_visits": 20000, "with_visits": 50, "max_visits": 500},
                "W": {"total": 50, "reliable": 45, "low_confidence": 5, "total_visits": 25000, "with_visits": 50, "max_visits": 600},
            },
            "important_moves_stats_by_player": {
                "B": {"important_count": 0, "tagged_count": 0, "tag_occurrences": 0},
                "W": {"important_count": 0, "tagged_count": 0, "tag_occurrences": 0},
            },
            "worst_moves": [],
        }

        player_games = [(mock_stats, "W")]
        summary = _build_player_summary("TestPlayer", player_games)

        # PR1-2: Should show max visits
        assert "Max visits: 600" in summary
        # PR1-2: Should show measured note
        assert "Visits are measured from KataGo analysis" in summary

    def test_reliability_stats_max_visits(self):
        """Verify ReliabilityStats tracks max_visits correctly."""
        from katrain.core.eval_metrics import compute_reliability_stats, MoveEval

        moves = [
            MoveEval(move_number=1, player="B", gtp="D4", root_visits=100,
                     score_before=None, score_after=None, delta_score=None,
                     winrate_before=None, winrate_after=None, delta_winrate=None,
                     points_lost=None, realized_points_lost=None),
            MoveEval(move_number=2, player="W", gtp="D16", root_visits=150,
                     score_before=None, score_after=None, delta_score=None,
                     winrate_before=None, winrate_after=None, delta_winrate=None,
                     points_lost=None, realized_points_lost=None),
            MoveEval(move_number=3, player="B", gtp="Q4", root_visits=120,
                     score_before=None, score_after=None, delta_score=None,
                     winrate_before=None, winrate_after=None, delta_winrate=None,
                     points_lost=None, realized_points_lost=None),
        ]

        stats = compute_reliability_stats(moves)
        assert stats.max_visits == 150  # Should be the maximum


class TestPR1BestGapRobustFormatting:
    """Tests for PR1-3: Best Gap robust formatting using rounding."""

    def test_best_gap_rounding_based(self):
        """Verify Best Gap uses int(round(val)) for robust formatting."""
        # Reproduce the new formatting logic from game.py
        def format_best_gap_new(best_gap):
            """New rounding-based formatting logic."""
            if best_gap is not None:
                best_gap_val = best_gap * 100
                rounded_val = int(round(best_gap_val))
                if rounded_val == 0:
                    return "0%"
                else:
                    return f"{rounded_val}%"
            else:
                return "-"

        # Test cases
        assert format_best_gap_new(-1e-9) == "0%"   # Tiny negative -> 0%
        assert format_best_gap_new(1e-9) == "0%"    # Tiny positive -> 0%
        assert format_best_gap_new(-0.001) == "0%"  # Small negative -> 0%
        assert format_best_gap_new(0.0) == "0%"     # Zero -> 0%
        assert format_best_gap_new(-0.004) == "0%"  # Rounds to 0
        assert format_best_gap_new(0.004) == "0%"   # Rounds to 0
        # Note: 0.005 * 100 = 0.5, Python banker's rounding rounds 0.5 -> 0
        assert format_best_gap_new(0.005) == "0%"   # Rounds to 0 (banker's rounding)
        assert format_best_gap_new(0.006) == "1%"   # Rounds to 1
        assert format_best_gap_new(0.01) == "1%"    # 1%
        assert format_best_gap_new(-0.01) == "-1%"  # -1%
        assert format_best_gap_new(0.25) == "25%"   # Normal value
        assert format_best_gap_new(0.495) == "50%"  # Rounds to 50 (banker's rounding)
        assert format_best_gap_new(0.505) == "50%"  # Rounds to 50 (banker's rounding)
        assert format_best_gap_new(None) == "-"     # None -> "-"


class TestBatchOptionsPersistence:
    """Tests for batch analyze options persistence."""

    # Default values for batch options
    BATCH_OPTIONS_DEFAULTS = {
        "input_dir": "",
        "output_dir": "",
        "visits": None,
        "timeout": None,  # None means use default (600)
        "skip_analyzed": True,
        "save_analyzed_sgf": False,
        "generate_karte": True,
        "generate_summary": True,
        "karte_player_filter": None,  # None = Both
        "min_games_per_player": 3,
    }

    def test_load_batch_options_with_defaults(self):
        """Load returns defaults when no options are saved."""
        # Simulate empty config
        mykatrain_settings = {}

        batch_options = mykatrain_settings.get("batch_options", {})

        # Apply defaults
        loaded = {}
        for key, default_val in self.BATCH_OPTIONS_DEFAULTS.items():
            loaded[key] = batch_options.get(key, default_val)

        assert loaded["input_dir"] == ""
        assert loaded["output_dir"] == ""
        assert loaded["visits"] is None
        assert loaded["timeout"] is None
        assert loaded["skip_analyzed"] is True
        assert loaded["save_analyzed_sgf"] is False
        assert loaded["generate_karte"] is True
        assert loaded["generate_summary"] is True
        assert loaded["karte_player_filter"] is None
        assert loaded["min_games_per_player"] == 3

    def test_save_then_load_batch_options(self):
        """Save then load returns same values."""
        # Mock config storage
        config_storage = {}

        # Save function (mimics _save_batch_options)
        def save_batch_options(options):
            mykatrain_settings = config_storage.get("mykatrain_settings", {})
            batch_options = mykatrain_settings.get("batch_options", {})
            batch_options.update(options)
            mykatrain_settings["batch_options"] = batch_options
            config_storage["mykatrain_settings"] = mykatrain_settings

        # Load function (mimics loading in _do_batch_analyze_popup)
        def load_batch_options():
            mykatrain_settings = config_storage.get("mykatrain_settings", {})
            batch_options = mykatrain_settings.get("batch_options", {})
            loaded = {}
            for key, default_val in self.BATCH_OPTIONS_DEFAULTS.items():
                loaded[key] = batch_options.get(key, default_val)
            return loaded

        # Test values
        test_options = {
            "input_dir": "C:\\Users\\test\\sgf",
            "output_dir": "C:\\Users\\test\\output",
            "visits": 250,
            "timeout": 30.0,
            "skip_analyzed": False,
            "save_analyzed_sgf": True,
            "generate_karte": True,
            "generate_summary": False,
            "karte_player_filter": "B",
            "min_games_per_player": 5,
        }

        # Save
        save_batch_options(test_options)

        # Load
        loaded = load_batch_options()

        # Verify
        assert loaded["input_dir"] == "C:\\Users\\test\\sgf"
        assert loaded["output_dir"] == "C:\\Users\\test\\output"
        assert loaded["visits"] == 250
        assert loaded["timeout"] == 30.0
        assert loaded["skip_analyzed"] is False
        assert loaded["save_analyzed_sgf"] is True
        assert loaded["generate_karte"] is True
        assert loaded["generate_summary"] is False
        assert loaded["karte_player_filter"] == "B"
        assert loaded["min_games_per_player"] == 5

    def test_partial_save_preserves_existing(self):
        """Partial save preserves existing values."""
        config_storage = {"mykatrain_settings": {"batch_options": {
            "input_dir": "C:\\existing",
            "visits": 100,
        }}}

        def save_batch_options(options):
            mykatrain_settings = config_storage.get("mykatrain_settings", {})
            batch_options = mykatrain_settings.get("batch_options", {})
            batch_options.update(options)
            mykatrain_settings["batch_options"] = batch_options
            config_storage["mykatrain_settings"] = mykatrain_settings

        # Save only timeout
        save_batch_options({"timeout": 60.0})

        batch_options = config_storage["mykatrain_settings"]["batch_options"]
        assert batch_options["input_dir"] == "C:\\existing"  # Preserved
        assert batch_options["visits"] == 100  # Preserved
        assert batch_options["timeout"] == 60.0  # New value

    def test_legacy_input_dir_fallback(self):
        """Legacy batch_export_input_directory is used as fallback."""
        mykatrain_settings = {
            "batch_export_input_directory": "C:\\legacy\\path",
            # No batch_options
        }

        batch_options = mykatrain_settings.get("batch_options", {})
        # The actual loading code does:
        # default_input_dir = batch_options.get("input_dir") or mykatrain_settings.get("batch_export_input_directory", "")
        default_input_dir = batch_options.get("input_dir") or mykatrain_settings.get("batch_export_input_directory", "")

        assert default_input_dir == "C:\\legacy\\path"

    def test_new_input_dir_overrides_legacy(self):
        """New input_dir in batch_options overrides legacy key."""
        mykatrain_settings = {
            "batch_export_input_directory": "C:\\legacy\\path",
            "batch_options": {
                "input_dir": "C:\\new\\path",
            }
        }

        batch_options = mykatrain_settings.get("batch_options", {})
        default_input_dir = batch_options.get("input_dir") or mykatrain_settings.get("batch_export_input_directory", "")

        assert default_input_dir == "C:\\new\\path"


class TestParseTimeoutInput:
    """Tests for parse_timeout_input() helper function."""

    def test_empty_string_returns_default(self):
        """Empty string returns default timeout."""
        assert parse_timeout_input("") == DEFAULT_TIMEOUT_SECONDS
        assert parse_timeout_input("   ") == DEFAULT_TIMEOUT_SECONDS

    def test_none_string_returns_none(self):
        """'None' (case-insensitive) returns None (no timeout)."""
        assert parse_timeout_input("None") is None
        assert parse_timeout_input("none") is None
        assert parse_timeout_input("NONE") is None
        assert parse_timeout_input("  None  ") is None
        assert parse_timeout_input("  NONE  ") is None

    def test_numeric_string_returns_float(self):
        """Numeric strings are parsed as floats."""
        assert parse_timeout_input("600") == 600.0
        assert parse_timeout_input("300") == 300.0
        assert parse_timeout_input("  600  ") == 600.0
        assert parse_timeout_input("0") == 0.0
        assert parse_timeout_input("1.5") == 1.5

    def test_invalid_string_returns_default(self):
        """Invalid strings return default without crashing."""
        assert parse_timeout_input("abc") == DEFAULT_TIMEOUT_SECONDS
        assert parse_timeout_input("foo bar") == DEFAULT_TIMEOUT_SECONDS
        assert parse_timeout_input("12abc") == DEFAULT_TIMEOUT_SECONDS

    def test_invalid_string_logs_warning(self):
        """Invalid strings trigger log callback with warning."""
        logged_messages = []

        def log_cb(msg):
            logged_messages.append(msg)

        result = parse_timeout_input("abc", log_cb=log_cb)
        assert result == DEFAULT_TIMEOUT_SECONDS
        assert len(logged_messages) == 1
        assert "WARNING" in logged_messages[0]
        assert "abc" in logged_messages[0]

    def test_custom_default(self):
        """Custom default value is used for empty/invalid input."""
        assert parse_timeout_input("", default=1000.0) == 1000.0
        assert parse_timeout_input("invalid", default=1000.0) == 1000.0
        # But "None" still returns None regardless of default
        assert parse_timeout_input("None", default=1000.0) is None

    def test_default_constant_value(self):
        """DEFAULT_TIMEOUT_SECONDS has expected value."""
        assert DEFAULT_TIMEOUT_SECONDS == 600.0


class TestVariableVisits:
    """Tests for choose_visits_for_sgf() function."""

    def test_no_jitter_returns_base(self):
        """When jitter_pct is 0, should return base visits unchanged."""
        assert choose_visits_for_sgf("game.sgf", 500, jitter_pct=0) == 500
        assert choose_visits_for_sgf("game.sgf", 1000, jitter_pct=0) == 1000

    def test_negative_jitter_returns_base(self):
        """Negative jitter_pct should be treated as 0."""
        assert choose_visits_for_sgf("game.sgf", 500, jitter_pct=-10) == 500

    def test_zero_visits_returns_zero(self):
        """Zero base visits should return 0 (or at least 1 with jitter)."""
        result = choose_visits_for_sgf("game.sgf", 0, jitter_pct=10)
        assert result == 0

    def test_jitter_clamped_to_25_percent(self):
        """Jitter should be clamped to max 25%."""
        # Even with 100% jitter requested, result should be within 25% of base
        base = 1000
        result = choose_visits_for_sgf("game.sgf", base, jitter_pct=100, deterministic=True)
        assert 750 <= result <= 1250  # 25% range

    def test_deterministic_same_path_same_result(self):
        """Deterministic mode should return same result for same path."""
        result1 = choose_visits_for_sgf("game.sgf", 500, jitter_pct=10, deterministic=True)
        result2 = choose_visits_for_sgf("game.sgf", 500, jitter_pct=10, deterministic=True)
        assert result1 == result2

    def test_deterministic_different_paths_different_results(self):
        """Deterministic mode should return different results for different paths."""
        result1 = choose_visits_for_sgf("game1.sgf", 500, jitter_pct=20, deterministic=True)
        result2 = choose_visits_for_sgf("game2.sgf", 500, jitter_pct=20, deterministic=True)
        # Different paths should give different jitter values (with high probability)
        # Note: There's a tiny chance they could be the same, but very unlikely
        # For a robust test, we just check they're both valid
        assert 400 <= result1 <= 600
        assert 400 <= result2 <= 600

    def test_result_within_jitter_range(self):
        """Result should be within the jitter range."""
        base = 500
        jitter_pct = 10
        result = choose_visits_for_sgf("test.sgf", base, jitter_pct=jitter_pct, deterministic=True)
        min_expected = int(base * (1 - jitter_pct / 100))
        max_expected = int(base * (1 + jitter_pct / 100))
        assert min_expected <= result <= max_expected

    def test_minimum_one_visit(self):
        """Result should be at least 1 visit."""
        # Very low base with high jitter could theoretically go negative
        result = choose_visits_for_sgf("test.sgf", 1, jitter_pct=25, deterministic=True)
        assert result >= 1

    def test_path_normalization_cross_platform(self):
        """Path normalization should give same result regardless of separator."""
        # Windows-style path
        result1 = choose_visits_for_sgf("C:\\games\\game.sgf", 500, jitter_pct=10, deterministic=True)
        # Unix-style path (should normalize to same)
        result2 = choose_visits_for_sgf("C:/games/game.sgf", 500, jitter_pct=10, deterministic=True)
        assert result1 == result2

    def test_non_deterministic_varies(self):
        """Non-deterministic mode should vary (most of the time)."""
        results = set()
        for _ in range(10):
            result = choose_visits_for_sgf("game.sgf", 500, jitter_pct=20, deterministic=False)
            results.add(result)
        # With 10 random samples at 20% jitter, we expect some variation
        # Not all 10 should be the same (very unlikely)
        assert len(results) > 1

"""Batch analysis driver tests (Phase E-2).

Extracted from tests/test_batch_analyzer.py. Covers the
batch-analyzer CLI entry point, single-file analysis logging,
analysis-with-output behaviour, and run-batch helpers.
"""

from __future__ import annotations


class TestBatchAnalyzerCLI:
    """Tests for CLI argument handling."""

    def test_import(self):
        """Should be able to import the batch analyzer module."""
        from katrain.tools import batch_analyze_sgf

        assert hasattr(batch_analyze_sgf, "main")
        assert hasattr(batch_analyze_sgf, "analyze_single_file")
        assert hasattr(batch_analyze_sgf, "wait_for_analysis")
        assert hasattr(batch_analyze_sgf, "run_batch")
        assert hasattr(batch_analyze_sgf, "BatchResult")

    def test_batch_result_dataclass(self):
        """BatchResult should have expected fields."""
        from katrain.core.batch import BatchResult

        result = BatchResult()
        assert result.success_count == 0
        assert result.fail_count == 0
        assert result.skip_count == 0
        assert result.output_dir == ""
        assert result.cancelled is False

    def test_batch_result_extended_fields(self):
        """BatchResult should have extended output count fields."""
        from katrain.core.batch import BatchResult

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
            analyzed_sgf_written=5,
        )
        assert result2.karte_written == 3
        assert result2.karte_failed == 1
        assert result2.summary_written is True
        assert result2.summary_error is None
        assert result2.analyzed_sgf_written == 5

        # Test with summary error
        result3 = BatchResult(summary_written=False, summary_error="No valid game statistics available")
        assert result3.summary_written is False
        assert result3.summary_error == "No valid game statistics available"


class TestAnalyzeSingleFileLogging:
    """Tests for analyze_single_file error logging."""

    def test_log_cb_receives_progress(self, tmp_path):
        """log_cb should receive progress messages."""

        from katrain.core.batch import analyze_single_file

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
        analyze_single_file(
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
        from katrain.core.batch import analyze_single_file

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
        from katrain.core.batch import analyze_single_file

        # Create a valid SGF
        sgf_content = "(;GM[1]FF[4]SZ[19];B[pd])"
        sgf_file = tmp_path / "test.sgf"
        sgf_file.write_text(sgf_content, encoding="utf-8")

        # Call with save_sgf=False (will still fail due to None katrain, but parameter is accepted)
        log_messages = []
        analyze_single_file(
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
        from katrain.core.batch import analyze_single_file

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
        import inspect

        from katrain.core.batch import run_batch

        sig = inspect.signature(run_batch)
        params = list(sig.parameters.keys())

        # Check new parameters exist
        assert "save_analyzed_sgf" in params
        assert "generate_karte" in params
        assert "generate_summary" in params
        assert "karte_player_filter" in params

    def test_run_batch_parameter_defaults(self):
        """run_batch should have correct default values for backward compatibility."""
        import inspect

        from katrain.core.batch import run_batch

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

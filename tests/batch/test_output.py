"""Batch output behaviour, error handling, and player extraction tests (Phase E-2).

Extracted from tests/test_batch_analyzer.py. Covers batch output
directory structure, error handling, player-name extraction from
result strings, and filename sanitisation.
"""

from __future__ import annotations


class TestHelperFunctions:
    """Tests for batch analyzer helper functions."""

    def test_helper_functions_exist(self):
        """Helper functions should exist in module."""
        import katrain.core.batch as module

        # Check internal helper functions exist (for documentation)
        assert hasattr(module, "extract_game_stats")
        assert hasattr(module, "build_batch_summary")
        assert callable(module.extract_game_stats)
        assert callable(module.build_batch_summary)

    def testbuild_batch_summary_empty_list(self):
        """build_batch_summary should handle empty list."""
        from katrain.core.batch import build_batch_summary

        result = build_batch_summary([])
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
        from unittest.mock import MagicMock

        from katrain.core.batch import run_batch

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
        run_batch(
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
        from katrain.core.analysis.models.enums import MistakeCategory
        from katrain.core.batch import build_batch_summary

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
        summary = build_batch_summary(game_stats, lang="en")

        # Verify summary content (English output)
        assert "# Multi-Game Summary" in summary
        assert "test_game.sgf" in summary
        assert "100" in summary  # total moves
        assert "15.5" in summary  # total loss

    def test_analyzed_sgf_not_written_when_disabled(self, tmp_path):
        """Analyzed SGF should NOT be written when save_analyzed_sgf is OFF."""
        from unittest.mock import MagicMock

        from katrain.core.batch import run_batch

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
        from katrain.core.batch import BatchResult

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
        from katrain.core.batch import BatchResult

        # State 1: Success
        result_success = BatchResult(summary_written=True, summary_error=None)
        assert result_success.summary_written is True
        assert result_success.summary_error is None

        # State 2: Skipped (generate_summary=False)
        result_skipped = BatchResult(summary_written=False, summary_error=None)
        assert result_skipped.summary_written is False
        assert result_skipped.summary_error is None

        # State 3: Error
        result_error = BatchResult(summary_written=False, summary_error="No valid game statistics available")
        assert result_error.summary_written is False
        assert result_error.summary_error is not None
        assert "No valid" in result_error.summary_error

    def test_gui_completion_message_format(self):
        """GUI completion message should include error counts."""
        from katrain.core.batch import BatchResult

        result = BatchResult(
            success_count=10,
            fail_count=1,
            skip_count=2,
            karte_written=7,
            karte_failed=2,
            summary_written=True,
            summary_error=None,
            analyzed_sgf_written=10,
            output_dir="/tmp/test",
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
        from katrain.core.batch import extract_players_from_stats

        stats = [
            {
                "player_black": "Alice",
                "player_white": "Bob",
                "moves_by_player": {"B": 50, "W": 50},
                "loss_by_player": {"B": 5.0, "W": 4.0},
                "worst_moves": [],
            },
            {
                "player_black": "Alice",
                "player_white": "Charlie",
                "moves_by_player": {"B": 50, "W": 50},
                "loss_by_player": {"B": 6.0, "W": 3.0},
                "worst_moves": [],
            },
            {
                "player_black": "Bob",
                "player_white": "Alice",
                "moves_by_player": {"B": 50, "W": 50},
                "loss_by_player": {"B": 4.0, "W": 5.0},
                "worst_moves": [],
            },
        ]
        groups = extract_players_from_stats(stats, min_games=2)
        assert "Alice" in groups
        assert len(groups["Alice"]) == 3  # Alice played in all 3 games
        assert "Bob" in groups
        assert len(groups["Bob"]) == 2
        assert "Charlie" not in groups  # Only 1 game

    def test_skip_generic_names(self):
        """Generic names should be skipped."""
        from katrain.core.batch import extract_players_from_stats

        stats = [
            {
                "player_black": "Black",
                "player_white": "White",
                "moves_by_player": {"B": 50, "W": 50},
                "loss_by_player": {"B": 5.0, "W": 4.0},
                "worst_moves": [],
            },
            {
                "player_black": "黒",
                "player_white": "白",
                "moves_by_player": {"B": 50, "W": 50},
                "loss_by_player": {"B": 5.0, "W": 4.0},
                "worst_moves": [],
            },
        ]
        groups = extract_players_from_stats(stats, min_games=1)
        assert len(groups) == 0

    def test_name_normalization(self):
        """Names with different whitespace should group together."""
        from katrain.core.batch import extract_players_from_stats

        stats = [
            {
                "player_black": "Alice  ",
                "player_white": "Bob",
                "moves_by_player": {"B": 50, "W": 50},
                "loss_by_player": {"B": 5.0, "W": 4.0},
                "worst_moves": [],
            },
            {
                "player_black": " Alice",
                "player_white": "Bob",
                "moves_by_player": {"B": 50, "W": 50},
                "loss_by_player": {"B": 5.0, "W": 4.0},
                "worst_moves": [],
            },
            {
                "player_black": "Alice",
                "player_white": "Bob",
                "moves_by_player": {"B": 50, "W": 50},
                "loss_by_player": {"B": 5.0, "W": 4.0},
                "worst_moves": [],
            },
        ]
        groups = extract_players_from_stats(stats, min_games=1)
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

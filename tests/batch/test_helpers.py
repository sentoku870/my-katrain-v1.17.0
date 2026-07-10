"""Batch helper-function tests (Phase E-2).

Extracted from tests/test_batch_analyzer.py. Covers entropy
normalisation, the ``--min-games`` parameter, the canonical-loss
helper, atomic file writing, and the WriteError dataclass.
"""

from __future__ import annotations


class TestFilenameSanitization:
    """Tests for filename sanitization."""

    def test_basic_names(self):
        from katrain.core.batch import sanitize_filename

        assert sanitize_filename("Alice") == "Alice"
        assert sanitize_filename("Bob Smith") == "Bob_Smith"

    def test_cjk_names(self):
        from katrain.core.batch import sanitize_filename

        assert sanitize_filename("田中太郎") == "田中太郎"
        # Slash is invalid character, should be replaced
        result = sanitize_filename("山田/ヨセ")
        assert "/" not in result
        assert "山田" in result

    def test_invalid_chars(self):
        from katrain.core.batch import sanitize_filename

        result = sanitize_filename("Alice<>Bob")
        assert "<" not in result
        assert ">" not in result

        result = sanitize_filename("User:Name")
        assert ":" not in result

    def test_windows_reserved(self):
        from katrain.core.batch import sanitize_filename

        assert sanitize_filename("CON") == "_CON_"
        assert sanitize_filename("NUL") == "_NUL_"
        assert sanitize_filename("com1") == "_com1_"

    def test_whitespace(self):
        from katrain.core.batch import sanitize_filename

        # Full-width spaces should be normalized
        result = sanitize_filename("　全角スペース　")
        assert result == "全角スペース"

        result = sanitize_filename("  multiple   spaces  ")
        assert result == "multiple_spaces"

    def test_empty_fallback(self):
        from katrain.core.batch import sanitize_filename

        assert sanitize_filename("") == "unknown"
        assert sanitize_filename("   ") == "unknown"
        assert sanitize_filename("...") == "unknown"

    def test_length_truncation(self):
        from katrain.core.batch import sanitize_filename

        long_name = "a" * 100
        result = sanitize_filename(long_name)
        assert len(result) <= 50


class TestEntropyNormalization:
    """Tests for board-size aware entropy normalization."""

    def test_uniform_distribution_all_sizes(self):
        """Uniform distribution should be EASY on all board sizes."""
        from katrain.core.analysis.logic_difficulty import _assess_difficulty_from_policy
        from katrain.core.eval_metrics import PositionDifficulty

        for size in [9, 13, 19]:
            n = size * size
            uniform = [1.0 / n] * n
            diff, _ = _assess_difficulty_from_policy(uniform, board_size=size)
            assert diff == PositionDifficulty.EASY, f"Uniform distribution on {size}x{size} should be EASY"

    def test_concentrated_distribution_all_sizes(self):
        """Single dominant move should be ONLY_MOVE or HARD on all board sizes."""
        from katrain.core.analysis.logic_difficulty import _assess_difficulty_from_policy
        from katrain.core.eval_metrics import PositionDifficulty

        for size in [9, 13, 19]:
            n = size * size
            concentrated = [0.0] * n
            concentrated[0] = 0.95
            concentrated[1] = 0.05
            diff, _ = _assess_difficulty_from_policy(concentrated, board_size=size)
            assert diff in (PositionDifficulty.ONLY_MOVE, PositionDifficulty.HARD), (
                f"Concentrated distribution on {size}x{size} should be ONLY_MOVE or HARD"
            )

    def test_board_size_as_tuple(self):
        """Should handle board_size as tuple (x, y)."""
        from katrain.core.analysis.logic_difficulty import _assess_difficulty_from_policy
        from katrain.core.eval_metrics import PositionDifficulty

        uniform = [1.0 / 361] * 361
        diff, _ = _assess_difficulty_from_policy(uniform, board_size=(19, 19))
        assert diff == PositionDifficulty.EASY

    def test_invalid_board_size_fallback(self):
        """Invalid board size should fallback to 19x19."""
        from katrain.core.analysis.logic_difficulty import _assess_difficulty_from_policy

        uniform = [1.0 / 361] * 361
        # Should not crash, uses 19x19 fallback
        diff1, _ = _assess_difficulty_from_policy(uniform, board_size=0)
        diff2, _ = _assess_difficulty_from_policy(uniform, board_size=-5)
        assert diff1 is not None
        assert diff2 is not None

    def test_empty_policy(self):
        """Empty policy should return UNKNOWN."""
        from katrain.core.analysis.logic_difficulty import _assess_difficulty_from_policy
        from katrain.core.eval_metrics import PositionDifficulty

        diff, score = _assess_difficulty_from_policy([])
        assert diff == PositionDifficulty.UNKNOWN
        assert score == 0.5


class TestRunBatchMinGamesParameter:
    """Tests for run_batch min_games_per_player parameter."""

    def test_run_batch_has_min_games_parameter(self):
        """run_batch should accept min_games_per_player parameter."""
        import inspect

        from katrain.core.batch import run_batch

        sig = inspect.signature(run_batch)
        params = list(sig.parameters.keys())

        assert "min_games_per_player" in params

    def test_run_batch_min_games_default(self):
        """min_games_per_player should default to 3."""
        import inspect

        from katrain.core.batch import run_batch

        sig = inspect.signature(run_batch)
        assert sig.parameters["min_games_per_player"].default == 3


class TestCanonicalLossHelper:
    """Tests for get_canonical_loss helper (single source of truth)."""

    def test_positive_loss_unchanged(self):
        """Positive loss should be returned as-is."""
        from katrain.core.batch import get_canonical_loss

        assert get_canonical_loss(5.0) == 5.0
        assert get_canonical_loss(0.5) == 0.5
        assert get_canonical_loss(100.0) == 100.0

    def test_negative_loss_clamped_to_zero(self):
        """Negative loss (gain from opponent mistake) should be clamped to 0."""
        from katrain.core.batch import get_canonical_loss

        assert get_canonical_loss(-3.0) == 0.0
        assert get_canonical_loss(-0.1) == 0.0
        assert get_canonical_loss(-100.0) == 0.0

    def test_zero_loss_unchanged(self):
        """Zero loss should remain zero."""
        from katrain.core.batch import get_canonical_loss

        assert get_canonical_loss(0.0) == 0.0

    def test_none_returns_zero(self):
        """None should return 0."""
        from katrain.core.batch import get_canonical_loss

        assert get_canonical_loss(None) == 0.0


class TestSafeWriteFile:
    """Tests for safe_write_file helper (A3: I/O error handling)."""

    def test_creates_parent_directories(self, tmp_path):
        """Should create parent directories if they don't exist."""
        from katrain.core.batch import safe_write_file

        nested_path = tmp_path / "a" / "b" / "c" / "test.md"
        error = safe_write_file(
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
        from katrain.core.batch import WriteError, safe_write_file

        test_path = tmp_path / "test.md"

        # Simulate permission error
        def mock_open(*args, **kwargs):
            raise PermissionError("Access denied")

        monkeypatch.setattr("builtins.open", mock_open)

        error = safe_write_file(
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
        from katrain.core.batch import safe_write_file

        test_path = tmp_path / "test.md"

        def mock_open(*args, **kwargs):
            raise OSError("Disk full")

        monkeypatch.setattr("builtins.open", mock_open)

        error = safe_write_file(
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
        from katrain.core.batch import safe_write_file

        test_path = tmp_path / "unicode_test.md"
        unicode_content = "# カルテ\n仙得 vs 顺势而韦\n囲碁分析"

        error = safe_write_file(
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
        from katrain.core.batch import WriteError

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
        from katrain.core.batch import BatchResult

        result = BatchResult()
        assert result.write_errors == []
        assert isinstance(result.write_errors, list)

    def test_write_errors_append(self):
        """Should be able to append WriteError objects."""
        from katrain.core.batch import BatchResult, WriteError

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
    """Tests for sanitize_filename trailing dots/spaces handling."""

    def test_strips_trailing_dots(self):
        """Should strip trailing dots (Windows requirement)."""
        from katrain.core.batch import sanitize_filename

        assert sanitize_filename("name...") == "name"
        # Dots in the middle are preserved, only trailing dots stripped
        assert sanitize_filename("file.name..") == "file.name"

    def test_strips_trailing_spaces(self):
        """Should strip trailing spaces (Windows requirement)."""
        from katrain.core.batch import sanitize_filename

        assert sanitize_filename("name   ") == "name"

    def test_handles_only_dots_and_spaces(self):
        """Should return 'unknown' for only dots and spaces."""
        from katrain.core.batch import sanitize_filename

        assert sanitize_filename("...   ") == "unknown"
        assert sanitize_filename("   ") == "unknown"


# ---------------------------------------------------------------------------

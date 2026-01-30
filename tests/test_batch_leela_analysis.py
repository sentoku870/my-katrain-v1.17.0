"""Phase 36: Leela batch analysis tests.

Tests for analyze_single_file_leela() and run_batch() with Leela engine.
CI-safe (no real engines, uses mocks).
"""
import pytest
import threading
from typing import List, Optional, Callable, Tuple
from unittest.mock import Mock, MagicMock, patch


# ---------------------------------------------------------------------------
# Mock LeelaEngine for testing
# ---------------------------------------------------------------------------

class MockLeelaEngineForBatch:
    """Mock LeelaEngine that simulates analysis behavior."""

    def __init__(self, alive: bool = True):
        self._alive = alive
        self._current_request_id: Optional[str] = None
        self._lock = threading.Lock()
        self.analysis_calls: List[dict] = []

    def is_alive(self) -> bool:
        return self._alive

    def is_idle(self) -> bool:
        with self._lock:
            return self._current_request_id is None

    def request_analysis(
        self,
        moves: List[Tuple[str, str]],
        callback: Callable,
        visits: Optional[int] = None,
        board_size: int = 19,
        komi: float = 6.5,
    ) -> bool:
        """Simulate analysis request."""
        if not self._alive:
            return False

        self.analysis_calls.append({
            "moves": moves,
            "visits": visits,
            "board_size": board_size,
            "komi": komi,
        })

        # Simulate immediate callback with mock result
        from katrain.core.leela.models import LeelaPositionEval, LeelaCandidate

        # Create a simple mock result (using actual LeelaCandidate fields)
        mock_result = LeelaPositionEval(
            candidates=[
                LeelaCandidate(
                    move="D4",
                    visits=100,
                    winrate=0.55,
                    prior=0.1,
                    pv=["D4", "Q16"],
                ),
                LeelaCandidate(
                    move="Q16",
                    visits=50,
                    winrate=0.52,
                    prior=0.08,
                    pv=["Q16", "D4"],
                ),
            ],
            root_visits=150,
            parse_error=None,
        )

        # Call callback synchronously for test simplicity
        callback(mock_result)
        return True

    def cancel_analysis(self) -> None:
        with self._lock:
            self._current_request_id = None


# ---------------------------------------------------------------------------
# Test: run_batch engine validation
# ---------------------------------------------------------------------------

class TestRunBatchEngineValidation:
    """Test run_batch() engine selection validation."""

    def test_leela_without_engine_returns_early(self, tmp_path):
        """Leela selected without leela_engine returns empty result."""
        from katrain.tools.batch_analyze_sgf import run_batch

        # Create input directory
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create mock katrain and engine
        katrain = Mock()
        katrain.config = Mock(return_value={})
        engine = Mock()  # KataGo engine (unused)

        log_messages = []

        result = run_batch(
            katrain=katrain,
            engine=engine,
            input_dir=str(input_dir),
            analysis_engine="leela",
            leela_engine=None,  # No Leela engine
            log_cb=lambda msg: log_messages.append(msg),
        )

        assert result.success_count == 0
        assert any("no leela_engine" in msg.lower() for msg in log_messages)

    def test_leela_with_dead_engine_returns_early(self, tmp_path):
        """Leela engine not alive returns empty result."""
        from katrain.tools.batch_analyze_sgf import run_batch

        # Create input directory
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        katrain = Mock()
        katrain.config = Mock(return_value={})
        engine = Mock()
        leela = MockLeelaEngineForBatch(alive=False)

        log_messages = []

        result = run_batch(
            katrain=katrain,
            engine=engine,
            input_dir=str(input_dir),
            analysis_engine="leela",
            leela_engine=leela,
            log_cb=lambda msg: log_messages.append(msg),
        )

        assert result.success_count == 0
        assert any("not running" in msg.lower() for msg in log_messages)

    def test_katago_logs_engine_type(self, tmp_path):
        """KataGo selection logs engine type."""
        from katrain.tools.batch_analyze_sgf import run_batch

        # Create input directory (empty)
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        katrain = Mock()
        katrain.config = Mock(return_value={})
        engine = Mock()

        log_messages = []

        result = run_batch(
            katrain=katrain,
            engine=engine,
            input_dir=str(input_dir),
            analysis_engine="katago",
            log_cb=lambda msg: log_messages.append(msg),
        )

        assert any("KataGo" in msg for msg in log_messages)


# ---------------------------------------------------------------------------
# Test: analyze_single_file_leela function signature
# ---------------------------------------------------------------------------

class TestAnalyzeSingleFileLeelaSignature:
    """Test analyze_single_file_leela() function exists and has correct signature."""

    def test_function_exists(self):
        """Function exists in batch module."""
        from katrain.tools.batch_analyze_sgf import analyze_single_file_leela
        assert callable(analyze_single_file_leela)

    def test_function_parameters(self):
        """Function has expected parameters."""
        import inspect
        from katrain.tools.batch_analyze_sgf import analyze_single_file_leela

        sig = inspect.signature(analyze_single_file_leela)
        params = list(sig.parameters.keys())

        # Required parameters
        assert "katrain" in params
        assert "leela_engine" in params
        assert "sgf_path" in params

        # Optional parameters
        assert "output_path" in params
        assert "visits" in params
        assert "file_timeout" in params
        assert "per_move_timeout" in params
        assert "cancel_flag" in params
        assert "log_cb" in params
        assert "save_sgf" in params
        assert "return_game" in params


# ---------------------------------------------------------------------------
# Test: run_batch with Leela parameters
# ---------------------------------------------------------------------------

class TestRunBatchLeelaParameters:
    """Test run_batch() has Leela-related parameters."""

    def test_run_batch_has_leela_params(self):
        """run_batch has analysis_engine and leela_engine parameters."""
        import inspect
        from katrain.tools.batch_analyze_sgf import run_batch

        sig = inspect.signature(run_batch)
        params = list(sig.parameters.keys())

        assert "analysis_engine" in params
        assert "leela_engine" in params
        assert "per_move_timeout" in params

    def test_run_batch_default_engine_is_katago(self):
        """Default analysis_engine is 'katago'."""
        import inspect
        from katrain.tools.batch_analyze_sgf import run_batch

        sig = inspect.signature(run_batch)
        default = sig.parameters["analysis_engine"].default

        assert default == "katago"


# ---------------------------------------------------------------------------
# Test: Phase 87.6 - Empty SGF handling and karte counter tracking
# ---------------------------------------------------------------------------

def _make_mock_katrain():
    """Create a properly mocked katrain object for Game initialization."""
    katrain = Mock()

    # Config mock that returns appropriate values for different keys
    def mock_config(key, default=None):
        configs = {
            "trainer": {
                "eval_thresholds": [0.5, 2, 5, 10],
                "save_analysis": True,
                "save_marks": True,
                "save_feedback": [True, True, True, True, True, True],
            },
            "leela": {"fast_visits": 100},
        }
        return configs.get(key, default if default is not None else {})

    katrain.config = mock_config

    # Game.__init__ calls katrain.engine.stop_pondering()
    mock_engine = Mock()
    mock_engine.stop_pondering = Mock()
    katrain.engine = mock_engine
    # Game uses katrain.log()
    katrain.log = Mock()
    # Game uses katrain.pondering
    katrain.pondering = False
    return katrain


class TestLeelaEmptySGFHandling:
    """Phase 87.6: Test that empty SGF files are handled correctly."""

    def test_leela_empty_sgf_returns_failure(self, tmp_path):
        """Empty SGF (0 moves) should return failure when return_game=True.

        Phase 87.6: Empty SGF (root node only, no moves) should be treated
        as analysis failure and return (None, empty snapshot).
        """
        from katrain.core.batch.analysis import analyze_single_file_leela
        from katrain.core.analysis.models import EvalSnapshot

        # Create an empty SGF (root node only, no moves)
        sgf_file = tmp_path / "empty.sgf"
        sgf_file.write_text("(;GM[1]FF[4]SZ[19])")

        katrain = _make_mock_katrain()
        leela = MockLeelaEngineForBatch(alive=True)

        log_messages = []

        result = analyze_single_file_leela(
            katrain=katrain,
            leela_engine=leela,
            sgf_path=str(sgf_file),
            return_game=True,
            log_cb=lambda msg: log_messages.append(msg),
        )

        # Should return tuple (None, EvalSnapshot(moves=[]))
        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        assert len(result) == 2, f"Expected 2-tuple, got {len(result)}-tuple"
        game, snapshot = result
        assert game is None, "Empty SGF should return game=None"
        assert isinstance(snapshot, EvalSnapshot), f"Expected EvalSnapshot, got {type(snapshot)}"
        assert len(snapshot.moves) == 0, f"Expected 0 moves, got {len(snapshot.moves)}"

        # Should log the error
        assert any("ERROR" in msg and "0 moves" in msg for msg in log_messages), \
            f"Expected 'ERROR: Empty SGF (0 moves)' in logs, got: {log_messages}"

    def test_leela_empty_sgf_returns_false_without_return_game(self, tmp_path):
        """Empty SGF (0 moves) should return False when return_game=False."""
        from katrain.core.batch.analysis import analyze_single_file_leela

        # Create an empty SGF (root node only, no moves)
        sgf_file = tmp_path / "empty.sgf"
        sgf_file.write_text("(;GM[1]FF[4]SZ[19])")

        katrain = _make_mock_katrain()
        leela = MockLeelaEngineForBatch(alive=True)

        result = analyze_single_file_leela(
            katrain=katrain,
            leela_engine=leela,
            sgf_path=str(sgf_file),
            return_game=False,
        )

        # Should return False
        assert result is False, f"Expected False, got {result}"


class TestLeelaKarteCounterTracking:
    """Phase 87.6: Test that karte counters track failed files correctly."""

    def test_batch_karte_failed_tracks_analysis_failures(self, tmp_path):
        """karte_failed should be incremented when analysis fails.

        Phase 87.6: When generate_karte=True, files that fail analysis
        should increment karte_failed so karte_total reflects input count.
        """
        from katrain.tools.batch_analyze_sgf import run_batch

        # Create input directory with 2 empty SGF files (will fail)
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "empty1.sgf").write_text("(;GM[1]FF[4]SZ[19])")
        (input_dir / "empty2.sgf").write_text("(;GM[1]FF[4]SZ[19])")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        katrain = _make_mock_katrain()
        # Note: Don't override katrain.config - _make_mock_katrain sets it up correctly
        engine = Mock()
        leela = MockLeelaEngineForBatch(alive=True)

        log_messages = []

        result = run_batch(
            katrain=katrain,
            engine=engine,
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            analysis_engine="leela",
            leela_engine=leela,
            generate_karte=True,
            log_cb=lambda msg: log_messages.append(msg),
        )

        # Both files should fail (empty SGF)
        assert result.fail_count == 2, f"Expected 2 failures, got {result.fail_count}"
        assert result.success_count == 0, f"Expected 0 successes, got {result.success_count}"

        # karte_failed should also be 2
        assert result.karte_failed == 2, \
            f"Expected karte_failed=2, got {result.karte_failed}"

        # karte_total = karte_written + karte_failed should be 2 (not 0/0)
        karte_total = result.karte_written + result.karte_failed
        assert karte_total == 2, \
            f"Expected karte_total=2, got karte_written={result.karte_written} + karte_failed={result.karte_failed} = {karte_total}"

    def test_batch_counters_consistency_with_mixed_results(self, tmp_path):
        """Counters should be consistent with success + fail = total input.

        Test with mixed results: 1 valid SGF (with moves) and 1 empty SGF.
        """
        from katrain.tools.batch_analyze_sgf import run_batch

        # Create input directory
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # 1 empty SGF (will fail)
        (input_dir / "empty.sgf").write_text("(;GM[1]FF[4]SZ[19])")

        # 1 SGF with moves (should succeed)
        (input_dir / "valid.sgf").write_text("(;GM[1]FF[4]SZ[19];B[dd];W[pp])")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        katrain = _make_mock_katrain()
        # Note: Don't override katrain.config - _make_mock_katrain sets it up correctly
        engine = Mock()
        leela = MockLeelaEngineForBatch(alive=True)

        log_messages = []

        result = run_batch(
            katrain=katrain,
            engine=engine,
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            analysis_engine="leela",
            leela_engine=leela,
            generate_karte=True,
            log_cb=lambda msg: log_messages.append(msg),
        )

        # Total should be 2 (1 empty + 1 valid)
        total_files = result.success_count + result.fail_count
        assert total_files == 2, \
            f"Expected total=2, got success={result.success_count} + fail={result.fail_count} = {total_files}"

        # Empty file fails, valid file succeeds
        assert result.fail_count == 1, f"Expected 1 failure (empty SGF), got {result.fail_count}"
        assert result.success_count == 1, f"Expected 1 success (valid SGF), got {result.success_count}"

        # karte_failed should match fail_count when generate_karte=True
        assert result.karte_failed == 1, \
            f"Expected karte_failed=1, got {result.karte_failed}"


# ---------------------------------------------------------------------------
# Test: LeelaEngine imports
# ---------------------------------------------------------------------------

class TestLeelaImports:
    """Test that Leela-related imports work."""

    def test_leela_engine_import(self):
        """LeelaEngine can be imported from batch module."""
        from katrain.tools.batch_analyze_sgf import LeelaEngine
        assert LeelaEngine is not None

    def test_leela_position_eval_import(self):
        """LeelaPositionEval can be imported from batch module."""
        from katrain.tools.batch_analyze_sgf import LeelaPositionEval
        assert LeelaPositionEval is not None

    def test_leela_conversion_import(self):
        """leela_position_to_move_eval can be imported from batch module."""
        from katrain.tools.batch_analyze_sgf import leela_position_to_move_eval
        assert callable(leela_position_to_move_eval)


# ---------------------------------------------------------------------------
# Test: EvalSnapshot import
# ---------------------------------------------------------------------------

class TestEvalSnapshotImport:
    """Test EvalSnapshot is properly imported for Leela analysis."""

    def test_eval_snapshot_import(self):
        """EvalSnapshot can be imported from batch module."""
        from katrain.tools.batch_analyze_sgf import EvalSnapshot
        assert EvalSnapshot is not None

    def test_move_eval_import(self):
        """MoveEval can be imported from batch module."""
        from katrain.tools.batch_analyze_sgf import MoveEval
        assert MoveEval is not None

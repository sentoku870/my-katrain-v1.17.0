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

        # Create a simple mock result
        mock_result = LeelaPositionEval(
            candidates=[
                LeelaCandidate(
                    move="D4",
                    visits=100,
                    winrate=0.55,
                    eval_pct=55.0,
                    prior=0.1,
                    pv=["D4", "Q16"],
                ),
                LeelaCandidate(
                    move="Q16",
                    visits=50,
                    winrate=0.52,
                    eval_pct=52.0,
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
# Test: Leela karte generation limitation
# ---------------------------------------------------------------------------

class TestLeelaKarteLimitation:
    """Test that Leela karte generation is appropriately limited."""

    def test_leela_karte_note_in_log(self, tmp_path):
        """Leela batch logs note about karte limitation."""
        from katrain.tools.batch_analyze_sgf import run_batch

        input_dir = tmp_path / "input"
        input_dir.mkdir()

        katrain = Mock()
        katrain.config = Mock(return_value={})
        engine = Mock()
        leela = MockLeelaEngineForBatch(alive=True)

        log_messages = []

        result = run_batch(
            katrain=katrain,
            engine=engine,
            input_dir=str(input_dir),
            analysis_engine="leela",
            leela_engine=leela,
            generate_karte=True,
            log_cb=lambda msg: log_messages.append(msg),
        )

        # Should have a note about karte limitation
        assert any("karte" in msg.lower() and "not" in msg.lower() for msg in log_messages)


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

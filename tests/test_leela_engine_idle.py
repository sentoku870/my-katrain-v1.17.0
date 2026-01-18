"""Phase 36: LeelaEngine.is_idle() unit tests.

Tests the is_idle() method state transitions and thread safety.
CI-safe (no real engines).
"""
import threading
import pytest
from typing import Optional, Callable, List
from unittest.mock import Mock, patch


# ---------------------------------------------------------------------------
# Mock LeelaEngine for testing (matches production interface)
# ---------------------------------------------------------------------------

class MockLeelaEngineWithState:
    """State transition mock for LeelaEngine.

    Simulates the production LeelaEngine's behavior for is_idle(),
    request_analysis(), and cancel_analysis().
    """

    def __init__(self):
        self._current_request_id: Optional[str] = None
        self._pending_callback: Optional[Callable] = None
        self._result_index: int = 0
        self.preset_results: List = []
        self._alive: bool = True
        self._lock = threading.Lock()  # Same as production

    def is_idle(self) -> bool:
        """Check if ready to accept new analysis request (lock protected)."""
        with self._lock:
            return self._current_request_id is None

    def is_alive(self) -> bool:
        """Check if engine process is running."""
        return self._alive

    def request_analysis(
        self,
        moves: List[str],
        callback: Callable,
        visits: Optional[int] = None,
        board_size: int = 19,
        komi: float = 6.5,
    ) -> bool:
        """Issue analysis request."""
        if not self._alive:
            return False

        with self._lock:
            if self._current_request_id is not None:
                # Cancel existing request
                self._current_request_id = None
                self._pending_callback = None

            self._current_request_id = f"mock-request-{self._result_index}"
            self._pending_callback = callback
        return True

    def complete_analysis(self, result=None):
        """Test helper: Simulate analysis completion."""
        with self._lock:
            if self._pending_callback is None:
                return

            callback = self._pending_callback
            self._current_request_id = None
            self._pending_callback = None
            self._result_index += 1

        # Call callback outside lock
        if callback and result:
            callback(result)

    def cancel_analysis(self) -> None:
        """Cancel current analysis (lock protected)."""
        with self._lock:
            self._current_request_id = None
            self._pending_callback = None

    def shutdown(self) -> None:
        """Shutdown engine."""
        self._alive = False
        self.cancel_analysis()

    def reset(self):
        """Reset for next test."""
        with self._lock:
            self._current_request_id = None
            self._pending_callback = None
            self._result_index = 0
            self._alive = True


# ---------------------------------------------------------------------------
# Test: is_idle() state transitions
# ---------------------------------------------------------------------------

class TestLeelaEngineIsIdle:
    """Test is_idle() state transitions."""

    @pytest.fixture
    def engine(self):
        """Create mock engine."""
        return MockLeelaEngineWithState()

    def test_initial_state_is_idle(self, engine):
        """Initial state: is_idle() == True."""
        assert engine.is_idle() is True

    def test_after_request_not_idle(self, engine):
        """After request_analysis(): is_idle() == False."""
        callback = Mock()
        engine.request_analysis(["D4"], callback)
        assert engine.is_idle() is False

    def test_after_completion_is_idle(self, engine):
        """After analysis completion: is_idle() == True."""
        callback = Mock()
        engine.request_analysis(["D4"], callback)
        assert engine.is_idle() is False

        engine.complete_analysis()
        assert engine.is_idle() is True

    def test_after_cancel_is_idle(self, engine):
        """After cancel_analysis(): is_idle() == True."""
        callback = Mock()
        engine.request_analysis(["D4"], callback)
        assert engine.is_idle() is False

        engine.cancel_analysis()
        assert engine.is_idle() is True

    def test_multiple_requests_replace_previous(self, engine):
        """Multiple requests replace previous (still not idle until done)."""
        callback1 = Mock()
        callback2 = Mock()

        engine.request_analysis(["D4"], callback1)
        assert engine.is_idle() is False

        engine.request_analysis(["Q16"], callback2)
        assert engine.is_idle() is False

        engine.complete_analysis()
        assert engine.is_idle() is True

    def test_shutdown_makes_not_alive(self, engine):
        """After shutdown: is_alive() == False."""
        assert engine.is_alive() is True
        engine.shutdown()
        assert engine.is_alive() is False
        # is_idle is still True after shutdown
        assert engine.is_idle() is True

    def test_request_after_shutdown_fails(self, engine):
        """request_analysis() fails after shutdown."""
        engine.shutdown()
        callback = Mock()
        result = engine.request_analysis(["D4"], callback)
        assert result is False
        # Still idle because request was rejected
        assert engine.is_idle() is True


class TestLeelaEngineIsIdleThreadSafety:
    """Test is_idle() thread safety."""

    @pytest.fixture
    def engine(self):
        """Create mock engine."""
        return MockLeelaEngineWithState()

    def test_concurrent_is_idle_reads(self, engine):
        """Multiple threads can read is_idle() concurrently."""
        results = []
        errors = []

        def read_is_idle():
            try:
                for _ in range(100):
                    results.append(engine.is_idle())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_is_idle) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 500  # 5 threads * 100 iterations

    def test_concurrent_request_and_cancel(self, engine):
        """Concurrent request and cancel don't deadlock."""
        errors = []

        def request_loop():
            try:
                for _ in range(50):
                    engine.request_analysis(["D4"], Mock())
            except Exception as e:
                errors.append(e)

        def cancel_loop():
            try:
                for _ in range(50):
                    engine.cancel_analysis()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=request_loop)
        t2 = threading.Thread(target=cancel_loop)

        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert len(errors) == 0
        assert not t1.is_alive(), "Request thread should have finished"
        assert not t2.is_alive(), "Cancel thread should have finished"


# ---------------------------------------------------------------------------
# Test: Production LeelaEngine.is_idle() (if available)
# ---------------------------------------------------------------------------

class TestProductionLeelaEngineIsIdle:
    """Test production LeelaEngine has is_idle() method."""

    def test_leela_engine_has_is_idle_method(self):
        """LeelaEngine class has is_idle() method."""
        from katrain.core.leela.engine import LeelaEngine

        assert hasattr(LeelaEngine, "is_idle")
        assert callable(getattr(LeelaEngine, "is_idle"))

    def test_leela_engine_has_cancel_analysis_method(self):
        """LeelaEngine class has cancel_analysis() method."""
        from katrain.core.leela.engine import LeelaEngine

        assert hasattr(LeelaEngine, "cancel_analysis")
        assert callable(getattr(LeelaEngine, "cancel_analysis"))

    def test_is_idle_returns_bool(self):
        """is_idle() signature returns bool."""
        from katrain.core.leela.engine import LeelaEngine
        import inspect

        sig = inspect.signature(LeelaEngine.is_idle)
        # Should have self as only parameter
        params = list(sig.parameters.keys())
        assert params == ["self"]

        # Return annotation should be bool (if present)
        if sig.return_annotation is not inspect.Signature.empty:
            assert sig.return_annotation is bool

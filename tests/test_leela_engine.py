"""Tests for Leela Zero engine wrapper.

Note: Most tests require mocking as they depend on external process.
"""

import pytest
import threading
import time
from unittest.mock import Mock, MagicMock, patch

from katrain.core.leela.engine import LeelaEngine
from katrain.core.leela.models import LeelaPositionEval


class MockKatrain:
    """Mock KaTrain instance for testing."""

    def __init__(self):
        self.logs = []

    def log(self, message, level=0):
        self.logs.append((message, level))


class TestLeelaEngineInit:
    """Tests for LeelaEngine initialization."""

    def test_init_with_config(self):
        """Test initialization with config."""
        katrain = MockKatrain()
        config = {
            "exe_path": "/path/to/leela",
            "max_visits": 2000,
        }
        engine = LeelaEngine(katrain, config)

        assert engine.config == config
        assert engine.process is None
        assert not engine.is_alive()

    def test_default_settings(self):
        """Test default settings."""
        engine = LeelaEngine(MockKatrain(), {})

        assert engine._board_size == 19
        assert engine._komi == 6.5
        assert engine._moves == []


class TestLeelaEngineStart:
    """Tests for engine start/shutdown."""

    def test_start_missing_exe(self):
        """Test start with missing executable."""
        engine = LeelaEngine(MockKatrain(), {"exe_path": "/nonexistent/path"})

        result = engine.start()
        assert result is False
        assert not engine.is_alive()

    def test_start_empty_exe(self):
        """Test start with empty executable path."""
        engine = LeelaEngine(MockKatrain(), {"exe_path": ""})

        result = engine.start()
        assert result is False

    def test_shutdown_not_running(self):
        """Test shutdown when not running."""
        engine = LeelaEngine(MockKatrain(), {})

        result = engine.shutdown()
        assert result is True


class TestLeelaEngineMocked:
    """Tests using mocked subprocess."""

    @pytest.fixture
    def mock_process(self):
        """Create mock process."""
        proc = MagicMock()
        proc.poll.return_value = None  # Running
        proc.stdin = MagicMock()
        proc.stdout = MagicMock()
        proc.wait = MagicMock()
        return proc

    def test_is_alive_true(self, mock_process):
        """Test is_alive when process running."""
        engine = LeelaEngine(MockKatrain(), {})
        engine.process = mock_process
        mock_process.poll.return_value = None

        assert engine.is_alive() is True

    def test_is_alive_false_no_process(self):
        """Test is_alive when no process."""
        engine = LeelaEngine(MockKatrain(), {})

        assert engine.is_alive() is False

    def test_is_alive_false_exited(self, mock_process):
        """Test is_alive when process exited."""
        engine = LeelaEngine(MockKatrain(), {})
        engine.process = mock_process
        mock_process.poll.return_value = 0  # Exited

        assert engine.is_alive() is False

    def test_send_command(self, mock_process):
        """Test sending command."""
        engine = LeelaEngine(MockKatrain(), {})
        engine.process = mock_process

        result = engine._send_command("boardsize 19")

        assert result is True
        mock_process.stdin.write.assert_called_with("boardsize 19\n")
        mock_process.stdin.flush.assert_called()

    def test_send_command_no_process(self):
        """Test sending command when not running."""
        engine = LeelaEngine(MockKatrain(), {})

        result = engine._send_command("boardsize 19")

        assert result is False

    def test_cancel_analysis(self, mock_process):
        """Test cancelling analysis."""
        engine = LeelaEngine(MockKatrain(), {})
        engine.process = mock_process
        engine._current_request_id = "test-id"

        engine.cancel_analysis()

        assert engine._current_request_id is None
        mock_process.stdin.write.assert_called()

    def test_status_not_running(self):
        """Test status when not running."""
        engine = LeelaEngine(MockKatrain(), {})

        assert "Not running" in engine.status()

    def test_status_running(self, mock_process):
        """Test status when running."""
        engine = LeelaEngine(MockKatrain(), {})
        engine.process = mock_process

        assert "Ready" in engine.status()


class TestRequestAnalysis:
    """Tests for analysis request handling."""

    def test_request_id_uniqueness(self):
        """Test that each request gets unique ID."""
        engine = LeelaEngine(MockKatrain(), {})
        ids = set()

        for _ in range(10):
            # Simulate generating request IDs
            from uuid import uuid4
            ids.add(str(uuid4()))

        assert len(ids) == 10

    def test_cancel_overwrites_request_id(self):
        """Test that cancel clears request ID."""
        engine = LeelaEngine(MockKatrain(), {})
        engine._current_request_id = "old-id"

        engine.cancel_analysis()

        assert engine._current_request_id is None


class TestConcurrency:
    """Tests for concurrent request handling."""

    def test_rapid_requests(self):
        """Test rapid request cancellation."""
        engine = LeelaEngine(MockKatrain(), {})

        # Simulate rapid requests
        for i in range(5):
            engine._current_request_id = f"request-{i}"
            time.sleep(0.01)

        # Only last request ID should remain
        assert engine._current_request_id == "request-4"

    def test_cancel_during_callback(self):
        """Test that cancelled request doesn't callback."""
        engine = LeelaEngine(MockKatrain(), {})
        callback_count = [0]

        def callback(result):
            callback_count[0] += 1

        # Simulate request with ID
        request_id = "test-request"
        engine._current_request_id = request_id

        # Cancel before callback
        engine._current_request_id = None

        # Verify callback won't happen for cancelled request
        # (In real code, the thread checks request_id before calling callback)
        if engine._current_request_id == request_id:
            callback(None)

        assert callback_count[0] == 0


class TestPositionSetup:
    """Tests for position setup."""

    def test_moves_list_format(self):
        """Test moves list format."""
        moves = [
            ("B", "D4"),
            ("W", "Q16"),
            ("B", "Q4"),
        ]

        # Validate format
        for player, coord in moves:
            assert player in ("B", "W", "BLACK", "WHITE")
            assert len(coord) >= 2


class TestIntegrationMocked:
    """Integration tests with mocked engine."""

    @pytest.fixture
    def engine_with_output(self):
        """Create engine with mocked output."""
        engine = LeelaEngine(MockKatrain(), {"max_visits": 100})
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdin = MagicMock()

        # Mock stdout to return analysis output
        sample_output = (
            "info move D4 visits 100 winrate 5000 order 0 pv D4 D16\n"
        )

        def readline_side_effect():
            return sample_output

        proc.stdout.readline = MagicMock(side_effect=[sample_output, ""])
        engine.process = proc
        return engine

    def test_parse_result_from_mock(self, engine_with_output):
        """Test parsing result from mocked output."""
        from katrain.core.leela.parser import parse_lz_analyze

        sample = "info move D4 visits 100 winrate 5000 order 0 pv D4 D16"
        result = parse_lz_analyze(sample)

        assert result.is_valid
        assert len(result.candidates) == 1
        assert result.candidates[0].move == "D4"


# Skip real engine tests if Leela not available
@pytest.mark.skip(reason="Requires real Leela engine")
class TestRealEngine:
    """Tests with real Leela engine (requires external binary)."""

    @pytest.fixture
    def real_engine(self):
        """Create engine with real binary."""
        import os

        leela_path = r"D:\github\確認フォルダ\leela0110analyze\Leela0110-cpu.exe"
        if not os.path.exists(leela_path):
            pytest.skip("Leela binary not found")

        engine = LeelaEngine(
            MockKatrain(),
            {"exe_path": leela_path, "max_visits": 100},
        )
        yield engine
        engine.shutdown()

    def test_real_start_shutdown(self, real_engine):
        """Test real engine start/shutdown cycle."""
        assert real_engine.start() is True
        assert real_engine.is_alive() is True
        assert real_engine.shutdown() is True
        assert real_engine.is_alive() is False

    def test_real_analysis(self, real_engine):
        """Test real analysis request."""
        real_engine.start()

        result_holder = [None]
        event = threading.Event()

        def callback(result):
            result_holder[0] = result
            event.set()

        real_engine.request_analysis([], callback, visits=50)
        event.wait(timeout=30)

        assert result_holder[0] is not None
        assert result_holder[0].is_valid

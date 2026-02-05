"""Tests for batch processing circuit breaker."""

import pytest


class TestEngineFailureTracker:
    """Test EngineFailureTracker class."""

    @pytest.fixture
    def tracker(self):
        from katrain.core.batch.orchestration import EngineFailureTracker

        return EngineFailureTracker(max_failures=3)

    def test_aborts_after_max_consecutive_failures(self, tracker):
        """Batch aborts after max consecutive engine failures."""
        assert not tracker.record_engine_failure("f1.sgf", "timeout")
        assert not tracker.record_engine_failure("f2.sgf", "timeout")
        assert tracker.record_engine_failure("f3.sgf", "timeout")
        assert tracker.should_abort()

    def test_file_errors_do_not_count(self, tracker):
        """File errors do not count toward circuit breaker."""
        for _ in range(100):
            tracker.record_file_error()

        assert tracker.consecutive_engine_failures == 0
        assert not tracker.should_abort()

    def test_success_resets_counter(self, tracker):
        """Success resets consecutive failure count."""
        tracker.record_engine_failure("f1.sgf", "timeout")
        tracker.record_engine_failure("f2.sgf", "timeout")
        tracker.record_success()

        assert tracker.consecutive_engine_failures == 0

    def test_file_errors_do_not_reset_counter(self, tracker):
        """File errors do not reset engine failure count."""
        tracker.record_engine_failure("f1.sgf", "timeout")
        tracker.record_file_error()
        tracker.record_engine_failure("f2.sgf", "timeout")
        tracker.record_file_error()

        assert tracker.consecutive_engine_failures == 2

    def test_abort_message_includes_details(self, tracker):
        """Abort message includes count and last file."""
        tracker.record_engine_failure("a.sgf", "err1")
        tracker.record_engine_failure("b.sgf", "err2")
        tracker.record_engine_failure("last.sgf", "final error")

        msg = tracker.get_abort_message()
        assert "3" in msg
        assert "last.sgf" in msg
        assert "final error" in msg


class TestAnalysisTimeoutError:
    """Test AnalysisTimeoutError exception."""

    def test_is_subclass_of_engine_error(self):
        """AnalysisTimeoutError should inherit from EngineError."""
        from katrain.core.errors import AnalysisTimeoutError, EngineError

        assert issubclass(AnalysisTimeoutError, EngineError)

    def test_can_be_raised_and_caught(self):
        """AnalysisTimeoutError can be raised and caught."""
        from katrain.core.errors import AnalysisTimeoutError

        with pytest.raises(AnalysisTimeoutError) as exc_info:
            raise AnalysisTimeoutError("Timeout after 60s", user_message="Analysis timeout")

        assert "60s" in str(exc_info.value)
        assert exc_info.value.user_message == "Analysis timeout"

    def test_caught_by_engine_error_handler(self):
        """AnalysisTimeoutError is caught by EngineError except block."""
        from katrain.core.errors import AnalysisTimeoutError, EngineError

        caught = False
        try:
            raise AnalysisTimeoutError("test")
        except EngineError:
            caught = True

        assert caught, "Should be caught by EngineError handler"


class TestBatchResultAbortedField:
    """Test BatchResult aborted field."""

    def test_batch_result_has_aborted_field(self):
        """BatchResult should have aborted field."""
        from katrain.core.batch.models import BatchResult

        result = BatchResult()
        assert hasattr(result, "aborted")
        assert result.aborted is False

    def test_batch_result_has_abort_reason(self):
        """BatchResult should have abort_reason field."""
        from katrain.core.batch.models import BatchResult

        result = BatchResult()
        assert hasattr(result, "abort_reason")
        assert result.abort_reason is None

    def test_batch_result_has_failure_counts(self):
        """BatchResult should have engine/file failure counts."""
        from katrain.core.batch.models import BatchResult

        result = BatchResult()
        assert hasattr(result, "engine_failure_count")
        assert hasattr(result, "file_error_count")
        assert result.engine_failure_count == 0
        assert result.file_error_count == 0


class TestEngineFailureTrackerEdgeCases:
    """Test edge cases for EngineFailureTracker."""

    def test_custom_max_failures(self):
        """Tracker respects custom max_failures."""
        from katrain.core.batch.orchestration import EngineFailureTracker

        tracker = EngineFailureTracker(max_failures=5)
        for i in range(4):
            assert not tracker.record_engine_failure(f"f{i}.sgf", "error")
        assert tracker.record_engine_failure("f4.sgf", "error")

    def test_success_clears_last_failure_info(self):
        """Success clears last failure file and reason."""
        from katrain.core.batch.orchestration import EngineFailureTracker

        tracker = EngineFailureTracker(max_failures=3)
        tracker.record_engine_failure("bad.sgf", "some error")
        assert tracker.last_failure_file == "bad.sgf"
        assert tracker.last_failure_reason == "some error"

        tracker.record_success()
        assert tracker.last_failure_file is None
        assert tracker.last_failure_reason is None

    def test_exactly_at_threshold(self):
        """Tracker triggers exactly at max_failures."""
        from katrain.core.batch.orchestration import EngineFailureTracker

        tracker = EngineFailureTracker(max_failures=1)
        # First failure should trigger abort
        assert tracker.record_engine_failure("f1.sgf", "error")
        assert tracker.should_abort()

    def test_mixed_success_and_failure_pattern(self):
        """Complex pattern of successes and failures."""
        from katrain.core.batch.orchestration import EngineFailureTracker

        tracker = EngineFailureTracker(max_failures=3)

        # 2 failures, then success (reset)
        tracker.record_engine_failure("a.sgf", "err")
        tracker.record_engine_failure("b.sgf", "err")
        tracker.record_success()
        assert tracker.consecutive_engine_failures == 0

        # 2 more failures
        tracker.record_engine_failure("c.sgf", "err")
        tracker.record_engine_failure("d.sgf", "err")
        assert tracker.consecutive_engine_failures == 2
        assert not tracker.should_abort()

        # File errors don't affect it
        tracker.record_file_error()
        assert tracker.consecutive_engine_failures == 2

        # 3rd engine failure triggers abort
        assert tracker.record_engine_failure("e.sgf", "final")
        assert tracker.should_abort()

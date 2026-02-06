# tests/test_test_analysis.py
"""Tests for Phase 89 test_analysis module.

CI-safe: No real KataGo binaries, GPU, or OpenCL required.
Pure unit tests for error classification logic.
"""

import pytest

from katrain.core.analysis_result import (
    EngineTestResult as AnalysisResult,
    ErrorCategory,
    classify_engine_error,
    should_offer_cpu_fallback,
    should_offer_restart,
    truncate_error_message,
)


# =============================================================================
# TestErrorCategory
# =============================================================================


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_all_categories_have_values(self):
        """All error categories have string values."""
        assert ErrorCategory.ENGINE_START_FAILED.value == "engine_start"
        assert ErrorCategory.MODEL_LOAD_FAILED.value == "model_load"
        assert ErrorCategory.BACKEND_ERROR.value == "backend"
        assert ErrorCategory.TIMEOUT.value == "timeout"
        assert ErrorCategory.LIGHTWEIGHT_MISSING.value == "lightweight_missing"
        assert ErrorCategory.UNKNOWN.value == "unknown"


# =============================================================================
# TestClassifyEngineError
# =============================================================================


class TestClassifyEngineError:
    """Tests for error classification logic."""

    # --- TIMEOUT ---

    def test_timeout_flag_returns_timeout(self):
        """is_timeout=True -> TIMEOUT regardless of error text."""
        assert classify_engine_error("any text", is_timeout=True) == ErrorCategory.TIMEOUT
        assert classify_engine_error("clGetPlatformIDs", is_timeout=True) == ErrorCategory.TIMEOUT

    # --- Strong Backend Signals ---

    @pytest.mark.parametrize(
        "error_text",
        [
            "clGetPlatformIDs returned -1",
            "Error: clGetPlatformIDs failed",
            "cl_out_of_resources: GPU memory exhausted",
            "cl_invalid_device: no valid device",
            "OpenCL error: device not found",
            "OpenCL failed to initialize",
            "No OpenCL devices available",
            "device not found in OpenCL context",
        ],
    )
    def test_strong_backend_signals(self, error_text):
        """Strong backend error patterns are classified correctly."""
        assert classify_engine_error(error_text) == ErrorCategory.BACKEND_ERROR

    # --- Weak Backend Signals ---

    @pytest.mark.parametrize(
        "error_text",
        [
            "GPU error: out of memory",
            "CUDA failed to allocate memory",
            "GPU not available for computation",
        ],
    )
    def test_weak_backend_signals(self, error_text):
        """Weak backend error patterns are classified correctly."""
        assert classify_engine_error(error_text) == ErrorCategory.BACKEND_ERROR

    # --- Model Load Errors ---

    @pytest.mark.parametrize(
        "error_text",
        [
            "Failed to load neural network model",
            "Model file not found: kata1.bin.gz",
            "Invalid model format",
            "Cannot open /path/to/model.bin",
            ".bin.gz file not found in models directory",
        ],
    )
    def test_model_load_errors(self, error_text):
        """Model load errors are classified correctly."""
        assert classify_engine_error(error_text) == ErrorCategory.MODEL_LOAD_FAILED

    # --- Engine Start Errors ---

    @pytest.mark.parametrize(
        "error_text",
        [
            "Executable file not found: katago",
            "Permission denied when running katago",
            "'katago' is not recognized as an internal or external command",
            "No such file or directory: /usr/bin/katago",
            "Cannot find the path specified",
        ],
    )
    def test_engine_start_errors(self, error_text):
        """Engine start errors are classified correctly."""
        assert classify_engine_error(error_text) == ErrorCategory.ENGINE_START_FAILED

    # --- False Positives Prevention ---

    def test_gpu_in_path_not_backend_error(self):
        """'GPU' in path should not be classified as backend error."""
        result = classify_engine_error("Loading from /GPU-models/kata.bin.gz successfully")
        assert result != ErrorCategory.BACKEND_ERROR

    def test_model_in_error_text_not_model_error(self):
        """Generic 'model' mention should not be model error."""
        result = classify_engine_error("Neural network model loaded successfully")
        assert result != ErrorCategory.MODEL_LOAD_FAILED

    # --- Unknown Errors ---

    def test_unknown_error(self):
        """Unrecognized errors are classified as UNKNOWN."""
        assert classify_engine_error("Some random error") == ErrorCategory.UNKNOWN
        assert classify_engine_error("") == ErrorCategory.UNKNOWN


# =============================================================================
# TestTestAnalysisResult
# =============================================================================


class TestAnalysisResultTests:
    """Tests for TestAnalysisResult dataclass."""

    def test_success_result(self):
        """Successful result has correct fields."""
        result = AnalysisResult(
            success=True,
            error_category=None,
            error_message=None,
        )
        assert result.success is True
        assert result.error_category is None
        assert result.error_message is None

    def test_failure_result(self):
        """Failure result has correct fields."""
        result = AnalysisResult(
            success=False,
            error_category=ErrorCategory.BACKEND_ERROR,
            error_message="clGetPlatformIDs failed",
        )
        assert result.success is False
        assert result.error_category == ErrorCategory.BACKEND_ERROR
        assert result.error_message == "clGetPlatformIDs failed"

    def test_result_is_frozen(self):
        """TestAnalysisResult is immutable (frozen dataclass)."""
        result = AnalysisResult(
            success=True,
            error_category=None,
            error_message=None,
        )
        with pytest.raises(AttributeError):
            result.success = False


# =============================================================================
# TestShouldOfferCpuFallback
# =============================================================================


class TestShouldOfferCpuFallback:
    """Tests for CPU fallback decision logic."""

    def test_backend_error_offers_fallback(self):
        """BACKEND_ERROR should offer CPU fallback."""
        result = AnalysisResult(
            success=False,
            error_category=ErrorCategory.BACKEND_ERROR,
            error_message="OpenCL error",
        )
        assert should_offer_cpu_fallback(result) is True

    def test_timeout_no_fallback(self):
        """TIMEOUT should NOT offer CPU fallback."""
        result = AnalysisResult(
            success=False,
            error_category=ErrorCategory.TIMEOUT,
            error_message="Timed out",
        )
        assert should_offer_cpu_fallback(result) is False

    def test_engine_start_no_fallback(self):
        """ENGINE_START_FAILED should NOT offer CPU fallback."""
        result = AnalysisResult(
            success=False,
            error_category=ErrorCategory.ENGINE_START_FAILED,
            error_message="Binary not found",
        )
        assert should_offer_cpu_fallback(result) is False

    def test_model_load_no_fallback(self):
        """MODEL_LOAD_FAILED should NOT offer CPU fallback."""
        result = AnalysisResult(
            success=False,
            error_category=ErrorCategory.MODEL_LOAD_FAILED,
            error_message="Model not found",
        )
        assert should_offer_cpu_fallback(result) is False

    def test_lightweight_missing_no_fallback(self):
        """LIGHTWEIGHT_MISSING should NOT offer CPU fallback."""
        result = AnalysisResult(
            success=False,
            error_category=ErrorCategory.LIGHTWEIGHT_MISSING,
            error_message="b10c128 not found",
        )
        assert should_offer_cpu_fallback(result) is False

    def test_success_no_fallback(self):
        """Successful result should NOT offer CPU fallback."""
        result = AnalysisResult(
            success=True,
            error_category=None,
            error_message=None,
        )
        assert should_offer_cpu_fallback(result) is False


# =============================================================================
# TestShouldOfferRestart
# =============================================================================


class TestShouldOfferRestart:
    """Tests for engine restart decision logic."""

    def test_timeout_offers_restart(self):
        """TIMEOUT should offer engine restart."""
        result = AnalysisResult(
            success=False,
            error_category=ErrorCategory.TIMEOUT,
            error_message="Timed out",
        )
        assert should_offer_restart(result) is True

    def test_backend_error_no_restart(self):
        """BACKEND_ERROR should NOT offer restart (will fail again)."""
        result = AnalysisResult(
            success=False,
            error_category=ErrorCategory.BACKEND_ERROR,
            error_message="OpenCL error",
        )
        assert should_offer_restart(result) is False

    def test_engine_start_no_restart(self):
        """ENGINE_START_FAILED should NOT offer restart (will fail again)."""
        result = AnalysisResult(
            success=False,
            error_category=ErrorCategory.ENGINE_START_FAILED,
            error_message="Binary not found",
        )
        assert should_offer_restart(result) is False

    def test_success_no_restart(self):
        """Successful result should NOT offer restart."""
        result = AnalysisResult(
            success=True,
            error_category=None,
            error_message=None,
        )
        assert should_offer_restart(result) is False


# =============================================================================
# TestTruncateErrorMessage
# =============================================================================


class TestTruncateErrorMessage:
    """Tests for error message truncation."""

    def test_short_message_unchanged(self):
        """Short messages are returned unchanged."""
        msg = "Short error"
        assert truncate_error_message(msg) == msg

    def test_long_message_truncated(self):
        """Long messages are truncated with ellipsis."""
        msg = "x" * 300
        result = truncate_error_message(msg, max_len=200)
        assert len(result) == 200
        assert result.endswith("...")

    def test_exact_length_unchanged(self):
        """Messages at exactly max_len are unchanged."""
        msg = "x" * 200
        result = truncate_error_message(msg, max_len=200)
        assert result == msg

    def test_custom_max_len(self):
        """Custom max_len is respected."""
        msg = "x" * 100
        result = truncate_error_message(msg, max_len=50)
        assert len(result) == 50
        assert result.endswith("...")

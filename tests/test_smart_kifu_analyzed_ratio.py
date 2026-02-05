"""Tests for Smart Kifu analyzed ratio computation (Phase 28).

Tests for:
- has_analysis_data()
- compute_analyzed_ratio_from_sgf_file()
- compute_training_set_summary()
- ImportErrorCode handling
- import_analyzed_sgf_folder()
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from katrain.core.smart_kifu.logic import (
    compute_analyzed_ratio_from_sgf_file,
    compute_training_set_summary,
    has_analysis_data,
)
from katrain.core.smart_kifu.models import (
    Context,
    GameEntry,
    ImportErrorCode,
    ImportResult,
    TrainingSetManifest,
    TrainingSetSummary,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_data_dir() -> Path:
    """Return the path to the test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def analyzed_data_dir(test_data_dir: Path) -> Path:
    """Return the path to the analyzed test data directory."""
    return test_data_dir / "analyzed"


# =============================================================================
# Tests for has_analysis_data()
# =============================================================================


class TestHasAnalysisData:
    """Tests for has_analysis_data() function."""

    def test_with_kt_data(self):
        """Node with KT data should return True."""
        node = MagicMock()
        node.analysis_from_sgf = ["some_base64_data"]
        assert has_analysis_data(node) is True

    def test_without_kt_attribute(self):
        """Node without analysis_from_sgf attribute should return False."""
        node = MagicMock(spec=[])  # No attributes
        assert has_analysis_data(node) is False

    def test_with_none(self):
        """Node with analysis_from_sgf=None should return False."""
        node = MagicMock()
        node.analysis_from_sgf = None
        assert has_analysis_data(node) is False

    def test_with_empty_list(self):
        """Node with analysis_from_sgf=[] should return False."""
        node = MagicMock()
        node.analysis_from_sgf = []
        assert has_analysis_data(node) is False

    def test_with_multiple_data(self):
        """Node with multiple KT data entries should return True."""
        node = MagicMock()
        node.analysis_from_sgf = ["data1", "data2", "data3"]
        assert has_analysis_data(node) is True


# =============================================================================
# Tests for compute_analyzed_ratio_from_sgf_file()
# =============================================================================


class TestComputeAnalyzedRatioFromSgfFile:
    """Tests for compute_analyzed_ratio_from_sgf_file() function."""

    def test_fully_analyzed(self, analyzed_data_dir: Path):
        """Fully analyzed SGF should return 1.0."""
        sgf_path = analyzed_data_dir / "fully_analyzed.sgf"
        ratio = compute_analyzed_ratio_from_sgf_file(str(sgf_path))
        assert ratio == 1.0

    def test_partial_analyzed(self, analyzed_data_dir: Path):
        """Partially analyzed SGF should return ratio between 0 and 1."""
        sgf_path = analyzed_data_dir / "partial_analyzed.sgf"
        ratio = compute_analyzed_ratio_from_sgf_file(str(sgf_path))
        # 3 out of 5 moves analyzed = 0.6
        assert ratio == pytest.approx(0.6, rel=0.01)

    def test_not_analyzed(self, analyzed_data_dir: Path):
        """Unanalyzed SGF should return 0.0."""
        sgf_path = analyzed_data_dir / "not_analyzed.sgf"
        ratio = compute_analyzed_ratio_from_sgf_file(str(sgf_path))
        assert ratio == 0.0

    def test_root_only(self, analyzed_data_dir: Path):
        """SGF with only root node should return None."""
        sgf_path = analyzed_data_dir / "root_only.sgf"
        ratio = compute_analyzed_ratio_from_sgf_file(str(sgf_path))
        assert ratio is None

    def test_with_pass(self, analyzed_data_dir: Path):
        """SGF with pass moves should correctly count all nodes."""
        sgf_path = analyzed_data_dir / "with_pass.sgf"
        ratio = compute_analyzed_ratio_from_sgf_file(str(sgf_path))
        # All 4 moves (including pass) are analyzed
        assert ratio == 1.0

    def test_with_branches(self, analyzed_data_dir: Path):
        """SGF with branches should only count mainline."""
        sgf_path = analyzed_data_dir / "with_branches.sgf"
        ratio = compute_analyzed_ratio_from_sgf_file(str(sgf_path))
        # Mainline: 4 moves, all analyzed
        assert ratio == 1.0

    def test_invalid_sgf(self):
        """Invalid SGF should return None."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sgf", delete=False) as f:
            f.write("invalid sgf content")
            f.flush()
            ratio = compute_analyzed_ratio_from_sgf_file(f.name)
            assert ratio is None

    def test_empty_file(self):
        """Empty file should return None."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sgf", delete=False) as f:
            f.write("")
            f.flush()
            ratio = compute_analyzed_ratio_from_sgf_file(f.name)
            assert ratio is None

    def test_nonexistent_file(self):
        """Nonexistent file should return None."""
        ratio = compute_analyzed_ratio_from_sgf_file("/nonexistent/path/file.sgf")
        assert ratio is None


# =============================================================================
# Tests for compute_training_set_summary()
# =============================================================================


class TestComputeTrainingSetSummary:
    """Tests for compute_training_set_summary() function."""

    def _make_entry(self, ratio: float | None) -> GameEntry:
        """Create a minimal GameEntry with the given analyzed_ratio."""
        return GameEntry(
            game_id=f"sha1:{hash(ratio)}",
            path="sgf/test.sgf",
            added_at="2026-01-17T00:00:00",
            context=Context.HUMAN,
            analyzed_ratio=ratio,
        )

    def test_empty_manifest(self):
        """Empty manifest should return zero summary."""
        manifest = TrainingSetManifest(games=[])
        summary = compute_training_set_summary(manifest)
        assert summary.total_games == 0
        assert summary.analyzed_games == 0
        assert summary.fully_analyzed_games == 0
        assert summary.average_analyzed_ratio is None
        assert summary.unanalyzed_games == 0

    def test_all_none(self):
        """All None ratios should return None average."""
        manifest = TrainingSetManifest(
            games=[
                self._make_entry(None),
                self._make_entry(None),
                self._make_entry(None),
            ]
        )
        summary = compute_training_set_summary(manifest)
        assert summary.total_games == 3
        assert summary.analyzed_games == 0
        assert summary.average_analyzed_ratio is None
        assert summary.unanalyzed_games == 3

    def test_all_fully_analyzed(self):
        """All 1.0 ratios should return fully analyzed."""
        manifest = TrainingSetManifest(
            games=[
                self._make_entry(1.0),
                self._make_entry(1.0),
            ]
        )
        summary = compute_training_set_summary(manifest)
        assert summary.total_games == 2
        assert summary.analyzed_games == 2
        assert summary.fully_analyzed_games == 2
        assert summary.average_analyzed_ratio == 1.0
        assert summary.unanalyzed_games == 0

    def test_mixed_ratios(self):
        """Mixed ratios should calculate correct average."""
        manifest = TrainingSetManifest(
            games=[
                self._make_entry(1.0),
                self._make_entry(0.5),
                self._make_entry(0.0),
                self._make_entry(None),
            ]
        )
        summary = compute_training_set_summary(manifest)
        assert summary.total_games == 4
        assert summary.analyzed_games == 3  # 1.0, 0.5, 0.0
        assert summary.fully_analyzed_games == 1  # only 1.0
        assert summary.average_analyzed_ratio == pytest.approx(0.5, rel=0.01)  # (1.0 + 0.5 + 0.0) / 3
        assert summary.unanalyzed_games == 1

    def test_zero_ratio_counted(self):
        """Zero ratio should be counted as analyzed (not None)."""
        manifest = TrainingSetManifest(
            games=[
                self._make_entry(0.0),
            ]
        )
        summary = compute_training_set_summary(manifest)
        assert summary.analyzed_games == 1
        assert summary.average_analyzed_ratio == 0.0
        assert summary.unanalyzed_games == 0


# =============================================================================
# Tests for ImportErrorCode
# =============================================================================


class TestImportErrorCode:
    """Tests for ImportErrorCode enum."""

    def test_enum_values(self):
        """Enum should have expected values."""
        assert ImportErrorCode.DUPLICATE.value == "duplicate"
        assert ImportErrorCode.PARSE_FAILED.value == "parse_failed"
        assert ImportErrorCode.FILE_NOT_FOUND.value == "file_not_found"
        assert ImportErrorCode.COPY_FAILED.value == "copy_failed"
        assert ImportErrorCode.UNKNOWN.value == "unknown"

    def test_comparison(self):
        """Enum comparison should work correctly."""
        error = ImportErrorCode.DUPLICATE
        assert error == ImportErrorCode.DUPLICATE
        assert error != ImportErrorCode.PARSE_FAILED


# =============================================================================
# Tests for ImportResult with average_analyzed_ratio
# =============================================================================


class TestImportResult:
    """Tests for ImportResult with average_analyzed_ratio field."""

    def test_default_average(self):
        """Default average_analyzed_ratio should be None."""
        result = ImportResult()
        assert result.average_analyzed_ratio is None

    def test_with_average(self):
        """average_analyzed_ratio should be set correctly."""
        result = ImportResult(
            success_count=3,
            average_analyzed_ratio=0.75,
        )
        assert result.average_analyzed_ratio == 0.75

    def test_zero_average_not_none(self):
        """Zero average should not be treated as None."""
        result = ImportResult(
            success_count=1,
            average_analyzed_ratio=0.0,
        )
        assert result.average_analyzed_ratio == 0.0
        assert result.average_analyzed_ratio is not None


# =============================================================================
# Tests for TrainingSetSummary
# =============================================================================


class TestTrainingSetSummary:
    """Tests for TrainingSetSummary dataclass."""

    def test_default_values(self):
        """Default values should be correct."""
        summary = TrainingSetSummary()
        assert summary.total_games == 0
        assert summary.analyzed_games == 0
        assert summary.fully_analyzed_games == 0
        assert summary.average_analyzed_ratio is None
        assert summary.unanalyzed_games == 0

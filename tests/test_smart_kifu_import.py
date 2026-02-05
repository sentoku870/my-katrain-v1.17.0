"""Tests for Smart Kifu import functions with ImportErrorCode (Phase 28).

Tests for:
- import_sgf_to_training_set() with compute_ratio option
- import_analyzed_sgf_folder()
"""

import shutil
from pathlib import Path

import pytest

from katrain.core.smart_kifu.io import (
    create_training_set,
    import_analyzed_sgf_folder,
    import_sgf_to_training_set,
)
from katrain.core.smart_kifu.models import Context, ImportErrorCode

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


@pytest.fixture
def temp_smart_kifu_dir(monkeypatch, tmp_path):
    """Create a temporary smart kifu directory."""
    smart_kifu_dir = tmp_path / "smart_kifu"
    training_sets_dir = smart_kifu_dir / "training_sets"
    training_sets_dir.mkdir(parents=True)

    # Monkey-patch the directory functions
    def mock_get_smart_kifu_dir():
        return smart_kifu_dir

    def mock_get_training_sets_dir():
        return training_sets_dir

    monkeypatch.setattr("katrain.core.smart_kifu.io.get_smart_kifu_dir", mock_get_smart_kifu_dir)
    monkeypatch.setattr("katrain.core.smart_kifu.io.get_training_sets_dir", mock_get_training_sets_dir)

    return training_sets_dir


# =============================================================================
# Tests for import_sgf_to_training_set()
# =============================================================================


class TestImportSgfToTrainingSet:
    """Tests for import_sgf_to_training_set() function."""

    def test_import_with_compute_ratio_true(self, temp_smart_kifu_dir, analyzed_data_dir):
        """Import with compute_ratio=True should set analyzed_ratio."""
        # Create a training set
        manifest = create_training_set("Test Set")
        assert manifest is not None
        set_id = manifest.set_id

        # Import with compute_ratio=True
        sgf_path = analyzed_data_dir / "fully_analyzed.sgf"
        entry, error_code = import_sgf_to_training_set(
            set_id=set_id,
            sgf_path=sgf_path,
            context=Context.HUMAN,
            compute_ratio=True,
        )

        assert entry is not None
        assert error_code is None
        assert entry.analyzed_ratio == 1.0

    def test_import_with_compute_ratio_false(self, temp_smart_kifu_dir, analyzed_data_dir):
        """Import with compute_ratio=False should leave analyzed_ratio as None."""
        manifest = create_training_set("Test Set")
        assert manifest is not None
        set_id = manifest.set_id

        sgf_path = analyzed_data_dir / "fully_analyzed.sgf"
        entry, error_code = import_sgf_to_training_set(
            set_id=set_id,
            sgf_path=sgf_path,
            context=Context.HUMAN,
            compute_ratio=False,
        )

        assert entry is not None
        assert error_code is None
        assert entry.analyzed_ratio is None

    def test_import_returns_duplicate_error_code(self, temp_smart_kifu_dir, analyzed_data_dir):
        """Duplicate import should return ImportErrorCode.DUPLICATE."""
        manifest = create_training_set("Test Set")
        assert manifest is not None
        set_id = manifest.set_id

        sgf_path = analyzed_data_dir / "fully_analyzed.sgf"

        # First import
        entry1, error1 = import_sgf_to_training_set(set_id=set_id, sgf_path=sgf_path, context=Context.HUMAN)
        assert entry1 is not None
        assert error1 is None

        # Second import (duplicate)
        entry2, error2 = import_sgf_to_training_set(set_id=set_id, sgf_path=sgf_path, context=Context.HUMAN)
        assert entry2 is None
        assert error2 == ImportErrorCode.DUPLICATE

    def test_import_nonexistent_file_returns_file_not_found(self, temp_smart_kifu_dir):
        """Importing nonexistent file should return FILE_NOT_FOUND."""
        manifest = create_training_set("Test Set")
        assert manifest is not None
        set_id = manifest.set_id

        entry, error_code = import_sgf_to_training_set(
            set_id=set_id,
            sgf_path=Path("/nonexistent/file.sgf"),
            context=Context.HUMAN,
        )

        assert entry is None
        assert error_code == ImportErrorCode.FILE_NOT_FOUND

    def test_import_to_nonexistent_set_returns_file_not_found(self, temp_smart_kifu_dir, analyzed_data_dir):
        """Importing to nonexistent training set should return FILE_NOT_FOUND."""
        sgf_path = analyzed_data_dir / "fully_analyzed.sgf"

        entry, error_code = import_sgf_to_training_set(
            set_id="nonexistent_set_id",
            sgf_path=sgf_path,
            context=Context.HUMAN,
        )

        assert entry is None
        assert error_code == ImportErrorCode.FILE_NOT_FOUND


# =============================================================================
# Tests for import_analyzed_sgf_folder()
# =============================================================================


class TestImportAnalyzedSgfFolder:
    """Tests for import_analyzed_sgf_folder() function."""

    def test_import_folder_success(self, temp_smart_kifu_dir, analyzed_data_dir):
        """Import folder should succeed and calculate ratios."""
        manifest = create_training_set("Test Set")
        assert manifest is not None
        set_id = manifest.set_id

        result = import_analyzed_sgf_folder(
            set_id=set_id,
            folder_path=analyzed_data_dir,
            context=Context.HUMAN,
        )

        assert result.success_count > 0
        assert result.failed_count == 0
        assert result.average_analyzed_ratio is not None

    def test_import_folder_calculates_average(self, temp_smart_kifu_dir, tmp_path, analyzed_data_dir):
        """Import folder should calculate correct average_analyzed_ratio."""
        # Create a folder with specific files
        test_folder = tmp_path / "test_sgf"
        test_folder.mkdir()

        # Copy files with known ratios
        shutil.copy(analyzed_data_dir / "fully_analyzed.sgf", test_folder / "a.sgf")
        shutil.copy(analyzed_data_dir / "not_analyzed.sgf", test_folder / "b.sgf")

        manifest = create_training_set("Test Set")
        assert manifest is not None
        set_id = manifest.set_id

        result = import_analyzed_sgf_folder(
            set_id=set_id,
            folder_path=test_folder,
            context=Context.HUMAN,
        )

        assert result.success_count == 2
        # Average of 1.0 and 0.0 = 0.5
        assert result.average_analyzed_ratio == pytest.approx(0.5, rel=0.01)

    def test_import_folder_handles_duplicates(self, temp_smart_kifu_dir, analyzed_data_dir):
        """Import folder should skip duplicates correctly."""
        manifest = create_training_set("Test Set")
        assert manifest is not None
        set_id = manifest.set_id

        # First import
        result1 = import_analyzed_sgf_folder(
            set_id=set_id,
            folder_path=analyzed_data_dir,
            context=Context.HUMAN,
        )
        initial_count = result1.success_count

        # Second import (all duplicates)
        result2 = import_analyzed_sgf_folder(
            set_id=set_id,
            folder_path=analyzed_data_dir,
            context=Context.HUMAN,
        )

        assert result2.success_count == 0
        assert result2.skipped_count == initial_count

    def test_import_folder_not_directory(self, temp_smart_kifu_dir, analyzed_data_dir):
        """Import non-directory should fail."""
        manifest = create_training_set("Test Set")
        assert manifest is not None
        set_id = manifest.set_id

        # Pass a file instead of directory
        file_path = analyzed_data_dir / "fully_analyzed.sgf"

        result = import_analyzed_sgf_folder(
            set_id=set_id,
            folder_path=file_path,
            context=Context.HUMAN,
        )

        assert result.failed_count == 1
        assert result.success_count == 0

    def test_import_empty_folder(self, temp_smart_kifu_dir, tmp_path):
        """Import empty folder should return empty result."""
        manifest = create_training_set("Test Set")
        assert manifest is not None
        set_id = manifest.set_id

        empty_folder = tmp_path / "empty"
        empty_folder.mkdir()

        result = import_analyzed_sgf_folder(
            set_id=set_id,
            folder_path=empty_folder,
            context=Context.HUMAN,
        )

        assert result.success_count == 0
        assert result.failed_count == 0
        assert result.skipped_count == 0
        assert result.average_analyzed_ratio is None

    def test_import_folder_with_none_ratios(self, temp_smart_kifu_dir, tmp_path, analyzed_data_dir):
        """Average should handle files that return None for ratio."""
        # Create folder with only root_only.sgf (returns None)
        test_folder = tmp_path / "test_sgf"
        test_folder.mkdir()
        shutil.copy(analyzed_data_dir / "root_only.sgf", test_folder / "a.sgf")
        shutil.copy(analyzed_data_dir / "fully_analyzed.sgf", test_folder / "b.sgf")

        manifest = create_training_set("Test Set")
        assert manifest is not None
        set_id = manifest.set_id

        result = import_analyzed_sgf_folder(
            set_id=set_id,
            folder_path=test_folder,
            context=Context.HUMAN,
        )

        assert result.success_count == 2
        # Only one valid ratio (1.0 from fully_analyzed.sgf)
        assert result.average_analyzed_ratio == pytest.approx(1.0, rel=0.01)

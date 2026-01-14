"""Tests for Smart Kifu Learning (Phase 13).

Test categories:
- Models: Enum values, Dataclass behavior
- Logic: Bucket key, engine profile ID, game ID, confidence, viewer level, handicap
- I/O: Manifest/profile roundtrip, SGF import, duplicate detection
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Temporary data directory for tests."""
    # Patch DATA_FOLDER to use temp directory
    monkeypatch.setattr("katrain.core.smart_kifu.io.DATA_FOLDER", str(tmp_path))
    return tmp_path


@pytest.fixture
def sample_sgf_content():
    """Sample SGF content for testing."""
    return """(;GM[1]FF[4]SZ[19]HA[0]KM[6.5]RE[B+R]
;B[pd];W[dd];B[pq];W[dp])"""


@pytest.fixture
def sample_sgf_with_handicap():
    """Sample SGF with handicap."""
    return """(;GM[1]FF[4]SZ[19]HA[3]KM[0.5]RE[W+5.5]
;B[pd];W[dd];B[pq];W[dp];B[qk])"""


# =============================================================================
# Test: models.py - Enums
# =============================================================================


class TestContextEnum:
    """Test Context enum."""

    def test_context_enum_values(self):
        """Context enum has expected values."""
        from katrain.core.smart_kifu import Context

        assert Context.HUMAN.value == "human"
        assert Context.VS_KATAGO.value == "vs_katago"
        assert Context.GENERATED.value == "generated"

    def test_context_enum_count(self):
        """Context enum has 3 members."""
        from katrain.core.smart_kifu import Context

        assert len(Context) == 3


class TestViewerPresetEnum:
    """Test ViewerPreset enum."""

    def test_viewer_preset_enum_values(self):
        """ViewerPreset enum has expected values."""
        from katrain.core.smart_kifu import ViewerPreset

        assert ViewerPreset.LITE.value == "lite"
        assert ViewerPreset.STANDARD.value == "standard"
        assert ViewerPreset.DEEP.value == "deep"


class TestConfidenceEnum:
    """Test Confidence enum."""

    def test_confidence_enum_values(self):
        """Confidence enum has expected values."""
        from katrain.core.smart_kifu import Confidence

        assert Confidence.LOW.value == "low"
        assert Confidence.MEDIUM.value == "medium"
        assert Confidence.HIGH.value == "high"


# =============================================================================
# Test: models.py - Dataclasses
# =============================================================================


class TestGameEntryDataclass:
    """Test GameEntry dataclass."""

    def test_game_entry_dataclass(self):
        """GameEntry can be created with required fields."""
        from katrain.core.smart_kifu import Context, GameEntry, GameSource

        entry = GameEntry(
            game_id="sha1:abc123",
            path="sgf/game_001.sgf",
            added_at="2026-01-15T10:00:00",
            context=Context.HUMAN,
        )
        assert entry.game_id == "sha1:abc123"
        assert entry.context == Context.HUMAN
        assert entry.analyzed_ratio is None  # Optional field

    def test_game_entry_optional_fields(self):
        """GameEntry optional fields default correctly."""
        from katrain.core.smart_kifu import Context, GameEntry

        entry = GameEntry(
            game_id="sha1:abc123",
            path="sgf/game_001.sgf",
            added_at="2026-01-15T10:00:00",
            context=Context.HUMAN,
        )
        assert entry.board_size is None
        assert entry.handicap is None
        assert entry.engine_profile_id is None


class TestTrainingSetManifest:
    """Test TrainingSetManifest dataclass."""

    def test_training_set_manifest_get_game_ids(self):
        """get_game_ids returns set of game IDs."""
        from katrain.core.smart_kifu import Context, GameEntry, TrainingSetManifest

        manifest = TrainingSetManifest(
            set_id="ts_test",
            name="Test Set",
            games=[
                GameEntry(
                    game_id="sha1:aaa",
                    path="sgf/a.sgf",
                    added_at="2026-01-01",
                    context=Context.HUMAN,
                ),
                GameEntry(
                    game_id="sha1:bbb",
                    path="sgf/b.sgf",
                    added_at="2026-01-02",
                    context=Context.HUMAN,
                ),
            ],
        )
        ids = manifest.get_game_ids()
        assert ids == {"sha1:aaa", "sha1:bbb"}

    def test_training_set_manifest_get_recent_games(self):
        """get_recent_games returns games sorted by added_at descending."""
        from katrain.core.smart_kifu import Context, GameEntry, TrainingSetManifest

        manifest = TrainingSetManifest(
            set_id="ts_test",
            games=[
                GameEntry(game_id="sha1:a", path="a.sgf", added_at="2026-01-01", context=Context.HUMAN),
                GameEntry(game_id="sha1:c", path="c.sgf", added_at="2026-01-03", context=Context.HUMAN),
                GameEntry(game_id="sha1:b", path="b.sgf", added_at="2026-01-02", context=Context.HUMAN),
            ],
        )
        recent = manifest.get_recent_games(2)
        assert len(recent) == 2
        assert recent[0].game_id == "sha1:c"  # Most recent
        assert recent[1].game_id == "sha1:b"


class TestBucketProfileDataclass:
    """Test BucketProfile dataclass."""

    def test_bucket_profile_dataclass(self):
        """BucketProfile can be created with defaults."""
        from katrain.core.smart_kifu import BucketProfile, Confidence, ViewerPreset

        profile = BucketProfile()
        assert profile.viewer_level == 5
        assert profile.viewer_preset == ViewerPreset.STANDARD
        assert profile.confidence == Confidence.LOW
        assert profile.analyzed_ratio is None

    def test_bucket_profile_analyzed_ratio_optional(self):
        """BucketProfile.analyzed_ratio is Optional[float]."""
        from katrain.core.smart_kifu import BucketProfile

        # None is valid
        profile = BucketProfile(analyzed_ratio=None)
        assert profile.analyzed_ratio is None

        # Float is valid
        profile = BucketProfile(analyzed_ratio=0.75)
        assert profile.analyzed_ratio == 0.75


class TestPlayerProfileDataclass:
    """Test PlayerProfile dataclass."""

    def test_player_profile_dataclass(self):
        """PlayerProfile can be created."""
        from katrain.core.smart_kifu import PlayerProfile

        profile = PlayerProfile()
        assert profile.profile_version == 1
        assert profile.per_context == {}


class TestImportResult:
    """Test ImportResult dataclass."""

    def test_import_result_has_failures(self):
        """has_failures returns True when failed_count > 0."""
        from katrain.core.smart_kifu import ImportResult

        result = ImportResult(success_count=5, failed_count=0)
        assert result.has_failures is False

        result = ImportResult(success_count=5, failed_count=2)
        assert result.has_failures is True

    def test_import_result_total_processed(self):
        """total_processed returns sum of all counts."""
        from katrain.core.smart_kifu import ImportResult

        result = ImportResult(success_count=10, failed_count=2, skipped_count=3)
        assert result.total_processed == 15


# =============================================================================
# Test: logic.py - Bucket Key
# =============================================================================


class TestComputeBucketKey:
    """Test compute_bucket_key function."""

    def test_compute_bucket_key_19_even(self):
        """19路盤、置石0-1は even."""
        from katrain.core.smart_kifu import compute_bucket_key

        assert compute_bucket_key(19, 0) == "19_even"
        assert compute_bucket_key(19, 1) == "19_even"

    def test_compute_bucket_key_19_handicap(self):
        """19路盤、置石2以上は handicap."""
        from katrain.core.smart_kifu import compute_bucket_key

        assert compute_bucket_key(19, 2) == "19_handicap"
        assert compute_bucket_key(19, 9) == "19_handicap"

    def test_compute_bucket_key_9_even(self):
        """9路盤、置石0は even."""
        from katrain.core.smart_kifu import compute_bucket_key

        assert compute_bucket_key(9, 0) == "9_even"

    def test_compute_bucket_key_13_even(self):
        """13路盤のテスト."""
        from katrain.core.smart_kifu import compute_bucket_key

        assert compute_bucket_key(13, 0) == "13_even"
        assert compute_bucket_key(13, 3) == "13_handicap"


# =============================================================================
# Test: logic.py - Engine Profile ID
# =============================================================================


class TestComputeEngineProfileId:
    """Test compute_engine_profile_id function."""

    def test_compute_engine_profile_id_deterministic(self):
        """Same input produces same output."""
        from katrain.core.smart_kifu import EngineProfileSnapshot, compute_engine_profile_id

        snapshot = EngineProfileSnapshot(model_name="kata1-b40c256", max_visits=1000, komi=6.5)
        id1 = compute_engine_profile_id(snapshot)
        id2 = compute_engine_profile_id(snapshot)
        assert id1 == id2

    def test_compute_engine_profile_id_16hex_length(self):
        """ID has 16 hex characters after prefix."""
        from katrain.core.smart_kifu import EngineProfileSnapshot, compute_engine_profile_id

        snapshot = EngineProfileSnapshot(model_name="test", max_visits=100)
        ep_id = compute_engine_profile_id(snapshot)
        assert ep_id.startswith("ep_")
        assert len(ep_id) == 3 + 16  # "ep_" + 16 hex

    def test_compute_engine_profile_id_none_excluded(self):
        """None values are excluded from hash."""
        from katrain.core.smart_kifu import EngineProfileSnapshot, compute_engine_profile_id

        snapshot = EngineProfileSnapshot(model_name="test", max_visits=None, komi=None)
        ep_id = compute_engine_profile_id(snapshot)
        assert ep_id.startswith("ep_")

    def test_compute_engine_profile_id_empty_string_excluded(self):
        """Empty string model_name is excluded."""
        from katrain.core.smart_kifu import EngineProfileSnapshot, compute_engine_profile_id

        # Empty string should be excluded
        snapshot1 = EngineProfileSnapshot(model_name="", max_visits=100)
        snapshot2 = EngineProfileSnapshot(model_name=None, max_visits=100)
        assert compute_engine_profile_id(snapshot1) == compute_engine_profile_id(snapshot2)

    def test_compute_engine_profile_id_zero_visits_included(self):
        """max_visits=0 is included (not treated as falsy)."""
        from katrain.core.smart_kifu import EngineProfileSnapshot, compute_engine_profile_id

        snapshot_zero = EngineProfileSnapshot(model_name="test", max_visits=0)
        snapshot_none = EngineProfileSnapshot(model_name="test", max_visits=None)
        # Should be different because 0 is included, None is excluded
        assert compute_engine_profile_id(snapshot_zero) != compute_engine_profile_id(snapshot_none)

    def test_compute_engine_profile_id_zero_komi_included(self):
        """komi=0.0 is included (not treated as falsy)."""
        from katrain.core.smart_kifu import EngineProfileSnapshot, compute_engine_profile_id

        snapshot_zero = EngineProfileSnapshot(model_name="test", komi=0.0)
        snapshot_none = EngineProfileSnapshot(model_name="test", komi=None)
        assert compute_engine_profile_id(snapshot_zero) != compute_engine_profile_id(snapshot_none)

    def test_compute_engine_profile_id_float_rounded(self):
        """Floats are rounded to 2 decimal places."""
        from katrain.core.smart_kifu import EngineProfileSnapshot, compute_engine_profile_id

        snapshot1 = EngineProfileSnapshot(komi=6.5)
        snapshot2 = EngineProfileSnapshot(komi=6.500001)
        assert compute_engine_profile_id(snapshot1) == compute_engine_profile_id(snapshot2)


# =============================================================================
# Test: logic.py - Game ID
# =============================================================================


class TestComputeGameId:
    """Test compute_game_id function."""

    def test_compute_game_id_deterministic(self):
        """Same content produces same ID."""
        from katrain.core.smart_kifu import compute_game_id

        content = "(;GM[1]FF[4]SZ[19])"
        id1 = compute_game_id(content)
        id2 = compute_game_id(content)
        assert id1 == id2
        assert id1.startswith("sha1:")

    def test_compute_game_id_crlf_normalized(self):
        """CRLF is normalized to LF."""
        from katrain.core.smart_kifu import compute_game_id

        content_lf = "(;GM[1]FF[4]\nSZ[19])"
        content_crlf = "(;GM[1]FF[4]\r\nSZ[19])"
        assert compute_game_id(content_lf) == compute_game_id(content_crlf)

    def test_compute_game_id_trailing_whitespace_stripped(self):
        """Trailing whitespace is stripped."""
        from katrain.core.smart_kifu import compute_game_id

        content = "(;GM[1]FF[4]SZ[19])"
        content_trailing = "(;GM[1]FF[4]SZ[19])  \n\n"
        assert compute_game_id(content) == compute_game_id(content_trailing)

    def test_compute_game_id_leading_whitespace_preserved(self):
        """Leading whitespace is preserved."""
        from katrain.core.smart_kifu import compute_game_id

        content = "(;GM[1]FF[4]SZ[19])"
        content_leading = "  (;GM[1]FF[4]SZ[19])"
        # Should be different because leading whitespace is preserved
        assert compute_game_id(content) != compute_game_id(content_leading)


# =============================================================================
# Test: logic.py - Confidence
# =============================================================================


class TestComputeConfidence:
    """Test compute_confidence function."""

    def test_compute_confidence_high(self):
        """High: samples >= 30 and analyzed_ratio >= 0.7."""
        from katrain.core.smart_kifu import Confidence, compute_confidence

        assert compute_confidence(30, 0.7) == Confidence.HIGH
        assert compute_confidence(50, 0.9) == Confidence.HIGH

    def test_compute_confidence_medium(self):
        """Medium: samples >= 10 and analyzed_ratio >= 0.4."""
        from katrain.core.smart_kifu import Confidence, compute_confidence

        assert compute_confidence(10, 0.4) == Confidence.MEDIUM
        assert compute_confidence(25, 0.6) == Confidence.MEDIUM

    def test_compute_confidence_low(self):
        """Low: below thresholds."""
        from katrain.core.smart_kifu import Confidence, compute_confidence

        assert compute_confidence(5, 0.8) == Confidence.LOW  # samples too low
        assert compute_confidence(30, 0.3) == Confidence.LOW  # ratio too low

    def test_compute_confidence_none_analyzed_ratio_returns_low(self):
        """analyzed_ratio=None always returns LOW."""
        from katrain.core.smart_kifu import Confidence, compute_confidence

        assert compute_confidence(100, None) == Confidence.LOW
        assert compute_confidence(0, None) == Confidence.LOW


# =============================================================================
# Test: logic.py - Viewer Level
# =============================================================================


class TestEstimateViewerLevel:
    """Test estimate_viewer_level function."""

    def test_estimate_viewer_level_ranges(self):
        """Returns values in range 1-10."""
        from katrain.core.smart_kifu import estimate_viewer_level

        # Low loss, low blunder -> high level
        assert estimate_viewer_level(0.3, 0.01) == 10

        # High loss, high blunder -> low level
        assert estimate_viewer_level(10.0, 0.5) == 1

        # Medium values
        level = estimate_viewer_level(2.0, 0.10)
        assert 1 <= level <= 10


class TestMapViewerLevelToPreset:
    """Test map_viewer_level_to_preset function."""

    def test_map_viewer_level_to_preset_lite(self):
        """Levels 1-3 map to Lite."""
        from katrain.core.smart_kifu import ViewerPreset, map_viewer_level_to_preset

        assert map_viewer_level_to_preset(1) == ViewerPreset.LITE
        assert map_viewer_level_to_preset(3) == ViewerPreset.LITE

    def test_map_viewer_level_to_preset_standard(self):
        """Levels 4-7 map to Standard."""
        from katrain.core.smart_kifu import ViewerPreset, map_viewer_level_to_preset

        assert map_viewer_level_to_preset(4) == ViewerPreset.STANDARD
        assert map_viewer_level_to_preset(7) == ViewerPreset.STANDARD

    def test_map_viewer_level_to_preset_deep(self):
        """Levels 8-10 map to Deep."""
        from katrain.core.smart_kifu import ViewerPreset, map_viewer_level_to_preset

        assert map_viewer_level_to_preset(8) == ViewerPreset.DEEP
        assert map_viewer_level_to_preset(10) == ViewerPreset.DEEP


# =============================================================================
# Test: logic.py - Handicap Adjustment
# =============================================================================


class TestSuggestHandicapAdjustment:
    """Test suggest_handicap_adjustment function."""

    def test_suggest_handicap_high_winrate(self):
        """High winrate (>70%) suggests -1 handicap."""
        from katrain.core.smart_kifu import suggest_handicap_adjustment

        new_handicap, reason = suggest_handicap_adjustment(0.75, 3)
        assert new_handicap == 2
        assert "減らす" in reason

    def test_suggest_handicap_low_winrate(self):
        """Low winrate (<30%) suggests +1 handicap."""
        from katrain.core.smart_kifu import suggest_handicap_adjustment

        new_handicap, reason = suggest_handicap_adjustment(0.25, 3)
        assert new_handicap == 4
        assert "増やす" in reason

    def test_suggest_handicap_target_range(self):
        """Target range (40-60%) maintains current handicap."""
        from katrain.core.smart_kifu import suggest_handicap_adjustment

        new_handicap, reason = suggest_handicap_adjustment(0.50, 3)
        assert new_handicap == 3
        assert "適正" in reason


# =============================================================================
# Test: io.py - Directory
# =============================================================================


class TestGetSmartKifuDir:
    """Test directory functions."""

    def test_get_smart_kifu_dir_uses_data_folder(self, temp_data_dir):
        """get_smart_kifu_dir returns path under DATA_FOLDER."""
        from katrain.core.smart_kifu import get_smart_kifu_dir

        result = get_smart_kifu_dir()
        assert str(temp_data_dir) in str(result)
        assert result.name == "smart_kifu"


# =============================================================================
# Test: io.py - Manifest I/O
# =============================================================================


class TestManifestIO:
    """Test manifest I/O functions."""

    def test_manifest_roundtrip(self, temp_data_dir):
        """Manifest can be saved and loaded."""
        from katrain.core.smart_kifu import (
            Context,
            GameEntry,
            TrainingSetManifest,
            load_manifest,
            save_manifest,
        )

        manifest = TrainingSetManifest(
            manifest_version=1,
            set_id="ts_test",
            name="Test Set",
            created_at="2026-01-15T10:00:00",
            games=[
                GameEntry(
                    game_id="sha1:abc",
                    path="sgf/game.sgf",
                    added_at="2026-01-15",
                    context=Context.HUMAN,
                    board_size=19,
                    handicap=0,
                ),
            ],
        )

        save_manifest(manifest)
        loaded = load_manifest("ts_test")

        assert loaded is not None
        assert loaded.set_id == "ts_test"
        assert loaded.name == "Test Set"
        assert len(loaded.games) == 1
        assert loaded.games[0].game_id == "sha1:abc"
        assert loaded.games[0].context == Context.HUMAN

    def test_manifest_version_saved(self, temp_data_dir):
        """manifest_version is saved in JSON."""
        from katrain.core.smart_kifu import (
            TrainingSetManifest,
            get_training_sets_dir,
            save_manifest,
        )

        manifest = TrainingSetManifest(
            manifest_version=1,
            set_id="ts_version",
            name="Version Test",
        )
        save_manifest(manifest)

        # Read raw JSON
        manifest_path = get_training_sets_dir() / "ts_version" / "manifest.json"
        with open(manifest_path, "r") as f:
            data = json.load(f)
        assert data["manifest_version"] == 1

    def test_manifest_empty_games(self, temp_data_dir):
        """Manifest with empty games list works."""
        from katrain.core.smart_kifu import (
            TrainingSetManifest,
            load_manifest,
            save_manifest,
        )

        manifest = TrainingSetManifest(set_id="ts_empty", name="Empty")
        save_manifest(manifest)
        loaded = load_manifest("ts_empty")

        assert loaded is not None
        assert loaded.games == []


# =============================================================================
# Test: io.py - Profile I/O
# =============================================================================


class TestProfileIO:
    """Test profile I/O functions."""

    def test_profile_roundtrip(self, temp_data_dir):
        """Profile can be saved and loaded."""
        from katrain.core.smart_kifu import (
            BucketProfile,
            Confidence,
            Context,
            ContextProfile,
            PlayerProfile,
            ViewerPreset,
            load_player_profile,
            save_player_profile,
        )

        profile = PlayerProfile(
            profile_version=1,
            created_at="2026-01-15",
            updated_at="2026-01-15",
            per_context={
                "human": ContextProfile(
                    context=Context.HUMAN,
                    buckets={
                        "19_even": BucketProfile(
                            viewer_level=7,
                            viewer_preset=ViewerPreset.STANDARD,
                            confidence=Confidence.MEDIUM,
                            samples=20,
                            analyzed_ratio=0.6,
                        ),
                    },
                ),
            },
        )

        save_player_profile(profile)
        loaded = load_player_profile()

        assert loaded.profile_version == 1
        assert "human" in loaded.per_context
        assert "19_even" in loaded.per_context["human"].buckets
        bucket = loaded.per_context["human"].buckets["19_even"]
        assert bucket.viewer_level == 7
        assert bucket.analyzed_ratio == 0.6

    def test_profile_empty(self, temp_data_dir):
        """Loading non-existent profile returns new profile."""
        from katrain.core.smart_kifu import load_player_profile

        profile = load_player_profile()
        assert profile.profile_version == 1
        assert profile.per_context == {}


# =============================================================================
# Test: io.py - SGF Import
# =============================================================================


class TestSGFImport:
    """Test SGF import functions."""

    def test_import_sgf_single_file(self, temp_data_dir, sample_sgf_content):
        """Single SGF file can be imported."""
        from katrain.core.smart_kifu import (
            Context,
            create_training_set,
            import_sgf_to_training_set,
        )

        # Create training set
        manifest = create_training_set("Test Import")

        # Create temp SGF file
        sgf_dir = temp_data_dir / "sgf_source"
        sgf_dir.mkdir()
        sgf_path = sgf_dir / "game1.sgf"
        sgf_path.write_text(sample_sgf_content, encoding="utf-8")

        # Import
        entry, error = import_sgf_to_training_set(
            manifest.set_id,
            sgf_path,
            Context.HUMAN,
        )

        assert error is None
        assert entry is not None
        assert entry.game_id.startswith("sha1:")
        assert entry.board_size == 19
        assert entry.handicap == 0

    def test_import_sgf_duplicate_skipped(self, temp_data_dir, sample_sgf_content):
        """Duplicate SGF is skipped."""
        from katrain.core.smart_kifu import (
            Context,
            create_training_set,
            import_sgf_to_training_set,
        )

        manifest = create_training_set("Duplicate Test")

        sgf_dir = temp_data_dir / "sgf_dup"
        sgf_dir.mkdir()
        sgf_path = sgf_dir / "game.sgf"
        sgf_path.write_text(sample_sgf_content, encoding="utf-8")

        # First import succeeds
        entry1, error1 = import_sgf_to_training_set(manifest.set_id, sgf_path, Context.HUMAN)
        assert error1 is None

        # Second import is skipped (duplicate)
        entry2, error2 = import_sgf_to_training_set(manifest.set_id, sgf_path, Context.HUMAN)
        assert entry2 is None
        assert "Duplicate" in error2

    def test_import_sgf_folder_success(self, temp_data_dir, sample_sgf_content, sample_sgf_with_handicap):
        """Folder import works with multiple files."""
        from katrain.core.smart_kifu import (
            Context,
            create_training_set,
            import_sgf_folder,
        )

        manifest = create_training_set("Folder Test")

        sgf_dir = temp_data_dir / "sgf_folder"
        sgf_dir.mkdir()
        (sgf_dir / "game1.sgf").write_text(sample_sgf_content, encoding="utf-8")
        (sgf_dir / "game2.sgf").write_text(sample_sgf_with_handicap, encoding="utf-8")

        result = import_sgf_folder(manifest.set_id, sgf_dir, Context.HUMAN)

        assert result.success_count == 2
        assert result.failed_count == 0
        assert result.skipped_count == 0

    def test_import_sgf_folder_partial_failure(self, temp_data_dir, sample_sgf_content):
        """Partial failures are handled gracefully."""
        from katrain.core.smart_kifu import (
            Context,
            create_training_set,
            import_sgf_folder,
        )

        manifest = create_training_set("Partial Fail")

        sgf_dir = temp_data_dir / "sgf_partial"
        sgf_dir.mkdir()
        (sgf_dir / "good.sgf").write_text(sample_sgf_content, encoding="utf-8")
        (sgf_dir / "bad.sgf").write_text("not valid sgf content", encoding="utf-8")

        result = import_sgf_folder(manifest.set_id, sgf_dir, Context.HUMAN)

        # One success, one failure (bad SGF still imports as file, metadata extraction may fail)
        assert result.total_processed == 2

    def test_import_sgf_folder_reports_skipped_count(self, temp_data_dir, sample_sgf_content):
        """Skipped files are counted correctly."""
        from katrain.core.smart_kifu import (
            Context,
            create_training_set,
            import_sgf_folder,
        )

        manifest = create_training_set("Skip Count")

        sgf_dir = temp_data_dir / "sgf_skip"
        sgf_dir.mkdir()
        (sgf_dir / "game.sgf").write_text(sample_sgf_content, encoding="utf-8")

        # First import
        result1 = import_sgf_folder(manifest.set_id, sgf_dir, Context.HUMAN)
        assert result1.success_count == 1
        assert result1.skipped_count == 0

        # Second import - should skip duplicate
        result2 = import_sgf_folder(manifest.set_id, sgf_dir, Context.HUMAN)
        assert result2.success_count == 0
        assert result2.skipped_count == 1
        assert "game.sgf" in result2.skipped_files


# =============================================================================
# Test: io.py - List Training Sets
# =============================================================================


class TestListTrainingSets:
    """Test list_training_sets function."""

    def test_list_training_sets(self, temp_data_dir):
        """Returns list of training set IDs."""
        from katrain.core.smart_kifu import create_training_set, list_training_sets

        create_training_set("Set A")
        create_training_set("Set B")

        sets = list_training_sets()
        assert len(sets) == 2

    def test_list_training_sets_empty(self, temp_data_dir):
        """Returns empty list when no sets exist."""
        from katrain.core.smart_kifu import list_training_sets

        sets = list_training_sets()
        assert sets == []

"""
Tests for SGF Save functionality in KaTrain Qt.

Tests cover:
- GameAdapter.save_sgf() method
- Round-trip load/save verification
- UTF-8 encoding
- Error handling
"""

import pytest
from pathlib import Path

from katrain_qt.core_adapter import GameAdapter


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def adapter():
    """Create a fresh GameAdapter instance."""
    return GameAdapter()


@pytest.fixture
def temp_sgf_file(tmp_path):
    """Create a temporary SGF file for testing."""
    sgf_file = tmp_path / "test_game.sgf"
    sgf_content = """(;GM[1]FF[4]SZ[19]KM[6.5]RU[Japanese]
PB[Black Player]PW[White Player]
;B[pd];W[dd];B[pq];W[dq])"""
    sgf_file.write_text(sgf_content, encoding="utf-8")
    return sgf_file


@pytest.fixture
def temp_sgf_with_unicode(tmp_path):
    """Create a temporary SGF file with Unicode characters."""
    sgf_file = tmp_path / "unicode_game.sgf"
    sgf_content = """(;GM[1]FF[4]SZ[19]KM[6.5]RU[Japanese]
PB[山田太郎]PW[鈴木一郎]
DT[2025-01-08]
;B[pd];W[dd];B[pq];W[dq])"""
    sgf_file.write_text(sgf_content, encoding="utf-8")
    return sgf_file


@pytest.fixture
def empty_adapter(adapter):
    """Create an adapter with a new game (no SGF loaded)."""
    adapter.new_game(size=19, komi=6.5, rules="japanese")
    return adapter


# =============================================================================
# Basic Save Tests
# =============================================================================

class TestSaveSGF:
    """Tests for GameAdapter.save_sgf method."""

    def test_save_returns_false_if_no_game(self, adapter, tmp_path):
        """save_sgf should return False if no game is loaded."""
        save_path = tmp_path / "output.sgf"
        result = adapter.save_sgf(str(save_path))
        assert result is False
        assert not save_path.exists()

    def test_save_creates_file(self, empty_adapter, tmp_path):
        """save_sgf should create the output file."""
        save_path = tmp_path / "output.sgf"
        result = empty_adapter.save_sgf(str(save_path))
        assert result is True
        assert save_path.exists()

    def test_save_creates_parent_directories(self, empty_adapter, tmp_path):
        """save_sgf should create parent directories if needed."""
        save_path = tmp_path / "subdir" / "nested" / "output.sgf"
        result = empty_adapter.save_sgf(str(save_path))
        assert result is True
        assert save_path.exists()

    def test_save_file_is_utf8(self, empty_adapter, tmp_path):
        """Saved file should be UTF-8 encoded."""
        save_path = tmp_path / "output.sgf"
        empty_adapter.save_sgf(str(save_path))

        # Should be readable as UTF-8
        content = save_path.read_text(encoding="utf-8")
        assert content.startswith("(;")


# =============================================================================
# Round-Trip Tests
# =============================================================================

class TestRoundTrip:
    """Tests for loading and saving SGF files."""

    def test_load_save_reload_basic(self, adapter, temp_sgf_file, tmp_path):
        """SGF should be loadable after save."""
        # Load original
        assert adapter.load_sgf_file(str(temp_sgf_file))

        # Save to new file
        save_path = tmp_path / "saved.sgf"
        assert adapter.save_sgf(str(save_path))

        # Reload saved file in new adapter
        adapter2 = GameAdapter()
        assert adapter2.load_sgf_file(str(save_path))

        # Verify content matches
        assert adapter2.board_size == 19
        assert adapter2.total_moves == 4

    def test_round_trip_preserves_moves(self, adapter, temp_sgf_file, tmp_path):
        """Round-trip should preserve all moves."""
        # Load original
        adapter.load_sgf_file(str(temp_sgf_file))
        adapter.nav_last()
        original_move_count = adapter.current_move_number

        # Save and reload
        save_path = tmp_path / "saved.sgf"
        adapter.save_sgf(str(save_path))

        adapter2 = GameAdapter()
        adapter2.load_sgf_file(str(save_path))
        adapter2.nav_last()

        assert adapter2.current_move_number == original_move_count

    def test_round_trip_preserves_metadata(self, adapter, temp_sgf_file, tmp_path):
        """Round-trip should preserve player names."""
        adapter.load_sgf_file(str(temp_sgf_file))

        original_black = adapter.black_player
        original_white = adapter.white_player
        original_komi = adapter.komi

        save_path = tmp_path / "saved.sgf"
        adapter.save_sgf(str(save_path))

        adapter2 = GameAdapter()
        adapter2.load_sgf_file(str(save_path))

        assert adapter2.black_player == original_black
        assert adapter2.white_player == original_white
        assert adapter2.komi == original_komi

    def test_round_trip_preserves_unicode(self, adapter, temp_sgf_with_unicode, tmp_path):
        """Round-trip should preserve Unicode characters in player names."""
        adapter.load_sgf_file(str(temp_sgf_with_unicode))

        original_black = adapter.black_player
        original_white = adapter.white_player

        # Verify Unicode was loaded
        assert "山田" in original_black
        assert "鈴木" in original_white

        # Save and reload
        save_path = tmp_path / "saved_unicode.sgf"
        adapter.save_sgf(str(save_path))

        adapter2 = GameAdapter()
        adapter2.load_sgf_file(str(save_path))

        assert adapter2.black_player == original_black
        assert adapter2.white_player == original_white

    def test_save_after_playing_moves(self, empty_adapter, tmp_path):
        """Should be able to save after playing moves."""
        # Play some moves
        empty_adapter.play_move_qt(3, 15)  # D4
        empty_adapter.play_move_qt(15, 3)  # Q16
        empty_adapter.play_move_qt(15, 15)  # Q4
        empty_adapter.play_move_qt(3, 3)   # D16

        # Save
        save_path = tmp_path / "new_game.sgf"
        assert empty_adapter.save_sgf(str(save_path))

        # Reload and verify
        adapter2 = GameAdapter()
        adapter2.load_sgf_file(str(save_path))
        adapter2.nav_last()

        assert adapter2.current_move_number == 4


# =============================================================================
# Node ID Tests
# =============================================================================

class TestCurrentNodeId:
    """Tests for GameAdapter.current_node_id property."""

    def test_node_id_returns_int(self, empty_adapter):
        """current_node_id should return an integer."""
        assert isinstance(empty_adapter.current_node_id, int)

    def test_node_id_changes_with_navigation(self, adapter, temp_sgf_file):
        """current_node_id should change when navigating."""
        adapter.load_sgf_file(str(temp_sgf_file))

        adapter.nav_first()
        id_at_root = adapter.current_node_id

        adapter.nav_next()
        id_at_move_1 = adapter.current_node_id

        assert id_at_root != id_at_move_1

    def test_node_id_same_when_returning(self, adapter, temp_sgf_file):
        """current_node_id should be the same when returning to same position."""
        adapter.load_sgf_file(str(temp_sgf_file))

        adapter.nav_first()
        id_at_root_1 = adapter.current_node_id

        adapter.nav_next()
        adapter.nav_prev()
        id_at_root_2 = adapter.current_node_id

        assert id_at_root_1 == id_at_root_2

    def test_node_id_zero_when_no_game(self, adapter):
        """current_node_id should return 0 when no game is loaded."""
        assert adapter.current_node_id == 0


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in save_sgf."""

    def test_save_emits_error_on_no_game(self, adapter, tmp_path):
        """save_sgf should emit error signal when no game is loaded."""
        errors = []
        adapter.error_occurred.connect(lambda msg: errors.append(msg))

        save_path = tmp_path / "output.sgf"
        adapter.save_sgf(str(save_path))

        assert len(errors) == 1
        assert "No game" in errors[0]

    def test_save_emits_status_on_success(self, empty_adapter, tmp_path):
        """save_sgf should emit status signal on success."""
        statuses = []
        empty_adapter.status_changed.connect(lambda msg: statuses.append(msg))

        save_path = tmp_path / "output.sgf"
        empty_adapter.save_sgf(str(save_path))

        assert len(statuses) >= 1
        assert any("Saved" in s for s in statuses)

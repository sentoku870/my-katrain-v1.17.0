"""
Tests for comment support in GameAdapter.

M5.1b: Move comments editing
"""

import pytest
from katrain_qt.core_adapter import GameAdapter


# SGF with comments
SGF_WITH_COMMENTS = """(;GM[1]FF[4]CA[UTF-8]SZ[19]KM[6.5]
C[Game comment at root]
;B[pd]C[First move comment]
;W[dd]
;B[dp]C[Third move comment])"""

# SGF without comments
SGF_NO_COMMENTS = """(;GM[1]FF[4]CA[UTF-8]SZ[19]KM[6.5]
;B[pd];W[dd];B[dp])"""

# SGF with unicode comments
SGF_UNICODE_COMMENTS = """(;GM[1]FF[4]CA[UTF-8]SZ[19]KM[6.5]
;B[pd]C[Japanese: \u65e5\u672c\u8a9e]
;W[dd]C[Emoji: \ud83d\udc4d])"""


class TestGetComment:
    """Tests for get_comment() method."""

    def test_no_game_returns_empty(self):
        adapter = GameAdapter()
        assert adapter.get_comment() == ""

    def test_root_with_comment(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_COMMENTS)
        assert adapter.get_comment() == "Game comment at root"

    def test_node_with_comment(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_COMMENTS)
        adapter.nav_next()  # B[pd]
        assert adapter.get_comment() == "First move comment"

    def test_node_without_comment(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_COMMENTS)
        adapter.nav_next()  # B[pd]
        adapter.nav_next()  # W[dd] - no comment
        assert adapter.get_comment() == ""

    def test_unicode_comment(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_UNICODE_COMMENTS)
        adapter.nav_next()  # B[pd]
        assert "日本語" in adapter.get_comment()


class TestSetComment:
    """Tests for set_comment() method."""

    def test_no_game_returns_false(self):
        adapter = GameAdapter()
        assert adapter.set_comment("test") is False

    def test_set_new_comment(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_NO_COMMENTS)
        adapter.nav_next()  # B[pd]
        assert adapter.set_comment("New comment") is True
        assert adapter.get_comment() == "New comment"

    def test_update_existing_comment(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_COMMENTS)
        adapter.nav_next()  # B[pd]
        assert adapter.set_comment("Updated comment") is True
        assert adapter.get_comment() == "Updated comment"

    def test_clear_comment(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_COMMENTS)
        adapter.nav_next()  # B[pd]
        assert adapter.set_comment("") is True
        assert adapter.get_comment() == ""

    def test_same_comment_returns_false(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_COMMENTS)
        adapter.nav_next()  # B[pd]
        # Setting same comment should return False (no change)
        assert adapter.set_comment("First move comment") is False

    def test_set_unicode_comment(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_NO_COMMENTS)
        adapter.nav_next()
        assert adapter.set_comment("日本語コメント 🎯") is True
        assert adapter.get_comment() == "日本語コメント 🎯"


class TestHasComment:
    """Tests for has_comment() method."""

    def test_no_game_returns_false(self):
        adapter = GameAdapter()
        assert adapter.has_comment() is False

    def test_node_with_comment(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_COMMENTS)
        adapter.nav_next()  # B[pd] has comment
        assert adapter.has_comment() is True

    def test_node_without_comment(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_NO_COMMENTS)
        adapter.nav_next()
        assert adapter.has_comment() is False

    def test_whitespace_only_comment_is_false(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_NO_COMMENTS)
        adapter.nav_next()
        adapter.set_comment("   ")  # Whitespace only
        assert adapter.has_comment() is False


class TestCommentPersistence:
    """Tests for comment persistence through save/load."""

    def test_comment_persists_through_save(self, tmp_path):
        # Create game with comment
        adapter = GameAdapter()
        adapter.new_game()
        adapter.play_move_qt(3, 15)  # D4
        adapter.set_comment("Test comment for D4")

        # Save
        save_path = tmp_path / "test_comment.sgf"
        assert adapter.save_sgf(str(save_path)) is True

        # Load in new adapter
        adapter2 = GameAdapter()
        assert adapter2.load_sgf_file(str(save_path)) is True
        adapter2.nav_next()  # Go to D4
        assert adapter2.get_comment() == "Test comment for D4"

    def test_unicode_comment_persists(self, tmp_path):
        adapter = GameAdapter()
        adapter.new_game()
        adapter.play_move_qt(3, 15)
        adapter.set_comment("コメント: 好手! 👍")

        save_path = tmp_path / "unicode_comment.sgf"
        adapter.save_sgf(str(save_path))

        adapter2 = GameAdapter()
        adapter2.load_sgf_file(str(save_path))
        adapter2.nav_next()
        assert adapter2.get_comment() == "コメント: 好手! 👍"

    def test_multiple_comments_persist(self, tmp_path):
        adapter = GameAdapter()
        adapter.new_game()
        adapter.play_move_qt(3, 15)  # Move 1
        adapter.set_comment("Move 1 comment")
        adapter.play_move_qt(15, 3)  # Move 2
        adapter.set_comment("Move 2 comment")
        adapter.play_move_qt(3, 3)   # Move 3
        adapter.set_comment("Move 3 comment")

        save_path = tmp_path / "multi_comment.sgf"
        adapter.save_sgf(str(save_path))

        adapter2 = GameAdapter()
        adapter2.load_sgf_file(str(save_path))

        adapter2.nav_next()  # Move 1
        assert adapter2.get_comment() == "Move 1 comment"
        adapter2.nav_next()  # Move 2
        assert adapter2.get_comment() == "Move 2 comment"
        adapter2.nav_next()  # Move 3
        assert adapter2.get_comment() == "Move 3 comment"


class TestCommentWithVariations:
    """Tests for comments with variations."""

    def test_different_variations_have_different_comments(self):
        # SGF with variations that have different comments
        sgf = """(;GM[1]FF[4]SZ[19]
;B[pd]
(;W[dd]C[Main line comment])
(;W[dc]C[Variation comment]))"""

        adapter = GameAdapter()
        adapter.load_sgf_string(sgf)
        adapter.nav_next()  # B[pd]

        # Main line
        adapter.switch_to_child(0)
        assert adapter.get_comment() == "Main line comment"

        # Go back and to variation
        adapter.nav_prev()
        adapter.switch_to_child(1)
        assert adapter.get_comment() == "Variation comment"

    def test_set_comment_on_variation(self):
        sgf = """(;GM[1]FF[4]SZ[19]
;B[pd]
(;W[dd])
(;W[dc]))"""

        adapter = GameAdapter()
        adapter.load_sgf_string(sgf)
        adapter.nav_next()  # B[pd]
        adapter.switch_to_child(1)  # Go to variation W[dc]

        adapter.set_comment("New variation comment")
        assert adapter.get_comment() == "New variation comment"

        # Main line should not have the comment
        adapter.nav_prev()
        adapter.switch_to_child(0)
        assert adapter.get_comment() == ""

"""
Tests for katrain/gui/features/karte_export.py

This module tests:
1. determine_user_color() - Determines user's color based on SGF player names

Note: do_export_karte_ui() is heavily Kivy-dependent and not tested here.
The UI function would require extensive mocking of Kivy components.

Test philosophy:
- Focus on pure/semi-pure functions
- Mock Game.root.get_property() for determine_user_color
- No Kivy imports required
"""

from unittest.mock import Mock

from katrain.gui.features.karte_export import determine_user_color

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def create_mock_game(
    player_black: str | None = None,
    player_white: str | None = None,
) -> Mock:
    """Create a mock Game with root.get_property method.

    Args:
        player_black: Value for PB property
        player_white: Value for PW property

    Returns:
        Mock game object
    """
    game = Mock()
    game.root = Mock()

    def get_property(prop, default=None):
        if prop == "PB":
            return player_black
        elif prop == "PW":
            return player_white
        return default

    game.root.get_property = get_property
    return game


# ---------------------------------------------------------------------------
# Tests for determine_user_color()
# ---------------------------------------------------------------------------


class TestDetermineUserColor:
    """Tests for determine_user_color() function."""

    # --- Normal cases: Exact match ---

    def test_exact_match_black(self):
        """Username exactly matching PB should return 'B'."""
        game = create_mock_game(player_black="Alice", player_white="Bob")

        result = determine_user_color(game, "Alice")

        assert result == "B"

    def test_exact_match_white(self):
        """Username exactly matching PW should return 'W'."""
        game = create_mock_game(player_black="Alice", player_white="Bob")

        result = determine_user_color(game, "Bob")

        assert result == "W"

    # --- Normal cases: Partial match ---

    def test_partial_match_black(self):
        """Username partially matching PB should return 'B'."""
        game = create_mock_game(player_black="Alice123", player_white="Bob")

        result = determine_user_color(game, "alice")

        assert result == "B"

    def test_partial_match_white(self):
        """Username partially matching PW should return 'W'."""
        game = create_mock_game(player_black="Alice", player_white="Bob_Player")

        result = determine_user_color(game, "bob")

        assert result == "W"

    # --- Normal cases: Case-insensitive ---

    def test_case_insensitive_black(self):
        """Match should be case-insensitive."""
        game = create_mock_game(player_black="ALICE", player_white="Bob")

        result = determine_user_color(game, "alice")

        assert result == "B"

    def test_case_insensitive_white(self):
        """Match should be case-insensitive for white."""
        game = create_mock_game(player_black="Alice", player_white="BOB")

        result = determine_user_color(game, "bob")

        assert result == "W"

    # --- Normal cases: Special characters ignored ---

    def test_special_chars_ignored_in_username(self):
        """Special characters in username should be ignored."""
        game = create_mock_game(player_black="Alice", player_white="Bob")

        result = determine_user_color(game, "A_l-i.c!e")

        assert result == "B"

    def test_special_chars_ignored_in_player_name(self):
        """Special characters in player name should be ignored."""
        game = create_mock_game(player_black="Alice_123", player_white="Bob")

        result = determine_user_color(game, "alice123")

        assert result == "B"

    def test_unicode_normalization(self):
        """Unicode characters should be handled without crash."""
        game = create_mock_game(player_black="田中太郎", player_white="山田花子")

        # Japanese characters are non-alphanumeric, so they get stripped
        # This test verifies no crash occurs
        # When both PB and PW normalize to empty string, and username also
        # normalizes to empty, the result depends on truthy checks:
        # - pb_norm = "" (falsy, so match_black = False)
        # - pw_norm = "" (falsy, so match_white = False)
        # → Neither matches → returns None
        result = determine_user_color(game, "田中太郎")

        # Both player names are Japanese-only, normalize to empty, no match
        assert result is None

    # --- Ambiguous cases ---

    def test_ambiguous_both_match(self):
        """Username matching both players should return None."""
        game = create_mock_game(player_black="Alice123", player_white="Alice456")

        result = determine_user_color(game, "alice")

        assert result is None

    def test_ambiguous_substring_both(self):
        """Username as substring of both should return None."""
        game = create_mock_game(player_black="SentokuBlack", player_white="SentokuWhite")

        result = determine_user_color(game, "sentoku")

        assert result is None

    # --- No match cases ---

    def test_no_match(self):
        """Username not matching any player should return None."""
        game = create_mock_game(player_black="Alice", player_white="Bob")

        result = determine_user_color(game, "Charlie")

        assert result is None

    # --- None/Empty input cases ---

    def test_empty_username(self):
        """Empty username should return None."""
        game = create_mock_game(player_black="Alice", player_white="Bob")

        result = determine_user_color(game, "")

        assert result is None

    def test_none_username(self):
        """None username should return None."""
        game = create_mock_game(player_black="Alice", player_white="Bob")

        result = determine_user_color(game, None)

        assert result is None

    def test_none_game(self):
        """None game should return None."""
        result = determine_user_color(None, "Alice")

        assert result is None

    def test_none_player_names(self):
        """None player names in SGF should be handled."""
        game = create_mock_game(player_black=None, player_white=None)

        result = determine_user_color(game, "Alice")

        assert result is None

    def test_empty_player_names(self):
        """Empty player names in SGF should be handled."""
        game = create_mock_game(player_black="", player_white="")

        result = determine_user_color(game, "Alice")

        assert result is None

    # --- Edge cases ---

    def test_only_black_set(self):
        """Only PB set, matching username should return 'B'."""
        game = create_mock_game(player_black="Alice", player_white=None)

        result = determine_user_color(game, "alice")

        assert result == "B"

    def test_only_white_set(self):
        """Only PW set, matching username should return 'W'."""
        game = create_mock_game(player_black=None, player_white="Bob")

        result = determine_user_color(game, "bob")

        assert result == "W"

    def test_numeric_username(self):
        """Numeric username should work."""
        game = create_mock_game(player_black="Player123", player_white="Player456")

        result = determine_user_color(game, "123")

        assert result == "B"

    def test_whitespace_in_username(self):
        """Whitespace in username should be ignored (stripped by normalize)."""
        game = create_mock_game(player_black="Alice", player_white="Bob")

        # Whitespace is stripped by normalize_name (non-alphanumeric)
        result = determine_user_color(game, "  alice  ")

        assert result == "B"

    def test_whitespace_in_player_name(self):
        """Whitespace in player name should be ignored."""
        game = create_mock_game(player_black="Alice Smith", player_white="Bob")

        result = determine_user_color(game, "alicesmith")

        assert result == "B"

    # --- Real-world patterns ---

    def test_foxwq_style_name(self):
        """FoxWQ style player names should work."""
        game = create_mock_game(player_black="sentoku(4D)", player_white="opponent(5D)")

        result = determine_user_color(game, "sentoku")

        assert result == "B"

    def test_kgs_style_name(self):
        """KGS style player names should work."""
        game = create_mock_game(player_black="sentoku [5d]", player_white="opponent [4d]")

        result = determine_user_color(game, "sentoku")

        assert result == "B"

    def test_online_go_style_name(self):
        """OGS style player names should work."""
        game = create_mock_game(player_black="sentoku (1234)", player_white="opponent (5678)")

        result = determine_user_color(game, "sentoku")

        assert result == "B"

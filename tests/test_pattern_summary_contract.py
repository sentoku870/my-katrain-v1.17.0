"""Phase 85: Pattern Summary Contract Tests.

This module tests:
- Data contract for pattern_data
- Input validation (player/gtp/move_number)
- Board size filtering (tuple/list, non-square)
- Deterministic sorting (source_index tie-breaker)
- Production safety (corrupt data handling)
"""

from __future__ import annotations

import logging

from katrain.core import eval_metrics
from katrain.gui.features.summary_formatter import (
    AREA_KEYS,
    PHASE_KEYS,
    SEVERITY_KEYS,
    _filter_by_board_size,
    _is_valid_gtp,
    _is_valid_move_number,
    _is_valid_player,
    _normalize_board_size,
    _PatternMoveEval,
    _reconstruct_pattern_input,
    _stable_sort_key,
    build_summary_from_stats,
)


def mock_config_fn(key: str, default=None):
    """Mock config function for tests."""
    return default


def create_single_game_stats(
    game_name: str = "test_game.sgf",
    board_size: tuple[int, int] | list[int] = (19, 19),
    date: str = "2025-01-05",
    total_moves: int = 50,
    source_index: int = 0,
    player_black: str = "PlayerB",
    player_white: str = "PlayerW",
    handicap: int = 0,
    total_points_lost: float = 15.0,
) -> dict:
    """Create a synthetic game stats dictionary for testing.

    This mirrors the structure returned by extract_game_stats().
    """
    # Distribute moves and loss across phases
    opening_moves = total_moves // 3
    middle_moves = total_moves // 3
    yose_moves = total_moves - opening_moves - middle_moves

    opening_loss = total_points_lost * 0.2
    middle_loss = total_points_lost * 0.5
    yose_loss = total_points_lost * 0.3

    # Create mistake counts distribution
    mistake_counts = {
        eval_metrics.MistakeCategory.GOOD: int(total_moves * 0.6),
        eval_metrics.MistakeCategory.INACCURACY: int(total_moves * 0.2),
        eval_metrics.MistakeCategory.MISTAKE: int(total_moves * 0.15),
        eval_metrics.MistakeCategory.BLUNDER: int(total_moves * 0.05),
    }

    mistake_total_loss = {
        eval_metrics.MistakeCategory.GOOD: 0.0,
        eval_metrics.MistakeCategory.INACCURACY: total_points_lost * 0.15,
        eval_metrics.MistakeCategory.MISTAKE: total_points_lost * 0.35,
        eval_metrics.MistakeCategory.BLUNDER: total_points_lost * 0.50,
    }

    # Freedom counts (all UNKNOWN for simplicity)
    freedom_counts = {diff: 0 for diff in eval_metrics.PositionDifficulty}
    freedom_counts[eval_metrics.PositionDifficulty.UNKNOWN] = total_moves

    # Phase moves and loss
    phase_moves = {
        "opening": opening_moves,
        "middle": middle_moves,
        "yose": yose_moves,
        "unknown": 0,
    }
    phase_loss = {
        "opening": opening_loss,
        "middle": middle_loss,
        "yose": yose_loss,
        "unknown": 0.0,
    }

    # Phase x Mistake cross-tabulation (simplified)
    phase_mistake_counts = {}
    phase_mistake_loss = {}

    stats = {
        "game_name": game_name,
        "player_black": player_black,
        "player_white": player_white,
        "handicap": handicap,
        "date": date,
        "board_size": board_size,
        "total_moves": total_moves,
        "source_index": source_index,
        "total_points_lost": total_points_lost,
        "moves_by_player": {"B": total_moves // 2, "W": total_moves // 2},
        "loss_by_player": {"B": total_points_lost / 2, "W": total_points_lost / 2},
        "mistake_counts": mistake_counts,
        "mistake_total_loss": mistake_total_loss,
        "freedom_counts": freedom_counts,
        "phase_moves": phase_moves,
        "phase_loss": phase_loss,
        "phase_mistake_counts": phase_mistake_counts,
        "phase_mistake_loss": phase_mistake_loss,
        "worst_moves": [],
        "mistake_counts_by_player": {
            "B": {cat: c // 2 for cat, c in mistake_counts.items()},
            "W": {cat: c // 2 for cat, c in mistake_counts.items()},
        },
        "mistake_total_loss_by_player": {
            "B": {cat: l / 2 for cat, l in mistake_total_loss.items()},
            "W": {cat: l / 2 for cat, l in mistake_total_loss.items()},
        },
        "freedom_counts_by_player": {
            "B": {diff: c // 2 for diff, c in freedom_counts.items()},
            "W": {diff: c // 2 for diff, c in freedom_counts.items()},
        },
        "phase_moves_by_player": {
            "B": {k: v // 2 for k, v in phase_moves.items()},
            "W": {k: v // 2 for k, v in phase_moves.items()},
        },
        "phase_loss_by_player": {
            "B": {k: v / 2 for k, v in phase_loss.items()},
            "W": {k: v / 2 for k, v in phase_loss.items()},
        },
        "phase_mistake_counts_by_player": {"B": {}, "W": {}},
        "phase_mistake_loss_by_player": {"B": {}, "W": {}},
        "reason_tags_by_player": {"B": {}, "W": {}},
        "important_moves_stats_by_player": {
            "B": {"important_count": 0, "tagged_count": 0, "tag_occurrences": 0},
            "W": {"important_count": 0, "tagged_count": 0, "tag_occurrences": 0},
        },
        "meaning_tags_by_player": {"B": {}, "W": {}},
        "reliability_by_player": {
            "B": {"total": 0, "reliable": 0, "low_confidence": 0, "total_visits": 0, "with_visits": 0, "max_visits": 0},
            "W": {"total": 0, "reliable": 0, "low_confidence": 0, "total_visits": 0, "with_visits": 0, "max_visits": 0},
        },
        "radar_by_player": {"B": None, "W": None},
        # Phase 85: pattern_data
        "pattern_data": [
            {
                "move_number": 25,
                "player": "B",
                "gtp": "D4",
                "score_loss": 5.0,
                "leela_loss_est": None,
                "points_lost": 5.0,
                "mistake_category": "BLUNDER",
                "meaning_tag_id": "overplay",
            },
            {
                "move_number": 45,
                "player": "B",
                "gtp": "Q16",
                "score_loss": 3.5,
                "leela_loss_est": None,
                "points_lost": 3.5,
                "mistake_category": "MISTAKE",
                "meaning_tag_id": "life_death",
            },
        ],
    }

    return stats


class TestPatternDataContract:
    """Verify pattern_data contract for mine_patterns()."""

    def test_required_fields_present(self):
        """pattern_data must contain all required fields."""
        required = {"move_number", "player", "gtp", "mistake_category"}
        loss_fields = {"score_loss", "leela_loss_est", "points_lost"}

        stats = create_single_game_stats()

        for item in stats["pattern_data"]:
            assert required.issubset(item.keys())
            assert any(item.get(f) is not None for f in loss_fields)

    def test_mistake_category_string_to_enum_conversion(self):
        """Valid mistake_category should convert from string to Enum."""
        data = {
            "move_number": 10,
            "player": "B",
            "gtp": "D4",
            "score_loss": 5.0,
            "mistake_category": "BLUNDER",
        }

        move_eval = _PatternMoveEval(data)

        assert move_eval.mistake_category == eval_metrics.MistakeCategory.BLUNDER

    def test_invalid_mistake_category_sets_none_and_logs_warning(self, caplog):
        """Invalid mistake_category should set None and log warning."""
        data = {
            "move_number": 10,
            "player": "B",
            "gtp": "D4",
            "score_loss": 5.0,
            "mistake_category": "INVALID_CATEGORY",
        }

        with caplog.at_level(logging.WARNING):
            move_eval = _PatternMoveEval(data)

        assert move_eval.mistake_category is None
        assert "Invalid mistake_category" in caplog.text


class TestInputValidation:
    """Test move validation functions."""

    def test_valid_player(self):
        assert _is_valid_player("B") is True
        assert _is_valid_player("W") is True
        assert _is_valid_player("X") is False
        assert _is_valid_player("") is False
        assert _is_valid_player(None) is False

    def test_valid_gtp(self):
        # Valid coordinates
        assert _is_valid_gtp("D4") is True
        assert _is_valid_gtp("A1") is True
        assert _is_valid_gtp("T19") is True
        assert _is_valid_gtp("d4") is True  # lowercase OK
        assert _is_valid_gtp("J10") is True  # J is valid (I is skipped)

        # Pass/resign
        assert _is_valid_gtp("pass") is False
        assert _is_valid_gtp("resign") is False
        assert _is_valid_gtp("PASS") is False  # case insensitive

        # Empty/None
        assert _is_valid_gtp("") is False
        assert _is_valid_gtp(None) is False
        assert _is_valid_gtp("  ") is False  # whitespace only

        # Invalid format (production safety - must not crash)
        assert _is_valid_gtp("Z99") is False  # out of range letter
        assert _is_valid_gtp("A0") is False  # 0 is invalid row
        assert _is_valid_gtp("A26") is False  # row > 25
        assert _is_valid_gtp("I5") is False  # I is skipped in GTP
        assert _is_valid_gtp("AA1") is False  # double letter
        assert _is_valid_gtp("1A") is False  # reversed format
        assert _is_valid_gtp("D") is False  # missing number
        assert _is_valid_gtp("4") is False  # missing letter
        assert _is_valid_gtp("D4D4") is False  # garbage

    def test_valid_gtp_board_size_bounds(self):
        """GTP validation should respect board_size."""
        # 19x19 board
        assert _is_valid_gtp("T19", board_size=19) is True
        assert _is_valid_gtp("T20", board_size=19) is False  # row out of bounds
        assert _is_valid_gtp("S19", board_size=19) is True

        # 9x9 board
        assert _is_valid_gtp("J9", board_size=9) is True
        assert _is_valid_gtp("J10", board_size=9) is False  # row out of bounds
        assert _is_valid_gtp("K9", board_size=9) is False  # col out of bounds (K=10th)

    def test_valid_move_number(self):
        assert _is_valid_move_number(1) is True
        assert _is_valid_move_number(100) is True
        assert _is_valid_move_number(0) is False
        assert _is_valid_move_number(-1) is False
        assert _is_valid_move_number(None) is False
        assert _is_valid_move_number("1") is False  # string


class TestBoardSizeFiltering:
    """Test board_size normalization and filtering."""

    def test_normalize_handles_tuple(self):
        assert _normalize_board_size((19, 19)) == (19, 19)
        assert _normalize_board_size((9, 9)) == (9, 9)

    def test_normalize_handles_list(self):
        """JSON deserialization may produce list instead of tuple."""
        assert _normalize_board_size([19, 19]) == (19, 19)
        assert _normalize_board_size([9, 9]) == (9, 9)

    def test_normalize_handles_invalid(self):
        assert _normalize_board_size(None) is None
        assert _normalize_board_size((19,)) is None  # too short
        assert _normalize_board_size([]) is None
        assert _normalize_board_size("19x19") is None  # string

    def test_filter_handles_mixed_tuple_and_list(self):
        """Filter should work with mixed tuple/list board_size formats."""
        stats_list = [
            create_single_game_stats(game_name="a.sgf", board_size=(19, 19)),
            create_single_game_stats(game_name="b.sgf", board_size=[19, 19]),  # list
        ]
        filtered, size = _filter_by_board_size(stats_list)

        assert size == 19
        assert len(filtered) == 2

    def test_filter_skips_non_square_boards(self, caplog):
        """Non-square boards should be skipped with warning."""
        stats_list = [
            create_single_game_stats(game_name="a.sgf", board_size=(19, 19)),
            create_single_game_stats(game_name="rect.sgf", board_size=(19, 13)),
        ]

        with caplog.at_level(logging.WARNING):
            filtered, size = _filter_by_board_size(stats_list)

        assert size == 19
        assert len(filtered) == 1
        assert "non-square" in caplog.text.lower()


class TestDeterministicOrdering:
    """Test deterministic sorting with source_index."""

    def test_stable_sort_key_uses_source_index(self):
        """source_index should break ties when other fields are equal."""
        stats_list = [
            create_single_game_stats(game_name="same.sgf", date="2025-01-01", total_moves=50, source_index=2),
            create_single_game_stats(game_name="same.sgf", date="2025-01-01", total_moves=50, source_index=1),
            create_single_game_stats(game_name="same.sgf", date="2025-01-01", total_moves=50, source_index=0),
        ]

        # Verify order is deterministic
        sorted_keys = [_stable_sort_key(s) for s in sorted(stats_list, key=_stable_sort_key)]
        assert sorted_keys[0][3] == 0  # source_index
        assert sorted_keys[1][3] == 1
        assert sorted_keys[2][3] == 2

    def test_empty_and_duplicate_game_names_sorted_stably(self):
        """Empty and duplicate game_name should be sorted deterministically."""
        stats_list = [
            create_single_game_stats(game_name="", source_index=1),
            create_single_game_stats(game_name="", source_index=0),
            create_single_game_stats(game_name="a.sgf", source_index=2),
        ]

        games = _reconstruct_pattern_input(stats_list, 19)
        game_names = [g[0] for g in games]

        # Empty strings sort first, then by source_index
        assert game_names[0] == ""
        assert game_names[1] == ""
        assert game_names[2] == "a.sgf"

    def test_skipped_invalid_moves_logged(self, caplog):
        """Invalid moves should be skipped with warning."""
        stats = create_single_game_stats()
        stats["pattern_data"] = [
            # Valid move
            {"move_number": 10, "player": "B", "gtp": "D4", "mistake_category": "BLUNDER", "score_loss": 5.0},
            # Invalid player
            {"move_number": 20, "player": "X", "gtp": "E5", "mistake_category": "MISTAKE", "score_loss": 3.0},
            # Invalid gtp
            {"move_number": 30, "player": "W", "gtp": "pass", "mistake_category": "MISTAKE", "score_loss": 3.0},
            # Invalid move_number
            {"move_number": 0, "player": "B", "gtp": "F6", "mistake_category": "BLUNDER", "score_loss": 4.0},
        ]

        with caplog.at_level(logging.DEBUG):
            games = _reconstruct_pattern_input([stats], 19)

        # Only 1 valid move should remain
        assert len(games) == 1
        assert len(games[0][1].moves) == 1
        assert games[0][1].moves[0].gtp == "D4"


class TestProductionSafety:
    """Test that Summary generation doesn't crash with corrupt data."""

    def test_summary_does_not_crash_on_corrupt_data(self):
        """Summary generation should not crash with corrupt data."""
        stats_list = [create_single_game_stats(game_name="good.sgf")]
        stats_list[0]["pattern_data"].append(
            {
                "move_number": 99,
                "player": "INVALID",  # Invalid player
                "gtp": "A1",
                "score_loss": 10.0,
                "mistake_category": "BLUNDER",
            }
        )

        # Should NOT raise
        output = build_summary_from_stats(stats_list, "TestPlayer", mock_config_fn)
        assert isinstance(output, str)

    def test_summary_does_not_crash_on_invalid_gtp_format(self):
        """Summary generation should not crash with invalid GTP coordinates."""
        stats_list = [create_single_game_stats(game_name="good.sgf")]
        stats_list[0]["pattern_data"].append(
            {
                "move_number": 50,
                "player": "B",
                "gtp": "Z99",  # Invalid coordinate format
                "score_loss": 10.0,
                "mistake_category": "BLUNDER",
            }
        )
        stats_list[0]["pattern_data"].append(
            {
                "move_number": 51,
                "player": "W",
                "gtp": "I5",  # 'I' is skipped in GTP
                "score_loss": 8.0,
                "mistake_category": "BLUNDER",
            }
        )

        # Should NOT raise - invalid moves are filtered out
        output = build_summary_from_stats(stats_list, "TestPlayer", mock_config_fn)
        assert isinstance(output, str)

    def test_summary_handles_list_board_size(self):
        """Summary should handle list board_size from JSON."""
        stats_list = [
            create_single_game_stats(game_name="a.sgf", board_size=[19, 19]),
            create_single_game_stats(game_name="b.sgf", board_size=[19, 19]),
        ]

        # Should NOT raise
        output = build_summary_from_stats(stats_list, "TestPlayer", mock_config_fn)
        assert isinstance(output, str)

    def test_summary_handles_none_meaning_tag_id(self):
        """Summary should handle None meaning_tag_id (pattern_miner normalizes to 'uncertain')."""
        stats_list = [
            create_single_game_stats(game_name="a.sgf"),
            create_single_game_stats(game_name="b.sgf"),
        ]
        # Set meaning_tag_id to None
        for stats in stats_list:
            for item in stats["pattern_data"]:
                item["meaning_tag_id"] = None

        # Should NOT raise - pattern_miner normalizes to "uncertain"
        output = build_summary_from_stats(stats_list, "TestPlayer", mock_config_fn)
        assert isinstance(output, str)


class TestUnknownSignatureFieldLogging:
    """Test that unknown signature field values are logged for debugging."""

    def test_phase_keys_expected_values(self):
        """PHASE_KEYS should contain exactly the expected values."""
        assert set(PHASE_KEYS.keys()) == {"opening", "middle", "endgame"}

    def test_area_keys_expected_values(self):
        """AREA_KEYS should contain exactly the expected values."""
        assert set(AREA_KEYS.keys()) == {"corner", "edge", "center"}

    def test_severity_keys_expected_values(self):
        """SEVERITY_KEYS should contain exactly the expected values."""
        assert set(SEVERITY_KEYS.keys()) == {"mistake", "blunder"}

"""
Tests for variation support in GameAdapter.

M5.1a: Basic Variation Selection
"""

import pytest
from katrain_qt.core_adapter import GameAdapter


# SGF with variations
# Main line: D4 -> Q16 -> D16
# Variation at move 1: D4 -> Q4 (alternative to Q16)
# Variation at move 2 (main line): D4 -> Q16 -> R4 (alternative to D16)
SGF_WITH_VARIATIONS = """(;GM[1]FF[4]CA[UTF-8]SZ[19]KM[6.5]
;B[pd]
(;W[dd]
(;B[dp];W[pp])
(;B[pp];W[cq])
)
(;W[dc];B[pq])
)"""

# Simpler SGF: just main line, no variations
SGF_NO_VARIATIONS = """(;GM[1]FF[4]CA[UTF-8]SZ[19]KM[6.5]
;B[pd];W[dd];B[dp];W[pp])"""


class TestHasVariations:
    """Tests for has_variations() method."""

    def test_no_game_returns_false(self):
        adapter = GameAdapter()
        assert adapter.has_variations() is False

    def test_root_with_single_child(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_NO_VARIATIONS)
        # At root, should have only 1 child (main line)
        assert adapter.has_variations() is False

    def test_root_with_variations(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        # At root after B[pd], root has 2 children (W[dd] and W[dc])
        # First need to understand the structure - root itself has 1 child
        # The variation is at move 1 (after B[pd])
        # At root position, there's 1 child
        assert adapter.has_variations() is False

    def test_after_first_move_has_variations(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # Go to B[pd]
        # After B[pd], there are 2 children: W[dd] and W[dc]
        assert adapter.has_variations() is True


class TestGetChildVariations:
    """Tests for get_child_variations() method."""

    def test_no_game_returns_empty(self):
        adapter = GameAdapter()
        assert adapter.get_child_variations() == []

    def test_at_end_of_game_returns_empty(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_NO_VARIATIONS)
        adapter.nav_last()
        assert adapter.get_child_variations() == []

    def test_main_line_single_child(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_NO_VARIATIONS)
        # At root, one child: B[pd]
        children = adapter.get_child_variations()
        assert len(children) == 1
        index, move, player = children[0]
        assert index == 0
        assert move == "Q16"  # pd in GTP
        assert player == "B"

    def test_with_variations_lists_all(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # Go to B[pd]
        children = adapter.get_child_variations()
        # Should have 2 children: W[dd] and W[dc]
        assert len(children) == 2
        # Check both are White moves
        for idx, move, player in children:
            assert player == "W"
        # Moves should be D16 (dd) and D17 (dc)
        moves = {move for _, move, _ in children}
        assert "D16" in moves  # dd
        assert "D17" in moves  # dc


class TestSwitchToChild:
    """Tests for switch_to_child() method."""

    def test_no_game_returns_false(self):
        adapter = GameAdapter()
        assert adapter.switch_to_child(0) is False

    def test_invalid_index_returns_false(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_NO_VARIATIONS)
        assert adapter.switch_to_child(-1) is False
        assert adapter.switch_to_child(999) is False

    def test_switch_to_main_line(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_NO_VARIATIONS)
        # At root, switch to child 0 (B[pd])
        assert adapter.switch_to_child(0) is True
        assert adapter.current_move_number == 1

    def test_switch_to_variation(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # Go to B[pd]
        # Get children to find which is variation
        children = adapter.get_child_variations()
        # Switch to second variation
        assert adapter.switch_to_child(1) is True
        assert adapter.current_move_number == 2


class TestGetCurrentVariationIndex:
    """Tests for get_current_variation_index() method."""

    def test_no_game_returns_zero(self):
        adapter = GameAdapter()
        assert adapter.get_current_variation_index() == 0

    def test_at_root_returns_zero(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        assert adapter.get_current_variation_index() == 0

    def test_main_line_returns_zero(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # B[pd]
        adapter.nav_next()  # W[dd] (main line)
        assert adapter.get_current_variation_index() == 0

    def test_variation_returns_correct_index(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # B[pd]
        adapter.switch_to_child(1)  # Switch to variation
        assert adapter.get_current_variation_index() == 1


class TestGetSiblingCount:
    """Tests for get_sibling_count() method."""

    def test_no_game_returns_one(self):
        adapter = GameAdapter()
        assert adapter.get_sibling_count() == 1

    def test_at_root_returns_one(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        assert adapter.get_sibling_count() == 1

    def test_with_siblings(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # B[pd]
        adapter.nav_next()  # W[dd] - this node has a sibling W[dc]
        assert adapter.get_sibling_count() == 2


class TestSwitchToSibling:
    """Tests for switch_to_sibling() method."""

    def test_no_game_returns_false(self):
        adapter = GameAdapter()
        assert adapter.switch_to_sibling(0) is False

    def test_at_root_returns_false(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        assert adapter.switch_to_sibling(0) is False

    def test_same_sibling_returns_false(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # B[pd]
        adapter.nav_next()  # W[dd]
        # Already at sibling 0, switching to 0 should return False
        assert adapter.switch_to_sibling(0) is False

    def test_switch_to_different_sibling(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # B[pd]
        adapter.nav_next()  # W[dd]
        # Switch to sibling 1 (W[dc])
        assert adapter.switch_to_sibling(1) is True
        assert adapter.get_current_variation_index() == 1


class TestNavVariation:
    """Tests for nav_next_variation() and nav_prev_variation() methods."""

    def test_no_game_returns_false(self):
        adapter = GameAdapter()
        assert adapter.nav_next_variation() is False
        assert adapter.nav_prev_variation() is False

    def test_at_root_returns_false(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        assert adapter.nav_next_variation() is False
        assert adapter.nav_prev_variation() is False

    def test_no_siblings_returns_false(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_NO_VARIATIONS)
        adapter.nav_next()  # B[pd] - only child
        assert adapter.nav_next_variation() is False
        assert adapter.nav_prev_variation() is False

    def test_next_variation_cycles(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # B[pd]
        adapter.nav_next()  # W[dd] (index 0)

        # Navigate to next (index 1)
        assert adapter.nav_next_variation() is True
        assert adapter.get_current_variation_index() == 1

        # Navigate to next again (should cycle back to 0)
        assert adapter.nav_next_variation() is True
        assert adapter.get_current_variation_index() == 0

    def test_prev_variation_cycles(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # B[pd]
        adapter.nav_next()  # W[dd] (index 0)

        # Navigate to prev (should cycle to last, index 1)
        assert adapter.nav_prev_variation() is True
        assert adapter.get_current_variation_index() == 1

        # Navigate to prev again (back to 0)
        assert adapter.nav_prev_variation() is True
        assert adapter.get_current_variation_index() == 0


class TestVariationWithAnalysisCache:
    """Tests to verify analysis cache handles variations correctly."""

    def test_different_variations_have_different_node_ids(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # B[pd]

        # Go to main line
        adapter.switch_to_child(0)
        node_id_main = adapter.current_node_id

        # Go back and to variation
        adapter.nav_prev()
        adapter.switch_to_child(1)
        node_id_var = adapter.current_node_id

        # Node IDs should be different
        assert node_id_main != node_id_var

    def test_same_node_has_same_id(self):
        adapter = GameAdapter()
        adapter.load_sgf_string(SGF_WITH_VARIATIONS)
        adapter.nav_next()  # B[pd]
        adapter.nav_next()  # W[dd]

        node_id_1 = adapter.current_node_id

        # Navigate away and back
        adapter.nav_prev()
        adapter.nav_next()

        node_id_2 = adapter.current_node_id

        # Should be the same node
        assert node_id_1 == node_id_2

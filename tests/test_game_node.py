"""Phase 199C-1: GameNode dedicated tests.

Target: raise katrain/core/game_node.py coverage from 49% to ~85%.

Covers the following previously-untested or under-tested areas:
- analysis_dumps / load_analysis round-trip (serialization)
- add_shortcut / remove_shortcut (branch collapsing)
- update_move_analysis (move merging logic)
- set_analysis (normal / refine_move / additional_moves modes)
- sgf_properties (KT analysis saving, marks, shortcuts, comments)
- comment (sgf / teach / details / interactive branches)
- policy_ranking (grid conversion + sorting)
- order_children, add_list_property, clear_analysis
- points_lost, parent_realized_points_lost, candidate_moves

Uses shared fixtures from conftest.py (root_node, install_node_analysis).
No Kivy imports — pure core-layer logic.
"""

from __future__ import annotations

import base64
import gzip
import json
from typing import Any

from katrain.core.constants.metadata import SGF_INTERNAL_COMMENTS_MARKER, SGF_SEPARATOR_MARKER
from katrain.core.constants.priorities import ADDITIONAL_MOVE_ORDER
from katrain.core.game_node import GameNode, analysis_dumps
from katrain.core.sgf_parser import Move

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis_json(
    *,
    root_visits: int = 100,
    root_winrate: float = 0.55,
    root_score: float = 3.0,
    move_infos: list[dict] | None = None,
    ownership: list[float] | None = None,
    policy: list[float] | None = None,
) -> dict[str, Any]:
    """Build a KataGo-style analysis JSON for set_analysis()."""
    return {
        "rootInfo": {
            "visits": root_visits,
            "winrate": root_winrate,
            "scoreLead": root_score,
        },
        "moveInfos": move_infos or [],
        "ownership": ownership,
        "policy": policy,
    }


def _make_move_info(
    gtp: str,
    *,
    order: int = 0,
    visits: int = 50,
    winrate: float = 0.55,
    score_lead: float = 3.0,
    pv: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "move": gtp,
        "order": order,
        "visits": visits,
        "winrate": winrate,
        "scoreLead": score_lead,
        "pv": pv or [gtp],
    }


# ---------------------------------------------------------------------------
# analysis_dumps / load_analysis round-trip
# ---------------------------------------------------------------------------


class TestAnalysisDumpLoad:
    """Test serialization and deserialization of analysis data."""

    def test_analysis_dumps_returns_three_base64_strings(self):
        analysis = {
            "moves": {"D4": {"move": "D4", "visits": 10}},
            "root": {"visits": 10, "winrate": 0.5, "scoreLead": 0.0},
            "ownership": [0.5] * 361,
            "policy": [0.01] * 362,
            "completed": True,
        }
        result = analysis_dumps(analysis)
        assert len(result) == 3
        for s in result:
            assert isinstance(s, str)
            base64.standard_b64decode(s)

    def test_analysis_dumps_strips_per_move_ownership(self):
        analysis = {
            "moves": {"D4": {"move": "D4", "visits": 10, "ownership": [1.0]}},
            "root": None,
            "ownership": [0.5] * 361,
            "policy": [0.01] * 362,
            "completed": False,
        }
        result = analysis_dumps(analysis)
        # Decode main data (index 2) and verify ownership was stripped from move
        main_data = json.loads(gzip.decompress(base64.standard_b64decode(result[2])))
        assert "ownership" not in main_data["moves"]["D4"]

    def test_load_analysis_returns_false_when_none(self, root_node):
        root_node.analysis_from_sgf = None
        assert root_node.load_analysis() is False

    def test_load_analysis_returns_false_when_empty(self, root_node):
        root_node.analysis_from_sgf = []
        assert root_node.load_analysis() is False

    def test_load_analysis_round_trip(self, root_node):
        original_analysis = {
            "moves": {"D4": {"move": "D4", "visits": 10, "winrate": 0.5, "scoreLead": 0.0, "order": 0}},
            "root": {"visits": 10, "winrate": 0.5, "scoreLead": 0.0},
            "ownership": [0.5] * 361,
            "policy": [0.01] * 362,
            "completed": True,
        }
        dumped = analysis_dumps(original_analysis)
        root_node.analysis_from_sgf = dumped
        result = root_node.load_analysis()
        assert result is True
        assert root_node.analysis["root"]["visits"] == 10
        assert len(root_node.analysis["ownership"]) == 361
        assert len(root_node.analysis["policy"]) == 362

    def test_load_analysis_bad_version_raises_value_error(self, root_node):
        dumped = analysis_dumps(
            {"moves": {}, "root": {"visits": 1}, "ownership": [0.5] * 361, "policy": [0.01] * 362, "completed": True}
        )
        root_node.analysis_from_sgf = dumped
        root_node.properties["KTV"] = ["99.99.99"]
        result = root_node.load_analysis()
        # Version too high → ValueError caught → returns False
        assert result is False

    def test_load_analysis_corrupt_data_returns_false(self, root_node):
        root_node.analysis_from_sgf = ["!!!not_base64!!!", "aaaa", "bbbb"]
        result = root_node.load_analysis()
        assert result is False


# ---------------------------------------------------------------------------
# add_shortcut / remove_shortcut
# ---------------------------------------------------------------------------


class TestShortcuts:
    """Test branch collapsing shortcuts."""

    def test_add_shortcut_links_nodes(self, root_node):
        child1 = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        child2 = GameNode(parent=child1, move=Move.from_gtp("Q16", player="W"))
        child3 = GameNode(parent=child2, move=Move.from_gtp("D16", player="B"))

        root_node.add_shortcut(child3)
        assert len(root_node.shortcuts_to) == 1
        to_node, via = root_node.shortcuts_to[0]
        assert to_node is child3
        assert child3.shortcut_from is root_node

    def test_add_shortcut_no_link_for_direct_child(self, root_node):
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        root_node.add_shortcut(child)
        # Only 2 nodes in path → no shortcut created (len(nodes) > 2 required)
        assert len(root_node.shortcuts_to) == 0

    def test_add_shortcut_no_link_for_unrelated_node(self, root_node):
        other_root = GameNode(properties={"SZ": 19})
        child = GameNode(parent=other_root, move=Move.from_gtp("D4", player="B"))
        # root_node.add_shortcut(child) — child is not a descendant of root_node
        root_node.add_shortcut(child)
        assert len(root_node.shortcuts_to) == 0

    def test_remove_shortcut_clears_link(self, root_node):
        child1 = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        child2 = GameNode(parent=child1, move=Move.from_gtp("Q16", player="W"))
        child3 = GameNode(parent=child2, move=Move.from_gtp("D16", player="B"))

        root_node.add_shortcut(child3)
        assert child3.shortcut_from is root_node

        child3.remove_shortcut()
        assert child3.shortcut_from is None
        assert len(root_node.shortcuts_to) == 0

    def test_remove_shortcut_no_from_does_nothing(self, root_node):
        root_node.remove_shortcut()  # shortcut_from is None
        assert root_node.shortcut_from is None


# ---------------------------------------------------------------------------
# update_move_analysis
# ---------------------------------------------------------------------------


class TestUpdateMoveAnalysis:
    """Test move analysis merging logic."""

    def test_new_move_added(self, root_node):
        move_analysis = {"visits": 50, "winrate": 0.6, "scoreLead": 2.0}
        root_node.update_move_analysis(move_analysis, "D4")
        assert "D4" in root_node.analysis["moves"]
        m = root_node.analysis["moves"]["D4"]
        assert m["visits"] == 50
        assert m["order"] == ADDITIONAL_MOVE_ORDER

    def test_existing_move_higher_visits_replaced(self, root_node):
        root_node.analysis["moves"]["D4"] = {"move": "D4", "visits": 30, "winrate": 0.5, "scoreLead": 1.0, "order": 0}
        new = {"visits": 100, "winrate": 0.6, "scoreLead": 2.0, "order": 1}
        root_node.update_move_analysis(new, "D4")
        m = root_node.analysis["moves"]["D4"]
        assert m["visits"] == 100
        assert m["winrate"] == 0.6

    def test_existing_move_lower_visits_merged_keys(self, root_node):
        root_node.analysis["moves"]["D4"] = {"move": "D4", "visits": 100, "winrate": 0.6, "scoreLead": 2.0, "order": 0}
        new = {"visits": 30, "prior": 0.15, "order": 1}
        root_node.update_move_analysis(new, "D4")
        m = root_node.analysis["moves"]["D4"]
        assert m["visits"] == 100  # kept old (higher)
        assert m["prior"] == 0.15  # added new key

    def test_merged_order_is_minimum(self, root_node):
        root_node.analysis["moves"]["D4"] = {"move": "D4", "visits": 100, "winrate": 0.6, "scoreLead": 2.0, "order": 3}
        new = {"visits": 200, "winrate": 0.7, "scoreLead": 3.0, "order": 1}
        root_node.update_move_analysis(new, "D4")
        assert root_node.analysis["moves"]["D4"]["order"] == 1


# ---------------------------------------------------------------------------
# set_analysis
# ---------------------------------------------------------------------------


class TestSetAnalysis:
    """Test set_analysis with different modes."""

    def test_normal_update_sets_root_and_moves(self, root_node):
        analysis_json = _make_analysis_json(
            move_infos=[_make_move_info("D4", order=0), _make_move_info("Q16", order=1)]
        )
        root_node.set_analysis(analysis_json)
        assert root_node.analysis["root"] is not None
        assert root_node.analysis["root"]["visits"] == 100
        assert "D4" in root_node.analysis["moves"]
        assert "Q16" in root_node.analysis["moves"]
        assert root_node.analysis["completed"] is True

    def test_normal_update_with_parent_propagates(self, root_node):
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        analysis_json = _make_analysis_json(move_infos=[_make_move_info("D4", order=0)])
        child.set_analysis(analysis_json)
        # Parent should have D4 in its moves (propagated from child's rootInfo)
        assert "D4" in root_node.analysis["moves"]

    def test_partial_result_does_not_complete(self, root_node):
        analysis_json = _make_analysis_json()
        root_node.set_analysis(analysis_json, partial_result=True)
        assert root_node.analysis["completed"] is False

    def test_refine_move_updates_specific_move(self, root_node):
        root_node.analysis["moves"]["D4"] = {
            "move": "D4",
            "visits": 30,
            "winrate": 0.5,
            "scoreLead": 1.0,
            "order": 0,
        }
        refine = Move.from_gtp("D4", player="B")
        analysis_json = _make_analysis_json(move_infos=[_make_move_info("D4", pv=["D4", "Q16", "D16"])])
        root_node.set_analysis(analysis_json, refine_move=refine)
        m = root_node.analysis["moves"]["D4"]
        assert "pv" in m
        assert m["pv"][0] == "D4"

    def test_additional_moves_preserves_old_order(self, root_node):
        root_node.analysis["moves"]["D4"] = {
            "move": "D4",
            "visits": 50,
            "winrate": 0.5,
            "scoreLead": 1.0,
            "order": 0,
        }
        analysis_json = _make_analysis_json(
            move_infos=[_make_move_info("Q16", order=0), _make_move_info("D16", order=1)]
        )
        root_node.set_analysis(analysis_json, additional_moves=True)
        # Old move D4 keeps its order=0; new moves get ADDITIONAL_MOVE_ORDER
        assert root_node.analysis["moves"]["D4"]["order"] == 0
        assert root_node.analysis["moves"]["Q16"]["order"] == ADDITIONAL_MOVE_ORDER

    def test_normal_update_resets_old_move_orders(self, root_node):
        root_node.analysis["moves"]["D4"] = {
            "move": "D4",
            "visits": 50,
            "winrate": 0.5,
            "scoreLead": 1.0,
            "order": 0,
        }
        analysis_json = _make_analysis_json(move_infos=[_make_move_info("Q16", order=0)])
        root_node.set_analysis(analysis_json)
        # Old move D4 should have its order bumped to ADDITIONAL_MOVE_ORDER
        assert root_node.analysis["moves"]["D4"]["order"] == ADDITIONAL_MOVE_ORDER

    def test_set_analysis_sets_ownership_and_policy(self, root_node):
        ownership = [0.5] * 361
        policy = [0.01] * 362
        analysis_json = _make_analysis_json(ownership=ownership, policy=policy)
        root_node.set_analysis(analysis_json)
        assert root_node.analysis["ownership"] == ownership
        assert root_node.analysis["policy"] == policy


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    """Test analysis-related properties."""

    def test_clear_analysis(self, root_node):
        root_node.analysis["root"] = {"visits": 100}
        root_node.analysis["completed"] = True
        root_node.clear_analysis()
        assert root_node.analysis["root"] is None
        assert root_node.analysis["completed"] is False
        assert root_node.analysis["moves"] == {}

    def test_analysis_exists_false_by_default(self, root_node):
        assert root_node.analysis_exists is False

    def test_analysis_exists_true_after_root_set(self, root_node):
        root_node.analysis["root"] = {"visits": 10}
        assert root_node.analysis_exists is True

    def test_analysis_complete_requires_both(self, root_node):
        root_node.analysis["root"] = {"visits": 10}
        root_node.analysis["completed"] = False
        assert root_node.analysis_complete is False
        root_node.analysis["completed"] = True
        assert root_node.analysis_complete is True

    def test_root_visits_default_zero(self, root_node):
        assert root_node.root_visits == 0

    def test_root_visits_from_analysis(self, root_node):
        root_node.analysis["root"] = {"visits": 42}
        assert root_node.root_visits == 42

    def test_root_visits_none_root(self, root_node):
        root_node.analysis["root"] = None
        assert root_node.root_visits == 0

    def test_score_none_when_no_analysis(self, root_node):
        assert root_node.score is None

    def test_score_from_analysis(self, root_node):
        root_node.analysis["root"] = {"scoreLead": 5.5, "visits": 10}
        assert root_node.score == 5.5

    def test_format_score_positive(self, root_node):
        root_node.analysis["root"] = {"scoreLead": 3.5, "visits": 10}
        result = root_node.format_score()
        assert result is not None
        assert "3.5" in result

    def test_format_score_negative(self, root_node):
        root_node.analysis["root"] = {"scoreLead": -2.0, "visits": 10}
        result = root_node.format_score()
        assert result is not None
        assert "2.0" in result

    def test_format_score_none(self, root_node):
        assert root_node.format_score() is None

    def test_winrate_none_when_no_analysis(self, root_node):
        assert root_node.winrate is None

    def test_winrate_from_analysis(self, root_node):
        root_node.analysis["root"] = {"winrate": 0.7, "visits": 10}
        assert root_node.winrate == 0.7

    def test_format_winrate_black_leading(self, root_node):
        root_node.analysis["root"] = {"winrate": 0.7, "visits": 10}
        result = root_node.format_winrate()
        assert result is not None
        assert "70.0%" in result

    def test_format_winrate_white_leading(self, root_node):
        root_node.analysis["root"] = {"winrate": 0.3, "visits": 10}
        result = root_node.format_winrate()
        assert result is not None
        assert "70.0%" in result

    def test_format_winrate_none(self, root_node):
        assert root_node.format_winrate() is None

    def test_points_lost_none_at_root(self, root_node):
        assert root_node.points_lost is None

    def test_points_lost_with_analysis(self, root_node):
        root_node.analysis["root"] = {"scoreLead": 5.0, "visits": 10, "winrate": 0.5}
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        child.analysis["root"] = {"scoreLead": 3.0, "visits": 10, "winrate": 0.5}
        # B played: sign = +1, points_lost = 1*(5.0-3.0) = 2.0
        assert child.points_lost == 2.0

    def test_points_lost_white_player(self, root_node):
        root_node.analysis["root"] = {"scoreLead": -3.0, "visits": 10, "winrate": 0.5}
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="W"))
        child.analysis["root"] = {"scoreLead": -1.0, "visits": 10, "winrate": 0.5}
        # W played: sign = -1, points_lost = -1*(-3.0 - (-1.0)) = -1*(-2.0) = 2.0
        assert child.points_lost == 2.0

    def test_parent_realized_points_lost_none_without_grandparent(self, root_node):
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        assert child.parent_realized_points_lost is None

    def test_parent_realized_points_lost_with_grandparent(self, root_node):
        root_node.analysis["root"] = {"scoreLead": 5.0, "visits": 10, "winrate": 0.5}
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        child.analysis["root"] = {"scoreLead": 3.0, "visits": 10, "winrate": 0.5}
        grandchild = GameNode(parent=child, move=Move.from_gtp("Q16", player="W"))
        grandchild.analysis["root"] = {"scoreLead": 4.0, "visits": 10, "winrate": 0.5}
        # W played grandchild's move: sign = -1*(4.0 - 5.0) = 1.0
        result = grandchild.parent_realized_points_lost
        assert result is not None
        assert result == 1.0

    def test_player_sign(self):
        assert GameNode.player_sign("B") == 1
        assert GameNode.player_sign("W") == -1
        assert GameNode.player_sign(None) == 0


# ---------------------------------------------------------------------------
# candidate_moves
# ---------------------------------------------------------------------------


class TestCandidateMoves:
    """Test candidate_moves property."""

    def test_empty_when_no_analysis(self, root_node):
        assert root_node.candidate_moves == []

    def test_returns_moves_sorted_by_order(self, root_node):
        root_node.analysis["root"] = {"scoreLead": 0.0, "winrate": 0.5, "visits": 100}
        root_node.analysis["moves"] = {
            "D4": {"move": "D4", "order": 0, "visits": 50, "scoreLead": 0.0, "winrate": 0.5},
            "Q16": {"move": "Q16", "order": 1, "visits": 30, "scoreLead": -2.0, "winrate": 0.4},
        }
        moves = root_node.candidate_moves
        assert len(moves) == 2
        assert moves[0]["move"] == "D4"
        assert moves[1]["move"] == "Q16"
        assert "pointsLost" in moves[0]
        assert "winrateLost" in moves[0]

    def test_candidate_moves_no_moves_uses_policy(self, root_node):
        root_node.analysis["root"] = {"scoreLead": 0.0, "winrate": 0.5, "visits": 100}
        root_node.analysis["moves"] = {}
        # With no moves and no policy → returns single pass move
        moves = root_node.candidate_moves
        assert len(moves) == 1
        assert moves[0]["move"] == "pass"

    def test_candidate_moves_points_lost_calculation(self, root_node):
        root_node.analysis["root"] = {"scoreLead": 5.0, "winrate": 0.6, "visits": 100}
        root_node.analysis["moves"] = {
            "D4": {"move": "D4", "order": 0, "visits": 50, "scoreLead": 5.0, "winrate": 0.6},
            "Q16": {"move": "Q16", "order": 1, "visits": 30, "scoreLead": 1.0, "winrate": 0.5},
        }
        moves = root_node.candidate_moves
        # Next player is B (sign=+1). For Q16: pointsLost = max(0, 1*(5.0-1.0)) = 4.0
        q16 = [m for m in moves if m["move"] == "Q16"][0]
        assert q16["pointsLost"] == 4.0


# ---------------------------------------------------------------------------
# policy_ranking
# ---------------------------------------------------------------------------


class TestPolicyRanking:
    """Test policy_ranking property."""

    def test_empty_when_no_policy(self, root_node):
        assert root_node.policy_ranking == []

    def test_policy_ranking_9x9(self):
        node = GameNode(properties={"SZ": 9})
        # 9x9 = 81 squares + 1 pass = 82 policy values
        policy = [0.0] * 82
        policy[40] = 0.5  # center-ish highest
        policy[0] = 0.3
        policy[81] = 0.1  # pass
        node.analysis["policy"] = policy
        ranking = node.policy_ranking
        assert len(ranking) == 82
        # Highest policy should be first
        assert ranking[0][0] == 0.5
        assert ranking[-1][0] <= ranking[0][0]

    def test_policy_ranking_handles_none_scores(self):
        node = GameNode(properties={"SZ": 9})
        policy = [None] * 82
        policy[0] = 0.5
        node.analysis["policy"] = policy
        ranking = node.policy_ranking
        assert len(ranking) == 82
        assert ranking[0][0] == 0.5  # 0.5 > -inf


# ---------------------------------------------------------------------------
# order_children
# ---------------------------------------------------------------------------


class TestOrderChildren:
    """Test static order_children method."""

    def test_auto_undo_sorting_order(self):
        node_none = GameNode()
        node_none.auto_undo = None
        node_false = GameNode()
        node_false.auto_undo = False
        node_true = GameNode()
        node_true.auto_undo = True
        result = GameNode.order_children([node_true, node_none, node_false])
        # Sort key: None→0.5, False→0, True→1
        assert result[0] is node_false
        assert result[1] is node_none
        assert result[2] is node_true


# ---------------------------------------------------------------------------
# add_list_property
# ---------------------------------------------------------------------------


class TestAddListProperty:
    """Test add_list_property for KT and C properties."""

    def test_kt_property_sets_analysis_from_sgf(self, root_node):
        root_node.add_list_property("KT", ["abc", "def"])
        assert root_node.analysis_from_sgf == ["abc", "def"]

    def test_c_property_extracts_note(self, root_node):
        root_node.add_list_property("C", ["Hello world"])
        assert root_node.note == "Hello world"

    def test_c_property_filters_internal_comments(self, root_node):
        root_node.add_list_property("C", [f"keep{SGF_SEPARATOR_MARKER}auto{SGF_INTERNAL_COMMENTS_MARKER}filtered"])
        assert SGF_INTERNAL_COMMENTS_MARKER not in root_node.note

    def test_other_property_delegates_to_super(self, root_node):
        root_node.add_list_property("RU", ["chinese"])
        assert root_node.get_property("RU") == "chinese"


# ---------------------------------------------------------------------------
# comment
# ---------------------------------------------------------------------------


class TestComment:
    """Test comment generation."""

    def test_root_comment_shows_komi_rules(self, root_node):
        result = root_node.comment()
        # Root node always shows komi/rules info
        assert len(result) > 0

    def test_root_comment_with_analysis(self, root_node):
        root_node.analysis["root"] = {"scoreLead": 0.5, "visits": 10, "winrate": 0.5}
        result = root_node.comment()
        assert "komi" in result.lower() or "ルール" in result or "ruleset" in result.lower()

    def test_move_comment_no_analysis(self, root_node):
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        result = child.comment()
        # "Analyzing move..." or "No analysis available"
        assert len(result) > 0

    def test_move_comment_with_analysis_sgf(self, root_node):
        root_node.analysis["root"] = {"scoreLead": 5.0, "visits": 100, "winrate": 0.6}
        root_node.analysis["moves"] = {
            "D4": {"move": "D4", "order": 0, "visits": 50, "scoreLead": 5.0, "winrate": 0.6, "pv": ["D4"]},
        }
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        child.analysis["root"] = {"scoreLead": 5.0, "visits": 100, "winrate": 0.6}
        result = child.comment(sgf=True)
        assert len(result) > 0

    def test_move_comment_best_move(self, root_node):
        root_node.analysis["root"] = {"scoreLead": 5.0, "visits": 100, "winrate": 0.6}
        root_node.analysis["moves"] = {
            "D4": {"move": "D4", "order": 0, "visits": 50, "scoreLead": 5.0, "winrate": 0.6, "pv": ["D4"]},
        }
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        child.analysis["root"] = {"scoreLead": 5.0, "visits": 100, "winrate": 0.6}
        result = child.comment(sgf=True)
        # Should mention best move since played move matches top candidate
        assert "best" in result.lower() or "最善" in result

    def test_move_comment_with_ai_thoughts(self, root_node):
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        child.ai_thoughts = "This is a good move"
        result = child.comment(details=True)
        assert "This is a good move" in result

    def test_move_comment_with_sgf_properties_c(self, root_node):
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        child.properties["C"] = ["Original comment"]
        result = child.comment()
        assert "Original comment" in result


# ---------------------------------------------------------------------------
# sgf_properties
# ---------------------------------------------------------------------------


class TestSgfProperties:
    """Test SGF property generation."""

    def test_basic_properties(self, root_node):
        props = root_node.sgf_properties()
        assert "CA" in props
        assert props["CA"] == ["UTF-8"]
        assert "AP" in props
        assert "KTV" in props

    def test_save_analysis_when_complete(self, root_node):
        root_node.analysis["root"] = {"visits": 10, "winrate": 0.5, "scoreLead": 0.0}
        root_node.analysis["completed"] = True
        root_node.analysis["ownership"] = [0.5] * 361
        root_node.analysis["policy"] = [0.01] * 362
        props = root_node.sgf_properties(save_analysis=True)
        assert "KT" in props
        assert len(props["KT"]) == 3

    def test_no_kt_when_analysis_incomplete(self, root_node):
        root_node.analysis["root"] = {"visits": 10, "winrate": 0.5, "scoreLead": 0.0}
        root_node.analysis["completed"] = False
        props = root_node.sgf_properties(save_analysis=True)
        assert "KT" not in props

    def test_shortcut_properties(self, root_node):
        child1 = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        child2 = GameNode(parent=child1, move=Move.from_gtp("Q16", player="W"))
        child3 = GameNode(parent=child2, move=Move.from_gtp("D16", player="B"))
        root_node.add_shortcut(child3)

        props = root_node.sgf_properties()
        assert "KTSID" in props

        child3_props = child3.sgf_properties()
        assert "KTSF" in child3_props

    def test_note_in_properties(self, root_node):
        root_node.note = "My note"
        props = root_node.sgf_properties()
        assert "C" in props
        assert "My note" in props["C"][0]


# ---------------------------------------------------------------------------
# analyze (engine delegation)
# ---------------------------------------------------------------------------


class TestAnalyze:
    """Test analyze method (engine delegation)."""

    def test_analyze_no_engine_does_nothing(self, root_node):
        root_node.analyze(engine=None)
        # Should not raise, should not set analysis
        assert root_node.analysis["root"] is None

    def test_analyze_calls_engine(self, root_node):
        from unittest.mock import MagicMock

        engine = MagicMock()
        root_node.analyze(engine=engine, visits=100)
        assert engine.request_analysis.called
        call_kwargs = engine.request_analysis.call_args
        assert call_kwargs.kwargs["visits"] == 100


# ---------------------------------------------------------------------------
# make_pv
# ---------------------------------------------------------------------------


class TestMakePv:
    """Test make_pv helper."""

    def test_make_pv_non_interactive(self, root_node):
        result = root_node.make_pv("B", ["D4", "Q16"], interactive=False)
        assert result == "BD4 Q16"

    def test_make_pv_interactive(self, root_node):
        result = root_node.make_pv("B", ["D4", "Q16"], interactive=True)
        assert "[ref=" in result
        assert "BD4 Q16" in result
        assert "[/ref]" in result


# ---------------------------------------------------------------------------
# move_policy_stats
# ---------------------------------------------------------------------------


class TestMovePolicyStats:
    """Test move_policy_stats method."""

    def test_returns_none_at_root(self, root_node):
        rank, prob, ranking = root_node.move_policy_stats()
        assert rank is None
        assert prob == 0.0
        assert ranking == []

    def test_returns_none_without_parent_policy(self, root_node):
        child = GameNode(parent=root_node, move=Move.from_gtp("D4", player="B"))
        rank, prob, ranking = child.move_policy_stats()
        assert rank is None
        assert ranking == []

    def test_returns_stats_with_parent_policy(self):
        parent = GameNode(properties={"SZ": 9})
        policy = [0.0] * 82
        policy[40] = 0.5  # E5 on 9x9
        parent.analysis["policy"] = policy
        child = GameNode(parent=parent, move=Move.from_gtp("E5", player="B"))
        rank, prob, ranking = child.move_policy_stats()
        assert rank == 1
        assert prob == 0.5
        assert len(ranking) == 82

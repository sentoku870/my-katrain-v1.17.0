"""Kifunarabe (棋譜並べ) core logic unit tests.

All tests are Kivy-independent and run on plain Python data classes.
"""

from dataclasses import dataclass, field
from typing import Any

import pytest

# ----------------------------------------------------------------------------
# Test helpers
# ----------------------------------------------------------------------------


@dataclass
class FakeNode:
    """Minimal stand-in for GameNode for the helpers under test.

    Only the attributes that kifunarabe.py touches are exposed.
    """

    next_player: str = "B"
    ordered_children: list[Any] = field(default_factory=list)
    analysis_exists: bool = False
    root_visits: int = 0
    candidate_moves: list[dict] = field(default_factory=list)


def _make_gtp_node(gtp: str, player: str = "B") -> Any:
    """Make a child node with ``move.gtp() == gtp``."""

    class _Move:
        def __init__(self, gtp: str) -> None:
            self._gtp = gtp

        def gtp(self) -> str:
            return self._gtp

    class _Child:
        def __init__(self, player: str) -> None:
            self.move = _Move(gtp)

    return _Child(player)


def _board_coords(letter: str, row_1based: int) -> tuple[int, int]:
    """Return the (col, row_0based) tuple for a GTP ``letter+row`` coord."""
    letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    col = letters.index(letter)
    return col, row_1based - 1


# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------


class TestKifunarabeConfig:
    def test_defaults(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig

        cfg = KifunarabeConfig()
        assert cfg.turn == "both"
        assert cfg.max_hints == 3
        assert cfg.max_moves == 0

    def test_invalid_turn(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig

        with pytest.raises(ValueError):
            KifunarabeConfig(turn="red")

    def test_invalid_hints(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig

        for bad in (-1, 6, 100):
            with pytest.raises(ValueError):
                KifunarabeConfig(max_hints=bad)

    def test_max_moves_default_is_zero(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig

        assert KifunarabeConfig().max_moves == 0

    def test_valid_max_moves(self) -> None:
        from katrain.core.study.kifunarabe import VALID_MAX_MOVES, KifunarabeConfig

        for n in VALID_MAX_MOVES:
            cfg = KifunarabeConfig(max_moves=n)
            assert cfg.max_moves == n

    def test_invalid_max_moves(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig

        for bad in (-1, 10, 25, 49, 1000):
            with pytest.raises(ValueError):
                KifunarabeConfig(max_moves=bad)

    def test_valid_hints_set(self) -> None:
        from katrain.core.study.kifunarabe import VALID_HINT_COUNTS, KifunarabeConfig

        for n in VALID_HINT_COUNTS:
            cfg = KifunarabeConfig(max_hints=n)
            assert cfg.max_hints == n


# ----------------------------------------------------------------------------
# Pure helpers
# ----------------------------------------------------------------------------


class TestShouldAutoAdvance:
    def test_turn_both_never_auto_advances(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig, should_auto_advance

        cfg = KifunarabeConfig(turn="both")
        assert should_auto_advance(cfg, "B") is False
        assert should_auto_advance(cfg, "W") is False

    def test_turn_black_skips_white(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig, should_auto_advance

        cfg = KifunarabeConfig(turn="B")
        assert should_auto_advance(cfg, "B") is False
        assert should_auto_advance(cfg, "W") is True

    def test_turn_white_skips_black(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig, should_auto_advance

        cfg = KifunarabeConfig(turn="W")
        assert should_auto_advance(cfg, "B") is True
        assert should_auto_advance(cfg, "W") is False


class TestEvaluateGuess:
    def test_correct_guess(self) -> None:
        from katrain.core.study.kifunarabe import evaluate_guess

        node = FakeNode(next_player="B")
        node.ordered_children = [_make_gtp_node("D4", "B")]
        # col D = 3, row 4 -> 0-based (3, 3)
        result = evaluate_guess((3, 3), node)
        assert result is True

    def test_wrong_guess_returns_false(self) -> None:
        from katrain.core.study.kifunarabe import evaluate_guess

        node = FakeNode(next_player="B")
        node.ordered_children = [_make_gtp_node("D4", "B")]
        result = evaluate_guess((4, 4), node)  # E5
        assert result is False

    def test_no_continuation_returns_none(self) -> None:
        from katrain.core.study.kifunarabe import evaluate_guess

        node = FakeNode(next_player="B")
        node.ordered_children = []
        result = evaluate_guess((3, 3), node)
        assert result is None

    def test_pass_is_never_a_correct_click(self) -> None:
        """Pass moves have no board coordinate; clicks should not match."""
        from katrain.core.study.kifunarabe import evaluate_guess

        node = FakeNode(next_player="W")
        node.ordered_children = [_make_gtp_node("pass", "W")]
        result = evaluate_guess((0, 0), node)
        assert result is False


class TestGetHintCandidates:
    def test_zero_hints_returns_empty(self) -> None:
        from katrain.core.study.kifunarabe import get_hint_candidates

        node = FakeNode(analysis_exists=True, root_visits=1000)
        node.candidate_moves = [{"move": "D4"}, {"move": "Q16"}]
        assert get_hint_candidates(node, max_hints=0) == []

    def test_no_analysis_returns_empty(self) -> None:
        from katrain.core.study.kifunarabe import get_hint_candidates

        node = FakeNode(analysis_exists=False, root_visits=0)
        node.candidate_moves = []
        assert get_hint_candidates(node, max_hints=3) == []

    def test_low_visits_returns_empty(self) -> None:
        from katrain.core.study.kifunarabe import get_hint_candidates

        node = FakeNode(analysis_exists=True, root_visits=10)
        node.candidate_moves = [{"move": "D4"}]
        assert get_hint_candidates(node, max_hints=3) == []

    def test_caps_to_max_hints(self) -> None:
        from katrain.core.study.kifunarabe import get_hint_candidates

        node = FakeNode(analysis_exists=True, root_visits=5000)
        node.candidate_moves = [{"move": m} for m in ["D4", "Q16", "R4", "D16", "Q4", "R10"]]
        out = get_hint_candidates(node, max_hints=3)
        assert out == ["D4", "Q16", "R4"]

    def test_dedupes_duplicate_moves(self) -> None:
        from katrain.core.study.kifunarabe import get_hint_candidates

        node = FakeNode(analysis_exists=True, root_visits=5000)
        node.candidate_moves = [{"move": "D4"}, {"move": "D4"}, {"move": "Q16"}]
        out = get_hint_candidates(node, max_hints=3)
        assert out == ["D4", "Q16"]


# ----------------------------------------------------------------------------
# Session
# ----------------------------------------------------------------------------


class TestSessionRecording:
    def test_empty_session_summary(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSession

        sess = KifunarabeSession(KifunarabeConfig())
        summary = sess.get_summary()
        assert summary.total_positions == 0
        assert summary.correct_count == 0
        assert summary.auto_advance_count == 0
        assert summary.correct_rate == 0.0
        assert summary.overall_rate == 0.0

    def test_record_correct_guess(self) -> None:
        from katrain.core.study.kifunarabe import (
            GuessOutcome,
            KifunarabeConfig,
            KifunarabeSession,
        )

        sess = KifunarabeSession(KifunarabeConfig())
        result = sess.record_guess(
            move_number=1,
            expected_gtp="D4",
            guessed_gtp="D4",
            hints_shown=3,
        )
        assert result.outcome == GuessOutcome.CORRECT
        summary = sess.get_summary()
        assert summary.total_positions == 1
        assert summary.correct_count == 1
        assert summary.correct_rate == 100.0

    def test_record_wrong_guess_is_wrong_guess_outcome(self) -> None:
        from katrain.core.study.kifunarabe import (
            GuessOutcome,
            KifunarabeConfig,
            KifunarabeSession,
        )

        sess = KifunarabeSession(KifunarabeConfig())
        result = sess.record_guess(
            move_number=1,
            expected_gtp="D4",
            guessed_gtp="E5",
        )
        # Phase 177-F: wrong but active guess → WRONG_GUESS (a failure),
        # not SKIPPED. SKIPPED is reserved for "no continuation" / "ended".
        assert result.outcome == GuessOutcome.WRONG_GUESS
        summary = sess.get_summary()
        assert summary.total_positions == 1
        assert summary.correct_count == 0
        assert summary.wrong_count == 1
        assert summary.skipped_count == 0
        # Wrong rate is over attempted guesses only.
        assert summary.wrong_rate == 100.0
        assert summary.correct_rate == 0.0

    def test_summary_separates_failures_from_skips(self) -> None:
        from katrain.core.study.kifunarabe import (
            KifunarabeConfig,
            KifunarabeSession,
        )

        sess = KifunarabeSession(KifunarabeConfig())
        sess.record_guess(1, "D4", "D4")          # correct
        sess.record_guess(2, "Q16", "R4")         # wrong
        sess.record_guess(3, "R10", "R10")        # correct
        sess.record_skipped_no_move(4)             # skipped (end of tree)
        s = sess.get_summary()
        assert s.correct_count == 2
        assert s.wrong_count == 1
        assert s.skipped_count == 1
        assert s.attempted_count == 3
        # correct_rate = 2/3 = 66.7%
        import math

        assert math.isclose(s.correct_rate, 66.6666, rel_tol=1e-3)

    def test_record_auto_advance(self) -> None:
        from katrain.core.study.kifunarabe import (
            GuessOutcome,
            KifunarabeConfig,
            KifunarabeSession,
        )

        sess = KifunarabeSession(KifunarabeConfig(turn="B"))
        result = sess.record_auto_advance(move_number=2)
        assert result.outcome == GuessOutcome.AUTO_ADVANCE
        summary = sess.get_summary()
        assert summary.auto_advance_count == 1
        assert summary.overall_rate == 100.0  # auto-advances count as 'OK'

    def test_summary_rates(self) -> None:
        from katrain.core.study.kifunarabe import (
            KifunarabeConfig,
            KifunarabeSession,
        )

        sess = KifunarabeSession(KifunarabeConfig())
        # 3 correct, 1 wrong (clicked but didn't match), 1 auto-advance
        sess.record_guess(1, "D4", "D4")
        sess.record_guess(2, "Q16", "Q16")
        sess.record_guess(3, "R4", "R4")
        sess.record_guess(4, "D16", "E5")
        sess.record_auto_advance(5)

        s = sess.get_summary()
        assert s.total_positions == 5
        assert s.correct_count == 3
        assert s.wrong_count == 1
        assert s.skipped_count == 0  # Phase 177-F: wrong guesses are not "skipped"
        assert s.auto_advance_count == 1
        # Correct rate is computed over attempted guesses only:
        # attempted = correct + wrong = 4, so 3/4 = 75%.
        assert s.correct_rate == pytest.approx(75.0)
        # Wrong rate is the complement over attempted: 1/4 = 25%.
        assert s.wrong_rate == pytest.approx(25.0)
        # Overall rate still treats auto-advance as correct: (3+1)/5 = 80%.
        assert s.overall_rate == pytest.approx(80.0)


class TestSessionLifecycle:
    def test_end_is_idempotent(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSession

        sess = KifunarabeSession(KifunarabeConfig())
        assert sess.is_active
        sess.end()
        assert not sess.is_active
        sess.end()  # idempotent
        assert not sess.is_active

    def test_clear_resets_results(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSession

        sess = KifunarabeSession(KifunarabeConfig())
        sess.record_guess(1, "D4", "D4")
        assert sess.results
        sess.clear()
        assert sess.results == []
        assert sess.is_active

    def test_max_moves_zero_never_ends_session(self) -> None:
        """``max_moves=0`` means "no limit" - session stays alive indefinitely."""
        from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSession

        sess = KifunarabeSession(KifunarabeConfig(max_moves=0))
        for i in range(100):
            sess.record_guess(i, "D4", "D4")
        assert sess.is_active
        assert sess.max_moves_reached is False

    def test_max_moves_limit_ends_session(self) -> None:
        """``record_guess`` after the cap ends the session and flags it."""
        from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSession

        sess = KifunarabeSession(KifunarabeConfig(max_moves=50))
        for i in range(1, 51):
            sess.record_guess(i, "D4", "D4")
            if sess.is_active:
                # Cap not reached yet
                assert i < 50
        # The 50th call hits the cap - session is closed with
        # ``max_moves_reached=True`` flagged for the summary popup.
        assert not sess.is_active
        assert sess.max_moves_reached is True
        assert sess.get_summary().max_moves_reached is True

    def test_max_moves_limit_counts_each_outcome(self) -> None:
        """The cap applies to the total count, not only wrong/correct."""
        from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSession

        sess = KifunarabeSession(KifunarabeConfig(max_moves=100))
        for i in range(1, 101):
            if i % 3 == 0:
                sess.record_auto_advance(i)
            elif i % 2 == 0:
                sess.record_guess(i, f"D{i}", f"R{i}")  # wrong
            else:
                sess.record_guess(i, f"D{i}", f"D{i}")  # correct
        assert not sess.is_active
        assert sess.max_moves_reached is True

    def test_summary_max_moves_reached_propagates(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSession

        sess = KifunarabeSession(KifunarabeConfig(max_moves=50))
        for i in range(1, 51):
            sess.record_guess(i, "D4", "D4")
        summary = sess.get_summary()
        assert summary.max_moves_reached is True


# ----------------------------------------------------------------------------
# Convenience re-exports
# ----------------------------------------------------------------------------


class TestReExports:
    def test_all_top_level_symbols_importable(self) -> None:
        from katrain.core.study import (
            MIN_CANDIDATE_VISITS,
            SIDE_BLACK,
            SIDE_BOTH,
            SIDE_WHITE,
            VALID_HINT_COUNTS,
            VALID_TURNS,
            GuessOutcome,
            KifunarabeConfig,
            KifunarabeGuessResult,
            KifunarabeSession,
            KifunarabeSummary,
            build_kifunarabe_options,
        )

        assert MIN_CANDIDATE_VISITS == 100
        assert SIDE_BOTH == "both"
        assert SIDE_BLACK == "B"
        assert SIDE_WHITE == "W"
        assert isinstance(VALID_TURNS, tuple)
        assert isinstance(VALID_HINT_COUNTS, tuple)
        assert GuessOutcome is not None
        assert KifunarabeConfig is not None
        assert KifunarabeGuessResult is not None
        assert KifunarabeSession is not None
        assert KifunarabeSummary is not None
        assert build_kifunarabe_options is not None


# ----------------------------------------------------------------------------
# build_kifunarabe_options
# ----------------------------------------------------------------------------


class TestBuildKifunarabeOptions:
    """Tests for the choice-set builder used by BadukPan hints in kifunarabe."""

    def _node(
        self,
        actual_gtp: str | None,
        candidates: list[dict],
        *,
        analysis_exists: bool = True,
        root_visits: int = 5000,
        children: list[Any] | None = None,
    ) -> Any:
        if children is None and actual_gtp is not None:
            children = [_make_gtp_node(actual_gtp, "B")]
        return FakeNode(
            ordered_children=children or [],
            analysis_exists=analysis_exists,
            root_visits=root_visits,
            candidate_moves=candidates,
        )

    def test_max_hints_zero_returns_empty(self) -> None:
        from katrain.core.study.kifunarabe import build_kifunarabe_options

        node = self._node("D4", [{"move": "D4", "order": 0, "visits": 100}])
        assert build_kifunarabe_options(node, 0) == []

    def test_max_hints_one_returns_only_actual(self) -> None:
        from katrain.core.study.kifunarabe import build_kifunarabe_options

        node = self._node("D4", [{"move": "Q16", "order": 0, "visits": 100}])
        assert build_kifunarabe_options(node, 1) == ["D4"]

    def test_max_hints_two_returns_actual_plus_best(self) -> None:
        from katrain.core.study.kifunarabe import build_kifunarabe_options

        node = self._node(
            "D4",
            [
                {"move": "D4", "order": 0, "visits": 5000},  # actual is also candidate
                {"move": "Q16", "order": 1, "visits": 4000},
                {"move": "R4", "order": 2, "visits": 3000},
            ],
        )
        out = build_kifunarabe_options(node, 2)
        assert out == ["D4", "Q16"]

    def test_max_hints_three_actual_plus_two_kata(self) -> None:
        from katrain.core.study.kifunarabe import build_kifunarabe_options

        node = self._node(
            "D4",
            [
                {"move": "Q16", "order": 0, "visits": 5000},
                {"move": "R4", "order": 1, "visits": 4000},
                {"move": "D16", "order": 2, "visits": 3000},
                {"move": "Q4", "order": 3, "visits": 2500},
            ],
        )
        out = build_kifunarabe_options(node, 3)
        # Actual first, then top 2 KataGo by order
        assert out == ["D4", "Q16", "R4"]

    def test_actual_in_candidates_deduped(self) -> None:
        from katrain.core.study.kifunarabe import build_kifunarabe_options

        node = self._node(
            "D4",
            [
                {"move": "D4", "order": 0, "visits": 5000},  # duplicate
                {"move": "Q16", "order": 1, "visits": 4000},
                {"move": "R4", "order": 2, "visits": 3000},
            ],
        )
        out = build_kifunarabe_options(node, 3)
        # Should still be 3 unique entries
        assert out == ["D4", "Q16", "R4"]

    def test_no_actual_move_returns_empty(self) -> None:
        from katrain.core.study.kifunarabe import build_kifunarabe_options

        node = self._node(None, [{"move": "D4", "order": 0, "visits": 100}])
        assert build_kifunarabe_options(node, 3) == []

    def test_low_visits_falls_back_to_only_actual(self) -> None:
        from katrain.core.study.kifunarabe import build_kifunarabe_options

        node = self._node("D4", [{"move": "Q16", "order": 0, "visits": 5000}], root_visits=50)
        # root_visits < 100, no KataGo candidates, fall back to actual only
        assert build_kifunarabe_options(node, 3) == ["D4"]

    def test_more_than_available_candidates(self) -> None:
        from katrain.core.study.kifunarabe import build_kifunarabe_options

        node = self._node("D4", [{"move": "Q16", "order": 0, "visits": 5000}])
        # Only 1 KataGo candidate available, max_hints=5 -> 2 total returned
        assert build_kifunarabe_options(node, 5) == ["D4", "Q16"]

    def test_order_is_ascending_not_shuffled(self) -> None:
        from katrain.core.study.kifunarabe import build_kifunarabe_options

        node = self._node(
            "D4",
            [
                {"move": "R4", "order": 0, "visits": 5000},
                {"move": "Q16", "order": 1, "visits": 4000},
                {"move": "D16", "order": 2, "visits": 3000},
                {"move": "Q4", "order": 3, "visits": 2500},
            ],
        )
        # Actual is first, KataGo top picks follow in order
        assert build_kifunarabe_options(node, 4) == ["D4", "R4", "Q16", "D16"]


class TestKifunarabeOptionsHintMoves:
    """The badukpan conversion must produce dicts that draw_kata_hint_marker can read."""

    def test_conversion_round_trip_for_each_option(self) -> None:
        from katrain.gui.badukpan_hints import _kifunarabe_options_to_hint_moves

        candidates = [
            {"move": "D4", "order": 0, "scoreLead": 5.0, "winrate": 0.6, "visits": 5000, "pv": ["D4"]},
            {"move": "Q16", "order": 1, "scoreLead": 3.0, "winrate": 0.55, "visits": 4000, "pv": ["Q16"]},
        ]
        node = FakeNode(
            ordered_children=[_make_gtp_node("D4", "B")],
            analysis_exists=True,
            root_visits=5000,
            candidate_moves=candidates,
        )
        out = _kifunarabe_options_to_hint_moves(node, ["D4", "Q16"])
        assert len(out) == 2
        assert [m["move"] for m in out] == ["D4", "Q16"]
        # First option is the actual move
        assert out[0]["_kifunarabe_actual"] is True
        assert out[1]["_kifunarabe_actual"] is False
        # KataGo-derived fields are filled from the candidate dict
        assert out[1]["order"] == 1
        assert out[1]["scoreLead"] == 3.0

    def test_empty_input_returns_empty(self) -> None:
        from katrain.gui.badukpan_hints import _kifunarabe_options_to_hint_moves

        node = FakeNode(ordered_children=[_make_gtp_node("D4", "B")], candidate_moves=[])
        assert _kifunarabe_options_to_hint_moves(node, []) == []

    def test_unknown_gtp_still_emits_minimal_dict(self) -> None:
        from katrain.gui.badukpan_hints import _kifunarabe_options_to_hint_moves

        node = FakeNode(
            ordered_children=[_make_gtp_node("D4", "B")],
            analysis_exists=True,
            candidate_moves=[],
        )
        out = _kifunarabe_options_to_hint_moves(node, ["D4", "R4"])
        assert len(out) == 2
        # Fallback values so the marker still draws even if KataGo did
        # not analyse this candidate.
        assert out[0]["move"] == "D4"
        assert out[1]["move"] == "R4"
        assert out[1]["scoreLead"] == 0
        assert out[1]["winrate"] == 0.5


# ----------------------------------------------------------------------------
# Display-config constants and the marker dict shape they feed
# ----------------------------------------------------------------------------


class TestKifunarabeDisplayConstants:
    """Phase 177-E display-toggle constants exported from core.constants."""

    def test_keys_are_namespaced(self) -> None:
        from katrain.core.constants import (
            KIFUNARABE_SHOW_ACTUAL_BORDER_KEY,
            KIFUNARABE_SHOW_DIGITS_KEY,
            KIFUNARABE_UNIFORM_COLOR_KEY,
        )

        for key in (
            KIFUNARABE_SHOW_DIGITS_KEY,
            KIFUNARABE_SHOW_ACTUAL_BORDER_KEY,
            KIFUNARABE_UNIFORM_COLOR_KEY,
        ):
            assert key.startswith("kifunarabe/")
            assert key.endswith(("show_digits", "show_actual_border", "uniform_color"))

    def test_defaults_make_marker_minimal(self) -> None:
        from katrain.core.constants import (
            KIFUNARABE_SHOW_ACTUAL_BORDER_DEFAULT,
            KIFUNARABE_SHOW_DIGITS_DEFAULT,
            KIFUNARABE_UNIFORM_COLOR_DEFAULT,
        )

        assert KIFUNARABE_SHOW_DIGITS_DEFAULT is False
        assert KIFUNARABE_SHOW_ACTUAL_BORDER_DEFAULT is False
        assert KIFUNARABE_UNIFORM_COLOR_DEFAULT is True


class TestKifunarabeMarkerGuards:
    """Verify the markers carry all the keys the renderer might consult."""

    def test_marker_has_engine_best_suppression_flag(self) -> None:
        from katrain.gui.badukpan_hints import _kifunarabe_options_to_hint_moves

        node = FakeNode(
            ordered_children=[_make_gtp_node("D4", "B")],
            analysis_exists=True,
            candidate_moves=[{"move": "D4", "order": 0, "visits": 100}],
        )
        out = _kifunarabe_options_to_hint_moves(node, ["D4", "Q16"])
        assert all("_kifunarabe_actual" in m for m in out)
        # Only the first marker (index 0 = the actual game move) is flagged
        # as the special "actual" indicator.
        flags = [m["_kifunarabe_actual"] for m in out]
        assert flags == [True, False]

    def test_required_renderer_keys_present(self) -> None:
        """draw_kata_hint_marker touches these keys; missing ones used to
        raise ``KeyError`` (cf. the ``winrateLost`` regression)."""
        from katrain.gui.badukpan_hints import _kifunarabe_options_to_hint_moves

        node = FakeNode(
            ordered_children=[_make_gtp_node("D4", "B")],
            analysis_exists=True,
            candidate_moves=[{"move": "D4", "order": 0, "visits": 100, "winrateLost": 0.0}],
        )
        out = _kifunarabe_options_to_hint_moves(node, ["D4", "Q16"])
        required = {
            "move", "order", "scoreLead", "winrate",
            "pointsLost", "relativePointsLost", "winrateLost",
            "visits", "pv",
        }
        for marker in out:
            missing = required - marker.keys()
            assert not missing, f"Missing renderer keys {missing} on {marker['move']!r}"
